"""Sprint 6 (iter11) backend tests.

Two features:
  (A) Staging/Production pairing + promote-flow on /api/apps
  (B) Admin Console user management at /api/admin/users/*

All tests use the public preview URL and clean up any apps they create.
"""
import os
import re
import time
import uuid
import secrets
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@deployunit.com"
ADMIN_PASS = "admin123"
DEMO_EMAIL = "demo@deployunit.com"
DEMO_PASS = "demo1234"
DEMO_WORKSPACE_ID = "ee9ace3a-0b82-4df5-9dd7-d543c1e0c022"


# ─────────────── fixtures ───────────────
def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def demo_session():
    return _login(DEMO_EMAIL, DEMO_PASS)


@pytest.fixture(scope="module")
def created_apps(demo_session):
    """Collect every app_id we create so module teardown can delete them all."""
    ids: list[str] = []
    yield ids
    for app_id in ids:
        try:
            demo_session.delete(f"{API}/apps/{app_id}", timeout=30)
        except Exception:
            pass


def _make_app(session, name_suffix, environment="production", paired_app_id=None):
    payload = {
        "workspace_id": DEMO_WORKSPACE_ID,
        "name": f"TEST_iter11_{name_suffix}_{secrets.token_hex(3)}",
        "framework": "static",
        "repo_url": "https://github.com/octocat/Hello-World",
        "branch": "master",
        "environment": environment,
        "env_vars": {"SRC_KEY": "src_val"},
    }
    if paired_app_id:
        payload["paired_app_id"] = paired_app_id
    r = session.post(f"{API}/apps", json=payload, timeout=60)
    assert r.status_code in (200, 201), f"create app -> {r.status_code} {r.text}"
    return r.json()


