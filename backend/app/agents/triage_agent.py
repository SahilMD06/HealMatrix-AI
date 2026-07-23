"""Patient Triage Agent.

Pipeline per docs/04_agent_design.md 2.1: red-flag rule pass -> XGBoost triage_esi ->
Gemini rationale -> department mapping. The red-flag pass runs unconditionally and
its verdict is final — neither the model nor the LLM can move a red-flagged patient
off ESI 1, which is why ``red_flags`` is computed before anything else below and
``esi_level`` is set to ``1`` directly rather than passed through any scoring step.

Three distinct degrade paths exist here, and they mean different things:
  - Gemini unavailable/fails: the ESI decision still comes from the trained model;
    only the human-readable rationale text falls back to a deterministic template.
    ``used_fallback`` stays ``False`` — the decision pipeline was not degraded.
  - ML model not trained: ``analyse()`` raises, and ``BaseAgent.run()`` drops to
    ``fallback()``, which is the pure rule engine this whole agent sits on top of.
    ``used_fallback`` is ``True`` here.
  - Red flags present: neither model is consulted for the ESI level at all — the
    guardrail is unconditional, by design.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import AgentResult, BaseAgent, emit
from app.agents.llm import llm_ready, structured_call
from app.agents.state import HealMatrixState
from app.core.config import settings
from app.core.constants import AgentName, TRIAGE_LABELS, TRIAGE_TARGET_MINUTES
from app.core.exceptions import ModelNotAvailableError
from app.ml import inference
from app.models.clinical import Vitals
from app.services.triage_rules import (
    build_rationale as rule_engine_rationale,
    detect_red_flags,
    score_severity,
    suggest_department,
    triage as rule_engine_triage,
)


class _TriageRationale(BaseModel):
    rationale: str = Field(
        description=(
            "2-4 sentence clinician-readable explanation of why this ESI level fits, "
            "referencing the specific vitals or history that drove it. Plain prose, "
            "no headers, no markdown, no bullet points."
        )
    )


def _ml_rationale_text(
    vitals: Vitals, esi_level: int, confidence: float, age: int
) -> str:
    """Deterministic explanation of an ML-derived ESI level.

    Used whenever Gemini is unavailable or its structured response fails validation
    twice — the rationale field must never be empty just because the LLM step
    couldn't complete.
    """
    observations: list[str] = []
    if vitals.spo2 < 95:
        observations.append(f"SpO2 {vitals.spo2}%")
    if vitals.shock_index >= 0.8:
        observations.append(f"elevated shock index ({vitals.shock_index})")
    if vitals.respiratory_rate > 24:
        observations.append(f"respiratory rate {vitals.respiratory_rate}/min")
    if vitals.temperature_c >= 38.5:
        observations.append(f"temperature {vitals.temperature_c}°C")
    if vitals.pain_score >= 5:
        observations.append(f"pain score {vitals.pain_score}/10")
    if age >= 65:
        observations.append(f"age {age}")

    summary = ", ".join(observations) if observations else "vital signs within expected ranges"
    return (
        f"XGBoost triage model assigned ESI {esi_level} ({TRIAGE_LABELS[esi_level]}) with "
        f"{round(confidence * 100)}% confidence. Contributing observations: {summary}. "
        f"Target clinician contact within {TRIAGE_TARGET_MINUTES[esi_level]} minutes."
    )


class PatientTriageAgent(BaseAgent):
    name = str(AgentName.TRIAGE)
    version = "1.0.0"

    async def analyse(self, state: HealMatrixState) -> AgentResult:
        vitals = Vitals(**state["vitals"])
        age = int(state["age"])
        sex = state.get("patient", {}).get("sex", "unknown")
        comorbidities = state.get("comorbidities", [])
        chief_complaint = state["chief_complaint"]

        red_flags = detect_red_flags(vitals)

        if not inference.triage_model_available():
            raise ModelNotAvailableError(
                "Triage ML model artifact not found; dropping to rule engine."
            )

        prediction = inference.predict_esi(
            vitals=vitals,
            age=age,
            sex=sex,
            comorbidity_count=len(comorbidities),
            chief_complaint=chief_complaint,
        )

        # Guardrail: red flags override the model unconditionally.
        esi_level = 1 if red_flags else prediction["esi_level"]
        confidence = 0.99 if red_flags else prediction["confidence"]
        department_code = suggest_department(chief_complaint, esi_level)

        rationale: str | None = None
        llm_model_used: str | None = None

        if red_flags:
            # The rule engine's own wording is exactly right here: it is describing
            # a protocol override, not a model prediction.
            score = score_severity(vitals, age, len(comorbidities))
            rationale = rule_engine_rationale(vitals, esi_level, red_flags, score, age)
        elif llm_ready():
            try:
                structured = await structured_call(
                    system_prompt=(
                        "You are a clinical triage explainer inside a hospital operations "
                        "system. You are given a patient's vitals and an ESI level a trained "
                        "model has already decided. Explain briefly why that level fits the "
                        "presentation. Do not change the ESI level, do not invent vitals or "
                        "history not given to you, and do not recommend treatment."
                    ),
                    user_prompt=(
                        f"Decided ESI level: {esi_level} ({TRIAGE_LABELS[esi_level]}).\n"
                        f"Model confidence: {confidence}.\n"
                        f"Vitals: heart rate {vitals.heart_rate} bpm, BP "
                        f"{vitals.systolic_bp}/{vitals.diastolic_bp} mmHg, SpO2 {vitals.spo2}%, "
                        f"temperature {vitals.temperature_c}°C, respiratory rate "
                        f"{vitals.respiratory_rate}/min, GCS {vitals.gcs}, pain "
                        f"{vitals.pain_score}/10.\n"
                        f"Age: {age}. Comorbidities: {', '.join(comorbidities) or 'none'}.\n"
                        f"Chief complaint: {chief_complaint}.\n"
                        f"Recommended department: {department_code}."
                    ),
                    schema=_TriageRationale,
                    temperature=settings.gemini_temperature,
                )
                rationale = structured.rationale
                llm_model_used = settings.gemini_model
            except Exception:
                rationale = None  # fall through to the deterministic template below

        if rationale is None:
            rationale = _ml_rationale_text(vitals, esi_level, confidence, age)

        messages = [
            emit(
                self.name,
                "triage_complete",
                {"esi_level": esi_level, "department_code": department_code},
                to_agent=str(AgentName.BED_ALLOCATION),
            ),
            emit(
                self.name,
                "disease_signal",
                {"chief_complaint": chief_complaint, "esi_level": esi_level},
                to_agent=str(AgentName.DISEASE_FORECAST),
            ),
        ]

        return AgentResult(
            agent=self.name,
            version=self.version,
            output={
                "esi_level": esi_level,
                "confidence": confidence,
                "recommended_department_code": department_code,
                "target_response_minutes": TRIAGE_TARGET_MINUTES[esi_level],
                "red_flags": red_flags,
                "rationale": rationale,
                "probabilities": prediction["probabilities"],
                "model_version": prediction["model_version"],
                "used_fallback": False,
            },
            rationale=rationale,
            confidence=confidence,
            messages=messages,
            used_fallback=False,
            status="success",
            llm_model=llm_model_used,
        )

    def fallback(self, state: HealMatrixState) -> AgentResult:
        vitals = Vitals(**state["vitals"])
        age = int(state["age"])
        comorbidities = state.get("comorbidities", [])
        chief_complaint = state["chief_complaint"]

        result = rule_engine_triage(vitals, chief_complaint, age, comorbidities)

        messages = [
            emit(
                self.name,
                "triage_complete",
                {
                    "esi_level": result["esi_level"],
                    "department_code": result["recommended_department_code"],
                },
                to_agent=str(AgentName.BED_ALLOCATION),
            ),
            emit(
                self.name,
                "disease_signal",
                {"chief_complaint": chief_complaint, "esi_level": result["esi_level"]},
                to_agent=str(AgentName.DISEASE_FORECAST),
            ),
        ]

        return AgentResult(
            agent=self.name,
            version=self.version,
            output=result,
            rationale=result["rationale"],
            confidence=result["confidence"],
            messages=messages,
            used_fallback=True,
            status="success",
        )
