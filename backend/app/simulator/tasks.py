"""Celery tasks that drive the live simulation.

The tick is what makes a demo feel alive: telemetry keeps arriving, occupancy
drifts, and stale bed reservations are reclaimed, all without anyone clicking
anything.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.logging_config import get_logger
from app.database.mongodb import (
    Collections,
    close_mongo_connection,
    connect_to_mongo,
    get_database,
)
from app.simulator.generators import HospitalSimulator, SimulationConfig

logger = get_logger(__name__)


def _run(coroutine):
    """Run an async coroutine from a synchronous Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coroutine)


async def _tick() -> dict[str, Any]:
    """Advance every active hospital by one simulated hour."""
    await connect_to_mongo()
    database = get_database()

    hospitals = await database[Collections.HOSPITALS].find({"is_active": True}).to_list(
        length=50
    )
    if not hospitals:
        logger.info("simulator.tick_skipped", reason="no hospitals seeded")
        return {"hospitals": 0}

    moment = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    written = {"energy": 0, "water": 0, "reservations_expired": 0}

    for hospital in hospitals:
        capacity = hospital.get("capacity") or {}
        sustainability = hospital.get("sustainability") or {}

        simulator = HospitalSimulator(
            SimulationConfig(
                seed=settings.simulator_seed + (hash(hospital["code"]) % 1000),
                total_beds=capacity.get("total_beds", 200),
                icu_beds=capacity.get("icu_beds", 20),
                roof_area_sqm=sustainability.get("roof_area_sqm", 2000.0),
                solar_kwp=sustainability.get("solar_kwp", 50.0),
            )
        )

        occupancy = await _live_occupancy(database, hospital["_id"], simulator, moment)

        energy = simulator.energy_log(moment, occupancy)
        energy.update(
            {"hospital_id": hospital["_id"], "created_at": moment, "updated_at": moment}
        )
        await database[Collections.ENERGY_LOGS].insert_one(energy)
        written["energy"] += 1

        water = simulator.water_log(moment, occupancy)
        water.update(
            {"hospital_id": hospital["_id"], "created_at": moment, "updated_at": moment}
        )
        await database[Collections.WATER_LOGS].insert_one(water)
        written["water"] += 1

        written["reservations_expired"] += await _expire_reservations(
            database, hospital["_id"]
        )

    logger.info("simulator.tick", **written, hospitals=len(hospitals))
    return {"hospitals": len(hospitals), **written}


async def _live_occupancy(database, hospital_id, simulator, moment) -> float:
    """Measure real occupancy from the bed collection, falling back to the model.

    Using the live figure keeps the energy and water series consistent with what
    the dashboards actually show, rather than drifting apart from it.
    """
    total = await database[Collections.BEDS].count_documents({"hospital_id": hospital_id})
    if not total:
        return simulator.occupancy_ratio(moment)

    occupied = await database[Collections.BEDS].count_documents(
        {"hospital_id": hospital_id, "status": "occupied"}
    )
    return round(occupied / total, 4)


async def _expire_reservations(database, hospital_id) -> int:
    """Return beds whose 30-minute hold has lapsed to the available pool."""
    result = await database[Collections.BEDS].update_many(
        {
            "hospital_id": hospital_id,
            "status": "reserved",
            "reserved_until": {"$lt": datetime.now(timezone.utc)},
        },
        {"$set": {"status": "available", "reserved_until": None}},
    )
    return result.modified_count


@celery_app.task(name="app.simulator.tasks.run_simulation_tick", bind=True, max_retries=2)
def run_simulation_tick(self) -> dict[str, Any]:
    """Periodic tick. Scheduled by Celery beat every SIMULATOR_TICK_SECONDS."""
    if not settings.simulator_enabled:
        return {"skipped": "simulator disabled"}

    try:
        return _run(_tick())
    except Exception as exc:  # noqa: BLE001 - a failed tick must not kill the worker
        logger.error("simulator.tick_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=30) from exc


@celery_app.task(name="app.simulator.tasks.shutdown")
def shutdown() -> None:
    """Release the Mongo connection pool when the worker stops."""
    _run(close_mongo_connection())
