"""Hospital network, departments, rooms, beds, staff and user accounts."""

from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

from app.core.constants import BedStatus, BedType, RoomType, Shift, UserRole
from app.models.base import (
    DocumentModel,
    GeoPoint,
    HealMatrixModel,
    ObjectIdField,
    TenantDocumentModel,
)


# ------------------------------------------------------------------ hospital
class Address(HealMatrixModel):
    line1: str
    line2: str | None = None
    city: str
    state: str
    pincode: str = Field(pattern=r"^\d{6}$")


class HospitalCapacity(HealMatrixModel):
    total_beds: int = Field(ge=0)
    icu_beds: int = Field(ge=0)
    emergency_beds: int = Field(ge=0)
    ot_count: int = Field(default=0, ge=0)


class SustainabilityProfile(HealMatrixModel):
    """Physical characteristics the sustainability agents reason over."""

    roof_area_sqm: float = Field(default=0.0, ge=0)
    solar_kwp: float = Field(default=0.0, ge=0)
    rainwater_capacity_l: float = Field(default=0.0, ge=0)
    stp_capacity_kld: float = Field(default=0.0, ge=0)


class Hospital(DocumentModel):
    code: str = Field(pattern=r"^[A-Z]{2}-[A-Z]{3}-\d{2}$")
    name: str
    type: str = Field(default="tertiary")
    location: GeoPoint
    address: Address
    capacity: HospitalCapacity
    capabilities: list[str] = Field(default_factory=list)
    sustainability: SustainabilityProfile = Field(default_factory=SustainabilityProfile)
    grid_emission_factor: float = Field(default=0.71, gt=0)
    contact_phone: str | None = None
    is_active: bool = True


# ---------------------------------------------------------------------- user
class UserPreferences(HealMatrixModel):
    theme: str = "system"
    notification_channels: list[str] = Field(default_factory=lambda: ["in_app"])
    default_dashboard: str | None = None


class User(DocumentModel):
    hospital_id: ObjectIdField | None = None  # null => network-level administrator
    email: EmailStr
    password_hash: str = Field(exclude=True)
    full_name: str
    role: UserRole
    department_id: ObjectIdField | None = None
    phone: str | None = None
    avatar_url: str | None = None
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    last_login_at: datetime | None = None
    failed_login_count: int = 0
    is_active: bool = True


# --------------------------------------------------------------------- staff
class RosterEntry(HealMatrixModel):
    date: datetime
    shift: Shift
    status: str = "scheduled"


class Staff(TenantDocumentModel):
    user_id: ObjectIdField | None = None
    employee_code: str
    full_name: str
    designation: str
    department_id: ObjectIdField
    specialisation: list[str] = Field(default_factory=list)
    shift: Shift = Shift.MORNING
    roster: list[RosterEntry] = Field(default_factory=list)
    on_duty: bool = False
    is_active: bool = True


# ---------------------------------------------------------------- department
class WasteProfile(HealMatrixModel):
    """Expected kg per bed-day per CPCB colour category."""

    yellow: float = 0.25
    red: float = 0.18
    white: float = 0.04
    blue: float = 0.03
    general: float = 0.85


class Department(TenantDocumentModel):
    code: str
    name: str
    floor: int = 0
    bed_count: int = 0
    head_staff_id: ObjectIdField | None = None
    hvac_zone: str = "ward"
    waste_profile: WasteProfile = Field(default_factory=WasteProfile)
    is_active: bool = True


# ---------------------------------------------------------------------- room
class FloorCoordinates(HealMatrixModel):
    """Normalised 0-1 position used to place the room on the digital-twin floorplan."""

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)


class Room(TenantDocumentModel):
    department_id: ObjectIdField
    room_number: str
    type: RoomType = RoomType.GENERAL
    capacity: int = Field(default=1, ge=1)
    floor: int = 0
    coordinates: FloorCoordinates
    equipment_ids: list[ObjectIdField] = Field(default_factory=list)


# ----------------------------------------------------------------------- bed
class OccupancyRecord(HealMatrixModel):
    admission_id: ObjectIdField
    occupied_from: datetime
    occupied_to: datetime | None = None


class Bed(TenantDocumentModel):
    department_id: ObjectIdField
    room_id: ObjectIdField
    bed_number: str
    type: BedType = BedType.GENERAL
    status: BedStatus = BedStatus.AVAILABLE
    current_admission_id: ObjectIdField | None = None
    reserved_until: datetime | None = None
    features: list[str] = Field(default_factory=list)
    last_cleaned_at: datetime | None = None
    occupancy_history: list[OccupancyRecord] = Field(default_factory=list)

    @property
    def is_assignable(self) -> bool:
        """A bed may only be assigned when free and not under maintenance."""
        return self.status == BedStatus.AVAILABLE and self.current_admission_id is None
