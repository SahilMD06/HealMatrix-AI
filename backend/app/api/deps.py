"""FastAPI dependencies: authentication, authorisation and tenant scoping.

Routes declare what they need (``CurrentUser``, ``require_roles(...)``, a scoped
repository) and receive it already validated. No route reads a raw token.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.constants import UserRole
from app.core.exceptions import AuthenticationError, AuthorizationError, TenantIsolationError
from app.core.security import decode_token
from app.database.repositories import (
    AdmissionRepository,
    AgentLogRepository,
    AmbulanceRepository,
    BedRepository,
    DepartmentRepository,
    EnergyLogRepository,
    InventoryRepository,
    MedicineRepository,
    NotificationRepository,
    PatientRepository,
    UserRepository,
    WasteRecordRepository,
    WaterLogRepository,
)
from app.models.base import PaginationParams

bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token")

# Roles permitted to read across the whole hospital network.
NETWORK_ROLES = {UserRole.ADMIN, UserRole.MANAGER}


class AuthenticatedUser:
    """Lightweight principal assembled from the token's claims.

    Deliberately not a database read: verifying the signature is enough for
    authorisation, which keeps every request one round-trip lighter.
    """

    def __init__(self, claims: dict[str, Any]) -> None:
        self.id: str = claims["sub"]
        self.role: str = claims.get("role", "")
        self.hospital_id: str | None = claims.get("hospital_id")
        self.email: str | None = claims.get("email")
        self.jti: str = claims.get("jti", "")

    @property
    def is_network_user(self) -> bool:
        """Network admins and managers may cross hospital boundaries when asked to."""
        return self.role in NETWORK_ROLES

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AuthenticatedUser {self.email} role={self.role}>"


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthenticatedUser:
    """Resolve and validate the bearer token into a principal."""
    if credentials is None:
        raise AuthenticationError("Authorization header is missing.")
    claims = decode_token(credentials.credentials, expected_type="access")
    return AuthenticatedUser(claims)


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


def require_roles(*allowed: str):
    """Dependency factory gating an endpoint to specific roles.

    Usage:  ``dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))]``
    """

    allowed_set = {str(role) for role in allowed}

    async def checker(user: CurrentUser) -> AuthenticatedUser:
        if user.role not in allowed_set:
            raise AuthorizationError(
                "Your role does not permit this action.",
                details={"required": sorted(allowed_set), "actual": user.role},
            )
        return user

    return checker


async def resolve_hospital_id(
    user: CurrentUser,
    hospital_id: Annotated[
        str | None,
        Query(description="Override the tenant. Network admins and managers only."),
    ] = None,
) -> str:
    """Determine which hospital this request operates on.

    Non-network roles are pinned to their own hospital. An attempt to override it is
    a tenant-isolation violation, not a silent fallback.
    """
    if hospital_id is None:
        if user.hospital_id is None:
            raise AuthorizationError(
                "This account is not attached to a hospital. Pass ?hospital_id= explicitly."
            )
        return user.hospital_id

    if hospital_id != user.hospital_id and not user.is_network_user:
        raise TenantIsolationError(
            "You may only access data for your own hospital.",
            details={"requested": hospital_id, "permitted": user.hospital_id},
        )
    return hospital_id


HospitalId = Annotated[str, Depends(resolve_hospital_id)]


async def get_pagination(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    sort_by: str = "created_at",
    sort_desc: bool = True,
) -> PaginationParams:
    """Standard pagination envelope, identical across every list endpoint."""
    return PaginationParams(skip=skip, limit=limit, sort_by=sort_by, sort_desc=sort_desc)


Pagination = Annotated[PaginationParams, Depends(get_pagination)]


def client_ip(request: Request) -> str:
    """Best-effort client IP, honouring the proxy header set by Render."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ------------------------------------------------------- scoped repositories
# Each factory yields a repository already bound to the resolved tenant, so a route
# handler physically cannot query another hospital's data.
def get_patient_repo(hospital_id: HospitalId) -> PatientRepository:
    return PatientRepository(hospital_id)


def get_admission_repo(hospital_id: HospitalId) -> AdmissionRepository:
    return AdmissionRepository(hospital_id)


def get_bed_repo(hospital_id: HospitalId) -> BedRepository:
    return BedRepository(hospital_id)


def get_department_repo(hospital_id: HospitalId) -> DepartmentRepository:
    return DepartmentRepository(hospital_id)


def get_inventory_repo(hospital_id: HospitalId) -> InventoryRepository:
    return InventoryRepository(hospital_id)


def get_agent_log_repo(hospital_id: HospitalId) -> AgentLogRepository:
    return AgentLogRepository(hospital_id)


def get_notification_repo(hospital_id: HospitalId) -> NotificationRepository:
    return NotificationRepository(hospital_id)


def get_user_repo() -> UserRepository:
    return UserRepository()


def get_medicine_repo() -> MedicineRepository:
    return MedicineRepository()


def get_energy_log_repo(hospital_id: HospitalId) -> EnergyLogRepository:
    return EnergyLogRepository(hospital_id)


def get_water_log_repo(hospital_id: HospitalId) -> WaterLogRepository:
    return WaterLogRepository(hospital_id)


def get_waste_record_repo(hospital_id: HospitalId) -> WasteRecordRepository:
    return WasteRecordRepository(hospital_id)


def get_ambulance_repo(hospital_id: HospitalId) -> AmbulanceRepository:
    return AmbulanceRepository(hospital_id)


PatientRepo = Annotated[PatientRepository, Depends(get_patient_repo)]
AdmissionRepo = Annotated[AdmissionRepository, Depends(get_admission_repo)]
BedRepo = Annotated[BedRepository, Depends(get_bed_repo)]
DepartmentRepo = Annotated[DepartmentRepository, Depends(get_department_repo)]
InventoryRepo = Annotated[InventoryRepository, Depends(get_inventory_repo)]
AgentLogRepo = Annotated[AgentLogRepository, Depends(get_agent_log_repo)]
NotificationRepo = Annotated[NotificationRepository, Depends(get_notification_repo)]
UserRepo = Annotated[UserRepository, Depends(get_user_repo)]
MedicineRepo = Annotated[MedicineRepository, Depends(get_medicine_repo)]
EnergyLogRepo = Annotated[EnergyLogRepository, Depends(get_energy_log_repo)]
WaterLogRepo = Annotated[WaterLogRepository, Depends(get_water_log_repo)]
WasteRecordRepo = Annotated[WasteRecordRepository, Depends(get_waste_record_repo)]
AmbulanceRepo = Annotated[AmbulanceRepository, Depends(get_ambulance_repo)]
