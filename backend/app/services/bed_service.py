"""Bed allocation business rules.

These invariants apply identically whether the caller is a nurse or the Bed
Allocation Agent, because both go through this service.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from bson import ObjectId

from app.core.constants import BedStatus, BedType
from app.core.exceptions import BedUnavailableError, ConflictError, NotFoundError
from app.core.logging_config import get_logger
from app.database.repositories import BedRepository, serialise, to_object_id
from app.models.base import utc_now

logger = get_logger(__name__)

RESERVATION_MINUTES = 30

# Which bed types can serve which acuity, most preferred first.
ESI_BED_PREFERENCE: dict[int, list[str]] = {
    1: [BedType.ICU, BedType.EMERGENCY, BedType.HDU],
    2: [BedType.HDU, BedType.ICU, BedType.EMERGENCY],
    3: [BedType.GENERAL, BedType.EMERGENCY, BedType.HDU],
    4: [BedType.GENERAL],
    5: [BedType.GENERAL],
}

# Weights used to score candidate beds. Documented in docs/04_agent_design.md.
SCORE_WEIGHTS = {
    "severity_fit": 0.35,
    "department_match": 0.25,
    "feature_match": 0.15,
    "type_preference": 0.15,
    "isolation": 0.10,
}


class BedService:
    """Selects, reserves and releases beds under explicit clinical constraints."""

    def __init__(self, beds: BedRepository) -> None:
        self.beds = beds

    # ------------------------------------------------------------- allocation
    async def recommend(
        self,
        esi_level: int,
        department_id: ObjectId | None = None,
        requires_isolation: bool = False,
        required_features: list[str] | None = None,
    ) -> dict[str, Any]:
        """Score every assignable bed and return the best candidate with alternatives."""
        candidates = await self.beds.find_available()

        if not candidates:
            raise BedUnavailableError(
                "No beds are currently available in this hospital.",
                details={"esi_level": esi_level},
            )

        preferred_types = ESI_BED_PREFERENCE.get(esi_level, [BedType.GENERAL])
        features = set(required_features or [])

        scored = []
        for bed in candidates:
            # Hard filters first. A bed that fails these is never a candidate.
            if bed.get("status") != BedStatus.AVAILABLE:
                continue
            if bed.get("current_admission_id") is not None:
                continue
            if requires_isolation and bed.get("type") != BedType.ISOLATION:
                continue

            score = self._score(bed, esi_level, department_id, preferred_types, features)
            scored.append((score, bed))

        if not scored:
            raise BedUnavailableError(
                "No bed satisfies the clinical constraints for this patient.",
                details={
                    "esi_level": esi_level,
                    "requires_isolation": requires_isolation,
                    "required_features": sorted(features),
                },
            )

        scored.sort(key=lambda pair: pair[0], reverse=True)
        best_score, best_bed = scored[0]

        return {
            "bed": serialise(best_bed),
            "score": round(best_score, 3),
            "alternatives": [serialise(bed) for _, bed in scored[1:4]],
            "candidates_considered": len(scored),
        }

    def _score(
        self,
        bed: dict,
        esi_level: int,
        department_id: ObjectId | None,
        preferred_types: list[str],
        required_features: set[str],
    ) -> float:
        """Weighted suitability score in the range 0-1."""
        score = 0.0

        # Type preference by acuity.
        bed_type = bed.get("type")
        if bed_type in preferred_types:
            rank = preferred_types.index(bed_type)
            score += SCORE_WEIGHTS["type_preference"] * (1.0 - rank / max(len(preferred_types), 1))

        # Severity fit: high acuity belongs in monitored beds.
        monitored = bed_type in {BedType.ICU, BedType.HDU, BedType.EMERGENCY}
        if esi_level <= 2 and monitored or esi_level >= 4 and not monitored:
            score += SCORE_WEIGHTS["severity_fit"]
        elif esi_level == 3:
            score += SCORE_WEIGHTS["severity_fit"] * 0.6

        # Department match.
        if department_id is not None and bed.get("department_id") == department_id:
            score += SCORE_WEIGHTS["department_match"]

        # Required equipment.
        bed_features = set(bed.get("features") or [])
        if required_features:
            covered = len(required_features & bed_features) / len(required_features)
            score += SCORE_WEIGHTS["feature_match"] * covered
        else:
            score += SCORE_WEIGHTS["feature_match"] * 0.5

        # Prefer not to burn an isolation bed on a patient who does not need one.
        if bed_type != BedType.ISOLATION:
            score += SCORE_WEIGHTS["isolation"]

        return score

    # ------------------------------------------------------------ transitions
    async def reserve(self, bed_id: str) -> dict:
        """Hold a bed for 30 minutes. Fails if another request won the race."""
        until = utc_now() + timedelta(minutes=RESERVATION_MINUTES)
        reserved = await self.beds.reserve(bed_id, until)

        if reserved is None:
            raise ConflictError(
                "That bed was taken by another request. Request a new recommendation.",
                details={"bed_id": bed_id},
            )

        logger.info("bed.reserved", bed_id=bed_id, until=until.isoformat())
        return serialise(reserved)

    async def assign(self, bed_id: str, admission_id: str | ObjectId) -> dict:
        """Move a bed to occupied and attach the admission."""
        occupied = await self.beds.occupy(bed_id, to_object_id(admission_id))

        if occupied is None:
            raise ConflictError(
                "That bed is no longer available for assignment.", details={"bed_id": bed_id}
            )

        await self.beds.update_one(
            self.beds.scope({"_id": to_object_id(bed_id)}),
            {
                "$push": {
                    "occupancy_history": {
                        "$each": [
                            {
                                "admission_id": to_object_id(admission_id),
                                "occupied_from": utc_now(),
                                "occupied_to": None,
                            }
                        ],
                        "$slice": -20,
                    }
                }
            },
        )

        logger.info("bed.assigned", bed_id=bed_id, admission_id=str(admission_id))
        return serialise(occupied)

    async def release(self, bed_id: str) -> dict:
        """Free a bed on discharge. It goes to cleaning, not straight to available."""
        bed = await self.beds.find_by_id(bed_id)
        if bed is None:
            raise NotFoundError("Bed not found.", details={"bed_id": bed_id})

        released = await self.beds.update_one(
            self.beds.scope({"_id": to_object_id(bed_id)}),
            {
                "$set": {
                    "status": BedStatus.CLEANING,
                    "current_admission_id": None,
                    "reserved_until": None,
                    "last_cleaned_at": utc_now(),
                }
            },
        )
        logger.info("bed.released", bed_id=bed_id)
        return serialise(released)

    async def set_status(self, bed_id: str, status: str) -> dict:
        """Manual status change, used for maintenance and cleaning completion."""
        bed = await self.beds.find_by_id(bed_id)
        if bed is None:
            raise NotFoundError("Bed not found.", details={"bed_id": bed_id})

        if status == BedStatus.AVAILABLE and bed.get("current_admission_id"):
            raise ConflictError(
                "Cannot mark an occupied bed available. Discharge the patient first."
            )

        updated = await self.beds.update(bed_id, {"status": status})
        return serialise(updated)

    # -------------------------------------------------------------- reporting
    async def occupancy_summary(self) -> dict:
        """Headline occupancy figures plus a per-department breakdown."""
        counts = await self.beds.aggregate(
            [{"$group": {"_id": "$status", "n": {"$sum": 1}}}]
        )
        by_status = {row["_id"]: row["n"] for row in counts}

        icu_counts = await self.beds.aggregate(
            [
                {"$match": {"type": BedType.ICU}},
                {"$group": {"_id": "$status", "n": {"$sum": 1}}},
            ]
        )
        icu_by_status = {row["_id"]: row["n"] for row in icu_counts}

        total = sum(by_status.values())
        occupied = by_status.get(BedStatus.OCCUPIED, 0)
        icu_total = sum(icu_by_status.values())
        icu_occupied = icu_by_status.get(BedStatus.OCCUPIED, 0)

        return {
            "total_beds": total,
            "occupied": occupied,
            "available": by_status.get(BedStatus.AVAILABLE, 0),
            "cleaning": by_status.get(BedStatus.CLEANING, 0),
            "maintenance": by_status.get(BedStatus.MAINTENANCE, 0),
            "reserved": by_status.get(BedStatus.RESERVED, 0),
            "occupancy_rate": round(occupied / total * 100, 1) if total else 0.0,
            "icu_total": icu_total,
            "icu_occupied": icu_occupied,
            "icu_occupancy_rate": round(icu_occupied / icu_total * 100, 1) if icu_total else 0.0,
            "by_department": await self.beds.occupancy_by_department(),
        }

    async def expire_stale_reservations(self) -> int:
        """Return beds whose 30-minute hold lapsed. Run by the simulator tick."""
        result = await self.beds.collection.update_many(
            self.beds.scope(
                {"status": BedStatus.RESERVED, "reserved_until": {"$lt": utc_now()}}
            ),
            {"$set": {"status": BedStatus.AVAILABLE, "reserved_until": None}},
        )
        if result.modified_count:
            logger.info("bed.reservations_expired", count=result.modified_count)
        return result.modified_count
