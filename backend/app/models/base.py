"""Shared Pydantic building blocks for every persisted document."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, GetCoreSchemaHandler
from pydantic_core import core_schema


class PyObjectId(ObjectId):
    """ObjectId that Pydantic v2 can validate and serialise to a string."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, _handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        def validate(value: Any) -> ObjectId:
            if isinstance(value, ObjectId):
                return value
            if isinstance(value, str) and ObjectId.is_valid(value):
                return ObjectId(value)
            raise ValueError(f"Invalid ObjectId: {value!r}")

        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.no_info_plain_validator_function(validate),
            serialization=core_schema.plain_serializer_function_ser_schema(str),
        )


ObjectIdField = Annotated[PyObjectId, Field(description="MongoDB ObjectId")]


def utc_now() -> datetime:
    """Timezone-aware UTC now. Used as the default for every timestamp field."""
    return datetime.now(timezone.utc)


class HealMatrixModel(BaseModel):
    """Base for all models: consistent config, ObjectId support, enum values."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        use_enum_values=True,
        str_strip_whitespace=True,
        json_encoders={ObjectId: str, datetime: lambda v: v.isoformat()},
    )


class TimestampedModel(HealMatrixModel):
    """Adds creation and modification timestamps."""

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class DocumentModel(TimestampedModel):
    """A persisted document with an identifier."""

    id: ObjectIdField | None = Field(default=None, alias="_id")


class TenantDocumentModel(DocumentModel):
    """A document scoped to a single hospital. The repository layer enforces the scope."""

    hospital_id: ObjectIdField


class GeoPoint(HealMatrixModel):
    """GeoJSON point, ordered [longitude, latitude] as MongoDB requires."""

    type: str = Field(default="Point", frozen=True)
    coordinates: list[float] = Field(min_length=2, max_length=2)

    @property
    def longitude(self) -> float:
        return self.coordinates[0]

    @property
    def latitude(self) -> float:
        return self.coordinates[1]

    @classmethod
    def from_lat_lng(cls, latitude: float, longitude: float) -> GeoPoint:
        return cls(coordinates=[longitude, latitude])


class DateRange(HealMatrixModel):
    """An inclusive reporting period."""

    start: datetime
    end: datetime
    granularity: str = "daily"


class PaginationParams(HealMatrixModel):
    """Standard pagination envelope for list endpoints."""

    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)
    sort_by: str = "created_at"
    sort_desc: bool = True
