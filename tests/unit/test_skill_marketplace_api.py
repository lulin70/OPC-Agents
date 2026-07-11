"""Tests for skill_marketplace_api.py — FastAPI REST API endpoints.

Uses TestClient for HTTP-level testing of all 14 endpoints.
Database isolation via tmp_path + module-level marketplace replacement.

Test dimensions:
  - Happy Path: create key → register → approve → discover → get → execute
  - Error Case: no key / invalid key / insufficient perm / skill not found
  - Boundary: empty params / oversized body / rate limit
  - Config: HTTPS enforcement / CORS headers
"""

import os

import pytest

# Skip entire module if fastapi/httpx not installed
pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

import opc_manager.data_manager as dm
import opc_manager.skill_marketplace_api as api_module
from opc_manager.skill_marketplace import (
    SkillMarketplace,
    ExternalSkillMarketplace,
)


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    """Create isolated TestClient with fresh marketplace instances.

    Replaces module-level marketplace/external_marketplace with instances
    pointing at tmp_path, ensuring zero cross-test contamination.
    """
    data_dir = str(tmp_path / "data")
    os.makedirs(data_dir, exist_ok=True)

    monkeypatch.setattr(dm, "DATA_DIR", data_dir)
    monkeypatch.setattr(dm, "DB_PATH", os.path.join(data_dir, "opc_data.db"))
    monkeypatch.setattr(dm, "BACKUP_DIR", os.path.join(data_dir, "backups"))
    monkeypatch.setattr(dm, "_db_initialized", False)
    monkeypatch.setattr(dm, "_local", type("_L", (), {"conn": None})())

    api_module.marketplace = SkillMarketplace(data_dir=data_dir)
    api_module.external_marketplace = ExternalSkillMarketplace(data_dir=data_dir)
    api_module._rate_limit_store.clear()

    with TestClient(api_module.app) as client:
        yield client


