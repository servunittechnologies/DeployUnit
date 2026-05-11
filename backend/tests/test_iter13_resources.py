"""Backend tests for iteration 13: resource sizing + addon billing + DB attachments.

Covers:
  * GET/PUT /api/apps/{id}/resources (charge, refund, insufficient credits)
  * GET/POST/DELETE /api/apps/{id}/connections (attach/detach + duplicate env-var + cross-WS reject)
  * GET/PUT /api/admin/resource-config (admin gating + persistence)
  * GET /api/admin/resource-defaults (baseline anchor)
  * Regression: admin /admin/users/{id}/credits adjusts credits via grant/consume (users.credits_balance)
"""
import os
import time
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@deployunit.com", "password": "admin123"}
MARTIJN = {"email": "martijn@servunit.com", "password": "servunit123"}
DEMO = {"email": "demo@deployunit.com", "password": "demo1234"}


# ──────────────────── fixtures ────────────────────
def _login(session: requests.Session, creds: dict) -> dict:
    r = session.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    _login(s, ADMIN)
    return s


@pytest.fixture(scope="module")
def martijn_session():
    s = requests.Session()
    _login(s, MARTIJN)
    return s


@pytest.fixture(scope="module")
def demo_session():
    s = requests.Session()
    _login(s, DEMO)
    return s


@pytest.fixture(scope="module")
def martijn_workspace(martijn_session):
    r = martijn_session.get(f"{API}/workspaces", timeout=20)
    assert r.status_code == 200, r.text
    wss = r.json()
    assert wss, "Martijn should have ServUnit workspace"
    # Pick the agency workspace
    ws = next((w for w in wss if w.get("plan") == "agency"), wss[0])
    return ws


@pytest.fixture(scope="module")
def martijn_app(martijn_session, martijn_workspace):
    r = martijn_session.get(f"{API}/apps?workspace_id={martijn_workspace['id']}", timeout=20)
    assert r.status_code == 200, r.text
    apps = r.json()
    assert apps, "ServUnit workspace should have at least one app"
    return apps[0]


