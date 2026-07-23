"""Determinism test for the Carbon Intelligence Agent.

Per docs/04_agent_design.md 2.8: "Deterministic by design — no LLM anywhere in
this pipeline, so the same inputs always produce byte-identical figures." This
is the one agent where that claim is checked directly: identical
``sustainability_totals`` and the same ``EMISSION_FACTOR_VERSION`` must produce
an identical output dict, not just a similar one, across repeated runs and
across fresh agent instances.
"""

from __future__ import annotations

import pytest

from app.agents.carbon_agent import CarbonIntelligenceAgent
from app.core.constants import EMISSION_FACTOR_VERSION

pytestmark = pytest.mark.unit


def make_state() -> dict:
    return {
        "total_beds": 120,
        "anaesthetic_gas_kg": {"sevoflurane": 4.2, "nitrous_oxide": 1.1},
        "sustainability_totals": {
            "energy_kwh": {"total": 5400.0, "grid": 4200.0, "solar": 900.0, "diesel_generator": 300.0},
            "water_litres": {
                "total": 82000.0, "municipal": 60000.0, "borewell": 10000.0,
                "rainwater": 8000.0, "recycled": 4000.0, "max_leak_probability": 0.12,
            },
            "waste_by_method_kg": {
                "incineration": 45.0, "autoclave": 60.0, "landfill": 20.0,
                "recycling": 15.0, "microwave": 0.0, "deep_burial": 0.0,
            },
            "waste_by_category_kg": {
                "yellow": 50.0, "red": 30.0, "white": 20.0, "blue": 15.0, "general": 25.0,
            },
            "recyclable_recovered_kg": 15.0,
        },
        "messages": [
            {"from_agent": "ambulance_dispatch", "to_agent": "carbon_intelligence",
             "intent": "fuel_litres", "payload": {"fuel_litres": 12.5}},
        ],
    }


class TestCarbonDeterminism:
    async def test_repeated_runs_on_the_same_agent_are_byte_identical(self):
        agent = CarbonIntelligenceAgent()
        state = make_state()

        first = await agent.analyse(state)
        second = await agent.analyse(state)

        assert first.output == second.output
        assert first.rationale == second.rationale
        assert first.confidence == second.confidence

    async def test_fresh_agent_instances_agree(self):
        state = make_state()
        first = await CarbonIntelligenceAgent().analyse(state)
        second = await CarbonIntelligenceAgent().analyse(state)
        assert first.output == second.output

    async def test_output_is_traceable_to_a_factor_version(self):
        result = await CarbonIntelligenceAgent().analyse(make_state())
        assert result.output["emission_factor_version"] == EMISSION_FACTOR_VERSION

    async def test_different_inputs_produce_different_totals(self):
        """Guards against a determinism test that would pass even if the agent
        ignored its inputs and returned a constant."""
        low_state = make_state()
        high_state = make_state()
        high_state["sustainability_totals"]["energy_kwh"]["grid"] = 40000.0

        low = await CarbonIntelligenceAgent().analyse(low_state)
        high = await CarbonIntelligenceAgent().analyse(high_state)
        assert high.output["total_kg"] > low.output["total_kg"]
