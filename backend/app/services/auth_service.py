"""
Authentication service: password hashing, JWT issue/verify.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
import structlog
from jose import JWTError, jwt

from app.config import settings

log = structlog.get_logger()


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: UUID, role: str, organization_id: UUID | None) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload: dict[str, object] = {
        "sub": str(user_id),
        "role": role,
        "org": str(organization_id) if organization_id else None,
        "exp": expire,
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    log.info("auth.token_issued", user_id=str(user_id), role=role, expires=expire.isoformat())
    return token


def decode_access_token(token: str) -> dict[str, object]:
    """
    Decode and validate a JWT. Raises JWTError on invalid/expired tokens.
    Returns the raw payload dict.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        log.warning("auth.token_invalid", error=str(exc))
        raise
    return payload  # type: ignore[return-value]
