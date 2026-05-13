"""Iter19 — Central notification dispatch pipeline.

Tests the new dispatch_event() pipeline through:
- POST /api/admin/notifications/fire  (admin synthetic event)
- GET  /api/admin/notifications/sends (audit log)
- POST /api/apps/{id}/restart        (real-event wiring)
- GET  /api/notifications/prefs      (supported_events regression)
- POST /api/notifications/test       (test-button regression)
- Direct dispatch_event() coverage   (cooldown + no-prefs + unsupported)
- Direct health_audit._probe_ssl()   (unreachable host)
- Scheduler registration check
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid

# Load backend/.env so direct services imports (MONGO_URL, DB_NAME) work when
# pytest is invoked from /app/backend without env vars exported.
def _load_env_file(path: str) -> None:
    try:
        with open(path) as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                v = v.strip().strip('"').strip("'")
                os.environ.setdefault(k.strip(), v)
    except FileNotFoundError:
        pass

_load_env_file("/app/backend/.env")

import pytest
import requests

# Read REACT_APP_BACKEND_URL from frontend/.env (backend container doesn't export it).
def _load_backend_url() -> str:
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if url:
        return url.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                line = line.strip()
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except FileNotFoundError:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")


BASE_URL = _load_backend_url()
ADMIN_EMAIL = "admin@deployunit.com"
ADMIN_PASS = "admin123"
DEMO_EMAIL = "demo@deployunit.com"
DEMO_PASS = "demo1234"
DEMO_WS = "ee9ace3a-0b82-4df5-9dd7-d543c1e0c022"
DEMO_APP = "63c1ba3c-8286-4e80-83d1-06a603132392"


# ─────────────────────── auth fixtures ───────────────────────
def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def demo():
    return _login(DEMO_EMAIL, DEMO_PASS)


# ─────────── admin/notifications/sends ───────────
class TestAdminSends:
    def test_sends_returns_list(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/notifications/sends", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_sends_workspace_filter(self, admin):
        r = admin.get(
            f"{BASE_URL}/api/admin/notifications/sends",
            params={"workspace_id": DEMO_WS, "limit": 20},
            timeout=15,
        )
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        for row in rows:
            assert row["workspace_id"] == DEMO_WS

    def test_sends_admin_only(self, demo):
        r = demo.get(f"{BASE_URL}/api/admin/notifications/sends", timeout=15)
        assert r.status_code in (401, 403)


# ─────────── admin/notifications/fire ───────────
SUPPORTED = [
    "app_restarted", "deploy_failed", "deploy_succeeded",
    "app_down", "app_recovered", "ssl_invalid",
    "domain_expiring", "build_warning", "credits_low",
]


class TestAdminFire:
    @pytest.mark.parametrize("event_type", SUPPORTED)
    def test_fire_each_event(self, admin, event_type):
        r = admin.post(
            f"{BASE_URL}/api/admin/notifications/fire",
            json={"workspace_id": DEMO_WS, "event_type": event_type,
                  "title": f"TEST_{event_type}", "body": "iter19 wiring check"},
            timeout=20,
        )
        assert r.status_code == 200, f"{event_type}: {r.status_code} {r.text}"
        data = r.json()
        # cooldown-skipped is never expected (force=True is hardcoded in admin endpoint)
        assert data.get("skipped") is None, f"{event_type} unexpectedly skipped: {data}"
        assert data.get("event") == event_type
        assert "members" in data
        assert "results" in data

    def test_fire_unknown_event_400(self, admin):
        r = admin.post(
            f"{BASE_URL}/api/admin/notifications/fire",
            json={"workspace_id": DEMO_WS, "event_type": "nonsense_event"},
            timeout=15,
        )
        assert r.status_code == 400
        body = r.json()
        assert "event_type" in (body.get("detail") or "")

    def test_fire_admin_only(self, demo):
        r = demo.post(
            f"{BASE_URL}/api/admin/notifications/fire",
            json={"workspace_id": DEMO_WS, "event_type": "deploy_succeeded"},
            timeout=15,
        )
        assert r.status_code in (401, 403)

    def test_fire_force_bypass_cooldown(self, admin):
        """Two identical fires within 1s should both dispatch (force=True default)."""
        title = f"TEST_force_{uuid.uuid4().hex[:8]}"
        payload = {"workspace_id": DEMO_WS, "event_type": "build_warning",
                   "title": title, "body": "force-bypass test"}
        r1 = admin.post(f"{BASE_URL}/api/admin/notifications/fire", json=payload, timeout=15)
        r2 = admin.post(f"{BASE_URL}/api/admin/notifications/fire", json=payload, timeout=15)
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json().get("skipped") is None
        assert r2.json().get("skipped") is None

    def test_fire_writes_inapp_bell(self, admin, demo):
        """After firing, the workspace bell should contain a matching row."""
        marker = f"TEST_bell_{uuid.uuid4().hex[:8]}"
        r = admin.post(
            f"{BASE_URL}/api/admin/notifications/fire",
            json={"workspace_id": DEMO_WS, "event_type": "deploy_succeeded",
                  "title": marker, "body": "bell write check"},
            timeout=15,
        )
        assert r.status_code == 200
        # Read back via the workspace owner
        time.sleep(0.5)
        r2 = demo.get(f"{BASE_URL}/api/notifications", params={"workspace_id": DEMO_WS}, timeout=15)
        assert r2.status_code == 200
        rows = r2.json()
        assert any(n.get("title") == marker for n in rows), \
            f"in-app bell row not found for marker={marker}"


# ─────────── real-event wiring: restart ───────────
class TestRestartWiring:
    def test_restart_fires_app_restarted(self, demo):
        before = demo.get(
            f"{BASE_URL}/api/notifications", params={"workspace_id": DEMO_WS}, timeout=15
        ).json()
        n_before = sum(1 for n in before if n.get("event_type") == "app_restarted")

        r = demo.post(f"{BASE_URL}/api/apps/{DEMO_APP}/restart", timeout=30)
        assert r.status_code == 200, f"restart failed: {r.status_code} {r.text}"

        # Allow async fan-out
        time.sleep(1.0)
        after = demo.get(
            f"{BASE_URL}/api/notifications", params={"workspace_id": DEMO_WS}, timeout=15
        ).json()
        n_after = sum(1 for n in after if n.get("event_type") == "app_restarted")
        assert n_after > n_before, (
            f"app_restarted event not written to in-app bell "
            f"(before={n_before} after={n_after})"
        )


# ─────────── /api/notifications/prefs regression ───────────
class TestPrefsRegression:
    def test_prefs_lists_new_events(self, demo):
        r = demo.get(f"{BASE_URL}/api/notifications/prefs", timeout=15)
        assert r.status_code == 200
        body = r.json()
        events = body.get("supported_events") or []
        assert "app_restarted" in events, f"missing app_restarted: {events}"
        assert "ssl_invalid" in events, f"missing ssl_invalid: {events}"
        # full new set
        for ev in SUPPORTED:
            assert ev in events, f"event {ev} missing from supported_events"
        # channels
        assert set(body.get("supported_channels") or []) >= {"sms", "email", "slack", "discord"}

    def test_test_button_still_works(self, demo):
        """Regression: POST /api/notifications/test still functions end-to-end."""
        r = demo.post(
            f"{BASE_URL}/api/notifications/test",
            json={"workspace_id": DEMO_WS, "channel": "email"},
            timeout=20,
        )
        assert r.status_code == 200, f"test button broken: {r.status_code} {r.text}"
        body = r.json()
        assert "results" in body
        # email always queues an in-app row (free path)
        statuses = [x.get("status") for x in body["results"]]
        assert any(s in ("queued", "sent") for s in statuses), f"unexpected statuses: {statuses}"


def test_scheduler_has_health_audit_job_placeholder():
    # see real impl at end of file
    pass


# ─────── direct dispatch_event tests via asyncio.run() ────────
import sys
sys.path.insert(0, "/app/backend")


async def _impl_dispatch_cooldown_skips_second_call():
    """Without force, two calls within window: second returns {skipped:'cooldown'}."""
    from services.event_dispatcher import dispatch_event
    from db import get_db
    db = get_db()

    ws = DEMO_WS
    ev = "build_warning"
    app_id = f"cooldowntest_{uuid.uuid4().hex[:8]}"  # unique app_id so we have a clean slot

    # Clean any prior cooldown row for this synthetic key
    await db.event_cooldowns.delete_many({"workspace_id": ws, "event_type": ev, "app_id": app_id})

    r1 = await dispatch_event(
        workspace_id=ws, event_type=ev,
        title="TEST_cooldown1", body="first", app_id=app_id, force=False,
    )
    r2 = await dispatch_event(
        workspace_id=ws, event_type=ev,
        title="TEST_cooldown2", body="second", app_id=app_id, force=False,
    )
    assert r1.get("skipped") is None, f"first call should fire, got {r1}"
    assert r2.get("skipped") == "cooldown", f"second call should be cooldown-skipped, got {r2}"
    assert r2.get("event") == ev

    # Verify only ONE in-app notification row was written
    titles = await db.notifications.find(
        {"workspace_id": ws, "app_id": app_id}, {"_id": 0, "title": 1}
    ).to_list(20)
    assert len(titles) == 1, f"expected exactly one bell row, got {titles}"

    # cleanup
    await db.notifications.delete_many({"workspace_id": ws, "app_id": app_id})
    await db.event_cooldowns.delete_many({"workspace_id": ws, "event_type": ev, "app_id": app_id})


async def _impl_dispatch_no_prefs_still_writes_bell():
    """If no members have notification_prefs, dispatch still writes the bell row."""
    from services.event_dispatcher import dispatch_event
    from db import get_db
    db = get_db()

    ws_id = f"ws_test_{uuid.uuid4().hex[:8]}"
    # Insert a synthetic workspace with an owner who has no notification_prefs
    user_id = f"user_test_{uuid.uuid4().hex[:8]}"
    await db.users.insert_one({"id": user_id, "email": f"{user_id}@example.com"})
    await db.workspaces.insert_one({"id": ws_id, "owner_id": user_id, "name": "TEST_ws"})

    try:
        r = await dispatch_event(
            workspace_id=ws_id, event_type="deploy_succeeded",
            title="TEST_no_prefs", body="no prefs configured", force=True,
        )
        assert r.get("members") == 0, f"expected members:0, got {r}"
        assert r.get("results") == []
        # bell row written?
        n = await db.notifications.find_one({"workspace_id": ws_id, "title": "TEST_no_prefs"})
        assert n is not None, "bell row not written even when no prefs configured"
    finally:
        await db.notifications.delete_many({"workspace_id": ws_id})
        await db.workspaces.delete_one({"id": ws_id})
        await db.users.delete_one({"id": user_id})


async def _impl_supported_event_types_complete():
    """SUPPORTED_EVENT_TYPES must include app_restarted + ssl_invalid + the 7 originals."""
    from services.notifications_sms import SUPPORTED_EVENT_TYPES
    expected = {
        "deploy_failed", "deploy_succeeded",
        "app_down", "app_recovered",
        "app_restarted",
        "build_warning", "domain_expiring",
        "ssl_invalid",
        "credits_low",
    }
    missing = expected - SUPPORTED_EVENT_TYPES
    assert not missing, f"missing event types: {missing}"


async def _impl_probe_ssl_unreachable():
    """_probe_ssl on a non-resolvable hostname → {ok:False, reason:'unreachable'}."""
    from services.health_audit import _probe_ssl
    # RFC 6761 — .invalid is guaranteed to never resolve
    res = await _probe_ssl("this-host-does-not-exist-iter19.invalid")
    assert res.get("ok") is False, f"expected ok:False, got {res}"
    assert res.get("reason") == "unreachable", f"expected reason=unreachable, got {res}"


def test_scheduler_has_health_audit_job():
    """Health audit job must be registered at 6h interval. We probe by hitting
    a status endpoint or by importing scheduler config — fall back to checking
    server.py defines it (already done) and verifying the function is callable."""
    import re
    with open("/app/backend/server.py") as f:
        src = f.read()
    assert re.search(r'add_job\(\s*health_audit_tick\s*,\s*"interval"\s*,\s*hours=6\s*,\s*id="health_audit"', src), \
        "health_audit job not registered at 6h interval in server.py"


# ─────── sync wrappers around async impls (no pytest-asyncio plugin needed) ───────
def _reset_motor_client():
    """asyncio.run() creates a fresh loop each call. The cached motor client
    is bound to the previous (now-closed) loop, so reset it between tests."""
    import db as _db_mod
    _db_mod._client = None
    _db_mod._db = None


def test_dispatch_cooldown_skips_second_call():
    _reset_motor_client()
    asyncio.run(_impl_dispatch_cooldown_skips_second_call())


def test_dispatch_no_prefs_still_writes_bell():
    _reset_motor_client()
    asyncio.run(_impl_dispatch_no_prefs_still_writes_bell())


def test_supported_event_types_complete():
    _reset_motor_client()
    asyncio.run(_impl_supported_event_types_complete())


def test_probe_ssl_unreachable():
    _reset_motor_client()
    asyncio.run(_impl_probe_ssl_unreachable())
