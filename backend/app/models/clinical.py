"""Patients, vitals, triage and admissions."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, computed_field

from app.core.constants import AdmissionSource, AdmissionStatus, DiseaseCategory
from app.models.base import HealMatrixModel, ObjectIdField, TenantDocumentModel


class ContactInfo(HealMatrixModel):
    phone: str
    email: str | None = None
    address: str | None = None


class EmergencyContact(HealMatrixModel):
    name: str
    relationship: str
    phone: str


class Patient(TenantDocumentModel):
    mrn: str = Field(description="Medical record number, unique per hospital")
    full_name: str
    age: int = Field(ge=0, le=130)
    sex: str = Field(pattern="^(male|female|other)$")
    blood_group: str | None = None
    contact: ContactInfo | None = None
    emergency_contact: EmergencyContact | None = None
    comorbidities: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    is_synthetic: bool = Field(
        default=True,
        description="Always true in this build; no real patient data is ever stored.",
    )


class Vitals(HealMatrixModel):
    """Observations captured at triage. Ranges are validated, not merely documented."""

    heart_rate: int = Field(ge=20, le=250, description="beats per minute")
    systolic_bp: int = Field(ge=40, le=280, description="mmHg")
    diastolic_bp: int = Field(ge=20, le=180, description="mmHg")
    spo2: float = Field(ge=50.0, le=100.0, description="peripheral oxygen saturation %")
    temperature_c: float = Field(ge=30.0, le=45.0)
    respiratory_rate: int = Field(ge=4, le=70, description="breaths per minute")
    gcs: int = Field(default=15, ge=3, le=15, description="Glasgow Coma Scale")
    pain_score: int = Field(default=0, ge=0, le=10)

    @computed_field
    @property
    def shock_index(self) -> float:
        """Heart rate divided by systolic BP. Above 0.9 suggests occult shock."""
        return round(self.heart_rate / self.systolic_bp, 3)

    @computed_field
    @property
    def mean_arterial_pressure(self) -> float:
        return round((self.systolic_bp + 2 * self.diastolic_bp) / 3, 1)


class TriageOutcome(HealMatrixModel):
    """Persisted output of the Patient Triage Agent, embedded in the admission."""

    esi_level: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_department_id: ObjectIdField | None = None
    recommended_department_code: str | None = None
    rationale: str
    red_flags: list[str] = Field(default_factory=list)
    target_response_minutes: int = 0
    model_version: str = "unknown"
    used_fallback: bool = False
    agent_run_id: str | None = None
    decided_at: datetime | None = None


class Diagnosis(HealMatrixModel):
    icd_code: str | None = None
    description: str
    is_primary: bool = False


class MedicineAdministration(HealMatrixModel):
    medicine_id: ObjectIdField
    quantity: int = Field(gt=0)
    administered_at: datetime
    administered_by: ObjectIdField | None = None


class Admission(TenantDocumentModel):
    """The central clinical event. Triage is embedded because the two are always read together."""

    patient_id: ObjectIdField
    admission_number: str
    source: AdmissionSource = AdmissionSource.WALK_IN
    chief_complaint: str
    vitals: Vitals
    triage: TriageOutcome | None = None
    department_id: ObjectIdField | None = None
    bed_id: ObjectIdField | None = None
    attending_staff_id: ObjectIdField | None = None
    diagnosis: list[Diagnosis] = Field(default_factory=list)
    disease_category: DiseaseCategory = DiseaseCategory.OTHER
    status: AdmissionStatus = AdmissionStatus.TRIAGED
    admitted_at: datetime | None = None
    discharged_at: datetime | None = None
    predicted_los_days: float | None = None
    actual_los_days: float | None = None
    medicines_administered: list[MedicineAdministration] = Field(default_factory=list)
    outcome: str | None = None
    notes: str | None = None

    @property
    def is_active(self) -> bool:
        return self.status in {
            AdmissionStatus.TRIAGED,
            AdmissionStatus.ADMITTED,
            AdmissionStatus.IN_TREATMENT,
        }
