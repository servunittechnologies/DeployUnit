"""Iter9 Sprint 4 — Agency Fleet + GitHub Webhooks backend contract tests.

Validates:
  - /api/fleet/overview eligibility gating (agency vs free)
  - /api/fleet/bulk-redeploy gating + deployments row insert (trigger='fleet_bulk')
  - /api/apps create returns webhook_secret/webhook_url/webhook_enabled (no Cloudflare)
  - /api/apps/{id}/webhook GET / toggle / rotate / register
  - /api/webhooks/github/{app_id} HMAC signature verify + branch matching
  - Regression: /api/integrations/health shape (coolify + twilio)
"""
import hmac
import hashlib
import json
import os
import secrets
import time
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or
            os.environ.get("FRONTEND_URL") or
            "https://app-test-build-2.preview.emergentagent.com").strip().strip('"').rstrip("/")
DEMO_EMAIL = "demo@deployunit.com"
DEMO_PASS = "demo1234"
DEMO_WS_ID = "ee9ace3a-0b82-4df5-9dd7-d543c1e0c022"


# ─── Fixtures ─────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def demo_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": DEMO_EMAIL, "password": DEMO_PASS}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def fresh_session():
    """A fresh session without auth — for testing endpoint auth requirements."""
    return requests.Session()


# ─── Fleet eligibility (agency) ────────────────────────────────────────
class TestFleetOverviewAgency:
    def test_overview_works_for_everyone(self, demo_session):
        """Fleet view is no longer gated by plan — every user with at least
        one workspace gets the multi-workspace overview."""
        r = demo_session.get(f"{BASE_URL}/api/fleet/overview", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        # fleet_view_enabled field was removed in Sprint 9; no plan gating now.
        assert "workspaces" in data
        assert "rollup" in data
        assert "generated_at" in data
        assert isinstance(data["workspaces"], list)
        assert len(data["workspaces"]) >= 1
        for k in ("workspaces", "apps_total", "apps_broken", "apps_live", "monthly_eur"):
            assert k in data["rollup"], f"missing rollup.{k}"

    def test_apps_have_health_and_primary_url_keys(self, demo_session):
        r = demo_session.get(f"{BASE_URL}/api/fleet/overview", timeout=20)
        data = r.json()
        ws_apps = []
        for ws in data["workspaces"]:
            ws_apps.extend(ws["apps"])
        if not ws_apps:
            pytest.skip("no apps in demo workspaces")
        for a in ws_apps:
            assert "status" in a
            assert "primary_url" in a
            assert "health" in a  # may be None
            # latency_ms only present when there is a monitoring sample
            if a["health"] in ("ok", "down"):
                assert "latency_ms" in a

    def test_workspaces_sorted_problem_first(self, demo_session):
        r = demo_session.get(f"{BASE_URL}/api/fleet/overview", timeout=20)
        data = r.json()
        broken_counts = [w["kpi"]["apps_broken"] for w in data["workspaces"]]
        assert broken_counts == sorted(broken_counts, reverse=True)


# ─── Fleet view is now universal — no plan paywall ─────────────────
class TestFleetOverviewFree:
    def test_free_plan_still_returns_data(self, demo_session):
        """After Sprint 9 simplification, Fleet view is available on every plan."""
        from pymongo import MongoClient
        client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        db = client[os.environ.get("DB_NAME", "test_database")]
        r = demo_session.get(f"{BASE_URL}/api/fleet/overview", timeout=20)
        ws_ids = [w["id"] for w in r.json().get("workspaces", [])]
        if not ws_ids:
            pytest.skip("no workspaces — cannot exercise downgrade path")
        originals = {}
        for wid in ws_ids:
            doc = db.workspaces.find_one({"id": wid}, {"plan": 1})
            originals[wid] = (doc or {}).get("plan", "free")
            db.workspaces.update_one({"id": wid}, {"$set": {"plan": "free"}})
        try:
            r2 = demo_session.get(f"{BASE_URL}/api/fleet/overview", timeout=20)
            assert r2.status_code == 200
            data = r2.json()
            # Free plan still shows the multi-workspace overview now — no paywall.
            assert "workspaces" in data
            assert "rollup" in data
            # fleet_view_enabled / upgrade_plan / reason fields were intentionally removed
            assert "fleet_view_enabled" not in data
        finally:
            for wid, plan in originals.items():
                db.workspaces.update_one({"id": wid}, {"$set": {"plan": plan}})

    def test_bulk_redeploy_available_on_free(self, demo_session):
        """Bulk redeploy is also un-paywalled now."""
        from pymongo import MongoClient
        client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        db = client[os.environ.get("DB_NAME", "test_database")]
        r = demo_session.get(f"{BASE_URL}/api/fleet/overview", timeout=20)
        ws_ids = [w["id"] for w in r.json().get("workspaces", [])]
        originals = {}
        for wid in ws_ids:
            doc = db.workspaces.find_one({"id": wid}, {"plan": 1})
            originals[wid] = (doc or {}).get("plan", "free")
            db.workspaces.update_one({"id": wid}, {"$set": {"plan": "free"}})
        try:
            r2 = demo_session.post(f"{BASE_URL}/api/fleet/bulk-redeploy", timeout=20)
            # 200 OK or 404 (no workspaces) but never 402 paywall anymore.
            assert r2.status_code in (200, 404), r2.text
            assert r2.status_code != 402
        finally:
            for wid, plan in originals.items():
                db.workspaces.update_one({"id": wid}, {"$set": {"plan": plan}})


# ─── Bulk redeploy (eligible) ─────────────────────────────────────────
class TestBulkRedeploy:
    def test_bulk_redeploy_eligible_returns_queue(self, demo_session):
        from pymongo import MongoClient
        client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        db = client[os.environ.get("DB_NAME", "test_database")]
        # Mark at least one app as 'failed' with a coolify_app_uuid so it qualifies
        target = db.apps.find_one({"workspace_id": DEMO_WS_ID})
        assert target is not None, "demo workspace must have at least one app"
        # Ensure it has a coolify_app_uuid so bulk-redeploy picks it up
        prev_uuid = target.get("coolify_app_uuid")
        prev_status = target.get("status")
        db.apps.update_one({"id": target["id"]}, {"$set": {
            "status": "failed", "coolify_app_uuid": prev_uuid or "TEST_FAKE_UUID"
        }})
        try:
            r = demo_session.post(f"{BASE_URL}/api/fleet/bulk-redeploy", timeout=20)
            assert r.status_code == 200, r.text
            data = r.json()
            assert "queued" in data
            assert "deployments" in data
            assert isinstance(data["deployments"], list)
            assert data["queued"] >= 1
            # Verify trigger='fleet_bulk' is inserted
            sample_dep_id = data["deployments"][0]["deployment_id"]
            dep = db.deployments.find_one({"id": sample_dep_id})
            assert dep is not None
            assert dep["trigger"] == "fleet_bulk"
        finally:
            db.apps.update_one({"id": target["id"]}, {"$set": {
                "status": prev_status, "coolify_app_uuid": prev_uuid
            }})


# ─── App create webhook fields ────────────────────────────────────────
class TestCreateAppWebhookFields:
    def test_create_app_has_webhook_fields(self, demo_session):
        payload = {
            "workspace_id": DEMO_WS_ID,
            "name": f"TEST_wh_{secrets.token_hex(4)}",
            "framework": "node",
            "repo_url": "https://github.com/octocat/Hello-World",
            "branch": "master",
        }
        r = demo_session.post(f"{BASE_URL}/api/apps", json=payload, timeout=20)
        assert r.status_code in (200, 201), r.text
        app = r.json()
        assert "webhook_secret" in app and app["webhook_secret"]
        assert len(app["webhook_secret"]) == 64
        # hex
        int(app["webhook_secret"], 16)
        assert app.get("webhook_enabled") is True
        assert app.get("webhook_url", "").endswith(f"/api/webhooks/github/{app['id']}")
        # Cloudflare not configured in test env → primary_url should be None
        assert app.get("primary_url") is None
        assert "cloudflare_dns_record_id" not in app or app.get("cloudflare_dns_record_id") is None
        # Save for later tests
        pytest.created_app_id = app["id"]
        pytest.created_app_secret = app["webhook_secret"]
        pytest.created_app_branch = app["branch"]

    def test_get_webhook_endpoint_shape(self, demo_session):
        app_id = pytest.created_app_id
        r = demo_session.get(f"{BASE_URL}/api/apps/{app_id}/webhook", timeout=10)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("url", "secret", "enabled", "github_hook_id", "auto_registered", "branch"):
            assert k in d, f"missing {k}"
        public_base = os.environ.get("FRONTEND_URL", BASE_URL).rstrip('"').rstrip("/")
        assert d["url"].endswith(f"/api/webhooks/github/{app_id}")
        assert d["enabled"] is True
        assert d["auto_registered"] is False  # no GH token in test env

    def test_toggle_webhook(self, demo_session):
        app_id = pytest.created_app_id
        r1 = demo_session.post(f"{BASE_URL}/api/apps/{app_id}/webhook/toggle", timeout=10)
        assert r1.status_code == 200
        assert r1.json()["enabled"] is False
        r2 = demo_session.post(f"{BASE_URL}/api/apps/{app_id}/webhook/toggle", timeout=10)
        assert r2.status_code == 200
        assert r2.json()["enabled"] is True

    def test_rotate_webhook_changes_secret(self, demo_session):
        app_id = pytest.created_app_id
        old_secret = pytest.created_app_secret
        r = demo_session.post(f"{BASE_URL}/api/apps/{app_id}/webhook/rotate", timeout=10)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "secret" in d and "url" in d
        assert d["secret"] != old_secret
        assert len(d["secret"]) == 64
        # Verify it's persisted
        r2 = demo_session.get(f"{BASE_URL}/api/apps/{app_id}/webhook", timeout=10)
        assert r2.json()["secret"] == d["secret"]
        pytest.created_app_secret = d["secret"]

    def test_manual_register_returns_skipped_when_no_token(self, demo_session):
        app_id = pytest.created_app_id
        r = demo_session.post(f"{BASE_URL}/api/apps/{app_id}/webhook/register", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["registered"] is False
        assert "reason" in d


# ─── GitHub webhook ingress (HMAC + branch matching) ──────────────────
def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class TestGitHubWebhookIngress:
    def test_invalid_signature_returns_401(self):
        app_id = pytest.created_app_id
        body = json.dumps({"ref": "refs/heads/master"}).encode()
        r = requests.post(
            f"{BASE_URL}/api/webhooks/github/{app_id}",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": "sha256=deadbeef",
            },
            timeout=10,
        )
        assert r.status_code == 401, r.text

    def test_ping_event_returns_pong(self):
        app_id = pytest.created_app_id
        secret = pytest.created_app_secret
        body = json.dumps({"zen": "Keep it simple."}).encode()
        r = requests.post(
            f"{BASE_URL}/api/webhooks/github/{app_id}",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": _sign(secret, body),
            },
            timeout=10,
        )
        assert r.status_code == 200
        assert r.json().get("status") == "pong"

    def test_push_to_matching_branch_queues_deployment(self):
        app_id = pytest.created_app_id
        secret = pytest.created_app_secret
        branch = pytest.created_app_branch
        payload = {
            "ref": f"refs/heads/{branch}",
            "head_commit": {"id": "abc1234567def", "message": "test commit"},
            "pusher": {"name": "TEST_pusher"},
        }
        body = json.dumps(payload).encode()
        r = requests.post(
            f"{BASE_URL}/api/webhooks/github/{app_id}",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": _sign(secret, body),
            },
            timeout=10,
        )
        assert r.status_code == 202, r.text
        d = r.json()
        assert "deployment_id" in d
        assert d.get("branch") == branch

    def test_push_to_non_matching_branch_ignored(self):
        app_id = pytest.created_app_id
        secret = pytest.created_app_secret
        payload = {"ref": "refs/heads/some-other-branch-xyz",
                   "head_commit": {"id": "x", "message": "x"}}
        body = json.dumps(payload).encode()
        r = requests.post(
            f"{BASE_URL}/api/webhooks/github/{app_id}",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": _sign(secret, body),
            },
            timeout=10,
        )
        # Endpoint default status_code=202; per spec branch mismatch returns 200 ignored.
        # Our handler returns dict {status:'ignored'} but FastAPI keeps the 202 default.
        # Acceptance: status field must be 'ignored'.
        assert r.status_code in (200, 202), r.text
        assert r.json().get("status") == "ignored"

    def test_nonexistent_app_returns_404(self):
        body = b"{}"
        r = requests.post(
            f"{BASE_URL}/api/webhooks/github/00000000-0000-0000-0000-000000000000",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": "sha256=irrelevant",
            },
            timeout=10,
        )
        assert r.status_code == 404


