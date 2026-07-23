"""Authentication and account management business rules."""

from __future__ import annotations

from app.core.config import settings
from app.core.constants import ROLE_DEFAULT_DASHBOARD
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.core.logging_config import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.database.repositories import UserRepository, serialise, to_object_id
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

logger = get_logger(__name__)

MAX_FAILED_LOGINS = 5


class AuthService:
    """Owns every rule about who may sign in and what their token contains."""

    def __init__(self, users: UserRepository) -> None:
        self.users = users

    # ------------------------------------------------------------ registration
    async def register(self, payload: RegisterRequest) -> UserResponse:
        email = payload.email.lower().strip()

        if await self.users.find_by_email(email):
            raise ConflictError(
                "An account with this email already exists.", details={"email": email}
            )

        document = {
            "email": email,
            "password_hash": hash_password(payload.password),
            "full_name": payload.full_name,
            "role": str(payload.role),
            "hospital_id": to_object_id(payload.hospital_id) if payload.hospital_id else None,
            "department_id": to_object_id(payload.department_id)
            if payload.department_id
            else None,
            "phone": payload.phone,
            "preferences": {
                "theme": "system",
                "notification_channels": ["in_app"],
                "default_dashboard": ROLE_DEFAULT_DASHBOARD.get(payload.role),
            },
            "last_login_at": None,
            "failed_login_count": 0,
            "is_active": True,
        }

        created = await self.users.insert(document)
        logger.info("auth.user_registered", email=email, role=str(payload.role))
        return self._to_user_response(created)

    # ------------------------------------------------------------------ login
    async def login(self, payload: LoginRequest) -> TokenResponse:
        email = payload.email.lower().strip()
        user = await self.users.find_by_email(email)

        # Same error for "no such user" and "wrong password" so the endpoint
        # cannot be used to enumerate valid accounts.
        if user is None:
            raise AuthenticationError("Incorrect email or password.")

        if not user.get("is_active", True):
            raise AuthenticationError("This account has been deactivated.")

        if user.get("failed_login_count", 0) >= MAX_FAILED_LOGINS:
            raise AuthenticationError(
                "Account temporarily locked after repeated failed sign-in attempts. "
                "Contact an administrator."
            )

        if not verify_password(payload.password, user["password_hash"]):
            await self.users.register_failed_login(email)
            logger.warning("auth.login_failed", email=email)
            raise AuthenticationError("Incorrect email or password.")

        await self.users.register_login(user["_id"])
        logger.info("auth.login_success", email=email, role=user["role"])
        return self._issue_tokens(user)

    # ---------------------------------------------------------------- refresh
    async def refresh(self, refresh_token: str) -> TokenResponse:
        claims = decode_token(refresh_token, expected_type="refresh")
        user = await self.users.find_by_id(claims["sub"])

        if user is None or not user.get("is_active", True):
            raise AuthenticationError("The account for this token is no longer active.")

        return self._issue_tokens(user)

    # ----------------------------------------------------------------- profile
    async def get_profile(self, user_id: str) -> UserResponse:
        user = await self.users.find_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        return self._to_user_response(user)

    async def update_profile(self, user_id: str, patch: dict) -> UserResponse:
        updates: dict = {}
        preferences: dict = {}

        for field in ("full_name", "phone", "avatar_url"):
            if patch.get(field) is not None:
                updates[field] = patch[field]

        for field in ("theme", "default_dashboard"):
            if patch.get(field) is not None:
                preferences[f"preferences.{field}"] = patch[field]

        updates.update(preferences)
        if not updates:
            return await self.get_profile(user_id)

        updated = await self.users.update(user_id, updates)
        return self._to_user_response(updated)

    async def change_password(self, user_id: str, current: str, new: str) -> None:
        user = await self.users.find_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")

        if not verify_password(current, user["password_hash"]):
            raise AuthenticationError("Current password is incorrect.")

        await self.users.update(user_id, {"password_hash": hash_password(new)})
        logger.info("auth.password_changed", user_id=str(user_id))

    # ----------------------------------------------------------------- helpers
    def _issue_tokens(self, user: dict) -> TokenResponse:
        user_id = str(user["_id"])
        hospital_id = str(user["hospital_id"]) if user.get("hospital_id") else None

        return TokenResponse(
            access_token=create_access_token(
                user_id=user_id,
                role=user["role"],
                hospital_id=hospital_id,
                email=user["email"],
            ),
            refresh_token=create_refresh_token(user_id),
            expires_in=settings.access_token_expire_minutes * 60,
            user=self._to_user_response(user),
        )

    @staticmethod
    def _to_user_response(user: dict) -> UserResponse:
        data = serialise(user) or {}
        preferences = data.get("preferences") or {}
        return UserResponse(
            id=data["id"],
            email=data["email"],
            full_name=data["full_name"],
            role=data["role"],
            hospital_id=data.get("hospital_id"),
            department_id=data.get("department_id"),
            phone=data.get("phone"),
            avatar_url=data.get("avatar_url"),
            default_dashboard=preferences.get("default_dashboard")
            or ROLE_DEFAULT_DASHBOARD.get(data["role"]),
            last_login_at=data.get("last_login_at"),
            is_active=data.get("is_active", True),
        )
