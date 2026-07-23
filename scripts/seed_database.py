#!/usr/bin/env python3
"""Seed the HealMatrix database with a coherent synthetic hospital network.

Creates 4 hospitals, their departments, rooms and beds, 6 demo user accounts per
hospital (one per role), a medicine catalogue with inventory batches, an ambulance
fleet, and optionally backfills months of energy, water, waste and admission history
for model training.

Usage
-----
    # Local checkout
    python scripts/seed_database.py                 # seed if empty
    python scripts/seed_database.py --force         # wipe and reseed
    python scripts/seed_database.py --history-days 180

    # Inside Docker Compose
    docker compose exec backend python /scripts/seed_database.py --force
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _locate_backend() -> Path:
    """Find the backend package.

    The script runs from two different layouts: a local checkout, where the backend
    is a sibling directory, and the Docker image, where ``scripts/`` is mounted at
    ``/scripts`` and the application lives at ``/app``.
    """
    candidates = [
        Path(__file__).resolve().parents[1] / "backend",
        Path("/app"),
        Path(__file__).resolve().parents[1],
    ]
    for candidate in candidates:
        if (candidate / "app" / "__init__.py").is_file():
            return candidate

    raise SystemExit(
        "Could not locate the backend package. Run this from the repository root, "
        "or inside the backend container."
    )


sys.path.insert(0, str(_locate_backend()))

from app.core.security import hash_password  # noqa: E402
from app.database.indexes import create_indexes  # noqa: E402
from app.database.mongodb import (  # noqa: E402
    Collections,
    close_mongo_connection,
    connect_to_mongo,
    get_database,
)
from app.simulator.generators import (  # noqa: E402
    HospitalSimulator,
    SimulationConfig,
)

# --------------------------------------------------------------------- data
HOSPITALS = [
    {
        "code": "HM-BLR-01", "name": "HealMatrix Central Hospital", "type": "tertiary",
        "coords": [77.5946, 12.9716], "city": "Bengaluru", "pincode": "560001",
        "beds": 400, "icu": 48, "emergency": 30, "ot": 8,
        "capabilities": ["cardiac", "trauma", "neonatal", "stroke", "dialysis", "burns"],
        "roof": 4200.0, "solar": 120.0, "grid_factor": 0.71,
    },
    {
        "code": "HM-BLR-02", "name": "HealMatrix North Community Hospital", "type": "secondary",
        "coords": [77.5806, 13.0350], "city": "Bengaluru", "pincode": "560024",
        "beds": 220, "icu": 20, "emergency": 16, "ot": 4,
        "capabilities": ["trauma", "dialysis", "neonatal"],
        "roof": 2400.0, "solar": 60.0, "grid_factor": 0.71,
    },
    {
        "code": "HM-BLR-03", "name": "HealMatrix East Speciality Centre", "type": "specialty",
        "coords": [77.6650, 12.9850], "city": "Bengaluru", "pincode": "560037",
        "beds": 160, "icu": 24, "emergency": 12, "ot": 5,
        "capabilities": ["cardiac", "stroke", "dialysis"],
        "roof": 1900.0, "solar": 85.0, "grid_factor": 0.71,
    },
    {
        "code": "HM-BLR-04", "name": "HealMatrix South Primary Centre", "type": "primary",
        "coords": [77.5850, 12.9100], "city": "Bengaluru", "pincode": "560076",
        "beds": 90, "icu": 6, "emergency": 8, "ot": 2,
        "capabilities": ["dialysis"],
        "roof": 1200.0, "solar": 30.0, "grid_factor": 0.71,
    },
]

DEPARTMENTS = [
    ("ED", "Emergency Department", 0, "opd", 0.18),
    ("ICU", "Intensive Care Unit", 3, "icu", 0.12),
    ("GEN-MED", "General Medicine", 1, "ward", 0.22),
    ("CARDIO", "Cardiology", 2, "icu", 0.12),
    ("ORTHO", "Orthopaedics", 2, "ward", 0.10),
    ("PULMO", "Pulmonology", 1, "ward", 0.08),
    ("NEURO", "Neurology", 3, "ward", 0.08),
    ("OBG", "Obstetrics and Gynaecology", 4, "ward", 0.10),
]

BED_TYPE_BY_DEPARTMENT = {
    "ED": "emergency", "ICU": "icu", "CARDIO": "hdu", "NEURO": "hdu",
    "OBG": "maternity", "GEN-MED": "general", "ORTHO": "general", "PULMO": "general",
}

BED_FEATURES = {
    "icu": ["ventilator", "monitor", "oxygen", "infusion_pump"],
    "hdu": ["monitor", "oxygen", "infusion_pump"],
    "emergency": ["monitor", "oxygen"],
    "maternity": ["monitor", "oxygen"],
    "general": ["oxygen"],
}

DEMO_USERS = [
    ("admin", "Admin", "Priya Raghavan"),
    ("doctor", "Doctor", "Dr Arjun Menon"),
    ("nurse", "Nurse", "Sister Lakshmi Nair"),
    ("pharmacist", "Pharmacist", "Vikram Shetty"),
    ("manager", "Manager", "Neha Kulkarni"),
    ("sustainability_officer", "Sustainability", "Kabir Desai"),
]

MEDICINES = [
    ("MED-0001", "Amoxicillin 500mg", "Amoxicillin", "antibiotic", "capsule", 850, True, False),
    ("MED-0002", "Paracetamol 650mg", "Paracetamol", "analgesic", "tablet", 180, True, False),
    ("MED-0003", "Adrenaline 1mg/ml", "Epinephrine", "emergency", "injection", 4200, True, False),
    ("MED-0004", "Atorvastatin 20mg", "Atorvastatin", "cardiac", "tablet", 640, False, False),
    ("MED-0005", "Insulin Glargine 100IU", "Insulin Glargine", "other", "injection", 28500, True, True),
    ("MED-0006", "Normal Saline 500ml", "Sodium Chloride 0.9%", "iv_fluid", "iv", 3200, True, False),
    ("MED-0007", "Ceftriaxone 1g", "Ceftriaxone", "antibiotic", "injection", 5600, True, False),
    ("MED-0008", "Propofol 200mg", "Propofol", "anaesthetic", "injection", 18900, True, False),
    ("MED-0009", "Salbutamol Inhaler", "Salbutamol", "other", "inhaler", 12400, False, False),
    ("MED-0010", "Heparin 5000IU", "Heparin Sodium", "cardiac", "injection", 9800, True, True),
    ("MED-0011", "Ibuprofen 400mg", "Ibuprofen", "analgesic", "tablet", 220, False, False),
    ("MED-0012", "Metformin 500mg", "Metformin", "other", "tablet", 310, False, False),
    ("MED-0013", "Azithromycin 500mg", "Azithromycin", "antibiotic", "tablet", 1650, False, False),
    ("MED-0014", "Ringer Lactate 500ml", "Compound Sodium Lactate", "iv_fluid", "iv", 3600, True, False),
    ("MED-0015", "Tetanus Toxoid", "Tetanus Vaccine", "vaccine", "injection", 4800, True, True),
    ("MED-0016", "Morphine 10mg", "Morphine Sulphate", "analgesic", "injection", 7200, True, False),
    ("MED-0017", "Furosemide 40mg", "Furosemide", "cardiac", "tablet", 290, False, False),
    ("MED-0018", "Omeprazole 20mg", "Omeprazole", "other", "capsule", 380, False, False),
]


def now() -> datetime:
    return datetime.now(timezone.utc)


async def wipe(database) -> None:
    for name in Collections.all():
        await database[name].delete_many({})
    print("  cleared all collections")


async def seed_hospitals(database) -> list[dict]:
    documents = []
    for spec in HOSPITALS:
        documents.append(
            {
                "code": spec["code"], "name": spec["name"], "type": spec["type"],
                "location": {"type": "Point", "coordinates": spec["coords"]},
                "address": {
                    "line1": f"{spec['name']} Campus", "city": spec["city"],
                    "state": "Karnataka", "pincode": spec["pincode"],
                },
                "capacity": {
                    "total_beds": spec["beds"], "icu_beds": spec["icu"],
                    "emergency_beds": spec["emergency"], "ot_count": spec["ot"],
                },
                "capabilities": spec["capabilities"],
                "sustainability": {
                    "roof_area_sqm": spec["roof"], "solar_kwp": spec["solar"],
                    "rainwater_capacity_l": spec["roof"] * 45,
                    "stp_capacity_kld": spec["beds"] * 0.4,
                },
                "grid_emission_factor": spec["grid_factor"],
                "is_active": True, "created_at": now(), "updated_at": now(),
            }
        )
    result = await database[Collections.HOSPITALS].insert_many(documents)
    for document, inserted_id in zip(documents, result.inserted_ids, strict=True):
        document["_id"] = inserted_id
    print(f"  {len(documents)} hospitals")
    return documents


async def seed_departments_rooms_beds(database, hospital: dict, spec: dict) -> int:
    department_documents = []
    for code, name, floor, hvac_zone, _share in DEPARTMENTS:
        department_documents.append(
            {
                "hospital_id": hospital["_id"], "code": code, "name": name,
                "floor": floor, "bed_count": 0, "head_staff_id": None,
                "hvac_zone": hvac_zone,
                "waste_profile": {
                    "yellow": 0.25, "red": 0.18, "white": 0.04,
                    "blue": 0.03, "general": 0.85,
                },
                "is_active": True, "created_at": now(), "updated_at": now(),
            }
        )
    result = await database[Collections.DEPARTMENTS].insert_many(department_documents)
    for document, inserted_id in zip(department_documents, result.inserted_ids, strict=True):
        document["_id"] = inserted_id

    rooms: list[dict] = []
    beds: list[dict] = []
    bed_counter = 0

    for department, (code, _name, floor, _zone, share) in zip(
        department_documents, DEPARTMENTS, strict=True
    ):
        department_beds = max(2, int(spec["beds"] * share))
        bed_type = BED_TYPE_BY_DEPARTMENT[code]
        room_type = {"icu": "icu", "emergency": "emergency"}.get(bed_type, "general")
        beds_per_room = 1 if bed_type in ("icu", "hdu") else 4
        room_count = max(1, department_beds // beds_per_room)

        for room_index in range(room_count):
            room = {
                "hospital_id": hospital["_id"], "department_id": department["_id"],
                "room_number": f"{code}-R{room_index + 1:03d}", "type": room_type,
                "capacity": beds_per_room, "floor": floor,
                "coordinates": {
                    "x": round(random.uniform(0.05, 0.95), 3),
                    "y": round(random.uniform(0.05, 0.95), 3),
                },
                "equipment_ids": [], "created_at": now(), "updated_at": now(),
            }
            rooms.append(room)

        room_result = await database[Collections.ROOMS].insert_many(
            rooms[-room_count:]
        )
        for room, inserted_id in zip(rooms[-room_count:], room_result.inserted_ids, strict=True):
            room["_id"] = inserted_id

        for room in rooms[-room_count:]:
            for _ in range(beds_per_room):
                if bed_counter >= sum(
                    max(2, int(spec["beds"] * s)) for _, _, _, _, s in DEPARTMENTS
                ):
                    break
                bed_counter += 1
                # Roughly 78% occupied at seed time, matching the simulator's baseline.
                roll = random.random()
                status = (
                    "occupied" if roll < 0.72
                    else "available" if roll < 0.92
                    else "cleaning" if roll < 0.97
                    else "maintenance"
                )
                beds.append(
                    {
                        "hospital_id": hospital["_id"],
                        "department_id": department["_id"],
                        "room_id": room["_id"],
                        "bed_number": f"{code}-{bed_counter:03d}",
                        "type": bed_type,
                        # Seeded beds start free; admissions attach later.
                        "status": "available" if status == "occupied" else status,
                        "current_admission_id": None,
                        "reserved_until": None,
                        "features": BED_FEATURES[bed_type],
                        "last_cleaned_at": now(),
                        "occupancy_history": [],
                        "created_at": now(), "updated_at": now(),
                    }
                )

        await database[Collections.DEPARTMENTS].update_one(
            {"_id": department["_id"]}, {"$set": {"bed_count": department_beds}}
        )

    if beds:
        await database[Collections.BEDS].insert_many(beds)
    return len(beds)


async def seed_users(database, hospitals: list[dict]) -> int:
    documents = []
    shared_hash = hash_password("HealMatrix@2026")

    for index, hospital in enumerate(hospitals):
        for role, label, full_name in DEMO_USERS:
            # Demo convention: role@hospitalcode.healmatrix.ai
            suffix = hospital["code"].lower().replace("-", "")
            documents.append(
                {
                    "hospital_id": hospital["_id"],
                    "email": f"{role}@{suffix}.healmatrix.ai",
                    "password_hash": shared_hash,
                    "full_name": f"{full_name}" if index == 0 else f"{full_name} ({label} {index + 1})",
                    "role": role,
                    "department_id": None,
                    "phone": f"+9198{random.randint(10000000, 99999999)}",
                    "avatar_url": None,
                    "preferences": {
                        "theme": "system",
                        "notification_channels": ["in_app"],
                        "default_dashboard": None,
                    },
                    "last_login_at": None, "failed_login_count": 0, "is_active": True,
                    "created_at": now(), "updated_at": now(),
                }
            )

    await database[Collections.USERS].insert_many(documents)
    print(f"  {len(documents)} users (password for all: HealMatrix@2026)")
    return len(documents)


async def seed_medicines(database) -> list[dict]:
    documents = []
    for sku, name, generic, category, form, price, critical, cold in MEDICINES:
        documents.append(
            {
                "sku": sku, "name": name, "generic_name": generic,
                "manufacturer": random.choice(["Cipla", "Sun Pharma", "Dr Reddy's", "Lupin"]),
                "category": category, "form": form, "strength": None,
                "unit_price_paise": price,
                "storage": {
                    "min_temp_c": 2.0 if cold else 15.0,
                    "max_temp_c": 8.0 if cold else 25.0,
                    "cold_chain": cold, "light_sensitive": form == "injection",
                },
                "is_critical": critical,
                "carbon_kg_per_unit": round(random.uniform(0.01, 0.35), 3),
                "is_active": True, "created_at": now(), "updated_at": now(),
            }
        )
    result = await database[Collections.MEDICINES].insert_many(documents)
    for document, inserted_id in zip(documents, result.inserted_ids, strict=True):
        document["_id"] = inserted_id
    print(f"  {len(documents)} medicines")
    return documents


async def seed_inventory(database, hospitals: list[dict], medicines: list[dict]) -> int:
    documents = []
    today = now().date()

    for hospital in hospitals:
        for medicine in medicines:
            for batch_index in range(random.randint(1, 3)):
                # A deliberate spread of expiry horizons so the expiry agent has work to do.
                days_to_expiry = random.choice(
                    [random.randint(5, 25), random.randint(26, 89), random.randint(90, 500)]
                )
                quantity = random.randint(40, 1400)
                reorder = int(quantity * random.uniform(0.15, 0.4))

                documents.append(
                    {
                        "hospital_id": hospital["_id"],
                        "medicine_id": medicine["_id"],
                        "batch_number": f"B{random.randint(10000, 99999)}-{batch_index + 1}",
                        "quantity": quantity,
                        "reserved_quantity": 0,
                        "expiry_date": (today + timedelta(days=days_to_expiry)).isoformat(),
                        "received_date": (today - timedelta(days=random.randint(10, 200))).isoformat(),
                        "unit_cost_paise": medicine["unit_price_paise"],
                        "reorder_point": reorder,
                        "max_stock": quantity * 2,
                        "storage_location": f"Rack-{random.randint(1, 24)}",
                        "status": "active",
                        "transfer_history": [],
                        "created_at": now(), "updated_at": now(),
                    }
                )

    await database[Collections.INVENTORY].insert_many(documents)
    print(f"  {len(documents)} inventory batches")
    return len(documents)


async def seed_ambulances(database, hospitals: list[dict]) -> int:
    documents = []
    for hospital in hospitals:
        base = hospital["location"]["coordinates"]
        for index in range(3):
            documents.append(
                {
                    "hospital_id": hospital["_id"],
                    "vehicle_number": f"KA-01-{hospital['code'][-2:]}-{1000 + index}",
                    "type": random.choice(["bls", "als", "als"]),
                    "status": random.choice(["idle", "idle", "idle", "dispatched", "maintenance"]),
                    "current_location": {
                        "type": "Point",
                        "coordinates": [
                            round(base[0] + random.uniform(-0.05, 0.05), 6),
                            round(base[1] + random.uniform(-0.05, 0.05), 6),
                        ],
                    },
                    "crew": [], "active_call": None,
                    "equipment": ["defibrillator", "oxygen", "stretcher"],
                    "fuel_type": random.choice(["diesel", "diesel", "cng"]),
                    "fuel_efficiency_kmpl": round(random.uniform(6.5, 11.0), 1),
                    "odometer_km": round(random.uniform(12000, 90000), 1),
                    "is_active": True, "created_at": now(), "updated_at": now(),
                }
            )
    await database[Collections.AMBULANCES].insert_many(documents)
    print(f"  {len(documents)} ambulances")
    return len(documents)


async def backfill_history(database, hospitals: list[dict], days: int) -> None:
    """Generate energy, water and waste history for model training."""
    if days <= 0:
        return

    end = now().replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)

    for hospital in hospitals:
        spec = next(h for h in HOSPITALS if h["code"] == hospital["code"])
        simulator = HospitalSimulator(
            SimulationConfig(
                seed=42 + hash(hospital["code"]) % 1000,
                total_beds=spec["beds"],
                icu_beds=spec["icu"],
                roof_area_sqm=spec["roof"],
                solar_kwp=spec["solar"],
            )
        )

        energy_rows: list[dict] = []
        water_rows: list[dict] = []
        waste_rows: list[dict] = []

        # Inject a water leak for one hospital so the anomaly detector has a positive case.
        leak_window = (
            (start + timedelta(days=days // 2), start + timedelta(days=days // 2 + 4))
            if hospital["code"] == "HM-BLR-02"
            else None
        )

        # Fetched once rather than per simulated day — this loop runs thousands of
        # iterations and a query inside it dominated the seed time.
        departments = await database[Collections.DEPARTMENTS].find(
            {"hospital_id": hospital["_id"]}
        ).to_list(length=20)

        moment = start
        seen_days: set = set()

        while moment <= end:
            occupancy = simulator.occupancy_ratio(moment)

            energy = simulator.energy_log(moment, occupancy)
            energy["hospital_id"] = hospital["_id"]
            energy["created_at"] = moment
            energy["updated_at"] = moment
            energy_rows.append(energy)

            leaking = bool(leak_window and leak_window[0] <= moment <= leak_window[1])
            water = simulator.water_log(moment, occupancy, leak_active=leaking)
            water["hospital_id"] = hospital["_id"]
            water["created_at"] = moment
            water["updated_at"] = moment
            water_rows.append(water)

            if moment.date() not in seen_days and departments:
                seen_days.add(moment.date())
                # Waste is attributed per department, so spread the daily records
                # across the roster rather than piling them on one ward.
                for record in simulator.waste_records(moment.date(), occupancy):
                    record["hospital_id"] = hospital["_id"]
                    record["department_id"] = random.choice(departments)["_id"]
                    record["date"] = record["date"].isoformat()
                    record["created_at"] = moment
                    record["updated_at"] = moment
                    waste_rows.append(record)

            moment += timedelta(hours=1)

        if energy_rows:
            await database[Collections.ENERGY_LOGS].insert_many(energy_rows)
        if water_rows:
            await database[Collections.WATER_LOGS].insert_many(water_rows)
        if waste_rows:
            await database[Collections.WASTE_RECORDS].insert_many(waste_rows)

        print(
            f"  {hospital['code']}: {len(energy_rows)} energy, "
            f"{len(water_rows)} water, {len(waste_rows)} waste rows"
        )


async def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the HealMatrix database.")
    parser.add_argument("--force", action="store_true", help="Wipe existing data first.")
    parser.add_argument(
        "--history-days", type=int, default=30,
        help="Days of energy/water/waste history to backfill (0 to skip).",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    args = parser.parse_args()

    random.seed(args.seed)

    await connect_to_mongo()
    database = get_database()

    existing = await database[Collections.HOSPITALS].count_documents({})
    if existing and not args.force:
        print(
            f"Database already contains {existing} hospitals. "
            "Re-run with --force to wipe and reseed."
        )
        await close_mongo_connection()
        return 1

    print("Seeding HealMatrix database")
    if args.force:
        await wipe(database)

    await create_indexes()
    print("  indexes created")

    hospitals = await seed_hospitals(database)

    total_beds = 0
    for hospital in hospitals:
        spec = next(h for h in HOSPITALS if h["code"] == hospital["code"])
        total_beds += await seed_departments_rooms_beds(database, hospital, spec)
    print(f"  {len(hospitals) * len(DEPARTMENTS)} departments, {total_beds} beds")

    await seed_users(database, hospitals)
    medicines = await seed_medicines(database)
    await seed_inventory(database, hospitals, medicines)
    await seed_ambulances(database, hospitals)

    if args.history_days:
        print(f"Backfilling {args.history_days} days of telemetry")
        await backfill_history(database, hospitals, args.history_days)

    print("\nSeed complete.")
    print("Sign in with:  admin@hmblr01.healmatrix.ai  /  HealMatrix@2026")

    await close_mongo_connection()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
