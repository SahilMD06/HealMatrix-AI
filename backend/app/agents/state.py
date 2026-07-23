"""Shared LangGraph state.

LangGraph threads one mutable state object through every node in a run. It is a
``TypedDict`` rather than a Pydantic model because LangGraph's graph compiler reduces
state updates key-by-key using the ``Annotated`` reducers below, and that reducer
mechanism is designed around plain mappings — wrapping it in a full model would just
mean re-validating on every node without buying anything, since each agent's own
output is already validated by its Pydantic ``AgentResult``/output schema before it
ever reaches this dict.

Two trigger shapes flow through the same graph:
  - ``patient_arrival``: one patient's vitals and complaint, fanning out through
    triage -> bed allocation -> disease forecast -> carbon/executive.
  - ``scheduled_cycle``: no single patient; the sustainability and operations
    agents read live aggregates instead of ``state["vitals"]``.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def _merge_dict(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Reducer for ``results``: later writes add keys, they never blow away earlier ones."""
    merged = dict(left)
    merged.update(right)
    return merged


class HealMatrixState(TypedDict, total=False):
    # ------------------------------------------------------------- run identity
    run_id: str
    hospital_id: str
    trigger: str  # app.core.constants.TriggerType value
    correlation_id: str | None
    as_of: str  # ISO-8601 timestamp the cycle is computed as of

    # --------------------------------------------------------- patient_arrival
    patient_id: str | None
    admission_id: str | None
    patient: dict[str, Any]
    vitals: dict[str, Any]
    chief_complaint: str
    age: int
    comorbidities: list[str]
    disease_category: str | None

    # ----------------------------------------------------------- scheduled_cycle
    # Every field below is populated by the cycle-setup step (see
    # app/agents/graph/cycle.py) before the graph is invoked with trigger
    # "scheduled_cycle" — LangGraph only threads through keys declared here, so an
    # agent reading ``state.get("hourly_energy_history")`` for a key missing from
    # this TypedDict gets silently dropped, not just absent-from-input. Every key
    # an agent's analyse() reads via state.get(...) must be declared here.
    recent_daily_admission_counts: list[float]
    total_beds: int
    hourly_energy_history: list[dict[str, Any]]
    zone_setpoints: dict[str, float]
    solar_kwp: float
    hourly_water_history: list[dict[str, Any]]
    roof_area_sqm: float
    rainfall_mm_forecast: float
    waste_description: str | None
    waste_history: list[dict[str, Any]]
    sustainability_totals: dict[str, Any]
    anaesthetic_gas_kg: dict[str, float]
    network_inventory_snapshot: list[dict[str, Any]] | None
    ambulance_call: dict[str, Any] | None
    available_ambulances: list[dict[str, Any]]
    active_assignments: list[dict[str, Any]]

    # ------------------------------------------------------------- accumulated
    # Keyed by AgentName value -> that agent's AgentResult.model_dump().
    results: Annotated[dict[str, dict[str, Any]], _merge_dict]
    # The inter-agent bus. Every AgentMessage a node emits is appended here, so a
    # downstream node (or the executive crew) can filter by `to_agent`.
    messages: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[dict[str, Any]], operator.add]


def messages_for(state: HealMatrixState, agent_name: str) -> list[dict[str, Any]]:
    """Messages addressed to ``agent_name`` specifically, plus any broadcast."""
    return [
        message
        for message in state.get("messages", [])
        if message.get("to_agent") in (agent_name, None)
    ]


def result_of(state: HealMatrixState, agent_name: str) -> dict[str, Any] | None:
    """The prior result of another agent already run in this graph, if any."""
    return state.get("results", {}).get(agent_name)
