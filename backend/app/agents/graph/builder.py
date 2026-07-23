"""Builds the LangGraph ``StateGraph`` that orchestrates all ten agents.

Three routes share one graph, selected by ``state["trigger"]``:
  - ``patient_arrival``: patient_triage -> bed_allocation -> END. This is the
    vertical slice ``AdmissionService.handle_arrival`` actually runs on every
    walk-in; disease forecast, sustainability and executive synthesis are cycle-
    level concerns, not per-patient ones, so they are deliberately not on this path
    (see docs/04_agent_design.md's per-agent "Trigger" field — most of them say
    "every cycle", not "patient_arrival").
  - ``scheduled_cycle``: disease_forecast -> medicine_intelligence ->
    energy_optimization -> water_conservation -> biomedical_waste ->
    carbon_intelligence -> executive_decision -> END. Carbon runs after the four
    agents that message it (bed census, energy, water, waste); the executive crew
    runs last because it synthesises everyone else's output out of shared state.
  - ``ambulance_call`` (carried on the ``manual`` trigger, gated by the presence
    of ``state["ambulance_call"]``): ambulance_dispatch -> END.

Every node writes exactly one ``AgentLog`` document per execution — that
one-log-per-agent-per-run invariant is what the integration test in the agent test
suite checks, and it is enforced here in one place rather than scattered across
every agent.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.bed_allocation_agent import BedAllocationAgent
from app.agents.carbon_agent import CarbonIntelligenceAgent
from app.agents.crews.executive_crew import ExecutiveDecisionAgent
from app.agents.dispatch_agent import AmbulanceDispatchAgent
from app.agents.disease_forecast_agent import DiseaseForecastAgent
from app.agents.energy_agent import EnergyOptimizationAgent
from app.agents.graph.dependencies import AgentDependencies
from app.agents.medicine_agent import MedicineIntelligenceAgent
from app.agents.state import HealMatrixState
from app.agents.triage_agent import PatientTriageAgent
from app.agents.water_agent import WaterConservationAgent
from app.agents.waste_agent import BiomedicalWasteAgent
from app.core.constants import TriggerType
from app.core.logging_config import get_logger

logger = get_logger(__name__)


async def _log_run(deps: AgentDependencies, state: HealMatrixState, result: Any) -> None:
    """Every executed agent writes exactly one AgentLog document, win or degrade."""
    llm_usage = (
        {"model": result.llm_model, "prompt_tokens": 0, "completion_tokens": 0, "latency_ms": result.duration_ms}
        if result.llm_model
        else None
    )
    error = (
        {"agent": result.agent, "type": "agent_error", "message": result.error, "recoverable": True}
        if result.error
        else None
    )
    await deps.agent_logs.insert(
        {
            "run_id": state["run_id"],
            "agent_name": result.agent,
            "agent_version": result.version,
            "triggered_by": state.get("trigger", str(TriggerType.MANUAL)),
            "input_summary": {"trigger": state.get("trigger")},
            "output": result.output,
            "rationale": result.rationale,
            "confidence": result.confidence,
            "messages_emitted": [message.model_dump() for message in result.messages],
            "used_fallback": result.used_fallback,
            "llm": llm_usage,
            "duration_ms": result.duration_ms,
            "status": result.status,
            "error": error,
            "correlation_id": state.get("correlation_id"),
        }
    )


def _node(agent, deps: AgentDependencies):
    """Wraps one agent as a LangGraph node: run -> log -> partial state update."""

    async def run_node(state: HealMatrixState) -> dict:
        result = await agent.run(state)
        await _log_run(deps, state, result)
        return {
            "results": {agent.name: result.model_dump()},
            "messages": [message.model_dump() for message in result.messages],
        }

    return run_node


def _route(state: HealMatrixState) -> str:
    trigger = state.get("trigger")
    if trigger == str(TriggerType.PATIENT_ARRIVAL):
        return "patient_arrival"
    if trigger == str(TriggerType.MANUAL) and state.get("ambulance_call"):
        return "ambulance_call"
    return "scheduled_cycle"


def build_graph(deps: AgentDependencies):
    """Compile the graph. Called once per request/cycle with fresh dependencies —
    the agents themselves are cheap to construct (no I/O in ``__init__``)."""
    triage_agent = PatientTriageAgent()
    bed_agent = BedAllocationAgent(deps.bed_service, deps.admission_service)
    disease_agent = DiseaseForecastAgent()
    medicine_agent = MedicineIntelligenceAgent(deps.inventory_service)
    energy_agent = EnergyOptimizationAgent()
    water_agent = WaterConservationAgent()
    waste_agent = BiomedicalWasteAgent()
    carbon_agent = CarbonIntelligenceAgent()
    dispatch_agent = AmbulanceDispatchAgent(deps.hospital_repo, deps.ambulance_repo)
    executive_agent = ExecutiveDecisionAgent()

    graph = StateGraph(HealMatrixState)
    graph.add_node("patient_triage", _node(triage_agent, deps))
    graph.add_node("bed_allocation", _node(bed_agent, deps))
    graph.add_node("disease_forecast", _node(disease_agent, deps))
    graph.add_node("medicine_intelligence", _node(medicine_agent, deps))
    graph.add_node("energy_optimization", _node(energy_agent, deps))
    graph.add_node("water_conservation", _node(water_agent, deps))
    graph.add_node("biomedical_waste", _node(waste_agent, deps))
    graph.add_node("carbon_intelligence", _node(carbon_agent, deps))
    graph.add_node("ambulance_dispatch", _node(dispatch_agent, deps))
    graph.add_node("executive_decision", _node(executive_agent, deps))

    graph.add_conditional_edges(
        START,
        _route,
        {
            "patient_arrival": "patient_triage",
            "scheduled_cycle": "disease_forecast",
            "ambulance_call": "ambulance_dispatch",
        },
    )

    # patient_arrival branch
    graph.add_edge("patient_triage", "bed_allocation")
    graph.add_edge("bed_allocation", END)

    # scheduled_cycle branch
    graph.add_edge("disease_forecast", "medicine_intelligence")
    graph.add_edge("medicine_intelligence", "energy_optimization")
    graph.add_edge("energy_optimization", "water_conservation")
    graph.add_edge("water_conservation", "biomedical_waste")
    graph.add_edge("biomedical_waste", "carbon_intelligence")
    graph.add_edge("carbon_intelligence", "executive_decision")
    graph.add_edge("executive_decision", END)

    # ambulance_call branch
    graph.add_edge("ambulance_dispatch", END)

    return graph.compile()
