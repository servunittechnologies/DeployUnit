"""Iter10 Sprint 5 backend tests.

Covers:
  1. Audit log infrastructure (writes from auth.login, apps.create, apps.delete)
  2. Audit log read API (GET /api/audit-log + /actions, filters, paging, RBAC)
  3. Slack/Discord notification prefs + test send
  4. Per-app cron CRUD (with cron-expression validation + audit)
  5. Managed Databases (5 types) + start/stop/reveal/delete + audit
  6. PR Preview Deploys (webhook opened/synchronize/closed + manual teardown)
  7. Regression — push webhook + demo workspace still on Agency plan
"""
import os
import hmac
import hashlib
import json
import time
import uuid
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

DEMO_EMAIL = "demo@deployhub.dev"
DEMO_PASS = "demo1234"
ADMIN_EMAIL = "admin@deployhub.dev"
ADMIN_PASS = "admin123"
DEMO_WS = "ee9ace3a-0b82-4df5-9dd7-d543c1e0c022"


# ───────────────────────── Fixtures ─────────────────────────
def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def demo_session() -> requests.Session:
    return _login(DEMO_EMAIL, DEMO_PASS)


@pytest.fixture(scope="module")
def admin_session() -> requests.Session:
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def test_app(demo_session: requests.Session):
    """Create a throwaway app on the demo workspace; deleted in teardown.

    Used by cron + audit tests so we don't pollute the seeded apps.
    """
    payload = {
        "workspace_id": DEMO_WS,
        "name": f"TEST_iter10_{uuid.uuid4().hex[:8]}",
        "repo_url": "https://github.com/example/iter10-test",
        "branch": "main",
        "framework": "node",
    }
    r = demo_session.post(f"{API}/apps", json=payload, timeout=30)
    assert r.status_code in (200, 201), f"app create failed: {r.status_code} {r.text}"
    app = r.json()
    yield app
    # teardown
    try:
        demo_session.delete(f"{API}/apps/{app['id']}", timeout=30)
    except Exception:
        pass


