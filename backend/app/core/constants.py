"""Domain constants and enumerations shared across the platform.

Centralising these prevents the drift that occurs when the same vocabulary is
re-declared in routes, services and agents.
"""

from enum import Enum


class StrEnum(str, Enum):  # noqa: UP042
    """String enum that serialises to its value in JSON and Mongo.

    Deliberately not ``enum.StrEnum``: an explicit ``str`` base with an explicit
    ``__str__`` keeps behaviour identical across the Motor driver, Pydantic v2
    serialisation and direct f-string interpolation, and keeps the module importable
    on Python 3.10 for tooling that has not yet moved to 3.11.
    """

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


# --------------------------------------------------------------------- people
class UserRole(StrEnum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    NURSE = "nurse"
    PHARMACIST = "pharmacist"
    MANAGER = "manager"
    SUSTAINABILITY_OFFICER = "sustainability_officer"


ROLE_DEFAULT_DASHBOARD: dict[str, str] = {
    UserRole.ADMIN: "/dashboard/admin",
    UserRole.DOCTOR: "/dashboard/doctor",
    UserRole.NURSE: "/dashboard/emergency",
    UserRole.PHARMACIST: "/dashboard/inventory",
    UserRole.MANAGER: "/dashboard/executive",
    UserRole.SUSTAINABILITY_OFFICER: "/dashboard/sustainability",
}


class Shift(StrEnum):
    MORNING = "morning"
    EVENING = "evening"
    NIGHT = "night"


# ------------------------------------------------------------------- clinical
class TriageLevel(int, Enum):
    """Emergency Severity Index. 1 is the most acute."""

    RESUSCITATION = 1
    EMERGENT = 2
    URGENT = 3
    LESS_URGENT = 4
    NON_URGENT = 5


TRIAGE_LABELS: dict[int, str] = {
    1: "Resuscitation",
    2: "Emergent",
    3: "Urgent",
    4: "Less Urgent",
    5: "Non-Urgent",
}

TRIAGE_TARGET_MINUTES: dict[int, int] = {1: 0, 2: 10, 3: 30, 4: 60, 5: 120}


class AdmissionStatus(StrEnum):
    TRIAGED = "triaged"
    ADMITTED = "admitted"
    IN_TREATMENT = "in_treatment"
    DISCHARGED = "discharged"
    TRANSFERRED = "transferred"
    DECEASED = "deceased"


class AdmissionSource(StrEnum):
    WALK_IN = "walk_in"
    AMBULANCE = "ambulance"
    REFERRAL = "referral"
    TRANSFER = "transfer"


class DiseaseCategory(StrEnum):
    RESPIRATORY = "respiratory"
    CARDIAC = "cardiac"
    TRAUMA = "trauma"
    INFECTIOUS = "infectious"
    GI = "gi"
    NEURO = "neuro"
    OBSTETRIC = "obstetric"
    OTHER = "other"


class BedType(StrEnum):
    GENERAL = "general"
    ICU = "icu"
    HDU = "hdu"
    EMERGENCY = "emergency"
    ISOLATION = "isolation"
    PEDIATRIC = "pediatric"
    MATERNITY = "maternity"


class BedStatus(StrEnum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    CLEANING = "cleaning"
    MAINTENANCE = "maintenance"
    RESERVED = "reserved"


class RoomType(StrEnum):
    GENERAL = "general"
    PRIVATE = "private"
    ICU = "icu"
    ISOLATION = "isolation"
    OT = "ot"
    EMERGENCY = "emergency"


# ------------------------------------------------------------------ pharmacy
class MedicineCategory(StrEnum):
    ANTIBIOTIC = "antibiotic"
    ANALGESIC = "analgesic"
    CARDIAC = "cardiac"
    EMERGENCY = "emergency"
    VACCINE = "vaccine"
    IV_FLUID = "iv_fluid"
    ANAESTHETIC = "anaesthetic"
    OTHER = "other"


class MedicineForm(StrEnum):
    TABLET = "tablet"
    CAPSULE = "capsule"
    INJECTION = "injection"
    SYRUP = "syrup"
    IV = "iv"
    INHALER = "inhaler"


class InventoryStatus(StrEnum):
    ACTIVE = "active"
    QUARANTINED = "quarantined"
    EXPIRED = "expired"
    TRANSFERRED_OUT = "transferred_out"
    CONSUMED = "consumed"


EXPIRY_ALERT_DAYS: tuple[int, ...] = (90, 30, 7)


# --------------------------------------------------------------------- waste
class WasteCategory(StrEnum):
    """CPCB Bio-Medical Waste Rules 2016 colour coding."""

    YELLOW = "yellow"
    RED = "red"
    WHITE = "white"
    BLUE = "blue"
    GENERAL = "general"


WASTE_CATEGORY_DESCRIPTION: dict[str, str] = {
    WasteCategory.YELLOW: "Human/animal anatomical, soiled, expired medicines, chemical waste",
    WasteCategory.RED: "Contaminated recyclable plastics: tubing, bottles, catheters, IV sets",
    WasteCategory.WHITE: "Waste sharps including used and discarded metal sharps",
    WasteCategory.BLUE: "Glassware and metallic body implants",
    WasteCategory.GENERAL: "Non-hazardous general municipal waste",
}


class DisposalMethod(StrEnum):
    INCINERATION = "incineration"
    AUTOCLAVE = "autoclave"
    MICROWAVE = "microwave"
    DEEP_BURIAL = "deep_burial"
    RECYCLING = "recycling"
    LANDFILL = "landfill"


MAX_STORAGE_HOURS: dict[str, int] = {
    WasteCategory.YELLOW: 48,
    WasteCategory.RED: 48,
    WasteCategory.WHITE: 72,
    WasteCategory.BLUE: 72,
    WasteCategory.GENERAL: 24,
}


# ------------------------------------------------------------------ ambulance
class AmbulanceStatus(StrEnum):
    IDLE = "idle"
    DISPATCHED = "dispatched"
    EN_ROUTE_SCENE = "en_route_scene"
    AT_SCENE = "at_scene"
    EN_ROUTE_HOSPITAL = "en_route_hospital"
    RETURNING = "returning"
    MAINTENANCE = "maintenance"


class AmbulanceType(StrEnum):
    BLS = "bls"
    ALS = "als"
    NEONATAL = "neonatal"
    MORTUARY = "mortuary"


# ------------------------------------------------------------------- agents
class AgentName(StrEnum):
    TRIAGE = "patient_triage"
    DISEASE_FORECAST = "disease_forecast"
    BED_ALLOCATION = "bed_allocation"
    MEDICINE = "medicine_intelligence"
    ENERGY = "energy_optimization"
    WATER = "water_conservation"
    WASTE = "biomedical_waste"
    CARBON = "carbon_intelligence"
    DISPATCH = "ambulance_dispatch"
    EXECUTIVE = "executive_decision"


class AgentStatus(StrEnum):
    SUCCESS = "success"
    DEGRADED = "degraded"
    FAILED = "failed"


class TriggerType(StrEnum):
    PATIENT_ARRIVAL = "patient_arrival"
    SCHEDULED_CYCLE = "scheduled_cycle"
    MANUAL = "manual"
    SCENARIO = "scenario"


# ------------------------------------------------------------ notifications
class NotificationType(StrEnum):
    MEDICINE_EXPIRY = "medicine_expiry"
    EMERGENCY_ALERT = "emergency_alert"
    WASTE_PICKUP = "waste_pickup"
    BED_AVAILABILITY = "bed_availability"
    WATER_LEAK = "water_leak"
    HIGH_ENERGY = "high_energy"
    OUTBREAK_WARNING = "outbreak_warning"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ReportType(StrEnum):
    HOSPITAL_PERFORMANCE = "hospital_performance"
    SUSTAINABILITY = "sustainability"
    CARBON = "carbon"
    ENERGY = "energy"
    WASTE = "waste"
    WATER = "water"
    EXECUTIVE_SUMMARY = "executive_summary"


# ------------------------------------------------------- emission factors v1
EMISSION_FACTOR_VERSION = "2024.1"

EMISSION_FACTORS: dict[str, float] = {
    # kg CO2e per unit
    "grid_electricity_kwh": 0.71,       # India CEA average grid factor
    "diesel_generator_kwh": 0.85,
    "solar_kwh": 0.048,                 # lifecycle
    "diesel_litre": 2.68,
    "petrol_litre": 2.31,
    "cng_kg": 2.75,
    "water_kilolitre": 0.34,            # treatment + pumping
    "waste_incineration_kg": 1.10,
    "waste_autoclave_kg": 0.28,
    "waste_landfill_kg": 0.58,
    "waste_recycling_kg": -0.42,        # avoided emissions
    "anaesthetic_desflurane_kg": 2540.0,
    "anaesthetic_sevoflurane_kg": 130.0,
    "nitrous_oxide_kg": 273.0,
}

# Weights used to compute the composite 0-100 sustainability score.
SUSTAINABILITY_WEIGHTS: dict[str, float] = {
    "energy": 0.30,
    "water": 0.20,
    "waste": 0.25,
    "carbon": 0.25,
}

# Clinical safety guardrails the Energy agent may never violate.
HVAC_SETPOINT_LIMITS: dict[str, tuple[float, float]] = {
    "ot": (20.0, 24.0),
    "icu": (20.0, 24.0),
    "ward": (22.0, 26.0),
    "opd": (23.0, 27.0),
    "admin": (23.0, 28.0),
    "pharmacy": (15.0, 25.0),
}
