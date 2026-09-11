import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import ProblemDetailException

# Argon2id password hasher
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def hash_token(raw_token: str) -> str:
    """Computes SHA-256 hex digest of a raw token string for secure DB lookup."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(
    user_id: uuid.UUID,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MIN)

    to_encode = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise ProblemDetailException(
                status_code=401,
                title="Unauthorized",
                detail="Invalid token type",
            )
        return payload
    except JWTError as err:
        raise ProblemDetailException(
            status_code=401,
            title="Unauthorized",
            detail=f"Invalid or expired authentication token: {err}",
        ) from err


def generate_refresh_token(
    family_id: uuid.UUID | None = None,
) -> tuple[str, str, uuid.UUID]:
    """
    Generates a secure random refresh token.
    Returns: (raw_token, sha256_token_hash, family_id)
    """
    raw_token = secrets.token_urlsafe(48)
    token_hash = hash_token(raw_token)
    assigned_family_id = family_id or uuid.uuid4()
    return raw_token, token_hash, assigned_family_id
