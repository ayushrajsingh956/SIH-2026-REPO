from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_event
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, get_optional_current_user
from app.core.exceptions import ProblemDetailException
from app.core.limiter import limiter
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    get_password_hash,
    hash_token,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import (
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a user account",
)
@limiter.limit("10/minute")
async def register(
    request: Request,
    user_in: UserRegister,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> User:
    # 1. Check if email already exists
    existing = await db.execute(select(User).where(User.email == user_in.email))
    if existing.scalar_one_or_none():
        raise ProblemDetailException(
            status_code=status.HTTP_409_CONFLICT,
            title="Email Conflict",
            detail="A user with this email address already exists",
            type_url="https://errors.legalmetro.gov.in/email-already-exists",
        )

    # 2. Determine role & activation status
    is_admin = current_user is not None and current_user.role == "admin"
    if is_admin:
        assigned_role = user_in.role or "viewer"
        is_active = True
    else:
        # Public self-registration creates pending viewer
        assigned_role = "viewer"
        is_active = False

    # 3. Create user
    user = User(
        name=user_in.name,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        role=assigned_role,
        district=user_in.district,
        state=user_in.state,
        is_active=is_active,
    )
    db.add(user)
    await db.flush()

    # 4. Audit Log
    await record_audit_event(
        db=db,
        user_id=current_user.id if current_user else None,
        action="USER_REGISTER",
        entity_type="user",
        entity_id=user.id,
        detail={
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "registered_by": str(current_user.id) if current_user else "self",
        },
    )

    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate with email & password",
)
@limiter.limit("5/minute")
async def login(
    request: Request,
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise ProblemDetailException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Unauthorized",
            detail="Incorrect email or password",
            type_url="https://errors.legalmetro.gov.in/invalid-credentials",
        )

    if not user.is_active:
        raise ProblemDetailException(
            status_code=status.HTTP_403_FORBIDDEN,
            title="Account Pending Approval",
            detail="Your account is pending administrator approval. Please contact the department.",
            type_url="https://errors.legalmetro.gov.in/account-inactive",
        )

    # Issue tokens
    access_token = create_access_token(user_id=user.id, role=user.role)
    raw_refresh_token, token_hash, family_id = generate_refresh_token()
    refresh_expires = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    db_refresh = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        family_id=family_id,
        expires_at=refresh_expires,
    )
    db.add(db_refresh)

    await record_audit_event(
        db=db,
        user_id=user.id,
        action="USER_LOGIN",
        entity_type="user",
        entity_id=user.id,
        detail={"role": user.role},
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MIN * 60,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token and issue new access token",
)
@limiter.limit("10/minute")
async def refresh_token(
    request: Request,
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    token_digest = hash_token(payload.refresh_token)

    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_digest))
    db_token = result.scalar_one_or_none()

    if not db_token:
        raise ProblemDetailException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Unauthorized",
            detail="Invalid refresh token",
            type_url="https://errors.legalmetro.gov.in/invalid-token",
        )

    # 1. Replay attack detection: token was already revoked!
    if db_token.revoked_at is not None:
        # Revoke the entire family
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == db_token.family_id)
            .values(revoked_at=datetime.now(UTC))
        )
        await record_audit_event(
            db=db,
            user_id=db_token.user_id,
            action="TOKEN_REPLAY_REVOCATION",
            entity_type="refresh_token",
            entity_id=db_token.id,
            detail={"family_id": str(db_token.family_id)},
        )
        await db.commit()
        raise ProblemDetailException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Token Reuse Detected",
            detail="A previously used refresh token was reused. All sessions in this chain have been terminated for security.",
            type_url="https://errors.legalmetro.gov.in/token-replay-detected",
        )

    # 2. Expiration check
    if db_token.expires_at < datetime.now(UTC):
        raise ProblemDetailException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Unauthorized",
            detail="Refresh token has expired",
            type_url="https://errors.legalmetro.gov.in/token-expired",
        )

    # 3. User verification
    user_res = await db.execute(select(User).where(User.id == db_token.user_id))
    user = user_res.scalar_one_or_none()
    if not user or not user.is_active:
        raise ProblemDetailException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Unauthorized",
            detail="User no longer active",
            type_url="https://errors.legalmetro.gov.in/account-inactive",
        )

    # 4. Rotation: revoke old token, issue new token in SAME family
    db_token.revoked_at = datetime.now(UTC)

    new_raw_token, new_hash, _ = generate_refresh_token(family_id=db_token.family_id)
    new_expires = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    new_db_token = RefreshToken(
        user_id=user.id,
        token_hash=new_hash,
        family_id=db_token.family_id,
        expires_at=new_expires,
    )
    db.add(new_db_token)

    new_access_token = create_access_token(user_id=user.id, role=user.role)

    await record_audit_event(
        db=db,
        user_id=user.id,
        action="TOKEN_REFRESH",
        entity_type="refresh_token",
        entity_id=new_db_token.id,
        detail={"family_id": str(db_token.family_id)},
    )

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_raw_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MIN * 60,
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get profile of currently logged-in user",
)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Log out and revoke refresh token",
)
async def logout(
    payload: RefreshTokenRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if payload and payload.refresh_token:
        token_digest = hash_token(payload.refresh_token)
        # Ownership check: a user may only revoke their own tokens
        await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.token_hash == token_digest,
                RefreshToken.user_id == current_user.id,
            )
            .values(revoked_at=datetime.now(UTC))
        )
    else:
        # Revoke all active tokens for this user
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == current_user.id)
            .values(revoked_at=datetime.now(UTC))
        )

    await record_audit_event(
        db=db,
        user_id=current_user.id,
        action="USER_LOGOUT",
        entity_type="user",
        entity_id=current_user.id,
    )

    return {"message": "Successfully logged out"}
