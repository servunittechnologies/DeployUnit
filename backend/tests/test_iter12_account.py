"""Iter12 — Account vs Workspace settings separation.

Tests:
  - /api/account snapshot
  - /api/account/plan (account-wide usage)
  - /api/account/credits + history + packs
  - /api/account/billing + PUT billing/profile (with VAT computation)
  - PATCH /api/account/profile
  - POST /api/account/password
  - POST /api/account/plan/checkout (free downgrade)
  - POST /api/account/plan/cancel
  - Backward compat: /api/credits/balance?workspace_id=, /api/workspaces/{id}/usage

NOTE: Mollie paid-plan checkout NOT exercised end-to-end (per request).
"""
import os
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

DEMO_EMAIL = "demo@deployhub.dev"
DEMO_PW = "demo1234"
ADMIN_EMAIL = "admin@deployhub.dev"
ADMIN_PW = "admin123"


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def demo_session():
    return _login(DEMO_EMAIL, DEMO_PW)


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN_EMAIL, ADMIN_PW)


# ─────────────────────────── /api/account snapshot ───────────────────────────
class TestAccountSnapshot:
    def test_snapshot_shape(self, demo_session):
        r = demo_session.get(f"{BASE_URL}/api/account", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        # Required top-level keys
        for k in ("profile", "plan", "usage", "credits", "workspaces", "notif_prefs_summary"):
            assert k in data, f"missing key: {k}"
        # Profile no secrets
        assert "password_hash" not in data["profile"]
        assert "_id" not in data["profile"]
        # Demo is on agency plan post-migration
        assert data["plan"]["id"] == "agency", f"expected agency, got {data['plan']}"
        # Usage aggregated
        assert "workspaces" in data["usage"]
        assert "apps" in data["usage"]
        assert "domains" in data["usage"]
        # Notif summary keys
        for k in ("phone_set", "slack_set", "discord_set"):
            assert k in data["notif_prefs_summary"]


# ─────────────────────────── /api/account/plan ───────────────────────────
class TestAccountPlan:
    def test_plan_returns_account_wide_usage(self, demo_session):
        r = demo_session.get(f"{BASE_URL}/api/account/plan", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "plan" in data and "usage" in data and "available_plans" in data
        assert isinstance(data["available_plans"], list)
        assert len(data["available_plans"]) >= 2
        # Plan has limits + features
        p = data["plan"]
        assert "limits" in p
        assert "name" in p
        # Usage object
        u = data["usage"]
        for k in ("apps", "domains", "databases", "team", "workspaces"):
            assert k in u, f"missing usage.{k}"


# ─────────────────────────── credits ───────────────────────────
class TestAccountCredits:
    def test_credits_balance(self, demo_session):
        r = demo_session.get(f"{BASE_URL}/api/account/credits", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("balance", "monthly_grant"):
            assert k in data, f"missing {k}"
        assert isinstance(data["balance"], int)

    def test_credits_history(self, demo_session):
        r = demo_session.get(f"{BASE_URL}/api/account/credits/history?limit=20", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        # Each row should have basic structure if present
        for row in data[:5]:
            assert "type" in row or "kind" in row, f"txn missing type: {row}"

    def test_credits_packs(self, demo_session):
        r = demo_session.get(f"{BASE_URL}/api/account/credits/packs", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list) and len(data) == 3
        ids = {p["id"] for p in data}
        assert ids == {"small", "medium", "large"}, f"got {ids}"


# ─────────────────────────── billing ───────────────────────────
class TestAccountBilling:
    def test_billing_shape(self, demo_session):
        r = demo_session.get(f"{BASE_URL}/api/account/billing", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("billing_profile", "subscription", "payments", "invoices"):
            assert k in data, f"missing {k}"
        assert isinstance(data["payments"], list)
        assert isinstance(data["invoices"], list)

    def test_put_billing_profile_computes_vat(self, demo_session):
        payload = {
            "company_name": "TEST_AcmeStudio",
            "address": "Hauptstrasse 1",
            "postal_code": "10115",
            "city": "Berlin",
            "country": "DE",
            "email": "billing@acme.test",
            "is_business": False,
        }
        r = demo_session.put(f"{BASE_URL}/api/account/billing/profile", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "profile" in data
        assert "vat_rate_applied" in data
        assert data["profile"]["country"] == "DE"
        assert data["profile"]["company_name"] == "TEST_AcmeStudio"

        # Verify persisted via GET
        r2 = demo_session.get(f"{BASE_URL}/api/account/billing", timeout=15)
        assert r2.status_code == 200
        bp = r2.json()["billing_profile"]
        assert bp["company_name"] == "TEST_AcmeStudio"
        assert "vat_rate" in bp


# ─────────────────────────── profile + password ───────────────────────────
class TestAccountProfileAndPassword:
    def test_patch_profile_updates_name(self, demo_session):
        # save original
        r0 = demo_session.get(f"{BASE_URL}/api/account", timeout=15)
        original_name = r0.json()["profile"].get("name") or "Demo"
        try:
            r = demo_session.patch(
                f"{BASE_URL}/api/account/profile",
                json={"name": "TEST_DemoRename"}, timeout=15,
            )
            assert r.status_code == 200, r.text
            assert r.json()["name"] == "TEST_DemoRename"
            # verify via GET
            r2 = demo_session.get(f"{BASE_URL}/api/account", timeout=15)
            assert r2.json()["profile"]["name"] == "TEST_DemoRename"
        finally:
            # restore
            demo_session.patch(
                f"{BASE_URL}/api/account/profile",
                json={"name": original_name}, timeout=15,
            )

    def test_password_wrong_current_returns_400(self, demo_session):
        r = demo_session.post(
            f"{BASE_URL}/api/account/password",
            json={"current_password": "wrongpw", "new_password": "newpasswd123"},
            timeout=15,
        )
        assert r.status_code == 400, r.text

    def test_password_min_length_8(self, demo_session):
        r = demo_session.post(
            f"{BASE_URL}/api/account/password",
            json={"current_password": DEMO_PW, "new_password": "short"},
            timeout=15,
        )
        # Pydantic min_length=8 -> 422
        assert r.status_code in (400, 422), r.text

    def test_password_change_and_relogin(self):
        """End-to-end: change password, re-login with new, restore original."""
        sess = _login(DEMO_EMAIL, DEMO_PW)
        new_pw = "demoNewPw99"
        try:
            r = sess.post(
                f"{BASE_URL}/api/account/password",
                json={"current_password": DEMO_PW, "new_password": new_pw}, timeout=15,
            )
            assert r.status_code == 200, r.text
            # re-login with new
            s2 = _login(DEMO_EMAIL, new_pw)
            # restore original
            r2 = s2.post(
                f"{BASE_URL}/api/account/password",
                json={"current_password": new_pw, "new_password": DEMO_PW}, timeout=15,
            )
            assert r2.status_code == 200, r2.text
        finally:
            # Final restore safety net — try with both possible states
            try:
                s3 = _login(DEMO_EMAIL, DEMO_PW)
            except AssertionError:
                s_new = _login(DEMO_EMAIL, new_pw)
                s_new.post(
                    f"{BASE_URL}/api/account/password",
                    json={"current_password": new_pw, "new_password": DEMO_PW}, timeout=15,
                )


# ─────────────────────────── plan checkout (free path) + cancel ───────────────────────────
class TestPlanCheckoutFreeAndCancel:
    """We use admin@ for these (currently on free) so we don't perturb demo's agency plan.
    Verifying contract shape only — Mollie not exercised."""

    def test_unknown_plan_rejected(self, admin_session):
        r = admin_session.post(
            f"{BASE_URL}/api/account/plan/checkout",
            json={"plan": "platinum"}, timeout=15,
        )
        # Pydantic Literal validation -> 422
        assert r.status_code in (400, 422), r.text

    def test_free_downgrade_immediate(self, admin_session):
        # admin is already on free per request context; downgrade-to-free is idempotent
        r = admin_session.post(
            f"{BASE_URL}/api/account/plan/checkout",
            json={"plan": "free"}, timeout=20,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["plan"] == "free"
        assert data["status"] == "active"
        assert data.get("checkout_url") is None

    def test_cancel_subscription(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/account/plan/cancel", timeout=20)
        # admin may or may not have a sub row — accept 200 or 404
        assert r.status_code in (200, 404), r.text
        if r.status_code == 200:
            assert r.json().get("status") == "canceled"


# ─────────────────────────── account-level limits apply across workspaces ───────────────────────────
class TestAccountWideLimits:
    def test_workspace_usage_resolves_owner_plan(self, demo_session):
        # Pick a workspace from snapshot
        r = demo_session.get(f"{BASE_URL}/api/account", timeout=15)
        wss = r.json()["workspaces"]
        assert wss, "demo should own at least one workspace"
        ws_id = wss[0]["id"]
        # Legacy endpoint — should still work
        r2 = demo_session.get(f"{BASE_URL}/api/workspaces/{ws_id}/usage", timeout=15)
        assert r2.status_code == 200, r2.text
        usage = r2.json()
        # Should reflect agency plan (owner is demo, on agency)
        assert "plan" in usage or "limits" in usage or "apps" in usage, f"usage shape: {usage}"


# ─────────────────────────── backward compat: credits/balance ───────────────────────────
class TestCreditsBackwardCompat:
    def test_credits_balance_by_workspace_id(self, demo_session):
        r = demo_session.get(f"{BASE_URL}/api/account", timeout=15)
        wss = r.json()["workspaces"]
        if not wss:
            pytest.skip("no workspaces")
        ws_id = wss[0]["id"]
        r2 = demo_session.get(
            f"{BASE_URL}/api/credits/balance?workspace_id={ws_id}", timeout=15,
        )
        # Legacy shim must resolve workspace -> owner user
        assert r2.status_code == 200, r2.text
        data = r2.json()
        assert "balance" in data
        assert isinstance(data["balance"], int)

        # Compare to account-level call — must be equal
        r3 = demo_session.get(f"{BASE_URL}/api/account/credits", timeout=15)
        assert r3.status_code == 200
        assert r3.json()["balance"] == data["balance"], \
            "workspace-keyed balance must equal user-keyed balance"


# ─────────────────────────── auth required ───────────────────────────
class TestAuthRequired:
    def test_account_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/account", timeout=15)
        assert r.status_code in (401, 403), f"got {r.status_code}"

    def test_account_plan_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/account/plan", timeout=15)
        assert r.status_code in (401, 403)
