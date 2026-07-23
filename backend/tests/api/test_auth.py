"""API tests for authentication, authorisation and tenant isolation."""

from __future__ import annotations

import pytest

from tests.conftest import PASSWORD, login

pytestmark = [pytest.mark.api, pytest.mark.asyncio]


class TestLogin:
    async def test_valid_credentials_return_tokens(self, client):
        response = await client.post(
            "/api/v1/auth/login", json={"email": "nurse@t.ai", "password": PASSWORD}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["access_token"] and body["refresh_token"]
        assert body["token_type"] == "bearer"
        assert body["user"]["role"] == "nurse"

    async def test_password_hash_is_never_returned(self, client):
        response = await client.post(
            "/api/v1/auth/login", json={"email": "nurse@t.ai", "password": PASSWORD}
        )
        assert "password_hash" not in response.text

    async def test_wrong_password_is_rejected(self, client):
        response = await client.post(
            "/api/v1/auth/login", json={"email": "nurse@t.ai", "password": "wrong-password"}
        )
        assert response.status_code == 401

    async def test_unknown_email_gives_identical_error(self, client):
        """Prevents using the endpoint to enumerate valid accounts."""
        unknown = await client.post(
            "/api/v1/auth/login", json={"email": "nobody@t.ai", "password": PASSWORD}
        )
        wrong = await client.post(
            "/api/v1/auth/login", json={"email": "nurse@t.ai", "password": "wrong-password"}
        )
        assert unknown.status_code == wrong.status_code == 401
        assert unknown.json()["error"]["message"] == wrong.json()["error"]["message"]

    async def test_token_carries_role_and_tenant(self, client):
        response = await client.post(
            "/api/v1/auth/login", json={"email": "nurse@t.ai", "password": PASSWORD}
        )
        user = response.json()["user"]
        assert user["hospital_id"] is not None
        assert user["default_dashboard"] == "/dashboard/emergency"


class TestTokens:
    async def test_protected_route_requires_a_token(self, client):
        assert (await client.get("/api/v1/auth/me")).status_code == 401

    async def test_garbage_token_is_rejected(self, client):
        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert response.status_code == 401

    async def test_refresh_issues_a_new_access_token(self, client):
        login_response = await client.post(
            "/api/v1/auth/login", json={"email": "nurse@t.ai", "password": PASSWORD}
        )
        refresh_token = login_response.json()["refresh_token"]
        response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert response.status_code == 200
        assert response.json()["access_token"]

    async def test_access_token_cannot_be_used_to_refresh(self, client):
        """Token type confusion is a classic JWT flaw; it must be rejected explicitly."""
        login_response = await client.post(
            "/api/v1/auth/login", json={"email": "nurse@t.ai", "password": PASSWORD}
        )
        access_token = login_response.json()["access_token"]
        response = await client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
        assert response.status_code == 401


class TestRoleBasedAccess:
    async def test_nurse_cannot_create_users(self, client, nurse):
        response = await client.post(
            "/api/v1/auth/register",
            headers=nurse,
            json={
                "email": "new@t.ai", "password": "Passw0rd123",
                "full_name": "New User", "role": "doctor",
            },
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"

    async def test_admin_can_create_users(self, client):
        admin = await login(client, "admin@t.ai")
        response = await client.post(
            "/api/v1/auth/register",
            headers=admin,
            json={
                "email": "new@t.ai", "password": "Passw0rd123",
                "full_name": "New User", "role": "doctor",
            },
        )
        assert response.status_code == 201

    async def test_nurse_cannot_discharge(self, client, nurse):
        response = await client.post(
            "/api/v1/admissions/000000000000000000000000/discharge",
            headers=nurse,
            json={"outcome": "recovered"},
        )
        assert response.status_code == 403

    async def test_duplicate_email_is_rejected(self, client):
        admin = await login(client, "admin@t.ai")
        payload = {
            "email": "nurse@t.ai", "password": "Passw0rd123",
            "full_name": "Duplicate", "role": "doctor",
        }
        response = await client.post("/api/v1/auth/register", headers=admin, json=payload)
        assert response.status_code == 409

    async def test_weak_password_is_rejected(self, client):
        admin = await login(client, "admin@t.ai")
        response = await client.post(
            "/api/v1/auth/register",
            headers=admin,
            json={
                "email": "weak@t.ai", "password": "12345678",
                "full_name": "Weak", "role": "doctor",
            },
        )
        assert response.status_code == 422


class TestTenantIsolation:
    async def test_cannot_request_another_hospitals_data(self, client, seeded):
        other = await login(client, "nurse@other.ai")
        response = await client.get(
            f"/api/v1/beds?hospital_id={seeded['hospital_id']}", headers=other
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "tenant_isolation_violation"

    async def test_scoped_queries_return_only_own_tenant(self, client, nurse):
        other = await login(client, "nurse@other.ai")
        ours = await client.get("/api/v1/beds", headers=nurse)
        theirs = await client.get("/api/v1/beds", headers=other)
        assert len(ours.json()) > 0
        assert len(theirs.json()) == 0
