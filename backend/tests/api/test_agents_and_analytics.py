"""API tests for the agent reasoning trail and analytics endpoints."""

from __future__ import annotations

import pytest

from tests.conftest import CRITICAL_ARRIVAL, MINOR_ARRIVAL

pytestmark = [pytest.mark.api, pytest.mark.asyncio]


class TestAgentTrace:
    async def test_every_arrival_produces_a_retrievable_trace(self, client, nurse):
        arrival = (
            await client.post("/api/v1/admissions/arrival", headers=nurse, json=CRITICAL_ARRIVAL)
        ).json()

        response = await client.get(
            f"/api/v1/agents/runs/{arrival['agent_run_id']}", headers=nurse
        )
        assert response.status_code == 200

        trace = response.json()
        assert trace["agents"] == 2
        names = {entry["agent_name"] for entry in trace["trace"]}
        assert names == {"patient_triage", "bed_allocation"}

    async def test_trace_entries_are_auditable(self, client, nurse):
        arrival = (
            await client.post("/api/v1/admissions/arrival", headers=nurse, json=CRITICAL_ARRIVAL)
        ).json()
        trace = (
            await client.get(f"/api/v1/agents/runs/{arrival['agent_run_id']}", headers=nurse)
        ).json()

        for entry in trace["trace"]:
            assert entry["rationale"], "every decision must explain itself"
            assert entry["input_summary"], "inputs must be recorded for audit"
            assert entry["confidence"] is not None
            assert entry["duration_ms"] >= 0
            assert entry["agent_version"]

    async def test_unknown_run_id_returns_404(self, client, nurse):
        response = await client.get("/api/v1/agents/runs/does-not-exist", headers=nurse)
        assert response.status_code == 404

    async def test_status_lists_all_ten_agents(self, client, nurse):
        response = await client.get("/api/v1/agents/status", headers=nurse)
        agents = response.json()
        assert len(agents) == 10
        assert {a["agent"] for a in agents} >= {"patient_triage", "executive_decision"}

    async def test_status_distinguishes_implemented_agents(self, client, nurse):
        await client.post("/api/v1/admissions/arrival", headers=nurse, json=CRITICAL_ARRIVAL)
        agents = {a["agent"]: a for a in (await client.get("/api/v1/agents/status", headers=nurse)).json()}
        assert agents["patient_triage"]["implemented"] is True
        assert agents["patient_triage"]["runs"] >= 1
        assert agents["carbon_intelligence"]["implemented"] is False

    async def test_runs_list_groups_by_run_id(self, client, nurse):
        await client.post("/api/v1/admissions/arrival", headers=nurse, json=CRITICAL_ARRIVAL)
        await client.post("/api/v1/admissions/arrival", headers=nurse, json=MINOR_ARRIVAL)

        runs = (await client.get("/api/v1/agents/runs", headers=nurse)).json()
        assert len(runs) == 2
        for run in runs:
            assert run["agents"] == 2
            assert run["triggered_by"] == "patient_arrival"


class TestAnalytics:
    async def test_overview_returns_headline_kpis(self, client, nurse):
        response = await client.get("/api/v1/analytics/overview", headers=nurse)
        assert response.status_code == 200
        for key in (
            "census", "admissions_24h", "critical_active", "occupancy_rate",
            "icu_occupancy_rate", "available_beds", "agent_decisions_24h",
        ):
            assert key in response.json()

    async def test_kpis_track_actual_activity(self, client, nurse):
        before = (await client.get("/api/v1/analytics/overview", headers=nurse)).json()
        await client.post("/api/v1/admissions/arrival", headers=nurse, json=CRITICAL_ARRIVAL)
        after = (await client.get("/api/v1/analytics/overview", headers=nurse)).json()

        assert after["census"] == before["census"] + 1
        assert after["critical_active"] == before["critical_active"] + 1
        # Two agents ran, so two decisions were logged.
        assert after["agent_decisions_24h"] == before["agent_decisions_24h"] + 2

    async def test_patient_analytics_returns_series(self, client, nurse):
        await client.post("/api/v1/admissions/arrival", headers=nurse, json=CRITICAL_ARRIVAL)
        response = await client.get("/api/v1/analytics/patients?days=7", headers=nurse)
        body = response.json()
        assert body["window_days"] == 7
        assert len(body["daily_totals"]) >= 1
        assert len(body["esi_distribution"]) >= 1

    async def test_occupancy_analytics_matches_bed_summary(self, client, nurse):
        analytics = (await client.get("/api/v1/analytics/occupancy", headers=nurse)).json()
        summary = (await client.get("/api/v1/beds/occupancy-summary", headers=nurse)).json()
        assert analytics["total_beds"] == summary["total_beds"]
        assert analytics["occupancy_rate"] == summary["occupancy_rate"]
