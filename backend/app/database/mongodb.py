"""MongoDB connection lifecycle.

A single Motor client is shared process-wide. Collections are exposed through the
``Collections`` accessor so collection names are never string-literals scattered
through the codebase.
"""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

from app.core.config import settings
from app.core.exceptions import DatabaseError
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class MongoDB:
    """Holds the process-wide Motor client and database handle."""

    client: AsyncIOMotorClient | None = None
    database: AsyncIOMotorDatabase | None = None


mongodb = MongoDB()


async def connect_to_mongo() -> None:
    """Open the connection pool and verify reachability. Called from the app lifespan."""
    if mongodb.client is not None:
        return

    logger.info("mongodb.connecting", db=settings.mongodb_db_name)
    mongodb.client = AsyncIOMotorClient(
        settings.mongodb_uri,
        maxPoolSize=settings.mongodb_max_pool_size,
        minPoolSize=settings.mongodb_min_pool_size,
        serverSelectionTimeoutMS=5000,
        uuidRepresentation="standard",
    )
    mongodb.database = mongodb.client[settings.mongodb_db_name]

    try:
        await mongodb.client.admin.command("ping")
    except (ServerSelectionTimeoutError, PyMongoError) as exc:
        mongodb.client = None
        mongodb.database = None
        logger.error("mongodb.connection_failed", error=str(exc))
        raise DatabaseError(f"Could not connect to MongoDB: {exc}") from exc

    logger.info("mongodb.connected", db=settings.mongodb_db_name)


async def close_mongo_connection() -> None:
    """Close the connection pool cleanly on shutdown."""
    if mongodb.client is not None:
        mongodb.client.close()
        mongodb.client = None
        mongodb.database = None
        logger.info("mongodb.disconnected")


def get_database() -> AsyncIOMotorDatabase:
    """Return the active database handle, or fail loudly."""
    if mongodb.database is None:
        raise DatabaseError("Database connection has not been initialised.")
    return mongodb.database


async def ping() -> bool:
    """Lightweight health probe used by ``/health/ready``."""
    try:
        if mongodb.client is None:
            return False
        await mongodb.client.admin.command("ping")
        return True
    except PyMongoError:
        return False


class Collections:
    """Canonical collection names, and typed accessors for each."""

    HOSPITALS = "hospitals"
    USERS = "users"
    STAFF = "staff"
    DEPARTMENTS = "departments"
    ROOMS = "rooms"
    BEDS = "beds"
    PATIENTS = "patients"
    ADMISSIONS = "admissions"
    AMBULANCES = "ambulances"
    MEDICINES = "medicines"
    INVENTORY = "inventory"
    ENERGY_LOGS = "energy_logs"
    WATER_LOGS = "water_logs"
    WASTE_RECORDS = "waste_records"
    CARBON_REPORTS = "carbon_reports"
    AGENT_LOGS = "agent_logs"
    SIMULATION_DATA = "simulation_data"
    KNOWLEDGE_BASE = "knowledge_base"
    NOTIFICATIONS = "notifications"
    REPORTS = "reports"
    AUDIT_LOGS = "audit_logs"

    @classmethod
    def all(cls) -> list[str]:
        """Every collection name, used by the index bootstrapper and test fixtures."""
        return [
            value
            for key, value in vars(cls).items()
            if key.isupper() and isinstance(value, str)
        ]

    @staticmethod
    def get(name: str) -> AsyncIOMotorCollection:
        """Return a collection handle by name."""
        return get_database()[name]
