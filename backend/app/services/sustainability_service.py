"""Aggregates raw energy/water/waste telemetry into the totals the Carbon
Intelligence Agent (and, later, the Energy and Water agents) need.

Kept as its own service — separate from the individual Energy/Water/Waste agents —
because the Carbon Intelligence Agent needs a cross-cutting view of all three
streams at once, and "agents call services, never repositories" applies here just
as much as it does to bed allocation.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from app.core.constants import DisposalMethod, WasteCategory
from app.database.repositories import EnergyLogRepository, WasteRecordRepository, WaterLogRepository
from app.models.base import utc_now


class SustainabilityService:
    def __init__(
        self,
        energy_logs: EnergyLogRepository,
        water_logs: WaterLogRepository,
        waste_records: WasteRecordRepository,
    ) -> None:
        self.energy_logs = energy_logs
        self.water_logs = water_logs
        self.waste_records = waste_records

    async def recent_totals(self, hours: int = 24) -> dict[str, Any]:
        """Everything the Carbon Intelligence Agent needs for one cycle, in one call."""
        since = utc_now() - timedelta(hours=hours)

        energy_rows = await self.energy_logs.aggregate(
            [
                {"$match": {"timestamp": {"$gte": since}}},
                {
                    "$group": {
                        "_id": None,
                        "total_kwh": {"$sum": "$consumption_kwh"},
                        "grid_kwh": {"$sum": "$source_mix.grid_kwh"},
                        "solar_kwh": {"$sum": "$source_mix.solar_kwh"},
                        "dg_kwh": {"$sum": "$source_mix.dg_kwh"},
                    }
                },
            ]
        )
        energy = energy_rows[0] if energy_rows else {}

        water_rows = await self.water_logs.aggregate(
            [
                {"$match": {"timestamp": {"$gte": since}}},
                {
                    "$group": {
                        "_id": None,
                        "total_litres": {"$sum": "$consumption_litres"},
                        "municipal_l": {"$sum": "$source.municipal_l"},
                        "borewell_l": {"$sum": "$source.borewell_l"},
                        "rainwater_l": {"$sum": "$source.rainwater_l"},
                        "recycled_l": {"$sum": "$source.recycled_l"},
                        "max_leak_probability": {"$max": "$leak_probability"},
                    }
                },
            ]
        )
        water = water_rows[0] if water_rows else {}

        waste_rows = await self.waste_records.aggregate(
            [
                {"$match": {"date": {"$gte": since.date()}}},
                {
                    "$group": {
                        "_id": {"category": "$category", "method": "$disposal_method"},
                        "weight_kg": {"$sum": "$weight_kg"},
                        "recyclable_recovered_kg": {"$sum": "$recyclable_recovered_kg"},
                    }
                },
            ]
        )
        waste_by_method: dict[str, float] = {method.value: 0.0 for method in DisposalMethod}
        waste_by_category: dict[str, float] = {category.value: 0.0 for category in WasteCategory}
        recyclable_recovered_kg = 0.0
        for row in waste_rows:
            method = row["_id"]["method"]
            category = row["_id"]["category"]
            waste_by_method[method] = waste_by_method.get(method, 0.0) + row["weight_kg"]
            waste_by_category[category] = waste_by_category.get(category, 0.0) + row["weight_kg"]
            recyclable_recovered_kg += row.get("recyclable_recovered_kg", 0.0)

        return {
            "period_hours": hours,
            "energy_kwh": {
                "total": energy.get("total_kwh", 0.0),
                "grid": energy.get("grid_kwh", 0.0),
                "solar": energy.get("solar_kwh", 0.0),
                "diesel_generator": energy.get("dg_kwh", 0.0),
            },
            "water_litres": {
                "total": water.get("total_litres", 0.0),
                "municipal": water.get("municipal_l", 0.0),
                "borewell": water.get("borewell_l", 0.0),
                "rainwater": water.get("rainwater_l", 0.0),
                "recycled": water.get("recycled_l", 0.0),
                "max_leak_probability": water.get("max_leak_probability", 0.0),
            },
            "waste_by_method_kg": waste_by_method,
            "waste_by_category_kg": waste_by_category,
            "recyclable_recovered_kg": recyclable_recovered_kg,
        }
