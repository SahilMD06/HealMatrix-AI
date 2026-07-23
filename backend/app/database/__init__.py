"""Data access layer: connection management, index bootstrap and repositories."""

from app.database import indexes, mongodb
from app.database.mongodb import Collections, get_database

__all__ = ["Collections", "get_database", "indexes", "mongodb"]
