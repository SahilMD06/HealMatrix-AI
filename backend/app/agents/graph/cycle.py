"""Assembles the initial ``HealMatrixState`` for a ``scheduled_cycle`` graph run
from live data, for one hospital.

This is deliberately separate from ``build_graph``/the agents themselves: the
graph's job is sequencing and message-passing between agents that have already
been handed their inputs; gathering those inputs from Mongo is a per-deployment
integration concern, done once here rather than duplicated inside every agent
(which would also make the agents impossible to unit-test without a database —
see how every agent test in the test suite constructs its state by hand).

Two things this deliberately does NOT populate, both documented rather than
silently defaulted:
  - ``waste_description``: classification is triggered per-item (e.g. from a UI
    "classify this waste" action), not once per cycle, so it is left unset here —
    the Biomedical Waste Agent's guardrail already handles that by reporting
    "requires_manual_review" rather than fabricating a description to classify.
  - ``network_inventory_snapshot``: a genuine cross-hospital query, which the
    tenant-scoped repository layer deliberately does not support querying by
    accident (see ``TenantRepository``). Populating it is a network-level
    aggregation left for a later build pass; until then, transfer proposals are
    honestly empty rather than fabricated.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from app.database.mongodb import Collections, get_database
from app.database.repositories import (
    AdmissionRepository,
    BedRepository,
    EnergyLogRepository,
    WasteRecordRepository,
    WaterLogRepository,
)
from app.models.base import utc_now
from app.services.admission_service import AdmissionService
from app.services.bed_service import BedService
from app.services.sustainability_service import SustainabilityService


async def build_scheduled_cycle_state(hospital_id: str, run_id: str) -> dict[str, Any]:
    """Gather everything the ``scheduled_cycle`` branch's agents need for one hospital."""
    database = get_database()
    hospital = await database[Collections.HOSPITALS].find_one({"_id": _oid(hospital_id)})
    sustainability_profile = (hospital or {}).get("sustainability", {})
    capacity = (hospital or {}).get("capacity", {})

    admissions_repo = AdmissionRepository(hospital_id)
    beds_repo = BedRepository(hospital_id)
    energy_repo = EnergyLogRepository(hospital_id)
    water_repo = WaterLogRepository(hospital_id)
    waste_repo = WasteRecordRepository(hospital_id)

    admission_service = AdmissionService(
        admissions=admissions_repo,
        patients=None,  # not needed for the scheduled_cycle branch's agents
        beds=beds_repo,
        departments=None,
        agent_logs=None,
        notifications=None,
    )
    bed_service = BedService(beds_repo)
    sustainability_service = SustainabilityService(energy_repo, water_repo, waste_repo)

    recent_admissions = await admission_service.recent_daily_admission_counts(days=90)

    since_hourly = utc_now() - timedelta(days=7)
    energy_rows = await energy_repo.find_many(
        {"timestamp": {"$gte": since_hourly}}, limit=24 * 7, sort_by="timestamp", sort_desc=False
    )
    water_rows = await water_repo.find_many(
        {"timestamp": {"$gte": since_hourly}}, limit=24 * 7, sort_by="timestamp", sort_desc=False
    )

    since_daily = (utc_now() - timedelta(days=14)).date()
    waste_rows = await waste_repo.find_many(
        {"date": {"$gte": since_daily}}, limit=200, sort_by="date", sort_desc=False
    )
    for row in waste_rows:
        row_date = row.get("date")
        row["weekday"] = row_date.weekday() if hasattr(row_date, "weekday") else None

    sustainability_totals = await sustainability_service.recent_totals(hours=24)
    occupancy = await bed_service.occupancy_summary()

    return {
        "run_id": run_id,
        "hospital_id": hospital_id,
        "trigger": "scheduled_cycle",
        "correlation_id": run_id,
        "as_of": utc_now().isoformat(),
        "recent_daily_admission_counts": recent_admissions,
        "total_beds": capacity.get("total_beds") or occupancy.get("total_beds", 0),
        "hourly_energy_history": energy_rows,
        "zone_setpoints": {},
        "solar_kwp": sustainability_profile.get("solar_kwp", 0.0),
        "hourly_water_history": water_rows,
        "roof_area_sqm": sustainability_profile.get("roof_area_sqm", 0.0),
        "rainfall_mm_forecast": 0.0,  # no weather feed wired up; a real deployment would inject this
        "waste_description": None,
        "waste_history": waste_rows,
        "sustainability_totals": sustainability_totals,
        "anaesthetic_gas_kg": {},
        "network_inventory_snapshot": None,
        "ambulance_call": None,
        "available_ambulances": [],
        "active_assignments": [],
        "results": {},
        "messages": [],
        "errors": [],
    }


def _oid(value: str):
    from bson import ObjectId

    return ObjectId(value)
