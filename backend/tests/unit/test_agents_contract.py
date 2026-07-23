"""Contract tests: every agent's output validates against the shape promised in
docs/04_agent_design.md section 2 (per-agent "Output" line), and every AgentResult
survives the exact round-trip the LangGraph node wrapper (app/agents/graph/builder.py
``_node``/``_log_run``) puts it through — ``model_dump()`` into ``state["results"]``
and into the ``AgentLog`` document.

Pydantic already enforces ``AgentResult``'s own field types and the
``0.0 <= confidence <= 1.0`` bound at construction time (a violation raises
``ValidationError`` before a test would ever see it) — what these tests add is
the per-agent output *shape* the spec promises, which is a plain dict and has no
schema of its own to lean on.
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
from app.models.intelligence import AgentMessage

pytestmark = pytest.mark.unit

# Required output keys per agent, taken directly from each agent's "Output:" line
# in docs/04_agent_design.md section 2. A superset is fine; a missing key is not.
REQUIRED_OUTPUT_KEYS: dict[str, set[str]] = {
    "patient_triage": {
        "esi_level", "confidence", "recommended_department_code",
        "rationale", "red_flags", "target_response_minutes",
    },
    "disease_forecast": {"forecast_14d", "icu_demand", "outbreak_warnings", "recommended_preallocation"},
    "bed_allocation": {
        "recommended_bed_id", "alternatives", "predicted_los_days",
        "occupancy_rate", "expected_discharges_24h", "escalation",
    },
    "medicine_intelligence": {"expiry_alerts", "low_stock_alerts", "demand_forecast", "transfer_proposals"},
    "energy_optimization": {
        "forecast_24h", "hvac_recommendations", "anomalies",
        "renewable_potential_kwh", "projected_savings_kwh",
    },
    "water_conservation": {"forecast_daily", "leak_signals", "harvesting_potential_l", "recommendations"},
    "biomedical_waste": {"classification", "forecast_kg", "segregation_anomalies", "pickup_schedule", "diversion_rate"},
    "carbon_intelligence": {
        "scope1", "scope2", "scope3", "total_kg",
        "per_bed_day_kg", "sustainability_score", "reduction_opportunities",
    },
    "ambulance_dispatch": {
        "assigned_ambulance_id", "destination_hospital_id",
        "eta_minutes", "distance_km", "route_polyline",
    },
    "executive_decision": {
        "executive_summary", "action_plan", "risk_register",
        "sustainability_recommendations", "conflicts_resolved",
    },
}

FALLBACK_CASES = [
    (PatientTriageAgent(), {
        "vitals": {"heart_rate": 76, "systolic_bp": 122, "diastolic_bp": 78, "spo2": 99.0,
                   "temperature_c": 36.7, "respiratory_rate": 15, "gcs": 15, "pain_score": 0},
        "age": 40, "comorbidities": [], "chief_complaint": "Routine review", "patient": {"sex": "male"},
    }),
    (BedAllocationAgent(bed_service=None, admission_service=None),
     {"results": {"patient_triage": {"output": {"esi_level": 3}}}}),
    (DiseaseForecastAgent(), {}),
    (MedicineIntelligenceAgent(inventory_service=None), {}),
    (EnergyOptimizationAgent(), {}),
    (WaterConservationAgent(), {}),
    (BiomedicalWasteAgent(), {}),
    (CarbonIntelligenceAgent(), {}),
    (AmbulanceDispatchAgent(hospitals=None, ambulances=None), {}),
    (ExecutiveDecisionAgent(), {}),
]


class TestOutputContract:
    @pytest.mark.parametrize("agent,state", FALLBACK_CASES, ids=lambda v: getattr(v, "name", None))
    def test_fallback_output_carries_every_required_key(self, agent, state):
        result = agent.fallback(state)
        required = REQUIRED_OUTPUT_KEYS[agent.name]
        missing = required - result.output.keys()
        assert not missing, f"{agent.name} fallback output is missing {missing}"


class TestAgentResultRoundTrip:
    """Mirrors exactly what app/agents/graph/builder.py's _node/_log_run do with a
    result: dump it into the shared state's ``results`` dict and into the
    AgentLog document. If this round-trip doesn't survive, a run would silently
    corrupt the audit trail."""

    @pytest.mark.parametrize("agent,state", FALLBACK_CASES, ids=lambda v: getattr(v, "name", None))
    def test_model_dump_round_trips(self, agent, state):
        result = agent.fallback(state)
        dumped = result.model_dump()

        assert dumped["agent"] == agent.name
        assert dumped["used_fallback"] is True
        # What _log_run persists into AgentLog.messages_emitted:
        for message in result.messages:
            assert isinstance(message, AgentMessage)
            message.model_dump()  # must not raise

        # What the graph's `results` reducer stores and a downstream agent later
        # reads back via app.agents.state.result_of() must reconstruct cleanly.
        rebuilt = AgentResult(**dumped)
        assert rebuilt == result
