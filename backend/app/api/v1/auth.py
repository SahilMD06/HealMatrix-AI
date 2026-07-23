"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, HospitalId, UserRepo, require_roles
from app.core.constants import UserRole
from app.database.repositories import to_object_id
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
    summary="Create a user account",
)
async def register(payload: RegisterRequest, users: UserRepo) -> UserResponse:
    """Administrators create accounts; there is no public self-registration."""
    return await AuthService(users).register(payload)


@router.post("/login", response_model=TokenResponse, summary="Sign in")
async def login(payload: LoginRequest, users: UserRepo) -> TokenResponse:
    """Exchange credentials for an access and refresh token pair."""
    return await AuthService(users).login(payload)


@router.post("/refresh", response_model=TokenResponse, summary="Refresh the access token")
async def refresh(payload: RefreshRequest, users: UserRepo) -> TokenResponse:
    """Exchange a valid refresh token for a fresh access token."""
    return await AuthService(users).refresh(payload.refresh_token)


@router.get("/me", response_model=UserResponse, summary="Current user profile")
async def me(user: CurrentUser, users: UserRepo) -> UserResponse:
    return await AuthService(users).get_profile(user.id)


@router.patch("/me", response_model=UserResponse, summary="Update profile")
async def update_me(
    payload: UpdateProfileRequest, user: CurrentUser, users: UserRepo
) -> UserResponse:
    return await AuthService(users).update_profile(user.id, payload.model_dump())


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change own password",
)
async def change_password(
    payload: ChangePasswordRequest, user: CurrentUser, users: UserRepo
) -> dict:
    """Change the caller's password.

    Returns a 200 with a small confirmation body. A 204 (No Content) would be more
    RESTful, but FastAPI/Starlette assert that a 204 route declares no response body,
    and this handler's ``-> dict`` annotation is a body — so 200 is the correct code
    here rather than fighting the framework.
    """
    await AuthService(users).change_password(
        user.id, payload.current_password, payload.new_password
    )
    return {"status": "password_changed"}


@router.get(
    "/users",
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))],
    summary="Staff roster for one hospital",
)
async def list_users(hospital_id: HospitalId, users: UserRepo) -> list[dict]:
    """Read-only roster for the Admin Dashboard. Password hashes are never
    serialised — ``serialise`` only ever sees the fields Mongo already stores,
    and ``UserRepository`` never selects ``password_hash`` out for this path
    since the response is trimmed to the same shape as ``UserResponse``."""
    rows = await users.find_many(
        {"hospital_id": to_object_id(hospital_id)}, limit=200, sort_by="full_name", sort_desc=False
    )
    return [
        {
            "id": str(row["_id"]),
            "email": row.get("email"),
            "full_name": row.get("full_name"),
            "role": row.get("role"),
            "department_id": str(row["department_id"]) if row.get("department_id") else None,
            "is_active": row.get("is_active", True),
            "last_login_at": row.get("last_login_at"),
        }
        for row in rows
    ]
