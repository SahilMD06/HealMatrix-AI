"""Shared pytest fixtures.

Tests run against an in-memory MongoDB (``mongomock_motor``) so the suite needs no
running database and is safe to execute in CI.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough-0123456789")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("BCRYPT_ROUNDS", "4")
os.environ.setdefault("GOOGLE_API_KEY", "")

import httpx  # noqa: E402
from bson import ObjectId  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.database import mongodb as db_module  # noqa: E402
from app.database.mongodb import Collections  # noqa: E402

PASSWORD = "HealMatrix@2026"

BED_PLAN = [("icu", "CARDIO", 4), ("emergency", "ED", 4), ("general", "GEN-MED", 8), ("hdu", "CARDIO", 2)]


@pytest.fixture
async def database():
    """Fresh in-memory database per test."""
    client = AsyncMongoMockClient()
    db_module.mongodb.client = client
    db_module.mongodb.database = client["healmatrix_test"]
    yield db_module.mongodb.database
    db_module.mongodb.client = None
    db_module.mongodb.database = None


@pytest.fixture
async def seeded(database):
    """A small but complete hospital: departments, beds, users, and a second tenant."""
    hospital_id = ObjectId()
    await database[Collections.HOSPITALS].insert_one(
        {
            "_id": hospital_id, "code": "HM-BLR-01", "name": "Test Hospital",
            "type": "tertiary",
            "location": {"type": "Point", "coordinates": [77.5946, 12.9716]},
            "capacity": {"total_beds": 20, "icu_beds": 4, "emergency_beds": 3, "ot_count": 1},
            "capabilities": ["cardiac", "trauma"], "grid_emission_factor": 0.71,
            "is_active": True,
        }
    )

    other_hospital_id = ObjectId()
    await database[Collections.HOSPITALS].insert_one(
        {
            "_id": other_hospital_id, "code": "HM-BLR-02", "name": "Other Hospital",
            "location": {"type": "Point", "coordinates": [77.58, 13.03]}, "is_active": True,
        }
    )

    departments: dict[str, ObjectId] = {}
    for code, name in [("ED", "Emergency"), ("CARDIO", "Cardiology"), ("GEN-MED", "General Medicine")]:
        department_id = ObjectId()
        await database[Collections.DEPARTMENTS].insert_one(
            {
                "_id": department_id, "hospital_id": hospital_id, "code": code,
                "name": name, "floor": 1, "bed_count": 0, "hvac_zone": "ward",
                "is_active": True,
            }
        )
        departments[code] = department_id

    room_id = ObjectId()
    await database[Collections.ROOMS].insert_one(
        {
            "_id": room_id, "hospital_id": hospital_id, "department_id": departments["ED"],
            "room_number": "ED-R001", "type": "emergency", "capacity": 4, "floor": 0,
            "coordinates": {"x": 0.2, "y": 0.3}, "equipment_ids": [],
        }
    )

    beds = []
    counter = 0
    for bed_type, department_code, count in BED_PLAN:
        for _ in range(count):
            counter += 1
            beds.append(
                {
                    "_id": ObjectId(), "hospital_id": hospital_id,
                    "department_id": departments[department_code], "room_id": room_id,
                    "bed_number": f"{department_code}-{counter:03d}", "type": bed_type,
                    "status": "available", "current_admission_id": None,
                    "reserved_until": None,
                    "features": ["monitor", "oxygen"] if bed_type in ("icu", "hdu") else ["oxygen"],
                    "occupancy_history": [],
                }
            )

    # A bed under maintenance. No code path may ever assign it.
    beds.append(
        {
            "_id": ObjectId(), "hospital_id": hospital_id,
            "department_id": departments["CARDIO"], "room_id": room_id,
            "bed_number": "MAINT-999", "type": "icu", "status": "maintenance",
            "current_admission_id": None, "features": ["ventilator"], "occupancy_history": [],
        }
    )
    await database[Collections.BEDS].insert_many(beds)

    password_hash = hash_password(PASSWORD)
    for role, email in [
        ("nurse", "nurse@t.ai"), ("doctor", "doctor@t.ai"),
        ("pharmacist", "pharm@t.ai"), ("admin", "admin@t.ai"),
    ]:
        await database[Collections.USERS].insert_one(
            {
                "_id": ObjectId(), "hospital_id": hospital_id, "email": email,
                "password_hash": password_hash, "full_name": f"Test {role}",
                "role": role, "department_id": None, "preferences": {},
                "failed_login_count": 0, "is_active": True,
            }
        )

    await database[Collections.USERS].insert_one(
        {
            "_id": ObjectId(), "hospital_id": other_hospital_id, "email": "nurse@other.ai",
            "password_hash": password_hash, "full_name": "Other Nurse", "role": "nurse",
            "preferences": {}, "failed_login_count": 0, "is_active": True,
        }
    )

    return {
        "hospital_id": hospital_id,
        "other_hospital_id": other_hospital_id,
        "departments": departments,
    }


@pytest.fixture
async def client(seeded):
    """HTTP client bound to the ASGI app, with the seeded database in place."""
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


async def login(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    """Sign in and return an Authorization header."""
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def nurse(client):
    return await login(client, "nurse@t.ai")


@pytest.fixture
async def doctor(client):
    return await login(client, "doctor@t.ai")


# --------------------------------------------------------------- payloads
CRITICAL_ARRIVAL = {
    "patient": {
        "full_name": "Synthetic Patient 4821", "age": 63, "sex": "male",
        "comorbidities": ["diabetes", "hypertension"],
    },
    "source": "ambulance",
    "chief_complaint": "Central chest pain radiating to left arm, 40 minutes",
    "vitals": {
        "heart_rate": 118, "systolic_bp": 96, "diastolic_bp": 62, "spo2": 92.0,
        "temperature_c": 36.8, "respiratory_rate": 26, "gcs": 15, "pain_score": 8,
    },
    "disease_category": "cardiac",
}

RED_FLAG_ARRIVAL = {
    "patient": {"full_name": "Synthetic Patient 9001", "age": 71, "sex": "female"},
    "chief_complaint": "Collapsed at home, unresponsive",
    "vitals": {
        "heart_rate": 132, "systolic_bp": 78, "diastolic_bp": 44, "spo2": 86.0,
        "temperature_c": 36.1, "respiratory_rate": 34, "gcs": 11, "pain_score": 6,
    },
    "disease_category": "cardiac",
}

MINOR_ARRIVAL = {
    "patient": {"full_name": "Synthetic Patient 7710", "age": 24, "sex": "male"},
    "chief_complaint": "Deep laceration to forearm",
    "vitals": {
        "heart_rate": 76, "systolic_bp": 122, "diastolic_bp": 78, "spo2": 99.0,
        "temperature_c": 36.7, "respiratory_rate": 15, "gcs": 15, "pain_score": 3,
    },
    "disease_category": "trauma",
}
