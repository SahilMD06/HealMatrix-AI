"""Graph tests for app/agents/graph/builder.py.

Per docs/04_agent_design.md section 4: "Conditional edges route correctly for
each trigger type; the conflict loop terminates after two iterations." This
builder's ``scheduled_cycle`` branch is a straight-line chain with no cyclical
conflict-resolution loop back into itself (see the module docstring in
app/agents/graph/builder.py) — the spec's generic "conflict resolution" concern
is instead handled entirely inside the Executive Decision Agent's own
prioritisation logic (patient safety > regulatory compliance > cost >
sustainability), which is tested separately in the fallback/contract suites.
What *is* checked here, honestly rather than against an aspirational loop that
doesn't exist in this implementation, is the property that actually matters for
"does it terminate": the compiled graph is a DAG. A cycle would hang a Celery
worker on every scheduled run.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agents.graph.builder import _route, build_graph
from app.core.constants import TriggerType

pytestmark = pytest.mark.unit

ALL_TEN_NODES = {
    "patient_triage", "bed_allocation", "disease_forecast", "medicine_intelligence",
    "energy_optimization", "water_conservation", "biomedical_waste",
    "carbon_intelligence", "ambulance_dispatch", "executive_decision",
}


def dummy_dependencies() -> SimpleNamespace:
    """Construction-only stand-in: build_graph's agent constructors merely store
    these references, never call them, so a real BedService/HospitalRepository
    is not needed just to compile and inspect the graph's wiring."""
    return SimpleNamespace(
        bed_service=None, admission_service=None, inventory_service=None,
        sustainability_service=None, hospital_repo=None, ambulance_repo=None,
        agent_logs=None,
    )


class TestRouting:
    @pytest.mark.parametrize(
        ("trigger", "ambulance_call", "expected"),
        [
            (str(TriggerType.PATIENT_ARRIVAL), None, "patient_arrival"),
            (str(TriggerType.SCHEDULED_CYCLE), None, "scheduled_cycle"),
            (str(TriggerType.MANUAL), {"longitude": 77.5, "latitude": 12.9, "priority": 1}, "ambulance_call"),
            (str(TriggerType.MANUAL), None, "scheduled_cycle"),  # manual with no call falls through
            (str(TriggerType.SCENARIO), None, "scheduled_cycle"),  # anything unrecognised defaults safely
        ],
    )
    def test_route_selects_the_correct_branch(self, trigger, ambulance_call, expected):
        state = {"trigger": trigger, "ambulance_call": ambulance_call}
        assert _route(state) == expected

    def test_missing_trigger_defaults_to_scheduled_cycle(self):
        assert _route({}) == "scheduled_cycle"


class TestGraphTopology:
    def test_every_agent_is_wired_as_a_node(self):
        graph = build_graph(dummy_dependencies())
        nodes = set(graph.get_graph().nodes) - {"__start__", "__end__"}
        assert nodes == ALL_TEN_NODES

    def test_conditional_entry_covers_all_three_triggers(self):
        graph = build_graph(dummy_dependencies())
        conditional_targets = {
            edge.target for edge in graph.get_graph().edges
            if edge.source == "__start__" and edge.conditional
        }
        assert conditional_targets == {"patient_triage", "disease_forecast", "ambulance_dispatch"}

    def test_patient_arrival_branch_is_the_documented_vertical_slice(self):
        """Per the spec: triage -> bed allocation -> END, nothing else on this path."""
        graph = build_graph(dummy_dependencies())
        edges = {(e.source, e.target) for e in graph.get_graph().edges if not e.conditional}
        assert ("patient_triage", "bed_allocation") in edges
        assert ("bed_allocation", "__end__") in edges

    def test_scheduled_cycle_branch_ends_with_the_executive_synthesis(self):
        graph = build_graph(dummy_dependencies())
        edges = {(e.source, e.target) for e in graph.get_graph().edges if not e.conditional}
        assert ("carbon_intelligence", "executive_decision") in edges
        assert ("executive_decision", "__end__") in edges

    def test_the_compiled_graph_is_a_dag(self):
        """A cycle anywhere would hang every scheduled Celery run forever. Depth-first
        search from every node must never revisit a node still on its own stack."""
        graph = build_graph(dummy_dependencies())
        adjacency: dict[str, list[str]] = {}
        for edge in graph.get_graph().edges:
            adjacency.setdefault(edge.source, []).append(edge.target)

        WHITE, GREY, BLACK = 0, 1, 2
        colour = {node: WHITE for node in graph.get_graph().nodes}

        def visit(node: str) -> None:
            colour[node] = GREY
            for neighbour in adjacency.get(node, []):
                if colour[neighbour] == GREY:
                    pytest.fail(f"cycle detected: {node} -> {neighbour}")
                if colour[neighbour] == WHITE:
                    visit(neighbour)
            colour[node] = BLACK

        for node in list(graph.get_graph().nodes):
            if colour[node] == WHITE:
                visit(node)
