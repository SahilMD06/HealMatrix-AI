"""API tests for the arrival-to-discharge vertical slice."""

from __future__ import annotations

import pytest

from tests.conftest import CRITICAL_ARRIVAL, MINOR_ARRIVAL, RED_FLAG_ARRIVAL

pytestmark = [pytest.mark.api, pytest.mark.asyncio]


class TestArrival:
    async def test_critical_arrival_is_triaged_and_allocated(self, client, nurse):
        response = await client.post(
            "/api/v1/admissions/arrival", headers=nurse, json=CRITICAL_ARRIVAL
        )
        assert response.status_code == 201, response.text
        body = response.json()

        assert body["triage"]["esi_level"] == 2
        assert body["triage"]["recommended_department_code"] == "CARDIO"
        assert body["triage"]["target_response_minutes"] == 10
        assert body["bed"]["bed_id"] is not None
        assert body["bed"]["type"] in ("icu", "hdu", "emergency")
        assert body["mrn"].startswith("MRN-")
        assert body["agent_run_id"]

    async def test_red_flags_escalate_to_resuscitation(self, client, nurse):
        response = await client.post(
            "/api/v1/admissions/arrival", headers=nurse, json=RED_FLAG_ARRIVAL
        )
        triage = response.json()["triage"]
        assert triage["esi_level"] == 1
        assert len(triage["red_flags"]) >= 2
        assert triage["recommended_department_code"] == "ED"

    async def test_minor_case_receives_a_general_bed(self, client, nurse):
        response = await client.post(
            "/api/v1/admissions/arrival", headers=nurse, json=MINOR_ARRIVAL
        )
        body = response.json()
        assert body["triage"]["esi_level"] in (4, 5)
        assert body["bed"]["type"] == "general"

    async def test_rationale_explains_the_decision(self, client, nurse):
        response = await client.post(
            "/api/v1/admissions/arrival", headers=nurse, json=CRITICAL_ARRIVAL
        )
        rationale = response.json()["triage"]["rationale"]
        assert len(rationale) > 60
        assert "shock index" in rationale.lower()

    async def test_invalid_vitals_are_rejected(self, client, nurse):
        payload = {**CRITICAL_ARRIVAL, "vitals": {**CRITICAL_ARRIVAL["vitals"], "heart_rate": 999}}
        response = await client.post("/api/v1/admissions/arrival", headers=nurse, json=payload)
        assert response.status_code == 422

    async def test_arrival_without_patient_details_is_rejected(self, client, nurse):
        payload = {k: v for k, v in CRITICAL_ARRIVAL.items() if k != "patient"}
        response = await client.post("/api/v1/admissions/arrival", headers=nurse, json=payload)
        assert response.status_code == 422


class TestBedInvariants:
    async def test_maintenance_bed_is_never_assigned(self, client, nurse):
        for payload in (CRITICAL_ARRIVAL, RED_FLAG_ARRIVAL, MINOR_ARRIVAL):
            await client.post("/api/v1/admissions/arrival", headers=nurse, json=payload)

        response = await client.get("/api/v1/beds?status=maintenance", headers=nurse)
        for bed in response.json():
            assert bed["current_admission_id"] is None

    async def test_occupancy_reflects_assignments(self, client, nurse):
        before = (await client.get("/api/v1/beds/occupancy-summary", headers=nurse)).json()
        await client.post("/api/v1/admissions/arrival", headers=nurse, json=CRITICAL_ARRIVAL)
        after = (await client.get("/api/v1/beds/occupancy-summary", headers=nurse)).json()
        assert after["occupied"] == before["occupied"] + 1
        assert after["available"] == before["available"] - 1

    async def test_availability_excludes_non_assignable_beds(self, client, nurse):
        response = await client.get("/api/v1/beds/availability", headers=nurse)
        for bed in response.json():
            assert bed["status"] == "available"
            assert bed["current_admission_id"] is None


class TestQueue:
    async def test_queue_is_ordered_by_acuity(self, client, nurse):
        for payload in (MINOR_ARRIVAL, CRITICAL_ARRIVAL, RED_FLAG_ARRIVAL):
            await client.post("/api/v1/admissions/arrival", headers=nurse, json=payload)

        queue = (await client.get("/api/v1/admissions/queue", headers=nurse)).json()
        levels = [entry["triage"]["esi_level"] for entry in queue]
        assert levels == sorted(levels), f"queue out of order: {levels}"

    async def test_queue_is_enriched_for_display(self, client, nurse):
        await client.post("/api/v1/admissions/arrival", headers=nurse, json=CRITICAL_ARRIVAL)
        queue = (await client.get("/api/v1/admissions/queue", headers=nurse)).json()
        entry = queue[0]
        assert entry["patient_name"]
        assert entry["patient_age"] is not None
        assert entry["waiting_minutes"] is not None


class TestDischarge:
    async def test_discharge_closes_admission_and_frees_bed(self, client, nurse, doctor):
        arrival = (
            await client.post("/api/v1/admissions/arrival", headers=nurse, json=CRITICAL_ARRIVAL)
        ).json()

        response = await client.post(
            f"/api/v1/admissions/{arrival['admission_id']}/discharge",
            headers=doctor,
            json={"outcome": "recovered"},
        )
        assert response.status_code == 200
        assert response.json()["actual_los_days"] is not None

        summary = (await client.get("/api/v1/beds/occupancy-summary", headers=nurse)).json()
        assert summary["cleaning"] >= 1

    async def test_double_discharge_is_rejected(self, client, nurse, doctor):
        arrival = (
            await client.post("/api/v1/admissions/arrival", headers=nurse, json=CRITICAL_ARRIVAL)
        ).json()
        url = f"/api/v1/admissions/{arrival['admission_id']}/discharge"
        await client.post(url, headers=doctor, json={"outcome": "recovered"})
        response = await client.post(url, headers=doctor, json={"outcome": "recovered"})
        assert response.status_code == 409


class TestErrorHandling:
    async def test_missing_resource_returns_structured_404(self, client, nurse):
        response = await client.get(
            "/api/v1/admissions/000000000000000000000000", headers=nurse
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"

    async def test_malformed_id_returns_422_not_500(self, client, nurse):
        response = await client.get("/api/v1/admissions/not-a-valid-id", headers=nurse)
        assert response.status_code == 422

    async def test_every_response_carries_a_correlation_id(self, client, nurse):
        response = await client.get("/api/v1/beds", headers=nurse)
        assert response.headers.get("X-Correlation-ID")
        assert response.headers.get("X-Process-Time-Ms")
