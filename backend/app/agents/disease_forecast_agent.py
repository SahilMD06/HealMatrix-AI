"""Disease Forecast Agent.

Per docs/04_agent_design.md 2.2: lag/seasonality feature build -> XGBoost
admissions_14d -> ICU demand derivation -> outbreak test. Runs on every scheduled
cycle rather than per-patient, since a single arrival tells you nothing about the
next two weeks' trend.

Two things this agent is honest about rather than papering over:
  - The forecast model predicts *total* daily admissions, not a per-category
    breakdown — the ``recent_daily_admission_counts`` window it trains and infers
    on is category-collapsed (see ``AdmissionService.recent_daily_admission_counts``).
    Category-level decomposition would need per-category history and is future work.
  - ICU demand is *derived*, not directly forecast: it applies a documented,
    assumed ICU-admission fraction to the total forecast. That fraction is a
    planning assumption, not a measured one, and the rationale says so.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from app.agents.base import AgentResult, BaseAgent, emit
from app.agents.state import HealMatrixState
from app.core.constants import AgentName
from app.core.exceptions import ModelNotAvailableError
from app.ml import inference
from app.ml.training.train_admissions_forecast import ADMISSIONS_LAG_DAYS

# Documented planning assumption: share of admissions that are ESI 1/2 and would
# need an ICU or HDU bed. Not measured from real outcome data — see module docstring.
ASSUMED_ICU_ADMISSION_RATE = 0.12

# Outbreak test per spec: > 2 sigma over baseline for 3 consecutive forecast days.
OUTBREAK_SIGMA_THRESHOLD = 2.0
OUTBREAK_MIN_CONSECUTIVE_DAYS = 3

# z-score for the 80th percentile of a normal distribution, used for the ICU p80 band.
Z_P80 = 0.8416


class DiseaseForecastAgent(BaseAgent):
    name = str(AgentName.DISEASE_FORECAST)
    version = "1.0.0"

    async def analyse(self, state: HealMatrixState) -> AgentResult:
        history: list[float] | None = state.get("recent_daily_admission_counts")
        if not history or len(history) < ADMISSIONS_LAG_DAYS:
            raise RuntimeError(
                f"Need at least {ADMISSIONS_LAG_DAYS} days of admission history in state."
            )
        if not inference.admissions_model_available():
            raise ModelNotAvailableError("Admissions forecast model artifact not found.")

        as_of = self._as_of(state)
        prediction = inference.predict_admissions_14d(
            recent_daily_counts=history,
            as_of_weekday=as_of.weekday(),
            as_of_month=as_of.month,
        )
        forecast = prediction["forecast_14d"]

        # The baseline must come from *before* the model's lag window, not from the
        # same days used to seed the forecast — otherwise a genuine spike in the
        # most recent days inflates its own baseline and the outbreak test never fires.
        reference_period = history[: -ADMISSIONS_LAG_DAYS] if len(history) > ADMISSIONS_LAG_DAYS + 13 else history
        baseline_mean = sum(reference_period) / len(reference_period)
        variance = sum((value - baseline_mean) ** 2 for value in reference_period) / len(reference_period)
        baseline_std = math.sqrt(variance)

        outbreak_warnings = self._detect_outbreaks(forecast, baseline_mean, baseline_std)

        icu_demand = [round(day * ASSUMED_ICU_ADMISSION_RATE, 1) for day in forecast]
        icu_p50 = round(sum(icu_demand) / len(icu_demand), 1)
        icu_std = math.sqrt(
            sum((value - icu_p50) ** 2 for value in icu_demand) / len(icu_demand)
        )
        icu_p80 = round(icu_p50 + Z_P80 * icu_std, 1)

        recommended_preallocation = (
            f"Pre-allocate approximately {math.ceil(icu_p80)} ICU/HDU beds across the forecast "
            "window based on the p80 demand band."
            if outbreak_warnings
            else "No pre-allocation beyond routine capacity recommended this cycle."
        )

        rationale = (
            f"14-day admissions forecast averages {round(sum(forecast) / len(forecast), 1)}/day "
            f"against a {round(baseline_mean, 1)} +/- {round(baseline_std, 1)} baseline. "
            f"Derived ICU demand: p50 {icu_p50}, p80 {icu_p80} beds/day (assuming "
            f"{round(ASSUMED_ICU_ADMISSION_RATE * 100)}% of admissions need ICU/HDU care — "
            "a planning assumption, not a measured rate)."
        )
        if outbreak_warnings:
            rationale += (
                f" Outbreak signal: {len(outbreak_warnings)} forecast day(s) exceed "
                f"{OUTBREAK_SIGMA_THRESHOLD} sigma over baseline for "
                f"{OUTBREAK_MIN_CONSECUTIVE_DAYS}+ consecutive days."
            )

        messages = [
            emit(
                self.name,
                "icu_demand",
                {"icu_demand_p50": icu_p50, "icu_demand_p80": icu_p80},
                to_agent=str(AgentName.BED_ALLOCATION),
            ),
            emit(
                self.name,
                "expected_case_mix",
                {"forecast_14d_total": round(sum(forecast), 1)},
                to_agent=str(AgentName.MEDICINE),
            ),
        ]
        if outbreak_warnings:
            messages.append(
                emit(self.name, "outbreak_warning", {"days": outbreak_warnings}, to_agent=None)
            )

        return AgentResult(
            agent=self.name,
            version=self.version,
            output={
                "forecast_14d": forecast,
                "icu_demand": {"p50": icu_p50, "p80": icu_p80},
                "outbreak_warnings": outbreak_warnings,
                "recommended_preallocation": recommended_preallocation,
                "baseline_mean": round(baseline_mean, 1),
                "baseline_std": round(baseline_std, 1),
                "model_version": prediction["model_version"],
                "used_fallback": False,
            },
            rationale=rationale,
            confidence=0.8 if not outbreak_warnings else 0.7,
            messages=messages,
            used_fallback=False,
            status="success",
        )

    def fallback(self, state: HealMatrixState) -> AgentResult:
        """No model, or insufficient history: hold the naive baseline forward.

        A flat repeat of the trailing 7-day average is a legitimate, conservative
        forecast floor — it will not catch a trend, but it will also never propose
        something wild off a broken input.
        """
        history: list[float] = state.get("recent_daily_admission_counts") or []
        recent_window = history[-7:] if history else [0.0]
        baseline_mean = sum(recent_window) / len(recent_window)
        forecast = [round(baseline_mean, 1)] * 14
        icu_p50 = round(baseline_mean * ASSUMED_ICU_ADMISSION_RATE, 1)

        return AgentResult(
            agent=self.name,
            version=self.version,
            output={
                "forecast_14d": forecast,
                "icu_demand": {"p50": icu_p50, "p80": icu_p50},
                "outbreak_warnings": [],
                "recommended_preallocation": "Insufficient history for a trend forecast; holding baseline flat.",
                "baseline_mean": round(baseline_mean, 1),
                "baseline_std": 0.0,
                "model_version": "naive_baseline@1.0.0",
                "used_fallback": True,
            },
            rationale=(
                "Forecast model or admission history unavailable; held the trailing 7-day "
                f"average ({round(baseline_mean, 1)}/day) flat for 14 days as a conservative floor."
            ),
            confidence=0.3,
            messages=[],
            used_fallback=True,
            status="success",
        )

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _as_of(state: HealMatrixState) -> datetime:
        raw = state.get("as_of")
        if raw:
            try:
                return datetime.fromisoformat(raw)
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    @staticmethod
    def _detect_outbreaks(
        forecast: list[float], baseline_mean: float, baseline_std: float
    ) -> list[dict]:
        """Flag runs of >= OUTBREAK_MIN_CONSECUTIVE_DAYS forecast days each more than
        OUTBREAK_SIGMA_THRESHOLD standard deviations above the historical baseline."""
        if baseline_std <= 0:
            return []

        threshold = baseline_mean + OUTBREAK_SIGMA_THRESHOLD * baseline_std
        flags = [value > threshold for value in forecast]

        warnings: list[dict] = []
        run_start: int | None = None
        for day_index, flagged in enumerate([*flags, False]):
            if flagged and run_start is None:
                run_start = day_index
            elif not flagged and run_start is not None:
                run_length = day_index - run_start
                if run_length >= OUTBREAK_MIN_CONSECUTIVE_DAYS:
                    warnings.append(
                        {
                            "start_day": run_start + 1,
                            "end_day": day_index,
                            "peak_value": round(max(forecast[run_start:day_index]), 1),
                            "threshold": round(threshold, 1),
                        }
                    )
                run_start = None

        return warnings
