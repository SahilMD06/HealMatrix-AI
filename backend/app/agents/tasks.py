"""Celery task that runs the ``scheduled_cycle`` agent graph for every active
hospital. This is what makes the sustainability/forecast/executive agents run
without anyone opening a dashboard — the same reason the simulator tick exists.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from app.database.mongodb import Collections, close_mongo_connection, connect_to_mongo, get_database

logger = get_logger(__name__)


def _run(coroutine):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coroutine)


async def _run_cycle_for_hospital(hospital_id: str) -> dict[str, Any]:
    from app.agents.graph.runner import run_scheduled_cycle_now

    run_id = str(uuid.uuid4())
    final_state = await run_scheduled_cycle_now(hospital_id, run_id)

    return {
        "run_id": run_id,
        "agents_run": list(final_state.get("results", {}).keys()),
        "degraded": [
            name for name, result in final_state.get("results", {}).items() if result.get("used_fallback")
        ],
    }


async def _run_all_hospitals() -> dict[str, Any]:
    await connect_to_mongo()
    database = get_database()

    hospitals = await database[Collections.HOSPITALS].find({"is_active": True}).to_list(length=50)
    summary: dict[str, Any] = {}
    for hospital in hospitals:
        hospital_id = str(hospital["_id"])
        try:
            summary[hospital_id] = await _run_cycle_for_hospital(hospital_id)
        except Exception as exc:  # noqa: BLE001 - one hospital's failure must not skip the rest
            logger.error("agents.scheduled_cycle_failed", hospital_id=hospital_id, error=str(exc))
            summary[hospital_id] = {"error": str(exc)}

    logger.info("agents.scheduled_cycle_complete", hospitals=len(hospitals))
    return summary


@celery_app.task(name="app.agents.tasks.run_scheduled_cycle", bind=True, max_retries=1)
def run_scheduled_cycle(self) -> dict[str, Any]:
    """Periodic task, scheduled by Celery beat. Runs the full sustainability/
    forecast/executive agent chain for every active hospital in the network."""
    try:
        return _run(_run_all_hospitals())
    except Exception as exc:  # noqa: BLE001 - a failed cycle must not kill the worker
        logger.error("agents.scheduled_cycle_task_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60) from exc


@celery_app.task(name="app.agents.tasks.shutdown")
def shutdown() -> None:
    _run(close_mongo_connection())
