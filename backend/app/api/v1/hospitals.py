"""Hospital network and department endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, DepartmentRepo, require_roles
from app.core.constants import UserRole
from app.core.exceptions import ConflictError, NotFoundError
from app.database.repositories import HospitalRepository, serialise

router = APIRouter(tags=["organisation"])


def get_hospital_repo() -> HospitalRepository:
    return HospitalRepository()


@router.get("/hospitals", summary="List hospitals in the network")
async def list_hospitals(_user: CurrentUser) -> list[dict]:
    """Every authenticated user can see the network roster; detail is still scoped."""
    repo = get_hospital_repo()
    rows = await repo.find_many({"is_active": True}, limit=100, sort_by="code", sort_desc=False)
    return [serialise(row) for row in rows]


@router.get("/hospitals/{hospital_id}", summary="Hospital detail")
async def get_hospital(hospital_id: str, _user: CurrentUser) -> dict:
    repo = get_hospital_repo()
    hospital = await repo.find_by_id(hospital_id)
    if hospital is None:
        raise NotFoundError("Hospital not found.", details={"id": hospital_id})
    return serialise(hospital)


@router.post(
    "/hospitals",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
    summary="Add a hospital to the network",
)
async def create_hospital(payload: dict) -> dict:
    repo = get_hospital_repo()
    code = str(payload.get("code", "")).upper()
    if await repo.find_by_code(code):
        raise ConflictError("A hospital with this code already exists.", details={"code": code})
    payload["code"] = code
    payload.setdefault("is_active", True)
    return serialise(await repo.insert(payload))


@router.get("/departments", summary="List departments")
async def list_departments(departments: DepartmentRepo, _user: CurrentUser) -> list[dict]:
    return [serialise(row) for row in await departments.list_active()]
