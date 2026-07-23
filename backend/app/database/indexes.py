"""Index definitions and idempotent bootstrap.

``create_index`` is idempotent in MongoDB, so this module is safe to run on every
application start. Index ordering follows the ESR rule (Equality, Sort, Range) and
every operational index leads with ``hospital_id`` to support tenant partitioning.
"""

from __future__ import annotations

from pymongo import ASCENDING, DESCENDING, GEOSPHERE, TEXT, IndexModel

from app.core.logging_config import get_logger
from app.database.mongodb import Collections, get_database

logger = get_logger(__name__)

SIX_MONTHS_SECONDS = 60 * 60 * 24 * 180

INDEX_DEFINITIONS: dict[str, list[IndexModel]] = {
    Collections.HOSPITALS: [
        IndexModel([("code", ASCENDING)], unique=True, name="uq_hospital_code"),
        IndexModel([("location", GEOSPHERE)], name="geo_hospital_location"),
        IndexModel(
            [("capabilities", ASCENDING), ("is_active", ASCENDING)],
            name="ix_capabilities_active",
        ),
    ],
    Collections.USERS: [
        IndexModel([("email", ASCENDING)], unique=True, name="uq_user_email"),
        IndexModel([("hospital_id", ASCENDING), ("role", ASCENDING)], name="ix_hosp_role"),
        IndexModel(
            [("hospital_id", ASCENDING), ("is_active", ASCENDING)], name="ix_hosp_active"
        ),
    ],
    Collections.STAFF: [
        IndexModel(
            [("hospital_id", ASCENDING), ("employee_code", ASCENDING)],
            unique=True,
            name="uq_employee_code",
        ),
        IndexModel(
            [
                ("hospital_id", ASCENDING),
                ("department_id", ASCENDING),
                ("on_duty", ASCENDING),
            ],
            name="ix_dept_onduty",
        ),
    ],
    Collections.DEPARTMENTS: [
        IndexModel(
            [("hospital_id", ASCENDING), ("code", ASCENDING)],
            unique=True,
            name="uq_department_code",
        ),
    ],
    Collections.ROOMS: [
        IndexModel(
            [("hospital_id", ASCENDING), ("room_number", ASCENDING)],
            unique=True,
            name="uq_room_number",
        ),
        IndexModel([("hospital_id", ASCENDING), ("type", ASCENDING)], name="ix_room_type"),
    ],
    Collections.BEDS: [
        IndexModel(
            [("hospital_id", ASCENDING), ("bed_number", ASCENDING)],
            unique=True,
            name="uq_bed_number",
        ),
        IndexModel(
            [("hospital_id", ASCENDING), ("status", ASCENDING), ("type", ASCENDING)],
            name="ix_bed_status_type",
        ),
        IndexModel(
            [
                ("hospital_id", ASCENDING),
                ("department_id", ASCENDING),
                ("status", ASCENDING),
            ],
            name="ix_bed_dept_status",
        ),
        IndexModel(
            [("current_admission_id", ASCENDING)], sparse=True, name="ix_bed_admission"
        ),
    ],
    Collections.PATIENTS: [
        IndexModel(
            [("hospital_id", ASCENDING), ("mrn", ASCENDING)], unique=True, name="uq_mrn"
        ),
        IndexModel([("full_name", TEXT)], name="txt_patient_name"),
    ],
    Collections.ADMISSIONS: [
        IndexModel([("admission_number", ASCENDING)], unique=True, name="uq_admission_number"),
        IndexModel(
            [
                ("hospital_id", ASCENDING),
                ("status", ASCENDING),
                ("admitted_at", DESCENDING),
            ],
            name="ix_adm_status_time",
        ),
        IndexModel(
            [("patient_id", ASCENDING), ("admitted_at", DESCENDING)], name="ix_adm_patient"
        ),
        IndexModel(
            [
                ("hospital_id", ASCENDING),
                ("department_id", ASCENDING),
                ("status", ASCENDING),
            ],
            name="ix_adm_dept_status",
        ),
        IndexModel(
            [
                ("hospital_id", ASCENDING),
                ("disease_category", ASCENDING),
                ("admitted_at", DESCENDING),
            ],
            name="ix_adm_disease_time",
        ),
        IndexModel(
            [
                ("hospital_id", ASCENDING),
                ("triage.esi_level", ASCENDING),
                ("status", ASCENDING),
            ],
            name="ix_adm_esi_status",
        ),
    ],
    Collections.AMBULANCES: [
        IndexModel([("vehicle_number", ASCENDING)], unique=True, name="uq_vehicle_number"),
        IndexModel([("current_location", GEOSPHERE)], name="geo_ambulance_location"),
        IndexModel([("hospital_id", ASCENDING), ("status", ASCENDING)], name="ix_amb_status"),
        IndexModel(
            [("active_call.priority", DESCENDING)], sparse=True, name="ix_amb_priority"
        ),
    ],
    Collections.MEDICINES: [
        IndexModel([("sku", ASCENDING)], unique=True, name="uq_sku"),
        IndexModel([("category", ASCENDING)], name="ix_med_category"),
        IndexModel([("name", TEXT), ("generic_name", TEXT)], name="txt_medicine"),
    ],
    Collections.INVENTORY: [
        IndexModel(
            [
                ("hospital_id", ASCENDING),
                ("medicine_id", ASCENDING),
                ("expiry_date", ASCENDING),
            ],
            name="ix_inv_med_expiry",
        ),
        IndexModel(
            [
                ("hospital_id", ASCENDING),
                ("expiry_date", ASCENDING),
                ("status", ASCENDING),
            ],
            name="ix_inv_expiry_status",
        ),
        IndexModel(
            [("hospital_id", ASCENDING), ("quantity", ASCENDING)], name="ix_inv_quantity"
        ),
        IndexModel(
            [("medicine_id", ASCENDING), ("expiry_date", ASCENDING)],
            name="ix_inv_network_transfer",
        ),
    ],
    Collections.ENERGY_LOGS: [
        IndexModel(
            [("hospital_id", ASCENDING), ("timestamp", DESCENDING)], name="ix_energy_time"
        ),
        IndexModel(
            [("hospital_id", ASCENDING), ("zone", ASCENDING), ("timestamp", DESCENDING)],
            name="ix_energy_zone_time",
        ),
    ],
    Collections.WATER_LOGS: [
        IndexModel(
            [("hospital_id", ASCENDING), ("timestamp", DESCENDING)], name="ix_water_time"
        ),
        IndexModel(
            [("hospital_id", ASCENDING), ("leak_probability", DESCENDING)],
            name="ix_water_leak",
        ),
    ],
    Collections.WASTE_RECORDS: [
        IndexModel(
            [("hospital_id", ASCENDING), ("date", DESCENDING), ("category", ASCENDING)],
            name="ix_waste_date_cat",
        ),
        IndexModel(
            [("hospital_id", ASCENDING), ("pickup.status", ASCENDING)], name="ix_waste_pickup"
        ),
        IndexModel(
            [
                ("hospital_id", ASCENDING),
                ("department_id", ASCENDING),
                ("date", DESCENDING),
            ],
            name="ix_waste_dept_date",
        ),
    ],
    Collections.CARBON_REPORTS: [
        IndexModel(
            [("hospital_id", ASCENDING), ("period.end", DESCENDING)], name="ix_carbon_period"
        ),
        IndexModel(
            [("hospital_id", ASCENDING), ("sustainability_score.overall", DESCENDING)],
            name="ix_carbon_score",
        ),
    ],
    Collections.AGENT_LOGS: [
        IndexModel(
            [("hospital_id", ASCENDING), ("created_at", DESCENDING)], name="ix_agentlog_time"
        ),
        IndexModel([("run_id", ASCENDING)], name="ix_agentlog_run"),
        IndexModel(
            [("agent_name", ASCENDING), ("created_at", DESCENDING)], name="ix_agentlog_agent"
        ),
        IndexModel(
            [
                ("hospital_id", ASCENDING),
                ("status", ASCENDING),
                ("created_at", DESCENDING),
            ],
            name="ix_agentlog_status",
        ),
    ],
    Collections.SIMULATION_DATA: [
        IndexModel([("hospital_id", ASCENDING), ("tick", DESCENDING)], name="ix_sim_tick"),
        IndexModel([("stream", ASCENDING), ("created_at", DESCENDING)], name="ix_sim_stream"),
        IndexModel(
            [("created_at", ASCENDING)],
            expireAfterSeconds=SIX_MONTHS_SECONDS,
            name="ttl_sim_data",
        ),
    ],
    Collections.KNOWLEDGE_BASE: [
        IndexModel([("chunk_id", ASCENDING)], unique=True, name="uq_chunk_id"),
        IndexModel([("category", ASCENDING)], name="ix_kb_category"),
        IndexModel([("faiss_index_position", ASCENDING)], name="ix_kb_position"),
        IndexModel([("content", TEXT)], name="txt_kb_content"),
    ],
    Collections.NOTIFICATIONS: [
        IndexModel(
            [("hospital_id", ASCENDING), ("created_at", DESCENDING)], name="ix_notif_time"
        ),
        IndexModel(
            [
                ("hospital_id", ASCENDING),
                ("target_roles", ASCENDING),
                ("severity", ASCENDING),
            ],
            name="ix_notif_role_sev",
        ),
        IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl_notifications"),
    ],
    Collections.REPORTS: [
        IndexModel(
            [
                ("hospital_id", ASCENDING),
                ("type", ASCENDING),
                ("period.end", DESCENDING),
            ],
            name="ix_report_type_period",
        ),
        IndexModel([("status", ASCENDING)], name="ix_report_status"),
        IndexModel([("celery_task_id", ASCENDING)], sparse=True, name="ix_report_task"),
    ],
    Collections.AUDIT_LOGS: [
        IndexModel(
            [("hospital_id", ASCENDING), ("created_at", DESCENDING)], name="ix_audit_time"
        ),
        IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="ix_audit_user"),
        IndexModel(
            [("resource.collection", ASCENDING), ("resource.id", ASCENDING)],
            name="ix_audit_resource",
        ),
    ],
}


async def create_indexes() -> dict[str, int]:
    """Create every declared index. Returns a map of collection -> index count."""
    database = get_database()
    created: dict[str, int] = {}

    for collection_name, models in INDEX_DEFINITIONS.items():
        try:
            await database[collection_name].create_indexes(models)
            created[collection_name] = len(models)
        except Exception as exc:  # noqa: BLE001 - startup must not hard-fail on one index
            logger.warning(
                "index.creation_failed", collection=collection_name, error=str(exc)
            )
            created[collection_name] = 0

    total = sum(created.values())
    logger.info("index.bootstrap_complete", collections=len(created), indexes=total)
    return created
