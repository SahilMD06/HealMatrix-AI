"""Request and response schemas for authentication."""

from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.core.constants import UserRole
from app.models.base import HealMatrixModel


class RegisterRequest(HealMatrixModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    role: UserRole
    hospital_id: str | None = None
    department_id: str | None = None
    phone: str | None = None

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        """Reject the passwords that show up in every breach corpus."""
        if value.isdigit() or value.isalpha():
            raise ValueError("Password must mix letters and numbers.")
        if value.lower() in {"password123", "admin123", "12345678"}:
            raise ValueError("Password is too common.")
        return value


class LoginRequest(HealMatrixModel):
    email: EmailStr
    password: str


class RefreshRequest(HealMatrixModel):
    refresh_token: str


class ChangePasswordRequest(HealMatrixModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserResponse(HealMatrixModel):
    id: str
    email: str
    full_name: str
    role: str
    hospital_id: str | None = None
    department_id: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    default_dashboard: str | None = None
    last_login_at: datetime | None = None
    is_active: bool = True


class TokenResponse(HealMatrixModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")
    user: UserResponse


class UpdateProfileRequest(HealMatrixModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = None
    avatar_url: str | None = None
    theme: str | None = None
    default_dashboard: str | None = None
