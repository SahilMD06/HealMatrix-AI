"""Water Conservation Agent.

Per docs/04_agent_design.md 2.6: IsolationForest on night-flow features -> leak
probability -> loss estimation -> harvesting yield -> intervention ranking by
litres saved per rupee.

IsolationForest is fit fresh on each cycle's trailing window rather than loaded
from a persisted artifact — unlike the triage and admissions models, this is
genuinely the right call here, not a corner cut: it is unsupervised, retrains in
milliseconds on a few hundred rows, and what counts as "anomalous night flow" is
specific to *this* hospital's current baseline, which drifts over time as
occupancy and fixtures change. Persisting a stale artifact would be the actual bug.

IsolationForest's ``score_samples`` is not a probability — it is converted to one
here via the point's percentile rank against the fitted training distribution,
a standard, documented way to turn an anomaly score into a 0-1 "how unusual is
this" figure without pretending it is a calibrated likelihood.
"""

from __future__ import annotations

import statistics
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest

from app.agents.base import AgentResult, BaseAgent, emit
from app.agents.state import HealMatrixState
from app.core.constants import AgentName

LEAK_CRITICAL_THRESHOLD = 0.8
MIN_TRAINING_ROWS = 20


class WaterConservationAgent(BaseAgent):
    name = str(AgentName.WATER)
    version = "1.0.0"

    async def analyse(self, state: HealMatrixState) -> AgentResult:
        history: list[dict] = state.get("hourly_water_history") or []
        if len(history) < MIN_TRAINING_ROWS:
            raise RuntimeError(f"Need at least {MIN_TRAINING_ROWS} hours of water history in state.")

        night_rows = [row for row in history if self._is_night(row)]
        if len(night_rows) < 5:
            raise RuntimeError("Not enough night-time readings to fit a leak model.")

        features = np.array(
            [[row.get("night_min_flow_lpm", 0.0), row.get("occupancy_ratio", 0.0)] for row in night_rows]
        )
        forest = IsolationForest(
            n_estimators=150, contamination="auto", random_state=20260723
        )
        forest.fit(features)
        training_scores = forest.score_samples(features)

        latest = night_rows[-1]
        latest_features = np.array(
            [[latest.get("night_min_flow_lpm", 0.0), latest.get("occupancy_ratio", 0.0)]]
        )
        latest_score = forest.score_samples(latest_features)[0]

        # Lower IsolationForest score = more anomalous. Percentile rank (inverted)
        # against the fitted distribution gives a 0-1 "unusualness" figure.
        percentile_below = float(np.mean(training_scores < latest_score))
        leak_probability = round(1.0 - percentile_below, 3)

        baseline_night_flow = statistics.fmean(row.get("night_min_flow_lpm", 0.0) for row in night_rows[:-1]) if len(night_rows) > 1 else 0.0
        excess_flow_lpm = max(latest.get("night_min_flow_lpm", 0.0) - baseline_night_flow, 0.0)
        estimated_loss_lpd = round(excess_flow_lpm * 60 * 24, 1)

        roof_area_sqm = state.get("roof_area_sqm", 0.0)
        rainfall_mm = state.get("rainfall_mm_forecast", 0.0)
        # Standard rainwater harvesting yield formula: area x rainfall x runoff coefficient.
        # 0.8 is a typical runoff coefficient for a hard hospital roof.
        harvesting_potential_l = round(roof_area_sqm * rainfall_mm * 0.8, 1)

        recommendations = self._rank_interventions(leak_probability, estimated_loss_lpd, harvesting_potential_l)

        forecast_daily = [round(row.get("consumption_litres", 0.0) * 24, 1) for row in history[-1:]] or [0.0]

        rationale = (
            f"Night minimum flow of {latest.get('night_min_flow_lpm')} L/min against a "
            f"{round(baseline_night_flow, 2)} L/min baseline yields a leak probability of "
            f"{leak_probability} (IsolationForest percentile rank, not a calibrated likelihood). "
            + (
                f"Estimated loss if sustained: {estimated_loss_lpd} L/day. "
                if estimated_loss_lpd > 0
                else ""
            )
            + f"Rainwater harvesting potential ~{harvesting_potential_l} L given current forecast rainfall."
        )

        messages = [
            emit(
                self.name,
                "water_kl",
                {"consumption_kl_24h": round(sum(forecast_daily) / 1000, 2)},
                to_agent=str(AgentName.CARBON),
            )
        ]
        if leak_probability > LEAK_CRITICAL_THRESHOLD:
            messages.append(
                emit(
                    self.name,
                    "critical_leak_alert",
                    {"leak_probability": leak_probability, "estimated_loss_lpd": estimated_loss_lpd},
                    to_agent=None,  # broadcast: this bypasses the executive cycle per spec
                )
            )

        return AgentResult(
            agent=self.name,
            version=self.version,
            output={
                "forecast_daily": forecast_daily,
                "leak_signals": [
                    {
                        "leak_probability": leak_probability,
                        "estimated_loss_lpd": estimated_loss_lpd,
                        "critical": leak_probability > LEAK_CRITICAL_THRESHOLD,
                    }
                ],
                "harvesting_potential_l": harvesting_potential_l,
                "recommendations": recommendations,
            },
            rationale=rationale,
            confidence=0.7,
            messages=messages,
            used_fallback=False,
            status="success",
        )

    def fallback(self, state: HealMatrixState) -> AgentResult:
        history: list[dict] = state.get("hourly_water_history") or []
        recent = history[-24:] if history else []
        forecast = (
            [round(statistics.fmean(row.get("consumption_litres", 0.0) for row in recent), 1)]
            if recent
            else [0.0]
        )
        return AgentResult(
            agent=self.name,
            version=self.version,
            output={
                "forecast_daily": forecast,
                "leak_signals": [],
                "harvesting_potential_l": 0.0,
                "recommendations": [],
            },
            rationale=(
                "Insufficient night-flow history to fit a leak-detection model this cycle; "
                "no anomaly assessment could be made. This is not the same as 'no leak detected'."
            ),
            confidence=0.1,
            messages=[],
            used_fallback=True,
            status="success",
        )

    @staticmethod
    def _is_night(row: dict) -> bool:
        timestamp = row.get("timestamp")
        hour = getattr(timestamp, "hour", None)
        return hour in (2, 3, 4) if hour is not None else False

    @staticmethod
    def _rank_interventions(
        leak_probability: float, estimated_loss_lpd: float, harvesting_potential_l: float
    ) -> list[dict[str, Any]]:
        interventions: list[dict[str, Any]] = []

        if leak_probability > 0.5 and estimated_loss_lpd > 0:
            # Municipal water cost assumption, documented: ~INR 0.06/L for a bulk
            # institutional connection — a planning estimate, not a billed rate.
            value_paise_per_day = estimated_loss_lpd * 6
            interventions.append(
                {
                    "action": "investigate_suspected_leak",
                    "litres_saved_per_day": estimated_loss_lpd,
                    "value_paise_per_day": round(value_paise_per_day, 0),
                    "priority": 1,
                }
            )

        if harvesting_potential_l > 500:
            interventions.append(
                {
                    "action": "capture_rainwater_harvesting_yield",
                    "litres_saved_per_day": harvesting_potential_l,
                    "value_paise_per_day": round(harvesting_potential_l * 6, 0),
                    "priority": 2,
                }
            )

        return sorted(interventions, key=lambda item: item["priority"])
