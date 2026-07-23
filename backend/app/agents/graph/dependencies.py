"""Bundles every service the graph's agents need, constructed once per hospital
context and threaded through ``build_graph``. Keeping this as one dataclass
(rather than each node reaching for a global) is what makes the graph testable —
a test can pass fakes for every field without touching Mongo at all.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.database.repositories import AgentLogRepository, AmbulanceRepository, HospitalRepository
from app.services.admission_service import AdmissionService
from app.services.bed_service import BedService
from app.services.inventory_service import InventoryService
from app.services.sustainability_service import SustainabilityService


@dataclass
class AgentDependencies:
    bed_service: BedService
    admission_service: AdmissionService
    inventory_service: InventoryService
    sustainability_service: SustainabilityService
    hospital_repo: HospitalRepository
    ambulance_repo: AmbulanceRepository
    agent_logs: AgentLogRepository
