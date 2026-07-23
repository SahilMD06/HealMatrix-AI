"""Pharmacy inventory business logic. Thin over the repository layer, same pattern
as ``BedService`` — the Medicine Intelligence Agent calls this, never the
repositories directly.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from app.core.constants import EXPIRY_ALERT_DAYS
from app.database.repositories import InventoryRepository, MedicineRepository, serialise
from app.models.base import utc_now


class InventoryService:
    def __init__(self, inventory: InventoryRepository, medicines: MedicineRepository) -> None:
        self.inventory = inventory
        self.medicines = medicines

    async def expiry_alerts(self, within_days: int = EXPIRY_ALERT_DAYS[0]) -> list[dict]:
        cutoff = utc_now().date() + timedelta(days=within_days)
        rows = await self.inventory.expiring_within(cutoff)
        return [serialise(row) for row in rows]

    async def low_stock_alerts(self) -> list[dict]:
        rows = await self.inventory.low_stock()
        return [serialise(row) for row in rows]

    async def find_medicine(self, sku: str) -> dict[str, Any] | None:
        return serialise(await self.medicines.find_by_sku(sku))
