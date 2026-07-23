"""Feature engineering shared between training and inference.

Kept as one module so the exact same transformation runs both when a model is
trained offline and when a live request is scored — the single most common way an
ML pipeline silently breaks is training and serving computing "the same" feature
two slightly different ways.
"""

from __future__ import annotations

from app.models.clinical import Vitals
from app.services.triage_rules import DEPARTMENT_KEYWORDS

# Fixed, versioned column order. Both the training script and the inference module
# import this list rather than each hard-coding their own — that is what guarantees
# they can never drift apart.
DEPARTMENT_HINTS: list[str] = ["CARDIO", "PULMO", "ORTHO", "NEURO", "GEN-MED", "OBG", "ED", "UNKNOWN"]

TRIAGE_FEATURE_COLUMNS: list[str] = [
    "heart_rate",
    "systolic_bp",
    "diastolic_bp",
    "spo2",
    "temperature_c",
    "respiratory_rate",
    "gcs",
    "pain_score",
    "shock_index",
    "mean_arterial_pressure",
    "age",
    "comorbidity_count",
    "sex_male",
    *[f"dept_hint_{code}" for code in DEPARTMENT_HINTS],
]


def complaint_department_hint(chief_complaint: str) -> str:
    """The same keyword match ``suggest_department`` uses, before the ESI-1 override.

    Used purely as a feature — a light signal of *what kind* of presentation this
    is — never as the agent's actual department decision, which still goes through
    ``suggest_department`` after the ESI level is known.
    """
    complaint = chief_complaint.lower()
    for keywords, department in DEPARTMENT_KEYWORDS:
        if any(keyword in complaint for keyword in keywords):
            return department
    return "UNKNOWN"


def triage_features(
    vitals: Vitals,
    age: int,
    sex: str,
    comorbidity_count: int,
    chief_complaint: str,
) -> dict[str, float]:
    """Build the fixed-order feature dict the triage model was trained on."""
    hint = complaint_department_hint(chief_complaint)

    features: dict[str, float] = {
        "heart_rate": float(vitals.heart_rate),
        "systolic_bp": float(vitals.systolic_bp),
        "diastolic_bp": float(vitals.diastolic_bp),
        "spo2": float(vitals.spo2),
        "temperature_c": float(vitals.temperature_c),
        "respiratory_rate": float(vitals.respiratory_rate),
        "gcs": float(vitals.gcs),
        "pain_score": float(vitals.pain_score),
        "shock_index": float(vitals.shock_index),
        "mean_arterial_pressure": float(vitals.mean_arterial_pressure),
        "age": float(age),
        "comorbidity_count": float(comorbidity_count),
        "sex_male": 1.0 if sex == "male" else 0.0,
    }
    for code in DEPARTMENT_HINTS:
        features[f"dept_hint_{code}"] = 1.0 if hint == code else 0.0

    return features


def triage_feature_row(**kwargs) -> list[float]:
    """``triage_features`` as an ordered row matching ``TRIAGE_FEATURE_COLUMNS``."""
    features = triage_features(**kwargs)
    return [features[column] for column in TRIAGE_FEATURE_COLUMNS]
