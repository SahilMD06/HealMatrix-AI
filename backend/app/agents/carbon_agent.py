"""Carbon Intelligence Agent.

Per docs/04_agent_design.md 2.8: **deterministic by design** — no LLM anywhere in
this pipeline, so the same inputs always produce byte-identical figures (see the
determinism test in the agent test suite). There is therefore no meaningful
distinction between "analyse" and "fallback" here the way there is for the ML/LLM
agents: both paths run the same arithmetic. ``analyse()`` is the version that reads
live totals computed by ``SustainabilityService``; ``fallback()`` only exists for
the case where those totals are missing from state entirely (the graph node that
should have populated them didn't run), and it makes that assumption explicit in
the rationale rather than silently reporting zero emissions as if that were real.

Every figure in ``EMISSION_FACTORS`` is versioned (``EMISSION_FACTOR_VERSION``), so
a report can always be traced back to the exact factor table that produced it.
"""

from __future__ import annotations

from app.agents.base import AgentResult, BaseAgent, emit
from app.agents.state import HealMatrixState, messages_for
from app.core.constants import (
    EMISSION_FACTOR_VERSION,
    EMISSION_FACTORS,
    SUSTAINABILITY_WEIGHTS,
    AgentName,
)

# Documented planning assumptions for the reduction-opportunity estimates below.
# These are not measured figures — they are stated so the numbers they produce can
# be read as "under this assumption", which is the honest way to present a
# techno-economic estimate with no real procurement data behind it.
GRID_COST_PAISE_PER_KWH = 780  # matches app.simulator.generators' cost_paise formula
SOLAR_CAPEX_PAISE_PER_KWP = 4_500_000  # ~INR 45,000/kWp, small-commercial rooftop, 2025
SOLAR_YIELD_KWH_PER_KWP_DAY = 4.0  # conservative Bengaluru-latitude estimate

# Carbon-score benchmark: an assumed "typical" tertiary-hospital figure, not a cited
# external benchmark. Scoring is 50 at the benchmark, approaching 100 as emissions
# fall towards zero and approaching 0 as they reach double the benchmark.
CARBON_BENCHMARK_KG_PER_BED_DAY = 18.0


