"""Deterministic triage logic.

This is the Patient Triage Agent's fallback path, and it is also the guardrail that
overrides the model when a red flag is present. It is pure, synchronous and never
touches the network, so it works with no API key and is trivially unit-testable.

Scoring follows the Emergency Severity Index (ESI) five-level scale.
"""

from __future__ import annotations

from app.core.constants import TRIAGE_LABELS, TRIAGE_TARGET_MINUTES
from app.models.clinical import Vitals

# Complaint keywords that route to a department. Ordered most to least specific.
DEPARTMENT_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("chest pain", "angina", "palpitation", "cardiac arrest"), "CARDIO"),
    (("breathless", "shortness of breath", "asthma", "wheeze", "cough", "pneumonia"), "PULMO"),
    (("fracture", "sprain", "dislocation", "back pain", "joint"), "ORTHO"),
    # Stroke is the most time-critical neurological presentation and most often
    # arrives described as unilateral weakness rather than as "stroke", so the
    # laterality phrases are matched explicitly.
    (
        ("head injury", "seizure", "stroke", "unconscious", "paralysis", "dizzy",
         "weakness of the right", "weakness of the left", "right side", "left side",
         "slurred", "facial droop", "numbness"),
        "NEURO",
    ),
    (("abdominal", "vomiting", "diarrhoea", "diarrhea", "nausea", "stomach"), "GEN-MED"),
    (("pregnan", "labour", "labor", "contraction", "bleeding pv"), "OBG"),
    (("burn", "laceration", "wound", "trauma", "accident", "rta"), "ED"),
    (("fever", "chills", "infection", "dengue", "malaria"), "GEN-MED"),
]

RED_FLAG_RULES: list[tuple[str, str]] = [
    ("spo2_critical", "Oxygen saturation below 90% with tachypnoea"),
    ("gcs_depressed", "Glasgow Coma Scale of 8 or below"),
    ("shock", "Hypotension with tachycardia, suggesting shock"),
    ("bradycardia_severe", "Heart rate below 40"),
    ("hypertensive_crisis", "Systolic blood pressure of 200 or above"),
    ("hypothermia", "Core temperature below 35 degrees Celsius"),
]


def detect_red_flags(vitals: Vitals) -> list[str]:
    """Return the codes of any immediately life-threatening vital sign patterns."""
    flags: list[str] = []

    if vitals.spo2 < 90 and vitals.respiratory_rate > 30:
        flags.append("spo2_critical")
    if vitals.gcs <= 8:
        flags.append("gcs_depressed")
    if vitals.systolic_bp < 90 and vitals.heart_rate > 120:
        flags.append("shock")
    if vitals.heart_rate < 40:
        flags.append("bradycardia_severe")
    if vitals.systolic_bp >= 200:
        flags.append("hypertensive_crisis")
    if vitals.temperature_c < 35.0:
        flags.append("hypothermia")

    return flags


def score_severity(vitals: Vitals, age: int, comorbidity_count: int) -> float:
    """Continuous acuity score. Higher means sicker. Range roughly 0-14."""
    score = 0.0

    # Oxygenation. 93% is the recognised concern threshold in adult triage, so the
    # middle band is set there rather than at 92 — a patient sitting exactly on 92
    # is hypoxaemic and must not fall through to the mildest band.
    if vitals.spo2 < 88:
        score += 4.0
    elif vitals.spo2 < 93:
        score += 2.5
    elif vitals.spo2 < 95:
        score += 1.2

    # Circulation
    if vitals.shock_index >= 1.0:
        score += 3.0
    elif vitals.shock_index >= 0.9:
        score += 2.0
    elif vitals.shock_index >= 0.8:
        score += 1.0

    if vitals.systolic_bp < 90:
        score += 2.0
    elif vitals.systolic_bp >= 180:
        score += 1.5

    # Respiration
    if vitals.respiratory_rate > 30 or vitals.respiratory_rate < 8:
        score += 2.0
    elif vitals.respiratory_rate > 24:
        score += 1.0

    # Neurology
    if vitals.gcs <= 8:
        score += 4.0
    elif vitals.gcs <= 12:
        score += 2.0
    elif vitals.gcs < 15:
        score += 1.0

    # Temperature
    if vitals.temperature_c >= 39.5 or vitals.temperature_c < 35.0:
        score += 1.5
    elif vitals.temperature_c >= 38.5:
        score += 0.75

    # Pain
    if vitals.pain_score >= 8:
        score += 1.5
    elif vitals.pain_score >= 5:
        score += 0.75

    # Host factors
    if age >= 75:
        score += 1.5
    elif age >= 65:
        score += 1.0
    elif age <= 1:
        score += 1.5

    score += min(comorbidity_count, 4) * 0.5

    return round(score, 2)


