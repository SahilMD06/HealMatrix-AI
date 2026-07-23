"""Runs the ``scheduled_cycle`` branch of the agent graph for one hospital,
returning the full final state rather than a bare summary.

This is the one place that assembles ``AgentDependencies`` for a scheduled cycle,
used by both the periodic Celery task (``app/agents/tasks.py``, which only needs a
summary for its own logging) and the on-demand API endpoint
(``POST /agents/run-cycle``, which needs every agent's actual output to render a
dashboard immediately rather than wait for the next hourly beat tick). Keeping the
assembly in one function means the two callers can never quietly diverge in which
services or repositories they hand the graph.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.agents.graph.builder import build_graph
from app.agents.graph.cycle import build_scheduled_cycle_state
from app.agents.graph.dependencies import AgentDependencies
from app.database.repositories import (
    AdmissionRepository,
    AgentLogRepository,
    AmbulanceRepository,
    BedRepository,
    EnergyLogRepository,
    HospitalRepository,
    InventoryRepository,
    MedicineRepository,
    WasteRecordRepository,
    WaterLogRepository,
)
from app.services.admission_service import AdmissionService
from app.services.bed_service import BedService
from app.services.inventory_service import InventoryService
from app.services.sustainability_service import SustainabilityService


async def run_scheduled_cycle_now(hospital_id: str, run_id: str | None = None) -> dict[str, Any]:
    """Builds live state for ``hospital_id``, runs the full scheduled_cycle graph
    (disease forecast -> medicine -> energy -> water -> waste -> carbon ->
    executive), and returns the final ``HealMatrixState`` as a plain dict.

    Every agent's ``AgentResult`` is already in ``state["results"]`` keyed by
    agent name (see ``app/agents/state.py``'s ``result_of`` helper) by the time
    this returns, and every one of them has already been written to
    ``agent_logs`` by the graph's own node wrapper — callers do not need to log
    anything themselves.
    """
    run_id = run_id or str(uuid.uuid4())
    initial_state = await build_scheduled_cycle_state(hospital_id, run_id)

    admissions_repo = AdmissionRepository(hospital_id)
    beds_repo = BedRepository(hospital_id)
    admission_service = AdmissionService(
        admissions=admissions_repo, patients=None, beds=beds_repo,
        departments=None, agent_logs=None, notifications=None,
    )
    energy_repo = EnergyLogRepository(hospital_id)
    water_repo = WaterLogRepository(hospital_id)
    waste_repo = WasteRecordRepository(hospital_id)

    deps = AgentDependencies(
        bed_service=BedService(beds_repo),
        admission_service=admission_service,
        inventory_service=InventoryService(InventoryRepository(hospital_id), MedicineRepository()),
        sustainability_service=SustainabilityService(energy_repo, water_repo, waste_repo),
        hospital_repo=HospitalRepository(),
        ambulance_repo=AmbulanceRepository(hospital_id),
        agent_logs=AgentLogRepository(hospital_id),
    )

    graph = build_graph(deps)
    final_state = await graph.ainvoke(initial_state)
    return dict(final_state)
