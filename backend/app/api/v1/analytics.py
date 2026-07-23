"""Analytics endpoints backing the dashboards."""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AdmissionRepo, AgentLogRepo, BedRepo, CurrentUser, InventoryRepo
from app.models.base import utc_now
from app.services.bed_service import BedService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", summary="Headline KPI strip")
async def overview(
    admissions: AdmissionRepo,
    beds: BedRepo,
    logs: AgentLogRepo,
    _user: CurrentUser,
) -> dict:
    """The four-to-six numbers that sit at the top of every dashboard."""
    occupancy = await BedService(beds).occupancy_summary()
    census = await admissions.census()

    since = utc_now() - timedelta(hours=24)
    admissions_24h = await admissions.count({"created_at": {"$gte": since}})
    critical = await admissions.count(
        {"triage.esi_level": {"$lte": 2}, "status": {"$in": list(admissions.ACTIVE_STATUSES)}}
    )
    agent_decisions = await logs.count({"created_at": {"$gte": since}})

    return {
        "census": census,
        "admissions_24h": admissions_24h,
        "critical_active": critical,
        "occupancy_rate": occupancy["occupancy_rate"],
        "icu_occupancy_rate": occupancy["icu_occupancy_rate"],
        "available_beds": occupancy["available"],
        "agent_decisions_24h": agent_decisions,
    }


@router.get("/patients", summary="Admission and acuity analytics")
async def patient_analytics(
    admissions: AdmissionRepo,
    _user: CurrentUser,
    days: Annotated[int, Query(ge=1, le=90)] = 14,
) -> dict:
    since = utc_now() - timedelta(days=days)
    by_day = await admissions.admissions_by_day(since)
    esi = await admissions.esi_distribution()

    # Collapse the per-category rows into a daily total series for the headline chart.
    totals: dict[str, int] = {}
    for row in by_day:
        totals[row["date"]] = totals.get(row["date"], 0) + row["count"]

    return {
        "window_days": days,
        "daily_totals": [{"date": d, "count": c} for d, c in sorted(totals.items())],
        "by_category": by_day,
        "esi_distribution": esi,
    }


@router.get("/occupancy", summary="Bed occupancy analytics")
async def occupancy_analytics(beds: BedRepo, _user: CurrentUser) -> dict:
    return await BedService(beds).occupancy_summary()


@router.get("/medicine", summary="Inventory risk analytics")
async def medicine_analytics(
    inventory: InventoryRepo,
    _user: CurrentUser,
    expiry_days: Annotated[int, Query(ge=1, le=365)] = 90,
) -> dict:
    cutoff = (utc_now() + timedelta(days=expiry_days)).date().isoformat()
    expiring = await inventory.expiring_within(cutoff)
    low_stock = await inventory.low_stock()

    value_at_risk = sum(
        (row.get("quantity", 0) or 0) * (row.get("unit_cost_paise", 0) or 0) for row in expiring
    )

    return {
        "expiring_count": len(expiring),
        "expiring": expiring[:50],
        "low_stock_count": len(low_stock),
        "low_stock": low_stock[:50],
        "value_at_risk_paise": value_at_risk,
    }