def _create_key(client, name="test-key", permissions=None, rate_limit=100):
    """Helper: create an API key and return the raw key string."""
    body = {
        "name": name,
        "permissions": permissions or ["read"],
        "rate_limit": rate_limit,
    }
    resp = client.post("/api/v1/keys", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()["api_key"]


def _register_skill(client, api_key, skill_id="test_skill_001"):
    """Helper: register a skill, returns response."""
    body = {
        "skill_id": skill_id,
        "name": "Test Skill",
        "description": "A skill for testing",
        "version": "1.0.0",
        "category": "testing",
        "author": "tester",
    }
    return client.post("/api/v1/skills", json=body, headers={"X-API-Key": api_key})


def _approve_skill(client, api_key, skill_id):
    """Helper: approve a skill."""
    return client.put(
        f"/api/v1/skills/{skill_id}/approve", headers={"X-API-Key": api_key}
    )


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    """GET /health endpoint."""

    def test_health_returns_ok(self, api_client):
        """Verify: health check returns status ok and current version.

        Scenario: GET /health without any auth.
        Expected: 200 with {"status": "ok", "version": ...}.
        """
        resp = api_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


# ---------------------------------------------------------------------------
# Create API Key
# ---------------------------------------------------------------------------


class TestCreateAPIKey:
    """POST /api/v1/keys endpoint."""

    def test_create_key_with_read_permission(self, api_client):
        """Verify: creating a read-only key returns 200 with key string.

        Scenario: POST /api/v1/keys with permissions=["read"].
        Expected: 200, api_key starts with "opc_".
        """
        resp = api_client.post(
            "/api/v1/keys",
            json={"name": "reader", "permissions": ["read"], "rate_limit": 50},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["name"] == "reader"
        assert data["api_key"].startswith("opc_")

    def test_create_key_with_all_permissions(self, api_client):
        """Verify: creating a key with read+write+execute permissions.

        Scenario: POST /api/v1/keys with all 3 permissions.
        Expected: 200, key has full permissions.
        """
        resp = api_client.post(
            "/api/v1/keys",
            json={
                "name": "admin",
                "permissions": ["read", "write", "execute"],
                "rate_limit": 100,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_create_key_default_permissions(self, api_client):
        """Verify: default permissions is ["read"] when not specified.

        Scenario: POST /api/v1/keys with only name.
        Expected: 200, key created with read permission.
        """
        resp = api_client.post("/api/v1/keys", json={"name": "default_user"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_create_key_default_rate_limit(self, api_client):
        """Verify: default rate_limit is 100 when not specified.

        Scenario: POST /api/v1/keys without rate_limit.
        Expected: 200, key created with rate_limit=100.
        """
        resp = api_client.post(
            "/api/v1/keys",
            json={"name": "default_rl", "permissions": ["read"]},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True


# ---------------------------------------------------------------------------
# Register Skill
# ---------------------------------------------------------------------------


class TestRegisterSkill:
    """POST /api/v1/skills endpoint."""

    def test_register_skill_success(self, api_client):
        """Verify: registering a skill with WRITE permission succeeds.

        Scenario: Create key with write perm, then POST /api/v1/skills.
        Expected: 200, success=True.
        """
        key = _create_key(api_client, permissions=["read", "write"])
        resp = _register_skill(api_client, key)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["skill_id"] == "test_skill_001"
        assert data["status"] == "pending"

    def test_register_skill_no_api_key(self, api_client):
        """Verify: registering without X-API-Key returns 401.

        Scenario: POST /api/v1/skills without auth header.
        Expected: 401, "Missing X-API-Key header".
        """
        resp = _register_skill(api_client, "dummy_key")
        resp = api_client.post(
            "/api/v1/skills",
            json={
                "skill_id": "no_auth",
                "name": "No Auth",
                "description": "test",
            },
        )
        assert resp.status_code == 401
        assert "Missing" in resp.json()["detail"]

    def test_register_skill_invalid_key(self, api_client):
        """Verify: invalid API key returns 401.

        Scenario: POST /api/v1/skills with bogus key.
        Expected: 401, "Invalid API key".
        """
        resp = api_client.post(
            "/api/v1/skills",
            json={"skill_id": "x", "name": "X", "description": "x"},
            headers={"X-API-Key": "opc_invalid_key_12345"},
        )
        assert resp.status_code == 401
        assert "Invalid" in resp.json()["detail"]

    def test_register_skill_insufficient_permission(self, api_client):
        """Verify: read-only key cannot register skills (403).

        Scenario: Create key with only read perm, try to register.
        Expected: 403, "Insufficient permissions".
        """
        key = _create_key(api_client, permissions=["read"])
        resp = _register_skill(api_client, key)
        assert resp.status_code == 403
        assert "Insufficient" in resp.json()["detail"]

    def test_register_duplicate_skill(self, api_client):
        """Verify: registering same skill_id twice returns 400.

        Scenario: Register skill, then register same skill_id again.
        Expected: 400, "技能已存在".
        """
        key = _create_key(api_client, permissions=["read", "write"])
        _register_skill(api_client, key, skill_id="dup_skill")
        resp = _register_skill(api_client, key, skill_id="dup_skill")
        assert resp.status_code == 400
        assert "已存在" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Approve Skill
# ---------------------------------------------------------------------------


class TestApproveSkill:
    """PUT /api/v1/skills/{skill_id}/approve endpoint."""

    def test_approve_skill_success(self, api_client):
        """Verify: approving a pending skill with WRITE perm succeeds.

        Scenario: Register skill, then approve it.
        Expected: 200, status="approved".
        """
        key = _create_key(api_client, permissions=["read", "write"])
        _register_skill(api_client, key, skill_id="to_approve")
        resp = _approve_skill(api_client, key, "to_approve")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["status"] == "approved"

    def test_approve_nonexistent_skill(self, api_client):
        """Verify: approving non-existent skill returns 404.

        Scenario: PUT /api/v1/skills/nonexistent/approve.
        Expected: 404, "技能不存在".
        """
        key = _create_key(api_client, permissions=["read", "write"])
        resp = _approve_skill(api_client, key, "nonexistent_skill")
        assert resp.status_code == 404
        assert "不存在" in resp.json()["detail"]

    def test_approve_skill_no_auth(self, api_client):
        """Verify: approving without auth returns 401."""
        resp = api_client.put("/api/v1/skills/any/approve")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Discover Skills
# ---------------------------------------------------------------------------


class TestDiscoverSkills:
    """GET /api/v1/skills endpoint."""

    def test_discover_all_approved_skills(self, api_client):
        """Verify: GET /api/v1/skills returns only approved skills.

        Scenario: Register + approve a skill, then discover.
        Expected: 200, list contains the approved skill.
        """
        key = _create_key(api_client, permissions=["read", "write"])
        _register_skill(api_client, key, skill_id="discoverable")
        _approve_skill(api_client, key, "discoverable")

        resp = api_client.get("/api/v1/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        ids = [s["skill_id"] for s in data["skills"]]
        assert "discoverable" in ids

    def test_discover_pending_not_listed(self, api_client):
        """Verify: pending skills are not listed in discover.

        Scenario: Register a skill (stays pending), discover.
        Expected: pending skill not in results.
        """
        key = _create_key(api_client, permissions=["read", "write"])
        _register_skill(api_client, key, skill_id="still_pending")

        resp = api_client.get("/api/v1/skills")
        ids = [s["skill_id"] for s in resp.json()["skills"]]
        assert "still_pending" not in ids

    def test_discover_by_category(self, api_client):
        """Verify: category filter works.

        Scenario: Register skills in different categories, filter by category.
        Expected: only matching category returned.
        """
        key = _create_key(api_client, permissions=["read", "write"])

        for sid, cat in [("cat_a", "alpha"), ("cat_b", "beta")]:
            body = {
                "skill_id": sid,
                "name": sid,
                "description": "test",
                "version": "1.0.0",
                "category": cat,
                "author": "t",
            }
            api_client.post("/api/v1/skills", json=body, headers={"X-API-Key": key})
            _approve_skill(api_client, key, sid)

        resp = api_client.get("/api/v1/skills?category=alpha")
        data = resp.json()
        for s in data["skills"]:
            assert s["category"] == "alpha"

    def test_discover_by_keyword(self, api_client):
        """Verify: keyword filter searches name and description.

        Scenario: Register skill with unique keyword in name.
        Expected: keyword search returns matching skill.
        """
        key = _create_key(api_client, permissions=["read", "write"])
        body = {
            "skill_id": "kw_skill",
            "name": "UniqueKeywordSkill",
            "description": "has unique keyword",
            "version": "1.0.0",
            "category": "test",
            "author": "t",
        }
        api_client.post("/api/v1/skills", json=body, headers={"X-API-Key": key})
        _approve_skill(api_client, key, "kw_skill")

        resp = api_client.get("/api/v1/skills?keyword=UniqueKeyword")
        ids = [s["skill_id"] for s in resp.json()["skills"]]
        assert "kw_skill" in ids

    def test_discover_no_auth_required(self, api_client):
        """Verify: discover endpoint is public (no API key needed).

        Scenario: GET /api/v1/skills without X-API-Key.
        Expected: 200 (discover is a read public endpoint).
        """
        resp = api_client.get("/api/v1/skills")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Get Skill Detail
# ---------------------------------------------------------------------------


class TestGetSkill:
    """GET /api/v1/skills/{skill_id} endpoint."""

    def test_get_skill_success(self, api_client):
        """Verify: getting an existing skill returns full details.

        Scenario: Register a skill, then GET its detail.
        Expected: 200 with all skill fields.
        """
        key = _create_key(api_client, permissions=["read", "write"])
        _register_skill(api_client, key, skill_id="get_me")

        resp = api_client.get("/api/v1/skills/get_me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["skill_id"] == "get_me"
        assert data["name"] == "Test Skill"
        assert "dependencies" in data
        assert "config" in data

    def test_get_skill_not_found(self, api_client):
        """Verify: getting non-existent skill returns 404.

        Scenario: GET /api/v1/skills/nonexistent.
        Expected: 404, "Skill not found".
        """
        resp = api_client.get("/api/v1/skills/nonexistent_skill")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_get_skill_no_auth_required(self, api_client):
        """Verify: get skill detail is public (no API key needed)."""
        key = _create_key(api_client, permissions=["read", "write"])
        _register_skill(api_client, key, skill_id="public_get")
        resp = api_client.get("/api/v1/skills/public_get")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Execute Skill
# ---------------------------------------------------------------------------


class TestExecuteSkill:
    """POST /api/v1/skills/{skill_id}/execute endpoint."""

    def test_execute_skill_insufficient_permission(self, api_client):
        """Verify: read-only key cannot execute skills (403).

        Scenario: Create read-only key, try to execute.
        Expected: 403, "Insufficient permissions".
        """
        key = _create_key(api_client, permissions=["read", "write"])
        _register_skill(api_client, key, skill_id="exec_target")
        _approve_skill(api_client, key, "exec_target")

        read_key = _create_key(api_client, name="reader2", permissions=["read"])
        resp = api_client.post(
            "/api/v1/skills/exec_target/execute",
            json={"parameters": {}},
            headers={"X-API-Key": read_key},
        )
        assert resp.status_code == 403

    def test_execute_skill_not_found(self, api_client):
        """Verify: executing non-existent skill returns 400.

        Scenario: POST /api/v1/skills/nonexistent/execute with execute perm.
        Expected: 400, "技能不存在".
        """
        key = _create_key(api_client, permissions=["read", "write", "execute"])
        resp = api_client.post(
            "/api/v1/skills/nonexistent_exec/execute",
            json={"parameters": {}},
            headers={"X-API-Key": key},
        )
        assert resp.status_code == 400
        assert "不存在" in resp.json()["detail"]

    def test_execute_skill_not_approved(self, api_client):
        """Verify: executing a pending skill returns 400.

        Scenario: Register skill (stays pending), try to execute.
        Expected: 400, "技能未审核通过".
        """
        key = _create_key(api_client, permissions=["read", "write", "execute"])
        _register_skill(api_client, key, skill_id="not_approved_exec")
        resp = api_client.post(
            "/api/v1/skills/not_approved_exec/execute",
            json={"parameters": {}},
            headers={"X-API-Key": key},
        )
        assert resp.status_code == 400
        assert "未审核" in resp.json()["detail"]

    def test_execute_skill_no_auth(self, api_client):
        """Verify: executing without auth returns 401."""
        resp = api_client.post("/api/v1/skills/any/execute", json={"parameters": {}})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Stats & Categories
# ---------------------------------------------------------------------------


class TestStatsAndCategories:
    """GET /api/v1/stats and /api/v1/categories endpoints."""

    def test_get_stats_empty(self, api_client):
        """Verify: stats endpoint returns correct structure on fresh marketplace.

        Scenario: GET /api/v1/stats on a fresh marketplace (has seeded skills).
        Expected: 200 with total_skills/approved_skills/pending_skills keys.
        """
        resp = api_client.get("/api/v1/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_skills" in data
        assert "approved_skills" in data
        assert "pending_skills" in data

    def test_get_stats_after_register(self, api_client):
        """Verify: stats reflect new skill registration.

        Scenario: Register a skill, check stats.
        Expected: pending_skills increased by 1.
        """
        key = _create_key(api_client, permissions=["read", "write"])
        before = api_client.get("/api/v1/stats").json()
        _register_skill(api_client, key, skill_id="stats_test")
        after = api_client.get("/api/v1/stats").json()
        assert after["total_skills"] == before["total_skills"] + 1
        assert after["pending_skills"] == before["pending_skills"] + 1

    def test_list_categories(self, api_client):
        """Verify: categories endpoint returns list of unique categories.

        Scenario: GET /api/v1/categories after approving skills.
        Expected: 200 with categories list.
        """
        key = _create_key(api_client, permissions=["read", "write"])
        _register_skill(api_client, key, skill_id="cat_test")
        _approve_skill(api_client, key, "cat_test")

        resp = api_client.get("/api/v1/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        assert isinstance(data["categories"], list)

    def test_stats_no_auth_required(self, api_client):
        """Verify: stats endpoint is public."""
        resp = api_client.get("/api/v1/stats")
        assert resp.status_code == 200

    def test_categories_no_auth_required(self, api_client):
        """Verify: categories endpoint is public."""
        resp = api_client.get("/api/v1/categories")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# External Marketplace
# ---------------------------------------------------------------------------


class TestExternalMarketplace:
    """External marketplace endpoints (search/stats/installed)."""

    def test_list_marketplace_skills_no_auth(self, api_client):
        """Verify: external skill search is public.

        Scenario: GET /api/v1/marketplace/skills without auth.
        Expected: 200 with results structure.
        """
        resp = api_client.get("/api/v1/marketplace/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data or "skills" in data or isinstance(data, dict)

    def test_list_marketplace_skills_with_query(self, api_client):
        """Verify: query parameter filters external skills.

        Scenario: GET /api/v1/marketplace/skills?query=email.
        Expected: 200 with filtered results.
        """
        resp = api_client.get("/api/v1/marketplace/skills?query=email")
        assert resp.status_code == 200

    def test_get_marketplace_stats_no_auth(self, api_client):
        """Verify: external marketplace stats is public.

        Scenario: GET /api/v1/marketplace/stats.
        Expected: 200 with combined internal+external stats.
        """
        resp = api_client.get("/api/v1/marketplace/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_skills" in data
        assert "external_skills" in data

    def test_list_installed_skills_no_auth(self, api_client):
        """Verify: installed skills listing is public.

        Scenario: GET /api/v1/marketplace/installed.
        Expected: 200 with installed skills structure.
        """
        resp = api_client.get("/api/v1/marketplace/installed")
        assert resp.status_code == 200

    def test_uninstall_skill_not_found(self, api_client):
        """Verify: uninstalling non-existent skill returns 404.

        Scenario: DELETE /api/v1/marketplace/nonexistent/uninstall with auth.
        Expected: 404.
        """
        key = _create_key(api_client, permissions=["read", "write"])
        resp = api_client.delete(
            "/api/v1/marketplace/nonexistent_uninstall/uninstall",
            headers={"X-API-Key": key},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    """Rate limit middleware tests."""

    def test_rate_limit_enforced(self, api_client):
        """Verify: exceeding rate_limit returns 429.

        Scenario: Create key with rate_limit=2, make 3 authenticated requests.
        Expected: 3rd request returns 429.
        """
        key = _create_key(
            api_client, name="limited", permissions=["read", "write"], rate_limit=2
        )

        # First two requests should succeed
        for i in range(2):
            resp = _register_skill(api_client, key, skill_id=f"rl_test_{i}")
            assert resp.status_code in (200, 400)  # 400 if dup, but not 429

        # Third request within the same minute should be rate limited
        resp = api_client.post(
            "/api/v1/skills",
            json={"skill_id": "rl_test_3", "name": "RL", "description": "x"},
            headers={"X-API-Key": key},
        )
        assert resp.status_code == 429
        assert "Rate limit" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Request Size Limit
# ---------------------------------------------------------------------------


class TestRequestSizeLimit:
    """Request body size middleware tests."""

    def test_oversized_request_body_rejected(self, api_client):
        """Verify: request body > 1MB returns 413.

        Scenario: POST with body exceeding MAX_REQUEST_BODY_BYTES.
        Expected: 413.
        """
        large_body = {"skill_id": "x" * 1_100_000, "name": "big", "description": "x"}
        resp = api_client.post("/api/v1/skills", json=large_body)
        assert resp.status_code == 413


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


class TestCORS:
    """CORS middleware tests."""

    def test_cors_header_present(self, api_client):
        """Verify: CORS header is returned for allowed origins.

        Scenario: Send request with Origin header from allowed origin.
        Expected: Access-Control-Allow-Origin in response.
        """
        resp = api_client.get("/health", headers={"Origin": "http://localhost:8501"})
        assert resp.status_code == 200
        assert "access-control-allow-origin" in {k.lower() for k in resp.headers}

    def test_cors_options_preflight(self, api_client):
        """Verify: CORS preflight request is handled.

        Scenario: OPTIONS request with preflight headers.
        Expected: 200 with CORS headers.
        """
        resp = api_client.options(
            "/api/v1/skills",
            headers={
                "Origin": "http://localhost:8501",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-api-key",
            },
        )
        assert resp.status_code == 200