def _find_user(admin_session, email: str):
    r = admin_session.get(f"{API}/admin/users?q={email}&limit=50", timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    users = body["users"] if isinstance(body, dict) else body
    return next((u for u in users if u.get("email") == email), None)


# ──────────────────── Admin resource-config ────────────────────
class TestAdminResourceConfig:
    def test_admin_get_resource_config(self, admin_session):
        r = admin_session.get(f"{API}/admin/resource-config", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "plan_defaults" in body and "pricing" in body
        # baseline values present
        assert body["plan_defaults"]["free"]["cpu_vcpu"] == 0.25
        assert body["plan_defaults"]["pro"]["memory_mb"] == 512
        assert body["plan_defaults"]["agency"]["storage_mb"] == 20480
        assert body["pricing"]["cpu_credits_per_unit"] == 100
        assert body["pricing"]["memory_credits_per_unit"] == 50
        assert body["pricing"]["storage_credits_per_unit"] == 25

    def test_admin_resource_defaults_anchor(self, admin_session):
        r = admin_session.get(f"{API}/admin/resource-defaults", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["plan_defaults"]["free"]["cpu_vcpu"] == 0.25
        assert body["pricing"]["cpu_unit_vcpu"] == 0.5

    def test_non_admin_blocked(self, demo_session):
        r = demo_session.get(f"{API}/admin/resource-config", timeout=15)
        assert r.status_code == 403, r.text

    def test_admin_put_resource_config_persists(self, admin_session):
        # Mutate a single pricing knob then revert
        r0 = admin_session.get(f"{API}/admin/resource-config", timeout=15).json()
        orig_cpu_price = r0["pricing"]["cpu_credits_per_unit"]
        try:
            r1 = admin_session.put(
                f"{API}/admin/resource-config",
                json={"pricing": {**r0["pricing"], "cpu_credits_per_unit": 123}},
                timeout=15,
            )
            assert r1.status_code == 200, r1.text
            assert r1.json()["pricing"]["cpu_credits_per_unit"] == 123
            # confirm persisted
            r2 = admin_session.get(f"{API}/admin/resource-config", timeout=15).json()
            assert r2["pricing"]["cpu_credits_per_unit"] == 123
        finally:
            admin_session.put(
                f"{API}/admin/resource-config",
                json={"pricing": {**r0["pricing"], "cpu_credits_per_unit": orig_cpu_price}},
                timeout=15,
            )


# ──────────────────── App resources ────────────────────
class TestAppResources:
    def test_get_app_resources_shape(self, martijn_session, martijn_app):
        r = martijn_session.get(f"{API}/apps/{martijn_app['id']}/resources", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        for key in ("plan_default", "addons", "effective", "monthly_cost_credits",
                    "pricing", "plan_defaults_all"):
            assert key in body, f"missing key {key}"
        # plan_default should be the agency tier
        assert body["plan_default"]["cpu_vcpu"] >= 1.0
        assert body["plan_default"]["memory_mb"] >= 1024

    def test_reset_addons_to_zero_first(self, martijn_session, martijn_app):
        # Make sure starting state is clean (no addons)
        r = martijn_session.put(
            f"{API}/apps/{martijn_app['id']}/resources",
            json={"extra_cpu_vcpu": 0, "extra_memory_mb": 0, "extra_storage_mb": 0},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        assert r.json()["monthly_cost_credits"] == 0

    def test_upgrade_and_downgrade_refund(self, martijn_session, martijn_app, admin_session):
        # Top-up credits so we can definitely upgrade (idempotent on admin)
        martijn = _find_user(admin_session, MARTIJN["email"])
        assert martijn, "could not find martijn user"
        admin_session.post(
            f"{API}/admin/users/{martijn['id']}/credits",
            json={"delta": 500, "reason": "TEST_iter13 top-up"},
            timeout=15,
        )

        # Read pre-upgrade balance
        me0 = martijn_session.get(f"{API}/account", timeout=15).json()
        bal0 = me0.get("profile",{}).get("credits_balance", 0)

        # Upgrade: +0.5 vCPU -> 100 cr / month, full-period pro-rated
        r_up = martijn_session.put(
            f"{API}/apps/{martijn_app['id']}/resources",
            json={"extra_cpu_vcpu": 0.5, "extra_memory_mb": 0, "extra_storage_mb": 0},
            timeout=20,
        )
        assert r_up.status_code == 200, r_up.text
        up_body = r_up.json()
        assert up_body["monthly_cost_credits"] == 100
        assert up_body["addons"]["cpu_vcpu"] == 0.5

        me1 = martijn_session.get(f"{API}/account", timeout=15).json()
        bal1 = me1.get("profile",{}).get("credits_balance", 0)
        # First-time charge should be full-period (~100 credits)
        spent = bal0 - bal1
        assert 95 <= spent <= 100, f"expected ~100cr charge, got {spent}"

        # Now downgrade in the same minute → refund the bulk back
        r_dn = martijn_session.put(
            f"{API}/apps/{martijn_app['id']}/resources",
            json={"extra_cpu_vcpu": 0, "extra_memory_mb": 0, "extra_storage_mb": 0},
            timeout=20,
        )
        assert r_dn.status_code == 200, r_dn.text
        assert r_dn.json()["monthly_cost_credits"] == 0

        me2 = martijn_session.get(f"{API}/account", timeout=15).json()
        bal2 = me2.get("profile",{}).get("credits_balance", 0)
        refunded = bal2 - bal1
        # Should be very close to what we spent (pro-rated same minute ≈ 100% back)
        assert refunded >= spent - 5, f"refund {refunded} too small vs spent {spent}"

    def test_insufficient_credits_returns_402(self, admin_session, martijn_session, martijn_app):
        # Drain credits to near-zero
        martijn = _find_user(admin_session, MARTIJN["email"])
        me = martijn_session.get(f"{API}/account", timeout=15).json()
        bal = me.get("profile",{}).get("credits_balance", 0)
        if bal > 5:
            admin_session.post(
                f"{API}/admin/users/{martijn['id']}/credits",
                json={"delta": -(bal - 5), "reason": "TEST_iter13 drain"},
                timeout=15,
            )
        # Attempt big upgrade that needs more credits than 5
        r = martijn_session.put(
            f"{API}/apps/{martijn_app['id']}/resources",
            json={"extra_cpu_vcpu": 2.0, "extra_memory_mb": 0, "extra_storage_mb": 0},
            timeout=20,
        )
        assert r.status_code == 402, f"expected 402 got {r.status_code}: {r.text}"
        detail = (r.json().get("detail") or "").lower()
        assert "credit" in detail
        # Restore a healthy balance for next tests
        admin_session.post(
            f"{API}/admin/users/{martijn['id']}/credits",
            json={"delta": 1000, "reason": "TEST_iter13 restore"},
            timeout=15,
        )

    def test_final_reset_addons(self, martijn_session, martijn_app):
        r = martijn_session.put(
            f"{API}/apps/{martijn_app['id']}/resources",
            json={"extra_cpu_vcpu": 0, "extra_memory_mb": 0, "extra_storage_mb": 0},
            timeout=20,
        )
        assert r.status_code == 200
        assert r.json()["addons"] == {"cpu_vcpu": 0.0, "memory_mb": 0, "storage_mb": 0}


# ──────────────────── DB connections ────────────────────
class TestDatabaseConnections:
    def test_list_connections_shape(self, martijn_session, martijn_app):
        r = martijn_session.get(f"{API}/apps/{martijn_app['id']}/connections", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "connections" in body
        assert "available_databases" in body
        # masked field check on available DBs (if any)
        for d in body["available_databases"]:
            if d.get("connection_string"):
                assert "connection_string_masked" in d
                assert "•••" in d["connection_string_masked"]

    def test_attach_and_duplicate_envvar_and_detach(self, martijn_session, martijn_app):
        r = martijn_session.get(f"{API}/apps/{martijn_app['id']}/connections", timeout=15).json()
        avail = r["available_databases"]
        if not avail:
            pytest.skip("no databases available in workspace to attach")
        db_id = avail[0]["id"]
        envname = "TEST_ITER13_URL"

        # Pre-clean: detach if env name already used
        existing = next((c for c in r["connections"] if c.get("env_var_name") == envname), None)
        if existing:
            martijn_session.delete(
                f"{API}/apps/{martijn_app['id']}/connections/{existing['id']}", timeout=15
            )

        # Attach
        a = martijn_session.post(
            f"{API}/apps/{martijn_app['id']}/connections",
            json={"db_id": db_id, "env_var_name": envname},
            timeout=15,
        )
        assert a.status_code == 200, a.text
        conn_id = a.json()["connection"]["id"]
        assert a.json()["connection"]["env_var_name"] == envname

        # Duplicate env var name → 409
        dup = martijn_session.post(
            f"{API}/apps/{martijn_app['id']}/connections",
            json={"db_id": db_id, "env_var_name": envname},
            timeout=15,
        )
        assert dup.status_code == 409, f"expected 409 got {dup.status_code}: {dup.text}"

        # Detach
        d = martijn_session.delete(
            f"{API}/apps/{martijn_app['id']}/connections/{conn_id}", timeout=15
        )
        assert d.status_code == 200, d.text
        assert d.json().get("ok") is True

    def test_attach_cross_workspace_rejected(self, martijn_session, demo_session, martijn_app):
        # Find a database from a different workspace via demo session
        demo_dbs = demo_session.get(f"{API}/databases", timeout=15)
        if demo_dbs.status_code != 200 or not demo_dbs.json():
            pytest.skip("demo workspace has no databases for cross-WS test")
        foreign_db = demo_dbs.json()[0]
        r = martijn_session.post(
            f"{API}/apps/{martijn_app['id']}/connections",
            json={"db_id": foreign_db["id"], "env_var_name": "FOREIGN_URL"},
            timeout=15,
        )
        # 400 (cross-WS) or 404 (db not visible) both acceptable as a reject
        assert r.status_code in (400, 404), f"expected 400/404 got {r.status_code}"

    def test_attach_invalid_envvar_pattern(self, martijn_session, martijn_app):
        r = martijn_session.get(f"{API}/apps/{martijn_app['id']}/connections", timeout=15).json()
        if not r["available_databases"]:
            pytest.skip("no DB available")
        db_id = r["available_databases"][0]["id"]
        bad = martijn_session.post(
            f"{API}/apps/{martijn_app['id']}/connections",
            json={"db_id": db_id, "env_var_name": "bad name!"},
            timeout=15,
        )
        assert bad.status_code == 422, f"expected pydantic 422 got {bad.status_code}"


# ──────────────────── Regression: admin credits adjust ────────────────────
class TestAdminCreditAdjust:
    def test_admin_adjust_credits_writes_to_users_credits_balance(self, admin_session, demo_session):
        demo = _find_user(admin_session, DEMO["email"])
        assert demo, "demo user missing"
        before = demo_session.get(f"{API}/account", timeout=15).json().get("profile",{}).get("credits_balance", 0)

        # +50 credits
        r = admin_session.post(
            f"{API}/admin/users/{demo['id']}/credits",
            json={"delta": 50, "reason": "TEST_iter13 regression"},
            timeout=15,
        )
        assert r.status_code in (200, 201), r.text

        after = demo_session.get(f"{API}/account", timeout=15).json().get("profile",{}).get("credits_balance", 0)
        assert after == before + 50, f"expected balance +50; was {before} → {after}"

        # Revert
        admin_session.post(
            f"{API}/admin/users/{demo['id']}/credits",
            json={"delta": -50, "reason": "TEST_iter13 revert"},
            timeout=15,
        )

    def test_admin_transactions_list_includes_adjustment(self, admin_session, demo_session):
        # Bump and check it shows up in their transactions
        demo = _find_user(admin_session, DEMO["email"])
        admin_session.post(
            f"{API}/admin/users/{demo['id']}/credits",
            json={"delta": 7, "reason": "TEST_iter13 txn check"},
            timeout=15,
        )
        time.sleep(0.5)
        txns = demo_session.get(f"{API}/account/credits/history", timeout=15)
        if txns.status_code != 200:
            pytest.skip(f"/account/transactions not available: {txns.status_code}")
        body = txns.json()
        items = body if isinstance(body, list) else body.get("transactions") or body.get("items") or []
        found = any("TEST_iter13 txn check" in (t.get("reason") or "") for t in items)
        assert found, "Admin credit adjustment did not appear in user's transactions list"
        # revert
        admin_session.post(
            f"{API}/admin/users/{demo['id']}/credits",
            json={"delta": -7, "reason": "TEST_iter13 revert"},
            timeout=15,
        )