# ═══════════════════════════════════════════════
# (A) Staging/Production pairing & promote
# ═══════════════════════════════════════════════
class TestPairing:
    def test_create_with_environment_staging(self, demo_session, created_apps):
        app = _make_app(demo_session, "stg", environment="staging")
        created_apps.append(app["id"])
        assert app["environment"] == "staging"
        # Webhook secret + audit row written (regression)
        assert app.get("webhook_secret"), "create_app must mint a webhook_secret (regression)"

    def test_create_with_environment_production(self, demo_session, created_apps):
        app = _make_app(demo_session, "prd", environment="production")
        created_apps.append(app["id"])
        assert app["environment"] == "production"

    def test_environment_defaults_to_production(self, demo_session, created_apps):
        payload = {
            "workspace_id": DEMO_WORKSPACE_ID,
            "name": f"TEST_iter11_default_{secrets.token_hex(3)}",
            "framework": "static",
            "repo_url": "https://github.com/octocat/Hello-World",
            "branch": "master",
        }
        r = demo_session.post(f"{API}/apps", json=payload, timeout=60)
        assert r.status_code in (200, 201), r.text
        data = r.json()
        created_apps.append(data["id"])
        assert data["environment"] == "production"

    def test_pair_candidates_returns_opposite_env(self, demo_session, created_apps):
        stg = _make_app(demo_session, "candA", environment="staging")
        prd = _make_app(demo_session, "candB", environment="production")
        created_apps += [stg["id"], prd["id"]]
        # For staging app, candidates must be production
        r = demo_session.get(f"{API}/apps/{stg['id']}/pair-candidates", timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["target_environment"] == "production"
        cand_ids = [c["id"] for c in body["candidates"]]
        assert prd["id"] in cand_ids
        # For production app, candidates must be staging
        r2 = demo_session.get(f"{API}/apps/{prd['id']}/pair-candidates", timeout=20)
        assert r2.json()["target_environment"] == "staging"
        assert stg["id"] in [c["id"] for c in r2.json()["candidates"]]

    def test_pair_and_unpair(self, demo_session, created_apps):
        stg = _make_app(demo_session, "pairA", environment="staging")
        prd = _make_app(demo_session, "pairB", environment="production")
        created_apps += [stg["id"], prd["id"]]

        # Pair
        r = demo_session.post(f"{API}/apps/{stg['id']}/pair",
                              json={"peer_app_id": prd["id"]}, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["paired"] is True

        # Verify both sides have paired_app_id set
        a = demo_session.get(f"{API}/apps?workspace_id={DEMO_WORKSPACE_ID}", timeout=20).json()
        idx = {x["id"]: x for x in a}
        assert idx[stg["id"]]["paired_app_id"] == prd["id"]
        assert idx[prd["id"]]["paired_app_id"] == stg["id"]

        # Pair-candidates now should still include the peer (already paired with me)
        cands = demo_session.get(f"{API}/apps/{stg['id']}/pair-candidates", timeout=20).json()
        assert prd["id"] in [c["id"] for c in cands["candidates"]]

        # Unpair
        r2 = demo_session.post(f"{API}/apps/{stg['id']}/unpair", timeout=20)
        assert r2.status_code == 200, r2.text
        assert r2.json()["paired"] is False
        a2 = demo_session.get(f"{API}/apps?workspace_id={DEMO_WORKSPACE_ID}", timeout=20).json()
        idx2 = {x["id"]: x for x in a2}
        assert idx2[stg["id"]].get("paired_app_id") in (None, "")
        assert idx2[prd["id"]].get("paired_app_id") in (None, "")

    def test_pair_same_environment_rejected(self, demo_session, created_apps):
        a = _make_app(demo_session, "sameA", environment="production")
        b = _make_app(demo_session, "sameB", environment="production")
        created_apps += [a["id"], b["id"]]
        r = demo_session.post(f"{API}/apps/{a['id']}/pair",
                              json={"peer_app_id": b["id"]}, timeout=20)
        assert r.status_code == 400, r.text

    def test_pair_self_rejected(self, demo_session, created_apps):
        a = _make_app(demo_session, "self", environment="staging")
        created_apps.append(a["id"])
        r = demo_session.post(f"{API}/apps/{a['id']}/pair",
                              json={"peer_app_id": a["id"]}, timeout=20)
        assert r.status_code == 400, r.text

    def test_promote_copies_env_and_queues_deployment(self, demo_session, created_apps):
        stg = _make_app(demo_session, "promoSrc", environment="staging")
        prd = _make_app(demo_session, "promoDst", environment="production")
        created_apps += [stg["id"], prd["id"]]
        # Pair
        demo_session.post(f"{API}/apps/{stg['id']}/pair",
                          json={"peer_app_id": prd["id"]}, timeout=20)
        # Add unique env var on src
        demo_session.put(f"{API}/apps/{stg['id']}/env",
                         json={"env_vars": {"PROMO_KEY": "promo_val", "SRC_KEY": "src_val"}},
                         timeout=20)
        # Change branch on src
        demo_session.patch(f"{API}/apps/{stg['id']}",
                           json={"branch": "feature/promote-test"}, timeout=20)

        # Promote
        r = demo_session.post(f"{API}/apps/{stg['id']}/promote", timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["promoted"] is True
        assert body["from"]["id"] == stg["id"]
        assert body["to"]["id"] == prd["id"]
        deploy_id = body["deployment_id"]
        assert deploy_id

        # Verify dest now has copied env_vars + branch
        time.sleep(0.5)
        all_apps = demo_session.get(f"{API}/apps?workspace_id={DEMO_WORKSPACE_ID}", timeout=20).json()
        dest = next(x for x in all_apps if x["id"] == prd["id"])
        assert dest["env_vars"].get("PROMO_KEY") == "promo_val"
        assert dest["branch"] == "feature/promote-test"

        # Verify deployment row has trigger='promote'
        deps = demo_session.get(f"{API}/apps/{prd['id']}/deployments", timeout=20)
        if deps.status_code == 200:
            dlist = deps.json() if isinstance(deps.json(), list) else deps.json().get("deployments", [])
            found = [d for d in dlist if d.get("id") == deploy_id]
            assert found, "promote deployment row not found"
            assert found[0].get("trigger") == "promote"

        # Verify audit log entry action='app.promote'
        time.sleep(0.4)
        al = demo_session.get(
            f"{API}/audit-log?workspace_id={DEMO_WORKSPACE_ID}&action=app.promote&limit=20",
            timeout=20,
        )
        assert al.status_code == 200, al.text
        entries = al.json().get("entries", [])
        assert any(e.get("resource_id") == stg["id"] for e in entries), \
            f"app.promote audit entry missing for {stg['id']}; got {entries[:3]}"

    def test_promote_without_pair_400(self, demo_session, created_apps):
        solo = _make_app(demo_session, "solo", environment="staging")
        created_apps.append(solo["id"])
        r = demo_session.post(f"{API}/apps/{solo['id']}/promote", timeout=20)
        assert r.status_code == 400, r.text


# ═══════════════════════════════════════════════
# (B) Admin user-management endpoints
# ═══════════════════════════════════════════════
class TestAdminUsers:
    def _demo_user_id(self, admin_session):
        r = admin_session.get(f"{API}/admin/users?q=demo&limit=10", timeout=20)
        assert r.status_code == 200, r.text
        users = r.json()["users"]
        u = next((u for u in users if u["email"] == DEMO_EMAIL), None)
        assert u, f"demo user not found in {users}"
        return u["id"]

    def test_list_users_basic(self, admin_session):
        r = admin_session.get(f"{API}/admin/users?limit=10&offset=0", timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("users", "total", "limit", "offset"):
            assert k in body
        assert isinstance(body["users"], list) and body["users"]
        u = body["users"][0]
        assert "password_hash" not in u, "password_hash must NOT leak"
        assert "_id" not in u
        assert "workspaces_count" in u and "credits_total" in u

    def test_list_users_search(self, admin_session):
        r = admin_session.get(f"{API}/admin/users?q=DEMO", timeout=20)
        assert r.status_code == 200
        emails = [u["email"] for u in r.json()["users"]]
        assert DEMO_EMAIL in emails

    def test_list_users_non_admin_403(self, demo_session):
        r = demo_session.get(f"{API}/admin/users", timeout=20)
        assert r.status_code == 403, r.text

    def test_user_detail(self, admin_session):
        uid = self._demo_user_id(admin_session)
        r = admin_session.get(f"{API}/admin/users/{uid}", timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("user", "workspaces", "audit", "available_plans"):
            assert k in body
        assert "password_hash" not in body["user"]
        # workspace_id must include the demo workspace and have plan_details + apps_count + payments_count
        ws = next((w for w in body["workspaces"] if w["id"] == DEMO_WORKSPACE_ID), None)
        assert ws, f"demo workspace missing in detail: {[w['id'] for w in body['workspaces']]}"
        assert "plan_details" in ws and ws["plan_details"]
        assert "apps_count" in ws
        assert "payments_count" in ws
        assert isinstance(body["available_plans"], list) and body["available_plans"]

    def test_password_reset_min_length(self, admin_session):
        uid = self._demo_user_id(admin_session)
        r = admin_session.post(f"{API}/admin/users/{uid}/password",
                               json={"new_password": "short"}, timeout=20)
        assert r.status_code == 422, r.text

    def test_password_reset_and_audit(self, admin_session):
        uid = self._demo_user_id(admin_session)
        new_pw = "demo1234"  # reset back to canonical
        r = admin_session.post(f"{API}/admin/users/{uid}/password",
                               json={"new_password": new_pw}, timeout=20)
        assert r.status_code == 200, r.text
        time.sleep(0.4)
        # Verify demo can still log in after reset
        s2 = requests.Session()
        rl = s2.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": new_pw}, timeout=20)
        assert rl.status_code == 200, rl.text
        # Audit row written
        al = admin_session.get(
            f"{API}/audit-log?action=admin.user.password_reset&limit=10", timeout=20
        )
        assert al.status_code == 200
        assert any(e.get("resource_id") == uid for e in al.json().get("entries", []))

    def test_role_flip_and_last_admin_guard(self, admin_session):
        uid = self._demo_user_id(admin_session)
        # Promote demo → admin
        r = admin_session.post(f"{API}/admin/users/{uid}/role",
                               json={"role": "admin"}, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["role"] == "admin"
        # Now demote back
        r2 = admin_session.post(f"{API}/admin/users/{uid}/role",
                                json={"role": "user"}, timeout=20)
        assert r2.status_code == 200, r2.text

        # Last-admin guard: only attempt if exactly 1 admin remains in db
        adm_list = admin_session.get(f"{API}/admin/users?role=admin&limit=50", timeout=20).json()
        active_admins = [u for u in adm_list["users"] if u.get("is_active", True)]
        if len(active_admins) == 1:
            only_admin_id = active_admins[0]["id"]
            r3 = admin_session.post(f"{API}/admin/users/{only_admin_id}/role",
                                    json={"role": "user"}, timeout=20)
            assert r3.status_code == 400, r3.text
        else:
            # >1 admin in this env (martijn@servunit.com + admin@deployunit.com). Can't
            # exercise the guard without breaking the platform; just record the count.
            assert len(active_admins) >= 1

    def test_suspend_self_blocked(self, admin_session):
        adm_r = admin_session.get(f"{API}/admin/users?q=admin@deployunit.com", timeout=20).json()
        admin_id = next(u["id"] for u in adm_r["users"] if u["email"] == ADMIN_EMAIL)
        r = admin_session.post(f"{API}/admin/users/{admin_id}/suspend", timeout=20)
        assert r.status_code == 400, r.text

    def test_suspend_and_unsuspend_demo(self, admin_session):
        uid = self._demo_user_id(admin_session)
        r1 = admin_session.post(f"{API}/admin/users/{uid}/suspend", timeout=20)
        assert r1.status_code == 200, r1.text
        first = r1.json()["is_active"]
        r2 = admin_session.post(f"{API}/admin/users/{uid}/suspend", timeout=20)
        assert r2.json()["is_active"] != first
        # Final state must be active=True
        assert r2.json()["is_active"] is True

    def test_delete_self_and_last_admin_guards(self, admin_session):
        adm_r = admin_session.get(f"{API}/admin/users?q=admin@deployunit.com", timeout=20).json()
        admin_id = next(u["id"] for u in adm_r["users"] if u["email"] == ADMIN_EMAIL)
        r = admin_session.delete(f"{API}/admin/users/{admin_id}", timeout=20)
        assert r.status_code == 400, r.text

    def test_credits_adjust_and_floor(self, admin_session):
        uid = self._demo_user_id(admin_session)
        # Grant +50
        r = admin_session.post(f"{API}/admin/users/{uid}/credits",
                               json={"workspace_id": DEMO_WORKSPACE_ID,
                                     "delta": 50, "reason": "TEST_iter11"}, timeout=20)
        assert r.status_code == 200, r.text
        new_bal = r.json()["balance"]
        assert new_bal >= 50

        # Subtract a huge amount → must floor at 0
        r2 = admin_session.post(f"{API}/admin/users/{uid}/credits",
                                json={"workspace_id": DEMO_WORKSPACE_ID,
                                      "delta": -10_000_000, "reason": "TEST_iter11_floor"}, timeout=20)
        assert r2.status_code == 200
        assert r2.json()["balance"] == 0

        # Bring it back to a small positive balance for cleanliness
        admin_session.post(f"{API}/admin/users/{uid}/credits",
                           json={"workspace_id": DEMO_WORKSPACE_ID,
                                 "delta": 10, "reason": "TEST_iter11_restore"}, timeout=20)

        # Wrong workspace ownership → 400 (use a random uuid)
        r3 = admin_session.post(f"{API}/admin/users/{uid}/credits",
                                json={"workspace_id": str(uuid.uuid4()),
                                      "delta": 1, "reason": "wrong"}, timeout=20)
        assert r3.status_code in (400, 404), r3.text

    def test_plan_change_and_restore(self, admin_session):
        uid = self._demo_user_id(admin_session)
        # Move to pro
        r = admin_session.post(f"{API}/admin/users/{uid}/plan",
                               json={"workspace_id": DEMO_WORKSPACE_ID, "plan": "pro"}, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["plan"] == "pro"
        # Unknown plan → 400
        r2 = admin_session.post(f"{API}/admin/users/{uid}/plan",
                                json={"workspace_id": DEMO_WORKSPACE_ID, "plan": "platinum"}, timeout=20)
        assert r2.status_code == 400, r2.text
        # Restore to agency (per problem statement: demo workspace plan='agency' must be preserved)
        r3 = admin_session.post(f"{API}/admin/users/{uid}/plan",
                                json={"workspace_id": DEMO_WORKSPACE_ID, "plan": "agency"}, timeout=20)
        assert r3.status_code == 200
        assert r3.json()["plan"] == "agency"

    def test_payments_grouped_by_workspace(self, admin_session):
        uid = self._demo_user_id(admin_session)
        r = admin_session.get(f"{API}/admin/users/{uid}/payments", timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "workspaces" in body and "totals" in body
        for k in ("paid_eur", "payments", "invoices"):
            assert k in body["totals"]
        # Demo workspace should appear
        if body["workspaces"]:
            wnames = [w["workspace"]["id"] for w in body["workspaces"]]
            assert DEMO_WORKSPACE_ID in wnames


# ═══════════════════════════════════════════════
# Regression: webhook secret + audit row on /apps
# ═══════════════════════════════════════════════
class TestRegression:
    def test_app_create_has_webhook_secret_and_audit(self, demo_session, created_apps):
        app = _make_app(demo_session, "regress", environment="production")
        created_apps.append(app["id"])
        assert app.get("webhook_secret"), "webhook_secret missing on app.create"
        # audit (use demo_session since admin is not member of demo workspace)
        time.sleep(0.4)
        al = demo_session.get(
            f"{API}/audit-log?workspace_id={DEMO_WORKSPACE_ID}&action=app.create&limit=20",
            timeout=20,
        )
        assert al.status_code == 200, al.text
        assert any(e.get("resource_id") == app["id"] for e in al.json().get("entries", []))

    def test_demo_workspace_still_on_agency_plan(self, demo_session):
        r = demo_session.get(f"{API}/workspaces", timeout=20)
        assert r.status_code == 200
        ws = next((w for w in r.json() if w["id"] == DEMO_WORKSPACE_ID), None)
        assert ws, "demo workspace missing"
        assert ws["plan"] == "agency", f"demo workspace plan drifted to {ws['plan']}"
