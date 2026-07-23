"""Patient, admission and bed endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    AdmissionRepo,
    AgentLogRepo,
    BedRepo,
    CurrentUser,
    DepartmentRepo,
    NotificationRepo,
    Pagination,
    PatientRepo,
    require_roles,
)
from app.core.constants import UserRole
from app.core.exceptions import NotFoundError
from app.database.repositories import serialise
from app.schemas.clinical import (
    AdmissionStatusRequest,
    ArrivalRequest,
    ArrivalResponse,
    BedResponse,
    BedStatusRequest,
    DischargeRequest,
    OccupancySummaryResponse,
    PatientCreateRequest,
    PatientResponse,
)
from app.services.admission_service import AdmissionService
from app.services.bed_service import BedService

CLINICAL_ROLES = (UserRole.DOCTOR, UserRole.NURSE, UserRole.ADMIN, UserRole.MANAGER)
WRITE_ROLES = (UserRole.DOCTOR, UserRole.NURSE, UserRole.ADMIN)

router = APIRouter(tags=["clinical"])


def _admission_service(
    admissions: AdmissionRepo,
    patients: PatientRepo,
    beds: BedRepo,
    departments: DepartmentRepo,
    agent_logs: AgentLogRepo,
    notifications: NotificationRepo,
) -> AdmissionService:
    return AdmissionService(admissions, patients, beds, departments, agent_logs, notifications)


AdmissionSvc = Annotated[AdmissionService, Depends(_admission_service)]


def _bed_service(beds: BedRepo) -> BedService:
    return BedService(beds)


BedSvc = Annotated[BedService, Depends(_bed_service)]


# ------------------------------------------------------------------- patients
@router.get(
    "/patients",
    response_model=list[PatientResponse],
    dependencies=[Depends(require_roles(*CLINICAL_ROLES))],
    summary="List patients",
)
async def list_patients(patients: PatientRepo, pagination: Pagination) -> list[PatientResponse]:
    rows = await patients.find_many(
        skip=pagination.skip,
        limit=pagination.limit,
        sort_by=pagination.sort_by,
        sort_desc=pagination.sort_desc,
    )
    return [PatientResponse(**serialise(row)) for row in rows]


@router.post(
    "/patients",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
    summary="Register a patient",
)
async def create_patient(
    payload: PatientCreateRequest, patients: PatientRepo
) -> PatientResponse:
    mrn = await patients.next_mrn()
    created = await patients.insert(
        {
            "mrn": mrn,
            "full_name": payload.full_name,
            "age": payload.age,
            "sex": payload.sex,
            "blood_group": payload.blood_group,
            "contact": {"phone": payload.phone} if payload.phone else None,
            "comorbidities": payload.comorbidities,
            "allergies": payload.allergies,
            "is_synthetic": True,
        }
    )
    return PatientResponse(**serialise(created))


@router.get(
    "/patients/{patient_id}",
    response_model=PatientResponse,
    dependencies=[Depends(require_roles(*CLINICAL_ROLES))],
    summary="Patient detail",
)
async def get_patient(patient_id: str, patients: PatientRepo) -> PatientResponse:
    patient = await patients.find_by_id(patient_id)
    if patient is None:
        raise NotFoundError("Patient not found.", details={"id": patient_id})
    return PatientResponse(**serialise(patient))


# ----------------------------------------------------------------- admissions
@router.post(
    "/admissions/arrival",
    response_model=ArrivalResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
    summary="Patient arrival — triage and allocate",
)
async def patient_arrival(payload: ArrivalRequest, service: AdmissionSvc) -> ArrivalResponse:
    """Register the arrival, run triage, allocate a bed and log the reasoning.

    This is the platform's core workflow. Every decision it makes is written to
    `agent_logs` and is retrievable by `agent_run_id`.
    """
    return await service.handle_arrival(payload)


@router.get(
    "/admissions/queue",
    dependencies=[Depends(require_roles(*CLINICAL_ROLES))],
    summary="Live triage queue",
)
async def admission_queue(service: AdmissionSvc) -> list[dict]:
    """Active admissions ordered by acuity, then by how long they have waited."""
    return await service.queue()


@router.get(
    "/admissions",
    dependencies=[Depends(require_roles(*CLINICAL_ROLES))],
    summary="List admissions",
)
async def list_admissions(
    admissions: AdmissionRepo,
    patients: PatientRepo,
    pagination: Pagination,
    admission_status: Annotated[str | None, Query(alias="status")] = None,
    department_id: str | None = None,
    esi_level: Annotated[int | None, Query(ge=1, le=5)] = None,
) -> list[dict]:
    filters: dict = {}
    if admission_status:
        filters["status"] = admission_status
    if department_id:
        from app.database.repositories import to_object_id

        filters["department_id"] = to_object_id(department_id)
    if esi_level:
        filters["triage.esi_level"] = esi_level

    rows = await admissions.find_many(
        filters,
        skip=pagination.skip,
        limit=pagination.limit,
        sort_by=pagination.sort_by,
        sort_desc=pagination.sort_desc,
    )

    results: list[dict] = []
    for row in rows:
        patient = await patients.find_by_id(row["patient_id"])
        data = serialise(row) or {}
        data["patient_name"] = patient["full_name"] if patient else None
        data["patient_age"] = patient["age"] if patient else None
        results.append(data)
    return results


@router.get(
    "/admissions/{admission_id}",
    dependencies=[Depends(require_roles(*CLINICAL_ROLES))],
    summary="Admission detail",
)
async def get_admission(
    admission_id: str, admissions: AdmissionRepo, patients: PatientRepo
) -> dict:
    admission = await admissions.find_by_id(admission_id)
    if admission is None:
        raise NotFoundError("Admission not found.", details={"id": admission_id})

    patient = await patients.find_by_id(admission["patient_id"])
    data = serialise(admission) or {}
    data["patient"] = serialise(patient)
    return data


@router.patch(
    "/admissions/{admission_id}/status",
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
    summary="Update admission status",
)
async def update_admission_status(
    admission_id: str, payload: AdmissionStatusRequest, service: AdmissionSvc
) -> dict:
    return await service.set_status(admission_id, payload.status, payload.notes)


@router.post(
    "/admissions/{admission_id}/discharge",
    dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.ADMIN))],
    summary="Discharge a patient",
)
async def discharge(
    admission_id: str, payload: DischargeRequest, service: AdmissionSvc
) -> dict:
    """Close the admission, release the bed and record realised length of stay."""
    return await service.discharge(admission_id, payload.outcome, payload.notes)


# ----------------------------------------------------------------------- beds
@router.get("/beds", response_model=list[BedResponse], summary="List beds")
async def list_beds(
    beds: BedRepo,
    _user: CurrentUser,
    bed_status: Annotated[str | None, Query(alias="status")] = None,
    bed_type: Annotated[str | None, Query(alias="type")] = None,
) -> list[BedResponse]:
    filters: dict = {}
    if bed_status:
        filters["status"] = bed_status
    if bed_type:
        filters["type"] = bed_type
    rows = await beds.find_many(filters, limit=200, sort_by="bed_number", sort_desc=False)
    return [BedResponse(**serialise(row)) for row in rows]


@router.get(
    "/beds/availability",
    response_model=list[BedResponse],
    summary="Assignable beds only",
)
async def bed_availability(
    beds: BedRepo,
    _user: CurrentUser,
    bed_type: Annotated[str | None, Query(alias="type")] = None,
) -> list[BedResponse]:
    rows = await beds.find_available(bed_type=bed_type)
    return [BedResponse(**serialise(row)) for row in rows]


@router.get(
    "/beds/occupancy-summary",
    response_model=OccupancySummaryResponse,
    summary="Occupancy KPIs",
)
async def occupancy_summary(service: BedSvc, _user: CurrentUser) -> OccupancySummaryResponse:
    return OccupancySummaryResponse(**await service.occupancy_summary())


@router.post(
    "/beds/{bed_id}/reserve",
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
    summary="Hold a bed for 30 minutes",
)
async def reserve_bed(bed_id: str, service: BedSvc) -> dict:
    return await service.reserve(bed_id)


@router.post(
    "/beds/{bed_id}/release",
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
    summary="Release a bed to cleaning",
)
async def release_bed(bed_id: str, service: BedSvc) -> dict:
    return await service.release(bed_id)


@router.patch(
    "/beds/{bed_id}/status",
    dependencies=[Depends(require_roles(UserRole.NURSE, UserRole.ADMIN))],
    summary="Set bed status",
)
async def set_bed_status(bed_id: str, payload: BedStatusRequest, service: BedSvc) -> dict:
    return await service.set_status(bed_id, payload.status)
