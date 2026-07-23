"""Repository layer.

Two rules make cross-tenant leakage structurally impossible:

1. ``TenantRepository`` injects ``hospital_id`` into every filter it builds. Callers
   cannot forget it, because they never construct the filter themselves.
2. Services never import ``motor``. If a query is needed, it belongs here.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Generic, TypeVar

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo import ReturnDocument

from app.core.exceptions import NotFoundError, ValidationError
from app.database.mongodb import Collections, get_database
from app.models.base import utc_now

T = TypeVar("T")


def to_object_id(value: str | ObjectId) -> ObjectId:
    """Coerce a string to ObjectId, raising a domain error rather than a bson error."""
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as exc:
        raise ValidationError(f"'{value}' is not a valid identifier.") from exc


def _coerce(value: Any) -> Any:
    """Recursively convert ObjectId values to strings.

    Nested documents (``triage.recommended_department_id``, embedded arrays such as
    ``occupancy_history``) also carry ObjectIds, and Pydantic cannot serialise them.
    Handling only the top level silently produces 500s on the nested endpoints.
    """
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {key: _coerce(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_coerce(item) for item in value]
    return value


def serialise(document: dict[str, Any] | None) -> dict[str, Any] | None:
    """Convert a Mongo document to a JSON-safe dict, renaming ``_id`` to ``id``."""
    if document is None:
        return None
    result = {key: _coerce(value) for key, value in document.items()}
    if "_id" in result:
        result["id"] = result.pop("_id")
    return result


class BaseRepository(Generic[T]):
    """CRUD for a single collection. Not tenant-scoped: use for network-wide masters."""

    collection_name: str

    def __init__(self, collection_name: str | None = None) -> None:
        if collection_name:
            self.collection_name = collection_name

    @property
    def collection(self) -> AsyncIOMotorCollection:
        return get_database()[self.collection_name]

    # ----------------------------------------------------------------- reads
    async def find_by_id(self, document_id: str | ObjectId) -> dict | None:
        return await self.collection.find_one({"_id": to_object_id(document_id)})

    async def get_by_id(self, document_id: str | ObjectId) -> dict:
        """Like ``find_by_id`` but raises NotFoundError instead of returning None."""
        document = await self.find_by_id(document_id)
        if document is None:
            raise NotFoundError(
                f"No {self.collection_name} record with id {document_id}.",
                details={"collection": self.collection_name, "id": str(document_id)},
            )
        return document

    async def find_one(self, filters: dict[str, Any]) -> dict | None:
        return await self.collection.find_one(filters)

    async def find_many(
        self,
        filters: dict[str, Any] | None = None,
        *,
        skip: int = 0,
        limit: int = 50,
        sort_by: str = "created_at",
        sort_desc: bool = True,
        projection: dict[str, Any] | None = None,
    ) -> list[dict]:
        cursor = (
            self.collection.find(filters or {}, projection)
            .sort(sort_by, -1 if sort_desc else 1)
            .skip(skip)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        return await self.collection.count_documents(filters or {})

    async def exists(self, filters: dict[str, Any]) -> bool:
        return await self.collection.count_documents(filters, limit=1) > 0

    async def aggregate(self, pipeline: list[dict[str, Any]]) -> list[dict]:
        return await self.collection.aggregate(pipeline).to_list(length=None)

    # ---------------------------------------------------------------- writes
    async def insert(self, document: dict[str, Any]) -> dict:
        payload = dict(document)
        now = utc_now()
        payload.setdefault("created_at", now)
        payload["updated_at"] = now
        result = await self.collection.insert_one(payload)
        payload["_id"] = result.inserted_id
        return payload

    async def insert_many(self, documents: list[dict[str, Any]]) -> int:
        if not documents:
            return 0
        now = utc_now()
        for document in documents:
            document.setdefault("created_at", now)
            document.setdefault("updated_at", now)
        result = await self.collection.insert_many(documents)
        return len(result.inserted_ids)

    async def update(self, document_id: str | ObjectId, patch: dict[str, Any]) -> dict:
        payload = {key: value for key, value in patch.items() if value is not None}
        payload["updated_at"] = utc_now()
        updated = await self.collection.find_one_and_update(
            {"_id": to_object_id(document_id)},
            {"$set": payload},
            return_document=ReturnDocument.AFTER,
        )
        if updated is None:
            raise NotFoundError(f"No {self.collection_name} record with id {document_id}.")
        return updated

    async def update_one(self, filters: dict[str, Any], update: dict[str, Any]) -> dict | None:
        """Escape hatch for atomic operators ($inc, $push, conditional $set)."""
        update.setdefault("$set", {})["updated_at"] = utc_now()
        return await self.collection.find_one_and_update(
            filters, update, return_document=ReturnDocument.AFTER
        )

    async def delete(self, document_id: str | ObjectId) -> bool:
        result = await self.collection.delete_one({"_id": to_object_id(document_id)})
        return result.deleted_count > 0


class TenantRepository(BaseRepository[T]):
    """Repository bound to one hospital. Every filter is scoped automatically."""

    def __init__(self, hospital_id: str | ObjectId, collection_name: str | None = None) -> None:
        super().__init__(collection_name)
        self.hospital_id = to_object_id(hospital_id)

    def scope(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        """Merge the tenant key into a filter. The one place scoping is applied."""
        return {**(filters or {}), "hospital_id": self.hospital_id}

    # Every inherited read is re-declared to apply the scope.
    async def find_by_id(self, document_id: str | ObjectId) -> dict | None:
        return await self.collection.find_one(self.scope({"_id": to_object_id(document_id)}))

    async def find_one(self, filters: dict[str, Any]) -> dict | None:
        return await self.collection.find_one(self.scope(filters))

    async def find_many(self, filters: dict[str, Any] | None = None, **kwargs) -> list[dict]:
        return await super().find_many(self.scope(filters), **kwargs)

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        return await self.collection.count_documents(self.scope(filters))

    async def exists(self, filters: dict[str, Any]) -> bool:
        return await self.collection.count_documents(self.scope(filters), limit=1) > 0

    async def insert(self, document: dict[str, Any]) -> dict:
        return await super().insert({**document, "hospital_id": self.hospital_id})

    async def insert_many(self, documents: list[dict[str, Any]]) -> int:
        for document in documents:
            document["hospital_id"] = self.hospital_id
        return await super().insert_many(documents)

    async def aggregate(self, pipeline: list[dict[str, Any]]) -> list[dict]:
        """Prepend a tenant $match so no pipeline can accidentally span hospitals."""
        return await super().aggregate([{"$match": {"hospital_id": self.hospital_id}}, *pipeline])


# --------------------------------------------------------------- concrete repos
class UserRepository(BaseRepository):
    collection_name = Collections.USERS

    async def find_by_email(self, email: str) -> dict | None:
        return await self.collection.find_one({"email": email.lower().strip()})

    async def register_login(self, user_id: str | ObjectId) -> None:
        await self.collection.update_one(
            {"_id": to_object_id(user_id)},
            {"$set": {"last_login_at": utc_now(), "failed_login_count": 0}},
        )

    async def register_failed_login(self, email: str) -> None:
        await self.collection.update_one(
            {"email": email.lower().strip()}, {"$inc": {"failed_login_count": 1}}
        )


class HospitalRepository(BaseRepository):
    collection_name = Collections.HOSPITALS

    async def find_by_code(self, code: str) -> dict | None:
        return await self.collection.find_one({"code": code.upper()})

    async def find_nearest_capable(
        self, longitude: float, latitude: float, capability: str | None = None, limit: int = 5
    ) -> list[dict]:
        """Geospatial search used by the dispatch agent to find suitable destinations."""
        query: dict[str, Any] = {
            "is_active": True,
            "location": {
                "$near": {
                    "$geometry": {"type": "Point", "coordinates": [longitude, latitude]},
                }
            },
        }
        if capability:
            query["capabilities"] = capability
        return await self.collection.find(query).limit(limit).to_list(length=limit)


class MedicineRepository(BaseRepository):
    collection_name = Collections.MEDICINES

    async def find_by_sku(self, sku: str) -> dict | None:
        return await self.collection.find_one({"sku": sku})


class DepartmentRepository(TenantRepository):
    collection_name = Collections.DEPARTMENTS

    async def find_by_code(self, code: str) -> dict | None:
        return await self.find_one({"code": code.upper()})

    async def list_active(self) -> list[dict]:
        return await self.find_many({"is_active": True}, limit=100, sort_by="code", sort_desc=False)


class PatientRepository(TenantRepository):
    collection_name = Collections.PATIENTS

    async def find_by_mrn(self, mrn: str) -> dict | None:
        return await self.find_one({"mrn": mrn})

    async def next_mrn(self) -> str:
        """Sequential MRN per hospital. Adequate for a single-writer demo workload."""
        total = await self.count()
        return f"MRN-{total + 1:06d}"


class BedRepository(TenantRepository):
    collection_name = Collections.BEDS

    async def find_available(
        self, bed_type: str | None = None, department_id: ObjectId | None = None
    ) -> list[dict]:
        filters: dict[str, Any] = {"status": "available", "current_admission_id": None}
        if bed_type:
            filters["type"] = bed_type
        if department_id:
            filters["department_id"] = department_id
        return await self.find_many(filters, limit=200, sort_by="bed_number", sort_desc=False)

    async def reserve(self, bed_id: str | ObjectId, until: Any) -> dict | None:
        """Conditional update: only succeeds if the bed is still available.

        This is the concurrency guard that stops two arrivals claiming one bed.
        """
        return await self.update_one(
            self.scope(
                {"_id": to_object_id(bed_id), "status": "available", "current_admission_id": None}
            ),
            {"$set": {"status": "reserved", "reserved_until": until}},
        )

    async def occupy(self, bed_id: str | ObjectId, admission_id: ObjectId) -> dict | None:
        return await self.update_one(
            self.scope({"_id": to_object_id(bed_id), "status": {"$in": ["available", "reserved"]}}),
            {
                "$set": {
                    "status": "occupied",
                    "current_admission_id": admission_id,
                    "reserved_until": None,
                }
            },
        )

    async def release(self, bed_id: str | ObjectId) -> dict | None:
        return await self.update_one(
            self.scope({"_id": to_object_id(bed_id)}),
            {
                "$set": {
                    "status": "cleaning",
                    "current_admission_id": None,
                    "last_cleaned_at": None,
                }
            },
        )

    async def occupancy_by_department(self) -> list[dict]:
        return await self.aggregate(
            [
                {"$group": {"_id": {"dept": "$department_id", "status": "$status"}, "n": {"$sum": 1}}},
                {
                    "$group": {
                        "_id": "$_id.dept",
                        "breakdown": {"$push": {"k": "$_id.status", "v": "$n"}},
                        "total": {"$sum": "$n"},
                    }
                },
                {
                    "$lookup": {
                        "from": Collections.DEPARTMENTS,
                        "localField": "_id",
                        "foreignField": "_id",
                        "as": "department",
                    }
                },
                {
                    "$project": {
                        "department_id": {"$toString": "$_id"},
                        "department": {"$first": "$department.name"},
                        "total": 1,
                        "breakdown": {"$arrayToObject": "$breakdown"},
                        "_id": 0,
                    }
                },
                {"$sort": {"department": 1}},
            ]
        )


class AdmissionRepository(TenantRepository):
    collection_name = Collections.ADMISSIONS

    ACTIVE_STATUSES = ("triaged", "admitted", "in_treatment")

    async def next_admission_number(self, year: int) -> str:
        total = await self.count()
        return f"ADM-{year}-{total + 1:06d}"

    async def active_queue(self, limit: int = 100) -> list[dict]:
        """Triage queue: most acute first, then longest waiting."""
        return await self.collection.find(
            self.scope({"status": {"$in": list(self.ACTIVE_STATUSES)}})
        ).sort([("triage.esi_level", 1), ("created_at", 1)]).limit(limit).to_list(length=limit)

    async def census(self) -> int:
        return await self.count({"status": {"$in": list(self.ACTIVE_STATUSES)}})

    async def expected_discharges_within(self, hours: int = 24) -> int:
        """Active admissions whose ``admitted_at + predicted_los_days`` falls inside the window.

        Used by the Bed Allocation Agent to report headroom rather than just the
        instantaneous occupancy snapshot — two hospitals at 95% occupancy are in very
        different positions if one has a dozen discharges due tomorrow morning.
        """
        cutoff = utc_now() + timedelta(hours=hours)
        return await self.count(
            {
                "status": {"$in": ["admitted", "in_treatment"]},
                "admitted_at": {"$ne": None},
                "predicted_los_days": {"$ne": None},
                "$expr": {
                    "$lte": [
                        {"$add": ["$admitted_at", {"$multiply": ["$predicted_los_days", 86400000]}]},
                        cutoff,
                    ]
                },
            }
        )

    async def admissions_by_day(self, since: Any) -> list[dict]:
        return await self.aggregate(
            [
                {"$match": {"created_at": {"$gte": since}}},
                {
                    "$group": {
                        "_id": {
                            "day": {
                                "$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}
                            },
                            "category": "$disease_category",
                        },
                        "count": {"$sum": 1},
                    }
                },
                {
                    "$project": {
                        "date": "$_id.day",
                        "category": "$_id.category",
                        "count": 1,
                        "_id": 0,
                    }
                },
                {"$sort": {"date": 1}},
            ]
        )

    async def daily_totals(self, since: Any) -> list[dict]:
        """Total arrivals per day, category-collapsed. Feeds the Disease Forecast Agent."""
        return await self.aggregate(
            [
                {"$match": {"created_at": {"$gte": since}}},
                {
                    "$group": {
                        "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                        "count": {"$sum": 1},
                    }
                },
                {"$project": {"date": "$_id", "count": 1, "_id": 0}},
                {"$sort": {"date": 1}},
            ]
        )

    async def esi_distribution(self) -> list[dict]:
        return await self.aggregate(
            [
                {"$match": {"triage.esi_level": {"$ne": None}}},
                {"$group": {"_id": "$triage.esi_level", "count": {"$sum": 1}}},
                {"$project": {"esi_level": "$_id", "count": 1, "_id": 0}},
                {"$sort": {"esi_level": 1}},
            ]
        )


class InventoryRepository(TenantRepository):
    collection_name = Collections.INVENTORY

    async def expiring_within(self, cutoff: Any) -> list[dict]:
        return await self.aggregate(
            [
                {"$match": {"status": "active", "expiry_date": {"$lte": cutoff}, "quantity": {"$gt": 0}}},
                {
                    "$lookup": {
                        "from": Collections.MEDICINES,
                        "localField": "medicine_id",
                        "foreignField": "_id",
                        "as": "medicine",
                    }
                },
                {
                    "$project": {
                        "id": {"$toString": "$_id"},
                        "batch_number": 1,
                        "quantity": 1,
                        "expiry_date": 1,
                        "unit_cost_paise": 1,
                        "medicine_name": {"$first": "$medicine.name"},
                        "sku": {"$first": "$medicine.sku"},
                        "is_critical": {"$first": "$medicine.is_critical"},
                        "_id": 0,
                    }
                },
                {"$sort": {"expiry_date": 1}},
            ]
        )

    async def low_stock(self) -> list[dict]:
        return await self.aggregate(
            [
                {"$match": {"status": "active"}},
                {"$match": {"$expr": {"$lte": ["$quantity", "$reorder_point"]}}},
                {
                    "$lookup": {
                        "from": Collections.MEDICINES,
                        "localField": "medicine_id",
                        "foreignField": "_id",
                        "as": "medicine",
                    }
                },
                {
                    "$project": {
                        "id": {"$toString": "$_id"},
                        "quantity": 1,
                        "reorder_point": 1,
                        "medicine_name": {"$first": "$medicine.name"},
                        "sku": {"$first": "$medicine.sku"},
                        "is_critical": {"$first": "$medicine.is_critical"},
                        "_id": 0,
                    }
                },
            ]
        )


class AgentLogRepository(TenantRepository):
    collection_name = Collections.AGENT_LOGS

    async def by_run(self, run_id: str) -> list[dict]:
        return await self.find_many({"run_id": run_id}, limit=50, sort_by="created_at", sort_desc=False)

    async def recent_runs(self, limit: int = 20) -> list[dict]:
        return await self.aggregate(
            [
                {"$sort": {"created_at": -1}},
                {
                    "$group": {
                        "_id": "$run_id",
                        "started_at": {"$last": "$created_at"},
                        "agents": {"$sum": 1},
                        "duration_ms": {"$sum": "$duration_ms"},
                        "triggered_by": {"$first": "$triggered_by"},
                        "degraded": {"$max": {"$cond": ["$used_fallback", 1, 0]}},
                        "failed": {"$max": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}},
                    }
                },
                {"$sort": {"started_at": -1}},
                {"$limit": limit},
                {"$project": {"run_id": "$_id", "_id": 0, "started_at": 1, "agents": 1,
                              "duration_ms": 1, "triggered_by": 1, "degraded": 1, "failed": 1}},
            ]
        )


class NotificationRepository(TenantRepository):
    collection_name = Collections.NOTIFICATIONS

    async def for_role(self, role: str, limit: int = 50) -> list[dict]:
        return await self.find_many({"target_roles": role}, limit=limit)

    async def unread_count(self, role: str, user_id: ObjectId) -> int:
        return await self.count({"target_roles": role, "read_by.user_id": {"$ne": user_id}})


class AuditLogRepository(TenantRepository):
    collection_name = Collections.AUDIT_LOGS


class EnergyLogRepository(TenantRepository):
    collection_name = Collections.ENERGY_LOGS


class WaterLogRepository(TenantRepository):
    collection_name = Collections.WATER_LOGS


class WasteRecordRepository(TenantRepository):
    collection_name = Collections.WASTE_RECORDS


class AmbulanceRepository(TenantRepository):
    collection_name = Collections.AMBULANCES


class RoomRepository(TenantRepository):
    collection_name = Collections.ROOMS


class StaffRepository(TenantRepository):
    collection_name = Collections.STAFF


class KnowledgeChunkRepository(BaseRepository):
    """The corpus is network-wide reference material (regulatory text), not
    hospital-specific data, so this is a ``BaseRepository`` rather than tenant-scoped."""

    collection_name = Collections.KNOWLEDGE_BASE

    async def by_category(self, category: str, limit: int = 50) -> list[dict]:
        return await self.find_many({"category": category}, limit=limit, sort_by="chunk_id", sort_desc=False)

    async def text_search(self, query: str, limit: int = 5) -> list[dict]:
        """MongoDB ``$text`` search — the retriever's fallback path when FAISS/
        sentence-transformers aren't installed (see requirements-ai.txt)."""
        cursor = (
            self.collection.find(
                {"$text": {"$search": query}}, {"score": {"$meta": "textScore"}}
            )
            .sort([("score", {"$meta": "textScore"})])
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def by_faiss_positions(self, positions: list[int]) -> list[dict]:
        rows = await self.find_many({"faiss_index_position": {"$in": positions}}, limit=len(positions) or 1)
        by_position = {row["faiss_index_position"]: row for row in rows}
        return [by_position[p] for p in positions if p in by_position]

    async def replace_all(self, chunks: list[dict]) -> int:
        """Full re-ingestion: the corpus is small and versioned, so a clean
        replace is simpler and safer than diffing chunk-by-chunk."""
        await self.collection.delete_many({})
        return await self.insert_many(chunks)
