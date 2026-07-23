"""Request and response schemas for the clinical endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.core.constants import AdmissionSource, DiseaseCategory
from app.models.base import HealMatrixModel
from app.models.clinical import Vitals


class PatientCreateRequest(HealMatrixModel):
    full_name: str = Field(min_length=2, max_length=120)
    age: int = Field(ge=0, le=130)
    sex: str = Field(pattern="^(male|female|other)$")
    blood_group: str | None = None
    phone: str | None = None
    comorbidities: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)


class PatientResponse(HealMatrixModel):
    id: str
    mrn: str
    full_name: str
    age: int
    sex: str
    blood_group: str | None = None
    comorbidities: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    created_at: datetime | None = None


class ArrivalRequest(HealMatrixModel):
    """Patient arrival. Accepts either an existing patient or inline registration."""

    patient_id: str | None = Field(
        default=None, description="Existing patient. Omit to register a new one."
    )
    patient: PatientCreateRequest | None = Field(
        default=None, description="Inline registration when patient_id is not supplied."
    )
    source: AdmissionSource = AdmissionSource.WALK_IN
    chief_complaint: str = Field(min_length=3, max_length=500)
    vitals: Vitals
    disease_category: DiseaseCategory = DiseaseCategory.OTHER
    run_agents: bool = Field(
        default=True, description="Set false to record the arrival without invoking the agents."
    )


class TriageResponse(HealMatrixModel):
    esi_level: int
    confidence: float
    recommended_department_code: str | None = None
    target_response_minutes: int
    red_flags: list[str] = Field(default_factory=list)
    rationale: str
    model_version: str
    used_fallback: bool


class BedAssignmentResponse(HealMatrixModel):
    bed_id: str | None = None
    bed_number: str | None = None
    type: str | None = None
    predicted_los_days: float | None = None
    reserved_until: datetime | None = None
    escalation: str | None = None


class ArrivalResponse(HealMatrixModel):
    admission_id: str
    admission_number: str
    patient_id: str
    mrn: str
    status: str
    triage: TriageResponse | None = None
    bed: BedAssignmentResponse | None = None
    agent_run_id: str | None = None
    degraded: bool = False


class AdmissionResponse(HealMatrixModel):
    id: str
    admission_number: str
    patient_id: str
    patient_name: str | None = None
    patient_age: int | None = None
    chief_complaint: str
    source: str
    status: str
    disease_category: str
    department_id: str | None = None
    bed_id: str | None = None
    triage: TriageResponse | None = None
    predicted_los_days: float | None = None
    admitted_at: datetime | None = None
    discharged_at: datetime | None = None
    created_at: datetime | None = None
    waiting_minutes: int | None = None


class AdmissionStatusRequest(HealMatrixModel):
    status: str = Field(pattern="^(triaged|admitted|in_treatment|discharged|transferred|deceased)$")
    notes: str | None = None


class DischargeRequest(HealMatrixModel):
    outcome: str = Field(default="recovered", pattern="^(recovered|referred|lama|expired)$")
    notes: str | None = None


class BedResponse(HealMatrixModel):
    id: str
    bed_number: str
    type: str
    status: str
    department_id: str
    room_id: str
    features: list[str] = Field(default_factory=list)
    current_admission_id: str | None = None
    reserved_until: datetime | None = None


class BedStatusRequest(HealMatrixModel):
    status: str = Field(pattern="^(available|occupied|cleaning|maintenance|reserved)$")


class OccupancySummaryResponse(HealMatrixModel):
    total_beds: int
    occupied: int
    available: int
    cleaning: int
    maintenance: int
    reserved: int
    occupancy_rate: float
    icu_total: int
    icu_occupied: int
    icu_occupancy_rate: float
    by_department: list[dict] = Field(default_factory=list)