def _clip(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


class CarbonIntelligenceAgent(BaseAgent):
    name = str(AgentName.CARBON)
    version = "1.0.0"

    async def analyse(self, state: HealMatrixState) -> AgentResult:
        totals = state.get("sustainability_totals")
        if not totals:
            raise RuntimeError("No sustainability_totals in state; graph did not populate them.")

        total_beds = state.get("total_beds")

        # Messages from other agents contribute Scope 1 figures this agent has no
        # other way to see (ambulance fuel, anaesthetic gas) — see the per-agent
        # "Messages emitted" list in docs/04_agent_design.md.
        fuel_litres = self._sum_message_number(state, "fuel_litres")
        anaesthetic_kg = state.get("anaesthetic_gas_kg", {})

        energy = totals["energy_kwh"]
        water = totals["water_litres"]
        waste_method = totals["waste_by_method_kg"]

        # ------------------------------------------------------------- scope 1
        diesel_generator_kg = energy["diesel_generator"] * EMISSION_FACTORS["diesel_generator_kwh"]
        ambulance_fuel_kg = fuel_litres * EMISSION_FACTORS["diesel_litre"]
        anaesthetic_kg_total = sum(
            anaesthetic_kg.get(gas, 0.0) * EMISSION_FACTORS.get(f"anaesthetic_{gas}_kg", 0.0)
            for gas in ("desflurane", "sevoflurane")
        ) + anaesthetic_kg.get("nitrous_oxide", 0.0) * EMISSION_FACTORS["nitrous_oxide_kg"]
        scope1_total = diesel_generator_kg + ambulance_fuel_kg + anaesthetic_kg_total

        # ------------------------------------------------------------- scope 2
        grid_kg = energy["grid"] * EMISSION_FACTORS["grid_electricity_kwh"]
        solar_kg = energy["solar"] * EMISSION_FACTORS["solar_kwh"]
        scope2_total = grid_kg + solar_kg

        # ------------------------------------------------------------- scope 3
        waste_kg = sum(
            waste_method.get(method, 0.0) * EMISSION_FACTORS[f"waste_{method}_kg"]
            for method in ("incineration", "autoclave", "landfill", "recycling")
            if f"waste_{method}_kg" in EMISSION_FACTORS
        )
        water_kg = (water["total"] / 1000.0) * EMISSION_FACTORS["water_kilolitre"]
        scope3_total = waste_kg + water_kg  # procurement, staff commute: no data source yet

        total_kg = scope1_total + scope2_total + scope3_total
        per_bed_day_kg = round(total_kg / total_beds, 3) if total_beds else None

        # ------------------------------------------------------------ sub-scores
        total_electricity = energy["grid"] + energy["solar"] + energy["diesel_generator"]
        renewable_share = energy["solar"] / total_electricity if total_electricity else 0.0
        energy_score = _clip(50 + 50 * renewable_share)

        sustainable_water = water["rainwater"] + water["recycled"]
        sustainable_water_share = sustainable_water / water["total"] if water["total"] else 0.0
        leak_penalty = water.get("max_leak_probability", 0.0) * 30
        water_score = _clip(40 + 60 * sustainable_water_share - leak_penalty)

        total_waste = sum(totals["waste_by_category_kg"].values())
        landfill_incin_share = (
            (waste_method.get("landfill", 0.0) + waste_method.get("incineration", 0.0)) / total_waste
            if total_waste
            else 0.0
        )
        waste_score = _clip(100 - landfill_incin_share * 70)

        if per_bed_day_kg is not None:
            carbon_score = _clip(100 - (per_bed_day_kg / CARBON_BENCHMARK_KG_PER_BED_DAY) * 50)
        else:
            carbon_score = _clip(100 - (total_kg / 1000) * 5)  # coarse fallback with no bed count

        overall = round(
            energy_score * SUSTAINABILITY_WEIGHTS["energy"]
            + water_score * SUSTAINABILITY_WEIGHTS["water"]
            + waste_score * SUSTAINABILITY_WEIGHTS["waste"]
            + carbon_score * SUSTAINABILITY_WEIGHTS["carbon"],
            1,
        )
        grade = self._grade(overall)

        reduction_opportunities = self._reduction_opportunities(energy, renewable_share)

        rationale = (
            f"Scope 1+2+3 emissions of {round(total_kg, 1)} kgCO2e this period "
            f"(grid {round(grid_kg, 1)}, diesel generator {round(diesel_generator_kg, 1)}, "
            f"waste {round(waste_kg, 1)}, water {round(water_kg, 1)} kgCO2e). "
            f"Composite sustainability score {overall}/100 (grade {grade}): "
            f"energy {round(energy_score, 1)}, water {round(water_score, 1)}, "
            f"waste {round(waste_score, 1)}, carbon {round(carbon_score, 1)}. "
            f"Renewable share of electricity is {round(renewable_share * 100, 1)}%."
        )

        messages = [
            emit(
                self.name,
                "sustainability_score",
                {"overall": overall, "grade": grade, "top_levers": reduction_opportunities[:2]},
                to_agent=str(AgentName.EXECUTIVE),
            )
        ]

        return AgentResult(
            agent=self.name,
            version=self.version,
            output={
                "scope1": {
                    "diesel_generator": round(diesel_generator_kg, 2),
                    "ambulance_fuel": round(ambulance_fuel_kg, 2),
                    "anaesthetic_gases": round(anaesthetic_kg_total, 2),
                    "total": round(scope1_total, 2),
                },
                "scope2": {"grid_electricity": round(grid_kg, 2), "total": round(scope2_total, 2)},
                "scope3": {
                    "waste_treatment": round(waste_kg, 2),
                    "water": round(water_kg, 2),
                    "procurement": 0.0,
                    "staff_commute": 0.0,
                    "total": round(scope3_total, 2),
                },
                "total_kg": round(total_kg, 2),
                "per_bed_day_kg": per_bed_day_kg,
                "sustainability_score": {
                    "energy": round(energy_score, 1),
                    "water": round(water_score, 1),
                    "waste": round(waste_score, 1),
                    "carbon": round(carbon_score, 1),
                    "overall": overall,
                    "grade": grade,
                },
                "reduction_opportunities": reduction_opportunities,
                "emission_factor_version": EMISSION_FACTOR_VERSION,
            },
            rationale=rationale,
            confidence=0.95,  # deterministic arithmetic; the only uncertainty is input completeness
            messages=messages,
            used_fallback=False,
            status="success",
        )

    def fallback(self, state: HealMatrixState) -> AgentResult:
        """Only reached when sustainability_totals is entirely missing from state."""
        return AgentResult(
            agent=self.name,
            version=self.version,
            output={
                "scope1": {"diesel_generator": 0.0, "ambulance_fuel": 0.0, "anaesthetic_gases": 0.0, "total": 0.0},
                "scope2": {"grid_electricity": 0.0, "total": 0.0},
                "scope3": {"waste_treatment": 0.0, "water": 0.0, "procurement": 0.0, "staff_commute": 0.0, "total": 0.0},
                "total_kg": 0.0,
                "per_bed_day_kg": None,
                "sustainability_score": {
                    "energy": 0.0, "water": 0.0, "waste": 0.0, "carbon": 0.0, "overall": 0.0, "grade": "E",
                },
                "reduction_opportunities": [],
                "emission_factor_version": EMISSION_FACTOR_VERSION,
            },
            rationale=(
                "No telemetry was available for this cycle (sustainability_totals missing "
                "from graph state), so no emissions figure could be computed. This is reported "
                "as zero rather than estimated, which is why the sustainability score is also "
                "zero — that score should not be read as 'perfectly sustainable'."
            ),
            confidence=0.0,
            messages=[],
            used_fallback=True,
            status="success",
        )

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _grade(overall: float) -> str:
        for cutoff, label in ((85, "A+"), (75, "A"), (65, "B"), (55, "C"), (45, "D")):
            if overall >= cutoff:
                return label
        return "E"

    @staticmethod
    def _sum_message_number(state: HealMatrixState, key: str) -> float:
        total = 0.0
        for message in messages_for(state, str(AgentName.CARBON)):
            total += float(message.get("payload", {}).get(key, 0.0))
        return total

    @staticmethod
    def _reduction_opportunities(energy: dict, renewable_share: float) -> list[dict]:
        """Ranked, explicitly-assumption-labelled levers. See module docstring."""
        opportunities: list[dict] = []

        if renewable_share < 0.6:
            grid_kwh_period = energy["grid"]
            shiftable_kwh = grid_kwh_period * 0.20
            if shiftable_kwh > 0:
                factor_delta = EMISSION_FACTORS["grid_electricity_kwh"] - EMISSION_FACTORS["solar_kwh"]
                tco2e_abated = round(shiftable_kwh * factor_delta / 1000, 3)
                required_kwp = shiftable_kwh / SOLAR_YIELD_KWH_PER_KWP_DAY if SOLAR_YIELD_KWH_PER_KWP_DAY else 0
                cost_paise = int(required_kwp * SOLAR_CAPEX_PAISE_PER_KWP)
                daily_saving_paise = shiftable_kwh * GRID_COST_PAISE_PER_KWH
                payback_months = (
                    round(cost_paise / (daily_saving_paise * 30), 1) if daily_saving_paise else None
                )
                opportunities.append(
                    {
                        "lever": "expand_solar_capacity",
                        "description": (
                            f"Shift ~20% of current grid draw ({round(shiftable_kwh, 1)} kWh/period) to solar "
                            f"via ~{round(required_kwp, 1)} kWp additional capacity. Assumes "
                            f"₹{SOLAR_CAPEX_PAISE_PER_KWP / 100:,.0f}/kWp capex and "
                            f"{SOLAR_YIELD_KWH_PER_KWP_DAY} kWh/kWp/day yield — a planning estimate, not a quote."
                        ),
                        "tco2e_abated": tco2e_abated,
                        "cost_paise": cost_paise,
                        "payback_months": payback_months,
                        "priority": 1,
                    }
                )

        if energy["diesel_generator"] > 0:
            dg_kwh = energy["diesel_generator"]
            factor_delta = EMISSION_FACTORS["diesel_generator_kwh"] - EMISSION_FACTORS["grid_electricity_kwh"]
            tco2e_abated = round(max(dg_kwh * factor_delta, 0.0) / 1000, 3)
            opportunities.append(
                {
                    "lever": "reduce_diesel_generator_reliance",
                    "description": (
                        f"{round(dg_kwh, 1)} kWh this period came from the diesel generator, roughly "
                        f"{round(EMISSION_FACTORS['diesel_generator_kwh'] / EMISSION_FACTORS['grid_electricity_kwh'], 1)}x "
                        "more carbon-intensive than grid power. Investigate whether this was planned "
                        "backup use or reflects grid-reliability gaps worth addressing with battery storage."
                    ),
                    "tco2e_abated": tco2e_abated,
                    "cost_paise": 0,  # investigation, not a capital project — no cost estimate offered
                    "payback_months": None,
                    "priority": 2,
                }
            )

        return sorted(opportunities, key=lambda item: item["priority"])
