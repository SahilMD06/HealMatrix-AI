"""Bed Allocation Agent.

Pipeline per docs/04_agent_design.md 2.3: candidate filter -> weighted scoring ->
LOS prediction -> 30-minute reservation. The scoring and hard filters (never a
maintenance or already-reserved bed) already live in ``BedService`` — this agent's
job is to read the Patient Triage Agent's output out of shared state, ask
``BedService`` for a recommendation, attach the operational context (occupancy
headroom, ICU overflow risk) the spec calls for, and emit the messages the rest of
the graph depends on.

This agent produces a *recommendation* only. The actual reserve-then-occupy write
sequence stays owned by ``AdmissionService.handle_arrival`` (it has to: the bed
can't be occupied until the admission document exists to attach it to), exactly as
it is today — the agent slots into that flow rather than replacing its transaction
boundary.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentResult, BaseAgent, emit
from app.agents.state import HealMatrixState, result_of
from app.core.constants import AgentName
from app.core.exceptions import BedUnavailableError, ConflictError, NotFoundError, ValidationError
from app.services.admission_service import AdmissionService
from app.services.bed_service import BedService

# Mean length of stay in days by ESI level. The same table
# ``admission_service.LOS_BY_ESI`` used before this agent existed; kept here too so
# the agent is self-contained, and re-exported so the two never drift apart.
LOS_BY_ESI: dict[int, float] = {1: 6.5, 2: 4.2, 3: 2.8, 4: 1.4, 5: 0.5}

ICU_OVERFLOW_THRESHOLD_PCT = 90.0


class BedAllocationAgent(BaseAgent):
    name = str(AgentName.BED_ALLOCATION)
    version = "1.0.0"

    def __init__(self, bed_service: BedService, admission_service: AdmissionService | None = None) -> None:
        self.bed_service = bed_service
        self.admission_service = admission_service

    async def analyse(self, state: HealMatrixState) -> AgentResult:
        triage = result_of(state, str(AgentName.TRIAGE))
        if triage is None:
            raise RuntimeError("Bed allocation requires a completed triage result in state.")

        esi_level = triage["output"]["esi_level"]
        department_code = triage["output"].get("recommended_department_code")

        occupancy = await self.bed_service.occupancy_summary()
        expected_discharges_24h = (
            await self.admission_service.expected_discharges_within(24)
            if self.admission_service
            else None
        )

        escalation: str | None = None
        if occupancy["icu_occupancy_rate"] >= ICU_OVERFLOW_THRESHOLD_PCT:
            escalation = "icu_overflow_risk"

        try:
            recommendation = await self.bed_service.recommend(esi_level=esi_level)
        except (BedUnavailableError, ConflictError, NotFoundError, ValidationError) as exc:
            # A legitimate business outcome ("we are full"), not an agent failure —
            # handled here rather than propagating to BaseAgent.run()'s fallback,
            # which has nothing more useful to try than the same BedService call.
            rationale = (
                f"No bed could be recommended for ESI {esi_level}: {exc.message} "
                "Patient should be held in the queue pending capacity."
            )
            return AgentResult(
                agent=self.name,
                version=self.version,
                output={
                    "recommended_bed_id": None,
                    "alternatives": [],
                    "predicted_los_days": LOS_BY_ESI.get(esi_level, 2.0),
                    "occupancy_rate": occupancy["occupancy_rate"],
                    "icu_occupancy_rate": occupancy["icu_occupancy_rate"],
                    "expected_discharges_24h": expected_discharges_24h,
                    "escalation": "no_bed_available",
                },
                rationale=rationale,
                confidence=0.4,
                messages=self._messages(occupancy, escalation or "no_bed_available"),
                used_fallback=False,
                status="degraded",
            )

        bed = recommendation["bed"]
        predicted_los = LOS_BY_ESI.get(esi_level, 2.0)
        rationale = (
            f"Recommended {bed['bed_number']} ({bed['type']}) for ESI {esi_level}"
            + (f" in {department_code}" if department_code else "")
            + f", suitability score {recommendation['score']} out of "
            f"{recommendation['candidates_considered']} assignable beds. "
            f"Predicted length of stay {predicted_los} days."
        )
        if escalation:
            rationale += (
                f" ICU occupancy is at {occupancy['icu_occupancy_rate']}%, at or above the "
                f"{ICU_OVERFLOW_THRESHOLD_PCT}% overflow threshold — escalating to the "
                "executive review even though this individual patient was placed."
            )

        output: dict[str, Any] = {
            "recommended_bed_id": bed["id"],
            "bed_number": bed["bed_number"],
            "bed_type": bed["type"],
            "alternatives": [alt["id"] for alt in recommendation["alternatives"]],
            "predicted_los_days": predicted_los,
            "score": recommendation["score"],
            "candidates_considered": recommendation["candidates_considered"],
            "occupancy_rate": occupancy["occupancy_rate"],
            "icu_occupancy_rate": occupancy["icu_occupancy_rate"],
            "expected_discharges_24h": expected_discharges_24h,
            "escalation": escalation,
        }

        return AgentResult(
            agent=self.name,
            version=self.version,
            output=output,
            rationale=rationale,
            confidence=min(0.95, 0.6 + recommendation["score"] * 0.4),
            messages=self._messages(occupancy, escalation),
            used_fallback=False,
            status="success",
        )

    def fallback(self, state: HealMatrixState) -> AgentResult:
        """No deterministic alternative to BedService itself — this only runs if
        BedService raised something unexpected (a real bug, not "no capacity",
        which ``analyse`` already handles as a normal outcome above)."""
        triage = result_of(state, str(AgentName.TRIAGE))
        esi_level = triage["output"]["esi_level"] if triage else None

        return AgentResult(
            agent=self.name,
            version=self.version,
            output={
                "recommended_bed_id": None,
                "alternatives": [],
                "predicted_los_days": LOS_BY_ESI.get(esi_level, 2.0) if esi_level else None,
                "occupancy_rate": None,
                "expected_discharges_24h": None,
                "escalation": "agent_error",
            },
            rationale=(
                "Bed allocation could not complete: the bed service raised an unexpected "
                "error. Patient should be held for manual bed assignment."
            ),
            confidence=0.2,
            messages=[],
            used_fallback=True,
            status="success",
        )

    def _messages(self, occupancy: dict, escalation: str | None) -> list:
        messages = [
            emit(
                self.name,
                "census_update",
                {"occupancy_rate": occupancy["occupancy_rate"]},
                to_agent=str(AgentName.CARBON),
            ),
        ]
        if escalation:
            messages.append(
                emit(
                    self.name,
                    "capacity_risk",
                    {"escalation": escalation, "icu_occupancy_rate": occupancy["icu_occupancy_rate"]},
                    to_agent=str(AgentName.EXECUTIVE),
                )
            )
        return messages
