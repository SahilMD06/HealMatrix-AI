"""Patient arrival, admission lifecycle and discharge.

The arrival flow is the platform's spine: it registers the patient, triages them,
allocates a bed and records the reasoning — the vertical slice a demo walks through.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.constants import (
    AdmissionStatus,
    AgentName,
    AgentStatus,
    NotificationType,
    Severity,
    TriggerType,
)
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from app.database.repositories import (
    AdmissionRepository,
    AgentLogRepository,
    BedRepository,
    DepartmentRepository,
    NotificationRepository,
    PatientRepository,
    serialise,
    to_object_id,
)
from app.models.base import utc_now
from app.schemas.clinical import (
    ArrivalRequest,
    ArrivalResponse,
    BedAssignmentResponse,
    TriageResponse,
)
from app.services.bed_service import BedService
from app.services.triage_rules import triage as run_triage_rules

# Imported lazily inside handle_arrival(), not at module load: app.agents.graph.builder
# imports langgraph, and this keeps a core-only install (no requirements-ai.txt)
# capable of importing this whole module — the graph import only happens on the
# code path that actually needs it, and if langgraph itself isn't installed at all
# (core-only deployment), handle_arrival falls back to the rule engine directly,
# exactly as it always has.

logger = get_logger(__name__)

# Mean length of stay in days by ESI level, used until the trained LOS model lands.
LOS_BY_ESI: dict[int, float] = {1: 6.5, 2: 4.2, 3: 2.8, 4: 1.4, 5: 0.5}


class AdmissionService:
    """Owns the arrival-to-discharge lifecycle."""

    def __init__(
        self,
        admissions: AdmissionRepository,
        patients: PatientRepository,
        beds: BedRepository,
        departments: DepartmentRepository,
        agent_logs: AgentLogRepository,
        notifications: NotificationRepository,
    ) -> None:
        self.admissions = admissions
        self.patients = patients
        self.beds = beds
        self.departments = departments
        self.agent_logs = agent_logs
        self.notifications = notifications
        self.bed_service = BedService(beds)

    # ---------------------------------------------------------------- arrival
    async def handle_arrival(self, payload: ArrivalRequest) -> ArrivalResponse:
        """Register, triage, allocate and log. The core demo path."""
        run_id = str(uuid.uuid4())
        started = utc_now()

        patient = await self._resolve_patient(payload)
        admission_number = await self.admissions.next_admission_number(started.year)

        # --- 1. Triage + bed recommendation, via the agent graph when available ---
        # ``_decide_via_graph`` runs the real Patient Triage + Bed Allocation agents
        # (ML model, Gemini rationale, guardrails, per-agent logging) through
        # LangGraph. If ``requirements-ai.txt`` (and therefore langgraph) isn't
        # installed at all — a valid, documented core-only deployment — this raises
        # ImportError and the method below drops to the exact same direct
        # rule-engine + BedService calls this flow always used before Phase 3.
        bed_recommendation: dict[str, Any] | None
        try:
            triage_result, bed_recommendation = await self._decide_via_graph(
                run_id=run_id, payload=payload, patient=patient
            )
        except ImportError:
            triage_started = utc_now()
            triage_result = run_triage_rules(
                vitals=payload.vitals,
                chief_complaint=payload.chief_complaint,
                age=patient["age"],
                comorbidities=patient.get("comorbidities", []),
            )
            await self._log_agent_run(
                run_id=run_id,
                agent=AgentName.TRIAGE,
                duration_ms=self._elapsed_ms(triage_started),
                output=triage_result,
                rationale=triage_result["rationale"],
                confidence=triage_result["confidence"],
                input_summary={
                    "chief_complaint": payload.chief_complaint,
                    "age": patient["age"],
                    "spo2": payload.vitals.spo2,
                    "shock_index": payload.vitals.shock_index,
                },
            )
            bed_recommendation = None  # signals "use the direct BedService call below"

        department = await self.departments.find_by_code(
            triage_result["recommended_department_code"]
        )
        department_id = department["_id"] if department else None

        # --- 2. Persist the admission ---------------------------------------
        admission_document = {
            "patient_id": patient["_id"],
            "admission_number": admission_number,
            "source": str(payload.source),
            "chief_complaint": payload.chief_complaint,
            "vitals": payload.vitals.model_dump(),
            "triage": {
                "esi_level": triage_result["esi_level"],
                "confidence": triage_result["confidence"],
                "recommended_department_id": department_id,
                "recommended_department_code": triage_result["recommended_department_code"],
                "rationale": triage_result["rationale"],
                "red_flags": triage_result["red_flags"],
                "target_response_minutes": triage_result["target_response_minutes"],
                "model_version": triage_result["model_version"],
                "used_fallback": triage_result["used_fallback"],
                "agent_run_id": run_id,
                "decided_at": utc_now(),
            },
            "department_id": department_id,
            "bed_id": None,
            "disease_category": str(payload.disease_category),
            "status": AdmissionStatus.TRIAGED,
            "admitted_at": None,
            "predicted_los_days": LOS_BY_ESI.get(triage_result["esi_level"], 2.0),
            "medicines_administered": [],
        }
        admission = await self.admissions.insert(admission_document)

        # --- 3. Commit the bed recommendation (or run the direct fallback) ----
        bed_response = BedAssignmentResponse()
        escalation: str | None = None
        bed_status = AgentStatus.DEGRADED

        if bed_recommendation is not None:
            # The graph already ran (and logged) the Bed Allocation Agent itself;
            # this only commits — or fails to commit — its recommendation.
            bed_id = bed_recommendation.get("recommended_bed_id")
            if bed_id:
                try:
                    await self.bed_service.assign(bed_id, admission["_id"])
                    await self.admissions.update(
                        admission["_id"],
                        {
                            "bed_id": to_object_id(bed_id),
                            "status": AdmissionStatus.ADMITTED,
                            "admitted_at": utc_now(),
                        },
                    )
                    bed_response = BedAssignmentResponse(
                        bed_id=bed_id,
                        bed_number=bed_recommendation.get("bed_number"),
                        type=bed_recommendation.get("bed_type"),
                        predicted_los_days=bed_recommendation.get(
                            "predicted_los_days", admission_document["predicted_los_days"]
                        ),
                    )
                    bed_status = AgentStatus.SUCCESS
                except (ConflictError, NotFoundError) as exc:
                    # Lost a race against a concurrent request between the agent's
                    # recommendation and this commit — rare, but a real possibility
                    # any time recommend-then-commit isn't a single atomic step.
                    escalation = "bed_taken_by_concurrent_request"
                    bed_response = BedAssignmentResponse(escalation=escalation)
                    logger.warning(
                        "admission.bed_race_lost", admission=admission_number, bed_id=bed_id, error=str(exc)
                    )
            else:
                escalation = bed_recommendation.get("escalation") or "no_bed_available"
                bed_response = BedAssignmentResponse(escalation=escalation)
        else:
            # langgraph not installed this deployment — the original direct path.
            bed_started = utc_now()
            try:
                recommendation = await self.bed_service.recommend(
                    esi_level=triage_result["esi_level"],
                    department_id=department_id,
                )
                bed = recommendation["bed"]
                await self.bed_service.assign(bed["id"], admission["_id"])
                await self.admissions.update(
                    admission["_id"],
                    {
                        "bed_id": to_object_id(bed["id"]),
                        "status": AdmissionStatus.ADMITTED,
                        "admitted_at": utc_now(),
                    },
                )
                bed_response = BedAssignmentResponse(
                    bed_id=bed["id"],
                    bed_number=bed["bed_number"],
                    type=bed["type"],
                    predicted_los_days=admission_document["predicted_los_days"],
                )
                bed_output: dict[str, Any] = {
                    "bed_id": bed["id"],
                    "bed_number": bed["bed_number"],
                    "score": recommendation["score"],
                    "candidates_considered": recommendation["candidates_considered"],
                }
                bed_rationale = (
                    f"Assigned {bed['bed_number']} ({bed['type']}) from "
                    f"{recommendation['candidates_considered']} assignable beds, "
                    f"suitability score {recommendation['score']}."
                )
                bed_status = AgentStatus.SUCCESS
            except (ConflictError, NotFoundError, ValidationError) as exc:
                escalation = "no_bed_available"
                bed_response = BedAssignmentResponse(escalation=escalation)
                bed_output = {"error": exc.code, "message": exc.message}
                bed_rationale = (
                    f"No bed could be assigned: {exc.message} "
                    "Patient held in queue pending capacity."
                )
                bed_status = AgentStatus.DEGRADED
                logger.warning("admission.bed_unavailable", admission=admission_number)

            await self._log_agent_run(
                run_id=run_id,
                agent=AgentName.BED_ALLOCATION,
                duration_ms=self._elapsed_ms(bed_started),
                output=bed_output,
                rationale=bed_rationale,
                confidence=0.9 if bed_status == AgentStatus.SUCCESS else 0.4,
                status=bed_status,
                input_summary={
                    "esi_level": triage_result["esi_level"],
                    "department": triage_result["recommended_department_code"],
                },
            )

        # --- 4. Notify on high acuity ---------------------------------------
        if triage_result["esi_level"] <= 2:
            await self._notify_critical(
                admission_number=admission_number,
                admission_id=admission["_id"],
                esi_level=triage_result["esi_level"],
                department_code=triage_result["recommended_department_code"],
                run_id=run_id,
            )

        logger.info(
            "admission.arrival_processed",
            admission=admission_number,
            esi=triage_result["esi_level"],
            bed=bed_response.bed_number,
            duration_ms=self._elapsed_ms(started),
        )

        return ArrivalResponse(
            admission_id=str(admission["_id"]),
            admission_number=admission_number,
            patient_id=str(patient["_id"]),
            mrn=patient["mrn"],
            status=AdmissionStatus.ADMITTED if bed_response.bed_id else AdmissionStatus.TRIAGED,
            triage=TriageResponse(
                esi_level=triage_result["esi_level"],
                confidence=triage_result["confidence"],
                recommended_department_code=triage_result["recommended_department_code"],
                target_response_minutes=triage_result["target_response_minutes"],
                red_flags=triage_result["red_flags"],
                rationale=triage_result["rationale"],
                model_version=triage_result["model_version"],
                used_fallback=triage_result["used_fallback"],
            ),
            bed=bed_response,
            agent_run_id=run_id,
            degraded=bed_status == AgentStatus.DEGRADED,
        )

    # -------------------------------------------------------------- lifecycle
    async def set_status(self, admission_id: str, status: str, notes: str | None = None) -> dict:
        admission = await self.admissions.find_by_id(admission_id)
        if admission is None:
            raise NotFoundError("Admission not found.", details={"id": admission_id})

        if admission["status"] in {AdmissionStatus.DISCHARGED, AdmissionStatus.DECEASED}:
            raise ConflictError("This admission is already closed and cannot be reopened.")

        patch: dict[str, Any] = {"status": status}
        if notes:
            patch["notes"] = notes

        updated = await self.admissions.update(admission_id, patch)
        return serialise(updated)

    async def discharge(self, admission_id: str, outcome: str, notes: str | None = None) -> dict:
        """Close the admission, free the bed and record the realised length of stay."""
        admission = await self.admissions.find_by_id(admission_id)
        if admission is None:
            raise NotFoundError("Admission not found.", details={"id": admission_id})

        if admission["status"] == AdmissionStatus.DISCHARGED:
            raise ConflictError("This patient has already been discharged.")

        discharged_at = utc_now()
        admitted_at = admission.get("admitted_at") or admission.get("created_at")
        actual_los = None
        if admitted_at:
            if admitted_at.tzinfo is None:
                admitted_at = admitted_at.replace(tzinfo=timezone.utc)
            actual_los = round((discharged_at - admitted_at).total_seconds() / 86400, 3)

        patch: dict[str, Any] = {
            "status": AdmissionStatus.DISCHARGED,
            "discharged_at": discharged_at,
            "outcome": outcome,
            "actual_los_days": actual_los,
        }
        if notes:
            patch["notes"] = notes

        updated = await self.admissions.update(admission_id, patch)

        if admission.get("bed_id"):
            await self.bed_service.release(str(admission["bed_id"]))

        logger.info(
            "admission.discharged",
            admission=admission["admission_number"],
            los_days=actual_los,
            outcome=outcome,
        )
        return serialise(updated)

    async def expected_discharges_within(self, hours: int = 24) -> int:
        """Thin pass-through so agents call the service layer, never the repository directly."""
        return await self.admissions.expected_discharges_within(hours=hours)

    async def recent_daily_admission_counts(self, days: int = 90) -> list[float]:
        """Fixed-length daily totals, oldest first, ending yesterday. Zero-fills gap days
        so the Disease Forecast Agent's lag window is never shorter than requested just
        because a quiet day produced no Mongo rows to aggregate."""
        since = utc_now() - timedelta(days=days)
        rows = await self.admissions.daily_totals(since)
        by_date = {row["date"]: row["count"] for row in rows}

        today = utc_now().date()
        counts: list[float] = []
        for offset in range(days, 0, -1):
            day = today - timedelta(days=offset)
            counts.append(float(by_date.get(day.isoformat(), 0)))
        return counts

    async def queue(self, limit: int = 100) -> list[dict]:
        """Live triage queue enriched with patient names and waiting time."""
        rows = await self.admissions.active_queue(limit=limit)
        now = utc_now()
        enriched: list[dict] = []

        for row in rows:
            patient = await self.patients.find_by_id(row["patient_id"])
            created = row.get("created_at")
            if created and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            waiting = int((now - created).total_seconds() // 60) if created else None

            data = serialise(row) or {}
            data["patient_name"] = patient["full_name"] if patient else None
            data["patient_age"] = patient["age"] if patient else None
            data["waiting_minutes"] = waiting
            enriched.append(data)

        return enriched

    # ------------------------------------------------------------- agent graph
    async def _decide_via_graph(
        self, run_id: str, payload: ArrivalRequest, patient: dict
    ) -> tuple[dict, dict | None]:
        """Run the ``patient_arrival`` branch of the LangGraph orchestration.

        Returns ``(triage_output, bed_allocation_output)`` — both are the agents'
        own output dicts (already logged to ``agent_logs`` by the graph's node
        wrapper), in the same shape the pre-Phase-3 direct calls produced, so
        nothing downstream in ``handle_arrival`` needs to know which path ran.

        Raises ``ImportError`` if langgraph isn't installed (core-only deployment,
        no ``requirements-ai.txt``) — the caller is expected to catch that and use
        the direct rule-engine + BedService calls instead.
        """
        from app.agents.graph.builder import build_graph
        from app.agents.graph.dependencies import AgentDependencies

        deps = AgentDependencies(
            bed_service=self.bed_service,
            admission_service=self,
            inventory_service=None,
            sustainability_service=None,
            hospital_repo=None,
            ambulance_repo=None,
            agent_logs=self.agent_logs,
        )
        graph = build_graph(deps)

        final_state = await graph.ainvoke(
            {
                "run_id": run_id,
                "hospital_id": str(self.beds.hospital_id),
                "trigger": str(TriggerType.PATIENT_ARRIVAL),
                "correlation_id": run_id,
                "vitals": payload.vitals.model_dump(),
                "age": patient["age"],
                "patient": {"sex": patient.get("sex", "unknown")},
                "comorbidities": patient.get("comorbidities", []),
                "chief_complaint": payload.chief_complaint,
                "results": {},
                "messages": [],
                "errors": [],
            }
        )

        triage_output = final_state["results"]["patient_triage"]["output"]
        bed_output = final_state["results"]["bed_allocation"]["output"]
        return triage_output, bed_output

    # ----------------------------------------------------------------- helpers
    async def _resolve_patient(self, payload: ArrivalRequest) -> dict:
        """Find the existing patient or register a new one inline."""
        if payload.patient_id:
            patient = await self.patients.find_by_id(payload.patient_id)
            if patient is None:
                raise NotFoundError(
                    "Patient not found.", details={"patient_id": payload.patient_id}
                )
            return patient

        if payload.patient is None:
            raise ValidationError("Provide either patient_id or an inline patient object.")

        mrn = await self.patients.next_mrn()
        return await self.patients.insert(
            {
                "mrn": mrn,
                "full_name": payload.patient.full_name,
                "age": payload.patient.age,
                "sex": payload.patient.sex,
                "blood_group": payload.patient.blood_group,
                "contact": {"phone": payload.patient.phone} if payload.patient.phone else None,
                "comorbidities": payload.patient.comorbidities,
                "allergies": payload.patient.allergies,
                "is_synthetic": True,
            }
        )

    async def _log_agent_run(
        self,
        run_id: str,
        agent: str,
        duration_ms: int,
        output: dict,
        rationale: str,
        confidence: float,
        input_summary: dict,
        status: str = AgentStatus.SUCCESS,
    ) -> None:
        await self.agent_logs.insert(
            {
                "run_id": run_id,
                "agent_name": str(agent),
                "agent_version": "1.0.0",
                "triggered_by": TriggerType.PATIENT_ARRIVAL,
                "input_summary": input_summary,
                "output": output,
                "rationale": rationale,
                "confidence": confidence,
                "messages_emitted": [],
                "used_fallback": True,
                "llm": None,
                "duration_ms": duration_ms,
                "status": str(status),
                "error": None,
            }
        )

    async def _notify_critical(
        self,
        admission_number: str,
        admission_id: Any,
        esi_level: int,
        department_code: str,
        run_id: str,
    ) -> None:
        await self.notifications.insert(
            {
                "type": NotificationType.EMERGENCY_ALERT,
                "severity": Severity.CRITICAL if esi_level == 1 else Severity.WARNING,
                "title": f"ESI {esi_level} arrival — {department_code}",
                "message": (
                    f"Admission {admission_number} triaged at ESI {esi_level}. "
                    f"Immediate clinician review required in {department_code}."
                ),
                "target_roles": ["doctor", "nurse", "manager"],
                "target_user_ids": [],
                "entity_ref": {"collection": "admissions", "id": admission_id},
                "source_agent": str(AgentName.TRIAGE),
                "agent_run_id": run_id,
                "action_url": f"/admissions/{admission_id}",
                "read_by": [],
                "expires_at": None,
            }
        )

    @staticmethod
    def _elapsed_ms(since: datetime) -> int:
        return int((utc_now() - since).total_seconds() * 1000)
