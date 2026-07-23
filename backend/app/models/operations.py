"""Pharmacy inventory and ambulance fleet."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import Field, computed_field

from app.core.constants import (
    AmbulanceStatus,
    AmbulanceType,
    InventoryStatus,
    MedicineCategory,
    MedicineForm,
)
from app.models.base import (
    DocumentModel,
    GeoPoint,
    HealMatrixModel,
    ObjectIdField,
    TenantDocumentModel,
    utc_now,
)


# ------------------------------------------------------------------ pharmacy
class StorageRequirement(HealMatrixModel):
    min_temp_c: float = 15.0
    max_temp_c: float = 25.0
    cold_chain: bool = False
    light_sensitive: bool = False


class Medicine(DocumentModel):
    """Network-wide catalogue entry. Stock lives in ``inventory``."""

    sku: str
    name: str
    generic_name: str
    manufacturer: str | None = None
    category: MedicineCategory = MedicineCategory.OTHER
    form: MedicineForm = MedicineForm.TABLET
    strength: str | None = None
    unit_price_paise: int = Field(ge=0)
    storage: StorageRequirement = Field(default_factory=StorageRequirement)
    is_critical: bool = Field(
        default=False, description="A stock-out of this SKU is a patient-safety event"
    )
    carbon_kg_per_unit: float = Field(default=0.0, ge=0)
    is_active: bool = True


class TransferRecord(HealMatrixModel):
    to_hospital_id: ObjectIdField
    quantity: int = Field(gt=0)
    transferred_at: datetime
    agent_run_id: str | None = None
    approved_by: ObjectIdField | None = None


class InventoryBatch(TenantDocumentModel):
    """A single batch of one SKU held at one hospital."""

    medicine_id: ObjectIdField
    batch_number: str
    quantity: int = Field(ge=0)
    reserved_quantity: int = Field(default=0, ge=0)
    expiry_date: date
    received_date: date
    unit_cost_paise: int = Field(ge=0)
    reorder_point: int = Field(default=0, ge=0)
    max_stock: int = Field(default=0, ge=0)
    storage_location: str | None = None
    status: InventoryStatus = InventoryStatus.ACTIVE
    transfer_history: list[TransferRecord] = Field(default_factory=list)

    @computed_field
    @property
    def available_quantity(self) -> int:
        return max(self.quantity - self.reserved_quantity, 0)

    @computed_field
    @property
    def days_to_expiry(self) -> int:
        return (self.expiry_date - utc_now().date()).days

    @computed_field
    @property
    def is_below_reorder_point(self) -> bool:
        return self.reorder_point > 0 and self.available_quantity <= self.reorder_point


# ----------------------------------------------------------------- ambulance
class CrewMember(HealMatrixModel):
    staff_id: ObjectIdField
    role: str


class ActiveCall(HealMatrixModel):
    call_id: str
    priority: int = Field(ge=1, le=5, description="1 is most urgent")
    pickup: GeoPoint
    destination_hospital_id: ObjectIdField | None = None
    eta_minutes: float | None = None
    distance_km: float | None = None
    route_polyline: str | None = None
    patient_description: str | None = None
    dispatched_at: datetime | None = None


class Ambulance(TenantDocumentModel):
    vehicle_number: str
    type: AmbulanceType = AmbulanceType.BLS
    status: AmbulanceStatus = AmbulanceStatus.IDLE
    current_location: GeoPoint
    crew: list[CrewMember] = Field(default_factory=list)
    active_call: ActiveCall | None = None
    equipment: list[str] = Field(default_factory=list)
    fuel_type: str = "diesel"
    fuel_efficiency_kmpl: float = Field(default=8.0, gt=0)
    odometer_km: float = Field(default=0.0, ge=0)
    is_active: bool = True

    @property
    def is_dispatchable(self) -> bool:
        return self.status == AmbulanceStatus.IDLE and self.is_active