# Band boundaries. Deliberately biased towards over-triage: in emergency medicine
# under-triage is the dangerous error, so the ESI 2 cut sits low enough that a
# patient with combined hypoxaemia, tachycardia and pain is escalated rather than
# left in the urgent queue.
ESI_THRESHOLDS: tuple[float, float, float] = (7.5, 4.5, 2.0)


def score_to_esi(score: float, red_flags: list[str]) -> int:
    """Map the continuous score to an ESI level. Red flags force level 1."""
    if red_flags:
        return 1
    emergent, urgent, less_urgent = ESI_THRESHOLDS
    if score >= emergent:
        return 2
    if score >= urgent:
        return 3
    if score >= less_urgent:
        return 4
    return 5


def suggest_department(chief_complaint: str, esi_level: int) -> str:
    """Map a free-text complaint to a department code."""
    if esi_level == 1:
        return "ED"

    complaint = chief_complaint.lower()
    for keywords, department in DEPARTMENT_KEYWORDS:
        if any(keyword in complaint for keyword in keywords):
            return department

    return "ED" if esi_level <= 2 else "GEN-MED"


def build_rationale(
    vitals: Vitals, esi_level: int, red_flags: list[str], score: float, age: int
) -> str:
    """Compose a clinician-readable explanation naming the driving observations."""
    if red_flags:
        descriptions = dict(RED_FLAG_RULES)
        reasons = "; ".join(descriptions[flag] for flag in red_flags if flag in descriptions)
        return (
            f"Immediate resuscitation indicated. {reasons}. "
            f"Shock index {vitals.shock_index}, SpO2 {vitals.spo2}%, GCS {vitals.gcs}. "
            "Escalated to ESI 1 by protocol regardless of composite score."
        )

    observations: list[str] = []
    if vitals.spo2 < 95:
        observations.append(f"hypoxaemia (SpO2 {vitals.spo2}%)")
    if vitals.shock_index >= 0.8:
        observations.append(f"elevated shock index ({vitals.shock_index})")
    if vitals.respiratory_rate > 24:
        observations.append(f"tachypnoea ({vitals.respiratory_rate}/min)")
    if vitals.temperature_c >= 38.5:
        observations.append(f"pyrexia ({vitals.temperature_c} C)")
    if vitals.pain_score >= 5:
        observations.append(f"pain score {vitals.pain_score}/10")
    if age >= 65:
        observations.append(f"age {age}")

    if observations:
        summary = ", ".join(observations)
        return (
            f"Assigned ESI {esi_level} ({TRIAGE_LABELS[esi_level]}) on a composite acuity "
            f"score of {score}. Contributing observations: {summary}. "
            f"Target clinician contact within {TRIAGE_TARGET_MINUTES[esi_level]} minutes."
        )

    return (
        f"Assigned ESI {esi_level} ({TRIAGE_LABELS[esi_level]}) on a composite acuity score "
        f"of {score}. Vital signs are within expected ranges and no red flags were detected. "
        f"Target clinician contact within {TRIAGE_TARGET_MINUTES[esi_level]} minutes."
    )


def triage(
    vitals: Vitals,
    chief_complaint: str,
    age: int,
    comorbidities: list[str] | None = None,
) -> dict:
    """Full deterministic triage. Returns the same shape as the agent's output."""
    comorbidity_list = comorbidities or []
    red_flags = detect_red_flags(vitals)
    score = score_severity(vitals, age, len(comorbidity_list))
    esi_level = score_to_esi(score, red_flags)

    # Confidence is highest at the extremes and lowest near a band boundary.
    distance = min(abs(score - boundary) for boundary in ESI_THRESHOLDS)
    confidence = 0.99 if red_flags else round(min(0.95, 0.62 + distance * 0.09), 2)

    return {
        "esi_level": esi_level,
        "confidence": confidence,
        "recommended_department_code": suggest_department(chief_complaint, esi_level),
        "target_response_minutes": TRIAGE_TARGET_MINUTES[esi_level],
        "red_flags": red_flags,
        "rationale": build_rationale(vitals, esi_level, red_flags, score, age),
        "acuity_score": score,
        "model_version": "triage_rules@1.0.0",
        "used_fallback": True,
    }
