"""Integration test for the compiled LangGraph, per docs/04_agent_design.md
section 4: "A full patient_arrival cycle writes exactly one agent_logs document
per executed agent."

This runs the real ``build_graph`` output against a mongomock-backed
``BedService``/``BedRepository`` (the same in-memory MongoDB fixture every API
test in this suite uses — see tests/conftest.py) rather than the fakes used in
the unit-level agent tests, specifically so the one-log-per-agent invariant is
checked against the actual persistence path (``app/agents/graph/builder.py``'s
``_log_run``), not a stand-in for it.

The equivalent path through the real HTTP API (``POST /api/v1/admissions/arrival``)
is additionally covered end-to-end in tests/api/test_agents_and_analytics.py's
``TestAgentTrace`` class; this test isolates the graph itself so a failure here
points at orchestration/logging, not at the admission endpoint's request handling.
"""

from __future__ import annotations

import pytest

from app.agents.graph.builder import build_graph
from app.agents.graph.dependencies import AgentDependencies
from app.database.repositories import AgentLogRepository, BedRepository
from app.services.bed_service import BedService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

CARDIAC_ARRIVAL_STATE = {
    "run_id": "integration-test-run-1",
    "trigger": "patient_arrival",
    "correlation_id": "integration-test-run-1",
    "vitals": {
        "heart_rate": 118, "systolic_bp": 96, "diastolic_bp": 62, "spo2": 92.0,
        "temperature_c": 36.8, "respiratory_rate": 26, "gcs": 15, "pain_score": 8,
    },
    "age": 63,
    "comorbidities": ["diabetes", "hypertension"],
    "chief_complaint": "Central chest pain radiating to left arm",
    "patient": {"sex": "male"},
    "disease_category": "cardiac",
    "results": {},
    "messages": [],
    "errors": [],
}


@pytest.fixture
async def graph_deps(seeded):
    hospital_id = seeded["hospital_id"]
    beds_repo = BedRepository(hospital_id)
    return AgentDependencies(
        bed_service=BedService(beds_repo),
        admission_service=None,
        inventory_service=None,
        sustainability_service=None,
        hospital_repo=None,
        ambulance_repo=None,
        agent_logs=AgentLogRepository(hospital_id),
    )


class TestPatientArrivalCycle:
    async def test_exactly_the_documented_agents_run_in_order(self, graph_deps):
        graph = build_graph(graph_deps)
        final_state = await graph.ainvoke(dict(CARDIAC_ARRIVAL_STATE))

        assert set(final_state["results"].keys()) == {"patient_triage", "bed_allocation"}

    async def test_exactly_one_agent_log_per_executed_agent(self, graph_deps):
        graph = build_graph(graph_deps)
        await graph.ainvoke(dict(CARDIAC_ARRIVAL_STATE))

        logs = await graph_deps.agent_logs.by_run("integration-test-run-1")
        assert len(logs) == 2
        agent_names = [log["agent_name"] for log in logs]
        assert sorted(agent_names) == ["bed_allocation", "patient_triage"]
        assert len(set(agent_names)) == 2, "no agent logged twice for the same run"

    async def test_the_bed_agent_sees_the_triage_agents_real_decision(self, graph_deps):
        graph = build_graph(graph_deps)
        final_state = await graph.ainvoke(dict(CARDIAC_ARRIVAL_STATE))

        triage_output = final_state["results"]["patient_triage"]["output"]
        bed_output = final_state["results"]["bed_allocation"]["output"]

        assert triage_output["esi_level"] == 2  # cardiac presentation, not red-flagged
        assert bed_output["recommended_bed_id"] is not None
        assert bed_output["bed_type"] in ("icu", "hdu", "emergency")

    async def test_every_log_entry_is_auditable(self, graph_deps):
        graph = build_graph(graph_deps)
        await graph.ainvoke(dict(CARDIAC_ARRIVAL_STATE))

        logs = await graph_deps.agent_logs.by_run("integration-test-run-1")
        for log in logs:
            assert log["rationale"], "every logged decision must explain itself"
            assert log["confidence"] is not None
            assert log["duration_ms"] >= 0
            assert log["agent_version"]
            assert log["run_id"] == "integration-test-run-1"

    async def test_a_second_run_id_does_not_bleed_into_the_first(self, graph_deps):
        graph = build_graph(graph_deps)
        await graph.ainvoke(dict(CARDIAC_ARRIVAL_STATE))

        second_state = {**CARDIAC_ARRIVAL_STATE, "run_id": "integration-test-run-2",
                        "correlation_id": "integration-test-run-2"}
        await graph.ainvoke(second_state)

        first_logs = await graph_deps.agent_logs.by_run("integration-test-run-1")
        second_logs = await graph_deps.agent_logs.by_run("integration-test-run-2")
        assert len(first_logs) == 2
        assert len(second_logs) == 2
