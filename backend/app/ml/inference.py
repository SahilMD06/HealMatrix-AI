"""Loads trained artifacts once per process and exposes plain prediction functions.

Agents import from here, never from ``app.ml.training.*`` — the training modules
pull in ``sklearn``'s training-time surface and are meant to be run offline as a
script, not imported by the running API. This module is the only thing that reads
the ``.joblib`` artifacts and is the seam a real MLOps setup would replace with a
model registry lookup, without any agent code needing to change.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from app.core.exceptions import ModelNotAvailableError
from app.core.logging_config import get_logger
from app.ml.features import TRIAGE_FEATURE_COLUMNS, triage_features
from app.models.clinical import Vitals

logger = get_logger(__name__)

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
TRIAGE_MODEL_PATH = ARTIFACT_DIR / "triage_esi_xgb.joblib"
ADMISSIONS_MODEL_PATH = ARTIFACT_DIR / "admissions_forecast_xgb.joblib"

# Re-exported so callers can keep writing ``from app.ml.inference import
# ModelUnavailableError`` — it is simply the project's existing domain exception.
ModelUnavailableError = ModelNotAvailableError


@lru_cache(maxsize=1)
def _load_triage_bundle() -> dict[str, Any]:
    if not TRIAGE_MODEL_PATH.exists():
        raise ModelNotAvailableError(
            f"No triage model artifact at {TRIAGE_MODEL_PATH}. "
            "Run: python -m app.ml.training.train_triage_model",
            details={"artifact": str(TRIAGE_MODEL_PATH)},
        )
    return joblib.load(TRIAGE_MODEL_PATH)


@lru_cache(maxsize=1)
def _load_admissions_bundle() -> dict[str, Any]:
    if not ADMISSIONS_MODEL_PATH.exists():
        raise ModelNotAvailableError(
            f"No admissions forecast artifact at {ADMISSIONS_MODEL_PATH}. "
            "Run: python -m app.ml.training.train_admissions_forecast",
            details={"artifact": str(ADMISSIONS_MODEL_PATH)},
        )
    return joblib.load(ADMISSIONS_MODEL_PATH)


def triage_model_available() -> bool:
    return TRIAGE_MODEL_PATH.exists()


def admissions_model_available() -> bool:
    return ADMISSIONS_MODEL_PATH.exists()


def predict_esi(
    vitals: Vitals,
    age: int,
    sex: str,
    comorbidity_count: int,
    chief_complaint: str,
) -> dict[str, Any]:
    """XGBoost ESI prediction. Raises ``ModelUnavailableError`` if untrained.

    Callers (the Patient Triage Agent) are responsible for applying the red-flag
    guardrail on top of this — this function has no knowledge of red flags and must
    not be treated as the final word on ESI 1.
    """
    bundle = _load_triage_bundle()
    model = bundle["model"]
    columns = bundle["feature_columns"]
    esi_classes: list[int] = bundle["esi_classes"]

    features = triage_features(
        vitals=vitals,
        age=age,
        sex=sex,
        comorbidity_count=comorbidity_count,
        chief_complaint=chief_complaint,
    )
    row = np.array([[features[column] for column in columns]], dtype=float)

    probabilities = model.predict_proba(row)[0]
    best_index = int(np.argmax(probabilities))

    return {
        "esi_level": esi_classes[best_index],
        "confidence": round(float(probabilities[best_index]), 4),
        "probabilities": {
            str(esi_classes[i]): round(float(p), 4) for i, p in enumerate(probabilities)
        },
        "model_version": bundle["model_version"],
    }


def predict_admissions_14d(recent_daily_counts: list[float], as_of_weekday: int, as_of_month: int) -> dict[str, Any]:
    """14-day-ahead daily admissions forecast from a trailing window of daily counts.

    ``recent_daily_counts`` must be the most recent ``ADMISSIONS_LAG_DAYS`` values,
    oldest first — the same window shape ``build_lag_features`` produces at training
    time. Raises ``ModelUnavailableError`` if untrained.
    """
    from app.ml.training.train_admissions_forecast import (
        ADMISSIONS_LAG_DAYS,
        build_feature_row,
    )

    bundle = _load_admissions_bundle()
    model = bundle["model"]
    columns = bundle["feature_columns"]

    if len(recent_daily_counts) < ADMISSIONS_LAG_DAYS:
        raise ModelUnavailableError(
            f"Need at least {ADMISSIONS_LAG_DAYS} days of history, got {len(recent_daily_counts)}."
        )

    window = list(recent_daily_counts[-ADMISSIONS_LAG_DAYS:])
    forecast: list[float] = []
    for day_offset in range(14):
        target_weekday = (as_of_weekday + day_offset + 1) % 7
        features = build_feature_row(window, target_weekday, as_of_month)
        row = np.array([[features[column] for column in columns]], dtype=float)
        predicted = float(model.predict(row)[0])
        predicted = max(predicted, 0.0)
        forecast.append(round(predicted, 1))
        window = window[1:] + [predicted]

    return {
        "forecast_14d": forecast,
        "model_version": bundle["model_version"],
    }
