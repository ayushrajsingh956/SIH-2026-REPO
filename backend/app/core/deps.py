import uuid
from collections.abc import Callable

from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import ProblemDetailException
from app.core.security import decode_access_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=True,
)

oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_access_token(token)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise ProblemDetailException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Unauthorized",
            detail="Token subject missing",
        )

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError as err:
        raise ProblemDetailException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Unauthorized",
            detail="Invalid user ID in token",
        ) from err

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if not user:
        raise ProblemDetailException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Unauthorized",
            detail="User no longer exists",
        )

    if not user.is_active:
        raise ProblemDetailException(
            status_code=status.HTTP_403_FORBIDDEN,
            title="Account Pending Approval",
            detail="User account is deactivated or pending approval by an administrator",
            type_url="https://errors.legalmetro.gov.in/account-inactive",
        )

    return user


async def get_optional_current_user(
    token: str | None = Depends(oauth2_scheme_optional),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if not token:
        return None
    try:
        return await get_current_user(token=token, db=db)
    except Exception:
        return None


def require_role(*roles: str) -> Callable[..., User]:
    async def role_dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in roles:
            raise ProblemDetailException(
                status_code=status.HTTP_403_FORBIDDEN,
                title="Forbidden",
                detail=f"Access forbidden: current role '{current_user.role}' is not in allowed roles {list(roles)}",
                type_url="https://errors.legalmetro.gov.in/insufficient-permissions",
            )
        return current_user

    return role_dependency