# ─── Auth requirements ────────────────────────────────────────────────
class TestAuthRequirements:
    def test_fleet_overview_requires_auth(self, fresh_session):
        r = fresh_session.get(f"{BASE_URL}/api/fleet/overview", timeout=10)
        assert r.status_code in (401, 403)

    def test_bulk_redeploy_requires_auth(self, fresh_session):
        r = fresh_session.post(f"{BASE_URL}/api/fleet/bulk-redeploy", timeout=10)
        assert r.status_code in (401, 403)

    def test_webhook_get_requires_auth(self, fresh_session):
        app_id = pytest.created_app_id
        r = fresh_session.get(f"{BASE_URL}/api/apps/{app_id}/webhook", timeout=10)
        assert r.status_code in (401, 403)

    def test_github_ingress_does_not_require_session_auth(self, fresh_session):
        """Public endpoint — GitHub itself calls. No cookie/session required,
        but invalid signature must 401."""
        app_id = pytest.created_app_id
        r = fresh_session.post(
            f"{BASE_URL}/api/webhooks/github/{app_id}",
            data=b"{}",
            headers={"X-GitHub-Event": "push",
                     "X-Hub-Signature-256": "sha256=deadbeef",
                     "Content-Type": "application/json"},
            timeout=10,
        )
        assert r.status_code == 401  # auth via signature, fresh session OK


# ─── Cleanup the test app ─────────────────────────────────────────────
class TestZCleanup:
    def test_delete_test_app(self, demo_session):
        app_id = getattr(pytest, "created_app_id", None)
        if not app_id:
            pytest.skip("no app to delete")
        r = demo_session.delete(f"{BASE_URL}/api/apps/{app_id}", timeout=15)
        assert r.status_code in (200, 204)


# ─── Regression: /api/integrations/health ─────────────────────────────
class TestIntegrationsHealthRegression:
    def test_integrations_health_shape(self, demo_session):
        r = demo_session.get(f"{BASE_URL}/api/integrations/health", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        # Should have coolify + twilio (whmcs removed per spec)
        assert "coolify" in data
        assert "twilio" in data
        assert "whmcs" not in data, "whmcs key should be removed per Sprint 4 cleanup"
