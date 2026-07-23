"""Fallback unit tests for all ten agents.

Per docs/04_agent_design.md section 4: "Each fallback() returns a valid
AgentResult with the LLM fully disabled." ``GOOGLE_API_KEY`` is empty in this
test environment (see tests/conftest.py), so ``llm_ready()`` is already False
throughout the suite — these tests call ``fallback()`` directly (bypassing
``analyse()`` entirely) to prove each agent has a safe, deterministic floor
that never touches the network and never raises, independent of whatever
``analyse()`` does.

Agents that take service dependencies (BedAllocationAgent, MedicineIntelligenceAgent,
AmbulanceDispatchAgent) are constructed with ``None`` in place of those services:
each one's ``fallback()`` body is checked below to confirm it never dereferences
them, which is exactly what makes it a genuine fallback rather than a path that
merely delegates the failure somewhere else.
"""

from __future__ import annotations

import pytest

from app.agents.base import AgentResult
from app.agents.bed_allocation_agent import BedAllocationAgent
from app.agents.carbon_agent import CarbonIntelligenceAgent
from app.agents.crews.executive_crew import ExecutiveDecisionAgent
from app.agents.dispatch_agent import AmbulanceDispatchAgent
from app.agents.disease_forecast_agent import DiseaseForecastAgent
from app.agents.energy_agent import EnergyOptimizationAgent
from app.agents.medicine_agent import MedicineIntelligenceAgent
from app.agents.triage_agent import PatientTriageAgent
from app.agents.water_agent import WaterConservationAgent
from app.agents.waste_agent import BiomedicalWasteAgent

pytestmark = pytest.mark.unit

TRIAGE_STATE = {
    "vitals": {
        "heart_rate": 76, "systolic_bp": 122, "diastolic_bp": 78, "spo2": 99.0,
        "temperature_c": 36.7, "respiratory_rate": 15, "gcs": 15, "pain_score": 0,
    },
    "age": 40,
    "comorbidities": [],
    "chief_complaint": "Routine review",
    "patient": {"sex": "female"},
}

BED_ALLOCATION_STATE = {
    "results": {"patient_triage": {"output": {"esi_level": 3, "recommended_department_code": "GEN-MED"}}},
}


def assert_valid_fallback(result: AgentResult, agent_name: str) -> None:
    assert isinstance(result, AgentResult)
    assert result.agent == agent_name
    assert result.used_fallback is True
    assert result.status in ("success", "degraded", "failed")
    assert 0.0 <= result.confidence <= 1.0
    assert isinstance(result.rationale, str) and result.rationale.strip(), "rationale must not be empty"
    assert isinstance(result.output, dict)


class TestFallbackFloor:
    def test_triage_fallback(self):
        agent = PatientTriageAgent()
        result = agent.fallback(TRIAGE_STATE)
        assert_valid_fallback(result, "patient_triage")
        assert result.output["esi_level"] in (1, 2, 3, 4, 5)

    def test_bed_allocation_fallback(self):
        agent = BedAllocationAgent(bed_service=None, admission_service=None)
        result = agent.fallback(BED_ALLOCATION_STATE)
        assert_valid_fallback(result, "bed_allocation")
        assert result.output["escalation"] == "agent_error"

    def test_disease_forecast_fallback(self):
        agent = DiseaseForecastAgent()
        result = agent.fallback({})
        assert_valid_fallback(result, "disease_forecast")
        assert len(result.output["forecast_14d"]) == 14

    def test_medicine_intelligence_fallback(self):
        agent = MedicineIntelligenceAgent(inventory_service=None)
        result = agent.fallback({})
        assert_valid_fallback(result, "medicine_intelligence")
        assert result.output["stockout_risk"] == "unknown"

    def test_energy_fallback(self):
        agent = EnergyOptimizationAgent()
        result = agent.fallback({})
        assert_valid_fallback(result, "energy_optimization")
        assert len(result.output["forecast_24h"]) == 24
        assert result.output["hvac_recommendations"] == []

    def test_water_fallback(self):
        agent = WaterConservationAgent()
        result = agent.fallback({})
        assert_valid_fallback(result, "water_conservation")

    def test_waste_fallback(self):
        agent = BiomedicalWasteAgent()
        result = agent.fallback({})
        assert_valid_fallback(result, "biomedical_waste")
        assert result.output["classification"] == "requires_manual_review"

    def test_carbon_fallback(self):
        agent = CarbonIntelligenceAgent()
        result = agent.fallback({})
        assert_valid_fallback(result, "carbon_intelligence")
        assert result.output["total_kg"] == 0.0
        assert result.output["sustainability_score"]["grade"] == "E"

    def test_dispatch_fallback(self):
        agent = AmbulanceDispatchAgent(hospitals=None, ambulances=None)
        result = agent.fallback({})
        assert_valid_fallback(result, "ambulance_dispatch")
        assert result.output["escalation"] == "manual_dispatch_required"

    def test_executive_fallback(self):
        agent = ExecutiveDecisionAgent()
        result = agent.fallback({})
        assert_valid_fallback(result, "executive_decision")
        assert "action_plan" in result.output
        assert "risk_register" in result.output


class TestRunTemplateAppliesFallback:
    """BaseAgent.run() must land on fallback() when analyse() cannot complete, and
    must mark the result 'degraded' rather than silently reporting 'success'."""

    async def test_carbon_run_degrades_when_totals_missing(self):
        agent = CarbonIntelligenceAgent()
        result = await agent.run({})  # no sustainability_totals -> analyse() raises
        assert result.used_fallback is True
        assert result.status == "degraded"
        assert result.duration_ms >= 0

    async def test_medicine_run_degrades_without_inventory_service(self):
        agent = MedicineIntelligenceAgent(inventory_service=None)
        result = await agent.run({})  # analyse() will AttributeError on None.expiry_alerts
        assert result.used_fallback is True
        assert result.status == "degraded"

    async def test_executive_run_uses_deterministic_synthesis_with_no_api_key(self):
        agent = ExecutiveDecisionAgent()
        result = await agent.run({})
        assert result.used_fallback is True
        assert result.status == "degraded"
        assert "no LLM configured" in result.rationale or "rule-based ranking" in result.rationale