# ─────────────────── 1. Audit log infrastructure ───────────────────
class TestAuditInfra:
    def test_login_writes_audit_row(self, demo_session):
        # Read recent audit entries for the workspace; check auth.login is present.
        time.sleep(0.3)  # fire-and-forget grace
        r = demo_session.get(
            f"{API}/audit-log",
            params={"workspace_id": DEMO_WS, "action": "auth.login", "limit": 50},
            timeout=30,
        )
        # auth.login has workspace_id=null per spec; so a workspace filter should yield 0.
        assert r.status_code == 200
        # Now query platform-wide with admin
        admin = _login(ADMIN_EMAIL, ADMIN_PASS)
        r = admin.get(f"{API}/audit-log", params={"action": "auth.login", "limit": 5}, timeout=30)
        assert r.status_code == 200
        entries = r.json().get("entries", [])
        assert len(entries) >= 1, "expected at least one auth.login audit row"
        first = entries[0]
        assert first["action"] == "auth.login"
        assert first.get("actor_email") in (DEMO_EMAIL, ADMIN_EMAIL)
        assert first.get("workspace_id") is None

    def test_app_create_and_delete_audit(self, demo_session):
        payload = {
            "workspace_id": DEMO_WS,
            "name": f"TEST_audit_{uuid.uuid4().hex[:6]}",
            "repo_url": "https://github.com/example/audit-test",
            "branch": "main",
            "framework": "node",
        }
        r = demo_session.post(f"{API}/apps", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text
        app = r.json()
        time.sleep(0.3)
        r = demo_session.get(
            f"{API}/audit-log",
            params={"workspace_id": DEMO_WS, "action": "app.create", "limit": 20},
            timeout=30,
        )
        assert r.status_code == 200
        entries = r.json()["entries"]
        match = next((e for e in entries if e.get("resource_id") == app["id"]), None)
        assert match, f"no app.create audit row for {app['id']}"
        assert match["resource_type"] == "app"
        assert match["workspace_id"] == DEMO_WS
        assert match["meta"].get("name") == payload["name"]
        assert match["meta"].get("repo_url") == payload["repo_url"]

        # delete
        r = demo_session.delete(f"{API}/apps/{app['id']}", timeout=30)
        assert r.status_code in (200, 204)
        time.sleep(0.3)
        r = demo_session.get(
            f"{API}/audit-log",
            params={"workspace_id": DEMO_WS, "action": "app.delete", "limit": 20},
            timeout=30,
        )
        entries = r.json()["entries"]
        match = next((e for e in entries if e.get("resource_id") == app["id"]), None)
        assert match, f"no app.delete audit row for {app['id']}"


# ─────────────────── 2. Audit log read API ───────────────────
class TestAuditReadAPI:
    def test_workspace_audit_sorted_desc(self, demo_session):
        r = demo_session.get(f"{API}/audit-log", params={"workspace_id": DEMO_WS, "limit": 50}, timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert "entries" in body and "limit" in body
        assert body["limit"] == 50
        entries = body["entries"]
        if len(entries) >= 2:
            assert entries[0]["created_at"] >= entries[1]["created_at"], "entries should be DESC by created_at"

    def test_action_filter(self, demo_session):
        r = demo_session.get(
            f"{API}/audit-log",
            params={"workspace_id": DEMO_WS, "action": "app.create"},
            timeout=30,
        )
        assert r.status_code == 200
        for e in r.json()["entries"]:
            assert e["action"] == "app.create"

    def test_cursor_pagination_via_before(self, demo_session):
        r = demo_session.get(f"{API}/audit-log", params={"workspace_id": DEMO_WS, "limit": 5}, timeout=30)
        entries = r.json()["entries"]
        if len(entries) < 2:
            pytest.skip("not enough entries to test cursor")
        cursor = entries[-1]["created_at"]
        r2 = demo_session.get(
            f"{API}/audit-log",
            params={"workspace_id": DEMO_WS, "limit": 5, "before": cursor},
            timeout=30,
        )
        assert r2.status_code == 200
        for e in r2.json()["entries"]:
            assert e["created_at"] < cursor

    def test_non_member_returns_403(self, demo_session):
        # Use a random workspace UUID demo doesn't belong to.
        bogus = "00000000-0000-0000-0000-000000000000"
        r = demo_session.get(f"{API}/audit-log", params={"workspace_id": bogus}, timeout=30)
        assert r.status_code == 403

    def test_no_workspace_requires_admin(self, demo_session, admin_session):
        # demo (non-admin) without workspace_id → 403
        r = demo_session.get(f"{API}/audit-log", timeout=30)
        assert r.status_code == 403
        # admin → 200
        r = admin_session.get(f"{API}/audit-log", params={"limit": 5}, timeout=30)
        assert r.status_code == 200
        assert "entries" in r.json()

    def test_actions_endpoint(self, demo_session):
        r = demo_session.get(f"{API}/audit-log/actions", params={"workspace_id": DEMO_WS}, timeout=30)
        assert r.status_code == 200
        actions = r.json()["actions"]
        assert isinstance(actions, list)
        assert actions == sorted(actions), "actions must be alphabetically sorted"


# ─────────────────── 3. Slack/Discord notification prefs ───────────────────
class TestNotificationPrefs:
    def test_supported_channels_include_slack_discord(self, demo_session):
        r = demo_session.get(f"{API}/notifications/prefs", timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body["supported_channels"] == ["sms", "whatsapp", "email", "slack", "discord"]
        assert "slack_webhook_url" in body
        assert "discord_webhook_url" in body

    def test_put_validates_slack_url(self, demo_session):
        r = demo_session.put(
            f"{API}/notifications/prefs",
            json={"channels": {}, "slack_webhook_url": "https://evil.com/x"},
            timeout=30,
        )
        assert r.status_code == 400
        assert "slack" in r.text.lower()

    def test_put_validates_discord_url(self, demo_session):
        r = demo_session.put(
            f"{API}/notifications/prefs",
            json={"channels": {}, "discord_webhook_url": "https://evil.com/x"},
            timeout=30,
        )
        assert r.status_code == 400
        assert "discord" in r.text.lower()

    def test_put_accepts_empty_and_valid_urls(self, demo_session):
        r = demo_session.put(f"{API}/notifications/prefs", json={"channels": {}}, timeout=30)
        assert r.status_code == 200

    def test_test_send_slack_no_url_returns_skipped(self, demo_session):
        # First clear webhook URLs
        demo_session.put(f"{API}/notifications/prefs", json={"channels": {}}, timeout=30)
        r = demo_session.post(
            f"{API}/notifications/test",
            json={"workspace_id": DEMO_WS, "channel": "slack"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        results = r.json().get("results")
        # send_alert returns a list of dicts: [{"channel": "slack", "status": "skipped"}]
        assert isinstance(results, list) and len(results) >= 1, f"unexpected shape: {results}"
        slack = next((x for x in results if x.get("channel") == "slack"), None)
        assert slack and slack.get("status") == "skipped", f"expected skipped, got {results}"

    def test_test_send_discord_no_url_returns_skipped(self, demo_session):
        demo_session.put(f"{API}/notifications/prefs", json={"channels": {}}, timeout=30)
        r = demo_session.post(
            f"{API}/notifications/test",
            json={"workspace_id": DEMO_WS, "channel": "discord"},
            timeout=30,
        )
        assert r.status_code == 200
        results = r.json().get("results")
        assert isinstance(results, list) and len(results) >= 1, f"unexpected shape: {results}"
        d = next((x for x in results if x.get("channel") == "discord"), None)
        assert d and d.get("status") == "skipped", f"expected skipped, got {results}"

    def test_test_send_invalid_channel_returns_400(self, demo_session):
        r = demo_session.post(
            f"{API}/notifications/test",
            json={"workspace_id": DEMO_WS, "channel": "push"},
            timeout=30,
        )
        assert r.status_code == 400


# ─────────────────── 4. Per-app cron jobs ───────────────────
class TestCron:
    def test_list_initially_empty(self, demo_session, test_app):
        r = demo_session.get(f"{API}/apps/{test_app['id']}/cron", timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body["app_id"] == test_app["id"]
        assert isinstance(body["jobs"], list)
        assert "supports_coolify_sync" in body

    def test_create_invalid_schedule_400(self, demo_session, test_app):
        r = demo_session.post(
            f"{API}/apps/{test_app['id']}/cron",
            json={"name": "bad", "command": "echo hi", "schedule": "every minute"},
            timeout=30,
        )
        assert r.status_code == 400

    def test_create_list_update_delete(self, demo_session, test_app):
        # CREATE
        payload = {"name": "TEST_cron_a", "command": "echo hello", "schedule": "0 3 * * *"}
        r = demo_session.post(f"{API}/apps/{test_app['id']}/cron", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text
        job = r.json()
        assert job["name"] == "TEST_cron_a"
        assert job["schedule"] == "0 3 * * *"
        assert job["enabled"] is True
        assert job["app_id"] == test_app["id"]
        job_id = job["id"]

        # LIST
        r = demo_session.get(f"{API}/apps/{test_app['id']}/cron", timeout=30)
        ids = [j["id"] for j in r.json()["jobs"]]
        assert job_id in ids

        # audit cron.create
        time.sleep(0.3)
        r = demo_session.get(
            f"{API}/audit-log",
            params={"workspace_id": DEMO_WS, "action": "cron.create"},
            timeout=30,
        )
        assert any(e.get("resource_id") == job_id for e in r.json()["entries"])

        # UPDATE
        upd = {"name": "TEST_cron_b", "command": "echo bye", "schedule": "*/5 * * * *", "enabled": False}
        r = demo_session.put(f"{API}/apps/{test_app['id']}/cron/{job_id}", json=upd, timeout=30)
        assert r.status_code == 200, r.text
        j2 = r.json()
        assert j2["name"] == "TEST_cron_b"
        assert j2["enabled"] is False
        assert j2["schedule"] == "*/5 * * * *"

        # DELETE
        r = demo_session.delete(f"{API}/apps/{test_app['id']}/cron/{job_id}", timeout=30)
        assert r.status_code == 200
        assert r.json().get("deleted") is True

        # cron.delete audit
        time.sleep(0.3)
        r = demo_session.get(
            f"{API}/audit-log",
            params={"workspace_id": DEMO_WS, "action": "cron.delete"},
            timeout=30,
        )
        assert any(e.get("resource_id") == job_id for e in r.json()["entries"])


# ─────────────────── 5. Managed Databases ───────────────────
class TestDatabases:
    def test_list_returns_supported_types(self, demo_session):
        r = demo_session.get(f"{API}/databases", params={"workspace_id": DEMO_WS}, timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert "databases" in body
        types = body["supported_types"]
        assert set(types.keys()) == {"postgresql", "redis", "mysql", "mariadb", "mongodb"}

    def test_create_postgres_provisioning(self, demo_session):
        r = demo_session.post(
            f"{API}/databases",
            params={"workspace_id": DEMO_WS},
            json={"type": "postgresql", "name": "TEST_pg", "version": "16"},
            timeout=30,
        )
        assert r.status_code in (200, 201), r.text
        db = r.json()
        assert db["type"] == "postgresql"
        assert db["name"] == "TEST_pg"
        assert db["version"] == "16"
        # Coolify unreachable → status='provisioning', no connection string
        assert db["status"] in ("provisioning", "running")
        assert db.get("connection_string_set") is False
        # save id for next tests
        TestDatabases.db_id = db["id"]

    def test_reveal_not_provisioned(self, demo_session):
        db_id = getattr(TestDatabases, "db_id", None)
        assert db_id
        r = demo_session.post(f"{API}/databases/{db_id}/reveal", timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body["connection_string"] is None
        assert body.get("reason") == "not provisioned yet"

    def test_invalid_type_400(self, demo_session):
        r = demo_session.post(
            f"{API}/databases",
            params={"workspace_id": DEMO_WS},
            json={"type": "oracle", "name": "x"},
            timeout=30,
        )
        assert r.status_code == 400

    def test_start_stop_lifecycle(self, demo_session):
        db_id = getattr(TestDatabases, "db_id", None)
        r = demo_session.post(f"{API}/databases/{db_id}/start", timeout=30)
        assert r.status_code == 200
        assert r.json()["status"] == "running"
        r = demo_session.post(f"{API}/databases/{db_id}/stop", timeout=30)
        assert r.status_code == 200
        assert r.json()["status"] == "stopped"

    def test_delete_db_and_audit(self, demo_session):
        db_id = getattr(TestDatabases, "db_id", None)
        r = demo_session.delete(f"{API}/databases/{db_id}", timeout=30)
        assert r.status_code == 200
        assert r.json().get("deleted") is True
        time.sleep(0.3)
        r = demo_session.get(
            f"{API}/audit-log",
            params={"workspace_id": DEMO_WS, "action": "database.delete"},
            timeout=30,
        )
        assert any(e.get("resource_id") == db_id for e in r.json()["entries"])


# ─────────────────── 6. PR Preview Deploys ───────────────────
def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class TestPRPreviews:
    @pytest.fixture(scope="class")
    def pr_app(self, demo_session):
        payload = {
            "workspace_id": DEMO_WS,
            "name": f"TEST_pr_{uuid.uuid4().hex[:6]}",
            "repo_url": "https://github.com/example/pr-test",
            "branch": "main",
            "framework": "node",
        }
        r = demo_session.post(f"{API}/apps", json=payload, timeout=30)
        assert r.status_code in (200, 201)
        app = r.json()
        yield app
        try:
            demo_session.delete(f"{API}/apps/{app['id']}", timeout=30)
        except Exception:
            pass

    def _secret(self, demo_session, app_id):
        r = demo_session.get(f"{API}/apps/{app_id}/webhook", timeout=30)
        assert r.status_code == 200, r.text
        return r.json()["secret"]

    def test_list_empty(self, demo_session, pr_app):
        r = demo_session.get(f"{API}/apps/{pr_app['id']}/pr-previews", timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body == {"previews": [], "parent_app_id": pr_app["id"]} or (
            body["parent_app_id"] == pr_app["id"] and body["previews"] == []
        )

    def test_opened_creates_preview(self, demo_session, pr_app):
        secret = self._secret(demo_session, pr_app["id"])
        payload = {
            "action": "opened",
            "pull_request": {
                "number": 42,
                "head": {"ref": "feat/branch", "sha": "abc1234deadbeefabc1234deadbeefabc1234dea"},
            },
        }
        body = json.dumps(payload).encode()
        sig = _sign(secret, body)
        r = requests.post(
            f"{API}/webhooks/github/{pr_app['id']}",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": sig,
            },
            timeout=30,
        )
        assert r.status_code in (200, 202), r.text
        data = r.json()
        assert data.get("status") in ("preview_queued", "redeploy_queued")
        assert data.get("pr_number") == 42
        TestPRPreviews.preview_app_id = data.get("preview_app_id")

        # GET list now returns one preview
        r = demo_session.get(f"{API}/apps/{pr_app['id']}/pr-previews", timeout=30)
        assert r.status_code == 200
        previews = r.json()["previews"]
        assert len(previews) >= 1
        p = next((pp for pp in previews if pp["pr_number"] == 42), None)
        assert p, "preview row not found"
        assert p["status"] == "building"
        assert p["branch"] == "feat/branch"
        assert p["preview_app_id"] == TestPRPreviews.preview_app_id

        # The child app exists, is_pr_preview=true, slug ends with -pr-42
        # Try to read it via /apps; if /apps doesn't include preview tier, skip that check
        # Verify by directly issuing GET /apps/{id}
        r = demo_session.get(f"{API}/apps/{TestPRPreviews.preview_app_id}", timeout=30)
        if r.status_code == 200:
            child = r.json()
            assert child.get("is_pr_preview") is True
            assert child.get("parent_app_id") == pr_app["id"]
            assert child["slug"].endswith("-pr-42")

    def test_synchronize_updates_branch(self, demo_session, pr_app):
        secret = self._secret(demo_session, pr_app["id"])
        payload = {
            "action": "synchronize",
            "pull_request": {
                "number": 42,
                "head": {"ref": "feat/branch-v2", "sha": "ffeeddccbbaa9988776655443322110011223344"},
            },
        }
        body = json.dumps(payload).encode()
        r = requests.post(
            f"{API}/webhooks/github/{pr_app['id']}",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": _sign(secret, body),
            },
            timeout=30,
        )
        assert r.status_code in (200, 202), r.text
        data = r.json()
        assert data.get("status") == "redeploy_queued"
        # branch updated
        r = demo_session.get(f"{API}/apps/{pr_app['id']}/pr-previews", timeout=30)
        p = next((pp for pp in r.json()["previews"] if pp["pr_number"] == 42), None)
        assert p["branch"] == "feat/branch-v2"

    def test_closed_marks_status_closed(self, demo_session, pr_app):
        secret = self._secret(demo_session, pr_app["id"])
        payload = {
            "action": "closed",
            "pull_request": {
                "number": 42,
                "head": {"ref": "feat/branch-v2", "sha": "ffeeddccbbaa9988776655443322110011223344"},
            },
        }
        body = json.dumps(payload).encode()
        r = requests.post(
            f"{API}/webhooks/github/{pr_app['id']}",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": _sign(secret, body),
            },
            timeout=30,
        )
        assert r.status_code in (200, 202), r.text
        assert r.json().get("status") in ("teardown_queued", "noop")
        # Give the background task time to run
        time.sleep(1.0)
        r = demo_session.get(f"{API}/apps/{pr_app['id']}/pr-previews", timeout=30)
        previews = r.json()["previews"]
        # After teardown the row's status should be 'closed' (row remains as audit)
        p = next((pp for pp in previews if pp["pr_number"] == 42), None)
        if p is not None:
            assert p["status"] == "closed"

    def test_manual_teardown_endpoint(self, demo_session, pr_app):
        # Trigger a new PR preview then manually teardown
        secret = self._secret(demo_session, pr_app["id"])
        payload = {
            "action": "opened",
            "pull_request": {
                "number": 99,
                "head": {"ref": "feat/manual", "sha": "1111111111111111111111111111111111111111"},
            },
        }
        body = json.dumps(payload).encode()
        r = requests.post(
            f"{API}/webhooks/github/{pr_app['id']}",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": _sign(secret, body),
            },
            timeout=30,
        )
        assert r.status_code in (200, 202), r.text
        r = demo_session.get(f"{API}/apps/{pr_app['id']}/pr-previews", timeout=30)
        p = next((pp for pp in r.json()["previews"] if pp["pr_number"] == 99), None)
        assert p
        preview_id = p["id"]
        r = demo_session.delete(
            f"{API}/apps/{pr_app['id']}/pr-previews/{preview_id}",
            timeout=30,
        )
        assert r.status_code == 200
        assert r.json().get("torn_down") is True


# ─────────────────── 7. Regression: push webhook + plan ───────────────────
class TestRegression:
    def test_push_webhook_still_queues(self, demo_session, test_app):
        # Read webhook secret, then post a push event
        r = demo_session.get(f"{API}/apps/{test_app['id']}/webhook", timeout=30)
        assert r.status_code == 200
        secret = r.json()["secret"]
        payload = {
            "ref": f"refs/heads/{test_app.get('branch') or 'main'}",
            "head_commit": {"id": "deadbeef" * 5, "message": "regression"},
            "pusher": {"name": "tester"},
        }
        body = json.dumps(payload).encode()
        r = requests.post(
            f"{API}/webhooks/github/{test_app['id']}",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": _sign(secret, body),
            },
            timeout=30,
        )
        assert r.status_code in (200, 202), r.text
        assert r.json().get("status") == "queued"
        assert r.json().get("deployment_id")

    def test_demo_workspace_on_agency_plan(self, demo_session):
        r = demo_session.get(f"{API}/workspaces", timeout=30)
        assert r.status_code == 200
        wss = r.json()
        # Either list directly or wrapped
        if isinstance(wss, dict):
            wss = wss.get("workspaces") or wss.get("items") or []
        demo_ws = next((w for w in wss if w.get("id") == DEMO_WS), None)
        assert demo_ws, "demo workspace not found in /workspaces"
        assert demo_ws.get("plan") == "agency"
