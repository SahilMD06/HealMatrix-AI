"""API tests for the sustainability, on-demand agent cycle and roster endpoints
that back the Sustainability, Executive and Admin dashboards (Phase 5)."""

from __future__ import annotations

import pytest

from tests.conftest import login

pytestmark = [pytest.mark.api, pytest.mark.asyncio]


class TestSustainabilitySummary:
    async def test_summary_returns_every_headline_section(self, client, nurse):
        response = await client.get("/api/v1/sustainability/summary", headers=nurse)
        assert response.status_code == 200, response.text
        body = response.json()
        for key in ("energy", "water", "waste_by_method_kg", "waste_by_category_kg", "carbon"):
            assert key in body

    async def test_carbon_breakdown_carries_a_sustainability_score(self, client, nurse):
        body = (await client.get("/api/v1/sustainability/summary", headers=nurse)).json()
        score = body["carbon"]["sustainability_score"]
        assert set(score) >= {"energy", "water", "waste", "carbon", "overall", "grade"}

    async def test_empty_telemetry_is_reported_honestly_not_estimated(self, client, nurse):
        """No energy/water/waste logs have been seeded for this hospital, so the
        agent's own 'no data, report zero rather than guess' behaviour should show."""
        body = (await client.get("/api/v1/sustainability/summary", headers=nurse)).json()
        assert body["carbon"]["total_kg"] == 0.0

    async def test_history_endpoints_return_lists(self, client, nurse):
        for path in ("energy-history", "water-history", "waste-history"):
            response = await client.get(f"/api/v1/sustainability/{path}", headers=nurse)
            assert response.status_code == 200
            assert isinstance(response.json(), list)


class TestRunCycle:
    async def test_nurse_cannot_trigger_a_cycle_run(self, client, nurse):
        response = await client.post("/api/v1/agents/run-cycle", headers=nurse)
        assert response.status_code == 403

    async def test_admin_can_trigger_a_cycle_run(self, client, seeded):
        admin = await login(client, "admin@t.ai")
        response = await client.post("/api/v1/agents/run-cycle", headers=admin)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["run_id"]
        assert "executive_decision" in body["results"]
        assert "carbon_intelligence" in body["results"]

    async def test_executive_synthesis_has_a_summary_and_action_plan(self, client, seeded):
        admin = await login(client, "admin@t.ai")
        body = (await client.post("/api/v1/agents/run-cycle", headers=admin)).json()
        executive_output = body["results"]["executive_decision"]["output"]
        assert executive_output["executive_summary"]
        assert isinstance(executive_output["action_plan"], list)

    async def test_a_manual_run_appears_in_the_agent_logs(self, client, seeded):
        admin = await login(client, "admin@t.ai")
        run = (await client.post("/api/v1/agents/run-cycle", headers=admin)).json()
        trace = (
            await client.get(f"/api/v1/agents/runs/{run['run_id']}", headers=admin)
        ).json()
        assert trace["agents"] == len(run["agents_run"])
        assert trace["triggered_by"] == "scheduled_cycle"


class TestUserRoster:
    async def test_admin_can_list_the_roster(self, client, seeded):
        admin = await login(client, "admin@t.ai")
        response = await client.get("/api/v1/auth/users", headers=admin)
        assert response.status_code == 200
        roster = response.json()
        assert len(roster) >= 4
        assert {row["role"] for row in roster} >= {"nurse", "doctor", "pharmacist", "admin"}

    async def test_roster_never_leaks_password_hashes(self, client, seeded):
        admin = await login(client, "admin@t.ai")
        roster = (await client.get("/api/v1/auth/users", headers=admin)).json()
        for row in roster:
            assert "password_hash" not in row

    async def test_nurse_cannot_list_the_roster(self, client, nurse):
        response = await client.get("/api/v1/auth/users", headers=nurse)
        assert response.status_code == 403

    async def test_roster_is_scoped_to_the_callers_hospital(self, client, seeded):
        admin = await login(client, "admin@t.ai")
        roster = (await client.get("/api/v1/auth/users", headers=admin)).json()
        assert all(row["email"] != "nurse@other.ai" for row in roster)
