"""Agent transparency endpoints.

These expose the machine-reasoning audit trail. Being able to open any decision and
see its inputs, output, rationale and latency is what separates this from a chatbot.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import AgentLogRepo, CurrentUser, HospitalId, Pagination, require_roles
from app.core.constants import AgentName, UserRole
from app.core.exceptions import NotFoundError
from app.database.repositories import serialise

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/status", summary="Per-agent health summary")
async def agent_status(logs: AgentLogRepo, _user: CurrentUser) -> list[dict]:
    """Last run, average latency and fallback rate for each of the ten agents."""
    aggregated = await logs.aggregate(
        [
            {
                "$group": {
                    "_id": "$agent_name",
                    "runs": {"$sum": 1},
                    "avg_duration_ms": {"$avg": "$duration_ms"},
                    "last_run_at": {"$max": "$created_at"},
                    "fallbacks": {"$sum": {"$cond": ["$used_fallback", 1, 0]}},
                    "failures": {
                        "$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}
                    },
                }
            }
        ]
    )
    by_name = {row["_id"]: row for row in aggregated}

    summary: list[dict] = []
    for agent in AgentName:
        stats = by_name.get(str(agent))
        runs = stats["runs"] if stats else 0
        summary.append(
            {
                "agent": str(agent),
                "runs": runs,
                "avg_duration_ms": round(stats["avg_duration_ms"], 1) if stats else None,
                "last_run_at": stats["last_run_at"] if stats else None,
                "fallback_rate": round(stats["fallbacks"] / runs, 3) if runs else None,
                "failure_rate": round(stats["failures"] / runs, 3) if runs else None,
                "implemented": runs > 0,
            }
        )
    return summary


@router.get("/runs", summary="Recent agent runs")
async def list_runs(
    logs: AgentLogRepo,
    _user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[dict]:
    """One row per graph execution, with agent count and total duration."""
    return await logs.recent_runs(limit=limit)


@router.get("/runs/{run_id}", summary="Full reasoning trace for one run")
async def get_run(run_id: str, logs: AgentLogRepo, _user: CurrentUser) -> dict:
    """Every agent's inputs, output and rationale for a single run, in order."""
    entries = await logs.by_run(run_id)
    if not entries:
        raise NotFoundError("No agent run with that identifier.", details={"run_id": run_id})

    serialised = [serialise(entry) for entry in entries]
    return {
        "run_id": run_id,
        "agents": len(serialised),
        "total_duration_ms": sum(entry.get("duration_ms", 0) for entry in serialised),
        "degraded": any(entry.get("used_fallback") for entry in serialised),
        "triggered_by": serialised[0].get("triggered_by"),
        "trace": serialised,
    }


@router.get(
    "/logs",
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))],
    summary="Raw agent log feed",
)
async def list_logs(
    logs: AgentLogRepo,
    pagination: Pagination,
    agent_name: str | None = None,
) -> list[dict]:
    filters = {"agent_name": agent_name} if agent_name else {}
    rows = await logs.find_many(
        filters, skip=pagination.skip, limit=pagination.limit
    )
    return [serialise(row) for row in rows]


@router.post(
    "/run-cycle",
    dependencies=[
        Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.SUSTAINABILITY_OFFICER))
    ],
    summary="Run the scheduled_cycle agent graph now, for this hospital",
)
async def run_cycle(hospital_id: HospitalId, _user: CurrentUser) -> dict:
    """Runs disease forecast -> medicine -> energy -> water -> waste -> carbon ->
    executive synthesis on demand, instead of waiting for the next hourly Celery
    beat tick. Every agent it runs still writes its own ``AgentLog`` entry, so a
    manual run is indistinguishable in the audit trail from a scheduled one.
    """
    from app.agents.graph.runner import run_scheduled_cycle_now

    final_state = await run_scheduled_cycle_now(hospital_id)
    results: dict[str, dict] = final_state.get("results", {})

    return {
        "run_id": final_state.get("run_id"),
        "agents_run": list(results.keys()),
        "degraded": [name for name, result in results.items() if result.get("used_fallback")],
        "results": results,
    }
