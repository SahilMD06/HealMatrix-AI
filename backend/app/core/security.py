"""Password hashing and JWT issue/verification.

Kept free of FastAPI imports so it can be unit-tested and reused by the Celery
workers and the seed script without pulling in the web framework.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import AuthenticationError

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.bcrypt_rounds,
)

TokenType = Literal["access", "refresh"]


# --------------------------------------------------------------------- hashing
def hash_password(plain_password: str) -> str:
    """Hash a password with bcrypt. Cost comes from settings so tests can lower it."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Constant-time password verification. Never raises on a malformed hash."""
    try:
        return pwd_context.verify(plain_password, password_hash)
    except ValueError:
        return False


# ---------------------------------------------------------------------- tokens
def _create_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(
    user_id: str,
    role: str,
    hospital_id: str | None,
    email: str | None = None,
) -> str:
    """Short-lived token carrying the claims every request needs: role and tenant."""
    return _create_token(
        subject=user_id,
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        extra_claims={"role": role, "hospital_id": hospital_id, "email": email},
    )


def create_refresh_token(user_id: str) -> str:
    """Long-lived token that carries no authorisation claims by design."""
    return _create_token(
        subject=user_id,
        token_type="refresh",
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any]:
    """Decode and validate a JWT, raising AuthenticationError on any problem."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as exc:
        raise AuthenticationError(f"Invalid or expired token: {exc}") from exc

    if expected_type and payload.get("type") != expected_type:
        raise AuthenticationError(
            f"Expected a {expected_type} token but received a {payload.get('type')} token."
        )

    if not payload.get("sub"):
        raise AuthenticationError("Token is missing its subject claim.")

    return payload


def token_jti(token: str) -> str:
    """Extract the unique token ID, used as the Redis deny-list key on logout."""
    return decode_token(token)["jti"]
