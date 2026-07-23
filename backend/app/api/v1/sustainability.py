"""Sustainability endpoints: energy, water, waste and carbon figures for the
Sustainability Dashboard.

The headline ``/summary`` route runs the real, deterministic Carbon Intelligence
Agent inline against live totals (``SustainabilityService.recent_totals``) rather
than duplicating its arithmetic here — this is the same agent the scheduled
Celery cycle uses, called synchronously because its whole pipeline is pure
computation with no I/O of its own and no LLM in the loop (see
``app/agents/carbon_agent.py``'s module docstring), so there is no cost to
running it on every dashboard load rather than waiting for the next hourly tick.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Query

from app.agents.carbon_agent import CarbonIntelligenceAgent
from app.api.deps import CurrentUser, EnergyLogRepo, HospitalId, WasteRecordRepo, WaterLogRepo
from app.database.mongodb import Collections, get_database
from app.database.repositories import to_object_id
from app.models.base import utc_now
from app.services.sustainability_service import SustainabilityService

router = APIRouter(prefix="/sustainability", tags=["sustainability"])


async def _total_beds(hospital_id: str) -> int:
    database = get_database()
    hospital = await database[Collections.HOSPITALS].find_one({"_id": to_object_id(hospital_id)})
    return ((hospital or {}).get("capacity", {}) or {}).get("total_beds", 0)


@router.get("/summary", summary="Energy, water, waste and carbon headline figures")
async def summary(
    hospital_id: HospitalId,
    energy: EnergyLogRepo,
    water: WaterLogRepo,
    waste: WasteRecordRepo,
    _user: CurrentUser,
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
) -> dict:
    service = SustainabilityService(energy, water, waste)
    totals = await service.recent_totals(hours=hours)

    state = {
        "total_beds": await _total_beds(hospital_id),
        "sustainability_totals": totals,
        "anaesthetic_gas_kg": {},
        "messages": [],
    }
    carbon = await CarbonIntelligenceAgent().run(state)

    return {
        "period_hours": hours,
        "energy": totals["energy_kwh"],
        "water": totals["water_litres"],
        "waste_by_method_kg": totals["waste_by_method_kg"],
        "waste_by_category_kg": totals["waste_by_category_kg"],
        "recyclable_recovered_kg": totals["recyclable_recovered_kg"],
        "carbon": carbon.output,
        "carbon_rationale": carbon.rationale,
        "degraded": carbon.used_fallback,
    }


@router.get("/energy-history", summary="Hourly energy consumption, trailing week")
async def energy_history(
    energy: EnergyLogRepo,
    _user: CurrentUser,
    days: Annotated[int, Query(ge=1, le=30)] = 7,
) -> list[dict]:
    since = utc_now() - timedelta(days=days)
    rows = await energy.find_many(
        {"timestamp": {"$gte": since}}, limit=24 * days, sort_by="timestamp", sort_desc=False
    )
    return [
        {
            "timestamp": row.get("timestamp"),
            "consumption_kwh": row.get("consumption_kwh", 0.0),
            "grid_kwh": row.get("source_mix", {}).get("grid_kwh", 0.0),
            "solar_kwh": row.get("source_mix", {}).get("solar_kwh", 0.0),
            "dg_kwh": row.get("source_mix", {}).get("dg_kwh", 0.0),
        }
        for row in rows
    ]


@router.get("/water-history", summary="Hourly water consumption, trailing week")
async def water_history(
    water: WaterLogRepo,
    _user: CurrentUser,
    days: Annotated[int, Query(ge=1, le=30)] = 7,
) -> list[dict]:
    since = utc_now() - timedelta(days=days)
    rows = await water.find_many(
        {"timestamp": {"$gte": since}}, limit=24 * days, sort_by="timestamp", sort_desc=False
    )
    return [
        {
            "timestamp": row.get("timestamp"),
            "consumption_litres": row.get("consumption_litres", 0.0),
            "night_min_flow_lpm": row.get("night_min_flow_lpm"),
            "leak_probability": row.get("leak_probability", 0.0),
        }
        for row in rows
    ]


@router.get("/waste-history", summary="Daily waste generation by category, trailing window")
async def waste_history(
    waste: WasteRecordRepo,
    _user: CurrentUser,
    days: Annotated[int, Query(ge=1, le=90)] = 14,
) -> list[dict]:
    since = (utc_now() - timedelta(days=days)).date()
    rows = await waste.find_many(
        {"date": {"$gte": since}}, limit=500, sort_by="date", sort_desc=False
    )
    return [
        {
            "date": str(row.get("date")),
            "category": row.get("category"),
            "disposal_method": row.get("disposal_method"),
            "weight_kg": row.get("weight_kg", 0.0),
            "recyclable_recovered_kg": row.get("recyclable_recovered_kg", 0.0),
        }
        for row in rows
    ]
