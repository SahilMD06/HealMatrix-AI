"""Domain models.

Importing from ``app.models`` gives access to every persisted entity without needing
to know which submodule declares it.
"""

from app.models.base import (
    DateRange,
    DocumentModel,
    GeoPoint,
    HealMatrixModel,
    ObjectIdField,
    PaginationParams,
    PyObjectId,
    TenantDocumentModel,
    TimestampedModel,
    utc_now,
)
from app.models.clinical import (
    Admission,
    Diagnosis,
    MedicineAdministration,
    Patient,
    TriageOutcome,
    Vitals,
)
from app.models.intelligence import (
    AgentError,
    AgentLog,
    AgentMessage,
    AuditLog,
    KnowledgeChunk,
    Notification,
    Report,
    SimulationEvent,
)
from app.models.operations import (
    ActiveCall,
    Ambulance,
    InventoryBatch,
    Medicine,
    TransferRecord,
)
from app.models.organisation import (
    Bed,
    Department,
    Hospital,
    Room,
    Staff,
    User,
)
from app.models.sustainability import (
    CarbonReport,
    EnergyLog,
    ReductionOpportunity,
    SustainabilityScore,
    WasteRecord,
    WaterLog,
)

__all__ = [
    "ActiveCall",
    "Admission",
    "AgentError",
    "AgentLog",
    "AgentMessage",
    "Ambulance",
    "AuditLog",
    "Bed",
    "CarbonReport",
    "DateRange",
    "Department",
    "Diagnosis",
    "DocumentModel",
    "EnergyLog",
    "GeoPoint",
    "HealMatrixModel",
    "Hospital",
    "InventoryBatch",
    "KnowledgeChunk",
    "Medicine",
    "MedicineAdministration",
    "Notification",
    "ObjectIdField",
    "PaginationParams",
    "Patient",
    "PyObjectId",
    "ReductionOpportunity",
    "Report",
    "Room",
    "SimulationEvent",
    "Staff",
    "SustainabilityScore",
    "TenantDocumentModel",
    "TimestampedModel",
    "TransferRecord",
    "TriageOutcome",
    "User",
    "Vitals",
    "WasteRecord",
    "WaterLog",
    "utc_now",
]
