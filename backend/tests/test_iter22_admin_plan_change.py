"""Tests for admin plan change (iter22 bug fix).

Reproduces the user-reported bug: as admin you change a user's plan in
Admin Console → User detail → Workspace card → plan dropdown, but the
plan never actually flipped. Root cause was that the endpoint wrote to
`workspaces.plan` while the plan resolver reads `users.plan`. This test
suite confirms the fix:

  * GET /api/admin/users/{id} returns ALL 4 plans (free/starter/pro/agency)
    in available_plans with correct prices (€0/€29/€99/€299).
  * POST /api/admin/users/{id}/plan flips users.plan AND keeps
    workspaces.plan in sync; the resolved plan_details on subsequent
    GETs reflects the new plan.
  * Round-trip: starter → pro → agency → free → pro restores correctly.
  * Non-admin gets 403.
  * Unknown plan id → 400.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://addon-showcase-1.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@deployunit.com"
ADMIN_PASS = "admin123"
USER_EMAIL = "demo@deployunit.com"
USER_PASS = "demo1234"


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def user_session():
    return _login(USER_EMAIL, USER_PASS)


@pytest.fixture(scope="module")
def demo_user(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/users", params={"q": "demo@deployunit.com"}, timeout=15)
    assert r.status_code == 200
    users = [u for u in r.json()["users"] if u["email"] == USER_EMAIL]
    assert users, "demo user not seeded"
    return users[0]


@pytest.fixture(scope="module")
def demo_workspace(admin_session, demo_user):
    r = admin_session.get(f"{BASE_URL}/api/admin/users/{demo_user['id']}", timeout=15)
    assert r.status_code == 200
    workspaces = r.json()["workspaces"]
    assert workspaces, "demo user owns no workspace"
    return workspaces[0]


@pytest.fixture(scope="module", autouse=True)
def restore_plan(admin_session, demo_user, demo_workspace):
    """Take a snapshot before the suite and restore it after, so other
    suites don't see a flipped plan."""
    original = demo_workspace.get("plan") or "free"
    yield
    admin_session.post(
        f"{BASE_URL}/api/admin/users/{demo_user['id']}/plan",
        json={"workspace_id": demo_workspace["id"], "plan": original},
        timeout=15,
    )


def test_available_plans_contains_starter_with_correct_prices(admin_session, demo_user):
    r = admin_session.get(f"{BASE_URL}/api/admin/users/{demo_user['id']}", timeout=15)
    assert r.status_code == 200
    plans = {p["id"]: p for p in r.json()["available_plans"]}
    assert {"free", "starter", "pro", "agency"} <= set(plans.keys()), f"Missing plans: {plans.keys()}"
    assert plans["free"]["price"] == 0.0
    assert plans["starter"]["price"] == 29.0
    assert plans["pro"]["price"] == 99.0
    assert plans["agency"]["price"] == 299.0


def test_set_plan_actually_flips(admin_session, demo_user, demo_workspace):
    # Flip to starter
    r = admin_session.post(
        f"{BASE_URL}/api/admin/users/{demo_user['id']}/plan",
        json={"workspace_id": demo_workspace["id"], "plan": "starter"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plan"] == "starter"
    assert "previous_plan" in body
    assert "mollie_synced" in body

    # Verify subsequent GET shows the change in BOTH user.plan and
    # workspaces.plan (the legacy display field) and the resolved
    # plan_details.
    r = admin_session.get(f"{BASE_URL}/api/admin/users/{demo_user['id']}", timeout=15)
    assert r.status_code == 200
    detail = r.json()
    assert detail["user"]["plan"] == "starter"
    ws = next(w for w in detail["workspaces"] if w["id"] == demo_workspace["id"])
    assert ws["plan"] == "starter"
    assert ws["plan_details"]["id"] == "starter"
    assert ws["plan_details"]["price"] == 29.0


def test_set_plan_roundtrip(admin_session, demo_user, demo_workspace):
    for target in ("pro", "agency", "free", "pro"):
        r = admin_session.post(
            f"{BASE_URL}/api/admin/users/{demo_user['id']}/plan",
            json={"workspace_id": demo_workspace["id"], "plan": target},
            timeout=15,
        )
        assert r.status_code == 200, f"flip to {target} failed: {r.text}"
        assert r.json()["plan"] == target
        # Cross-verify
        v = admin_session.get(f"{BASE_URL}/api/admin/users/{demo_user['id']}", timeout=15).json()
        assert v["user"]["plan"] == target


def test_set_plan_unknown_id_returns_400(admin_session, demo_user, demo_workspace):
    r = admin_session.post(
        f"{BASE_URL}/api/admin/users/{demo_user['id']}/plan",
        json={"workspace_id": demo_workspace["id"], "plan": "ultraplatinum"},
        timeout=15,
    )
    assert r.status_code == 400


def test_set_plan_non_admin_is_forbidden(user_session, demo_user, demo_workspace):
    r = user_session.post(
        f"{BASE_URL}/api/admin/users/{demo_user['id']}/plan",
        json={"workspace_id": demo_workspace["id"], "plan": "pro"},
        timeout=15,
    )
    assert r.status_code == 403


def test_set_plan_wrong_workspace_owner_returns_400(admin_session, demo_user):
    # Pass a workspace_id that exists but isn't owned by demo
    r = admin_session.post(
        f"{BASE_URL}/api/admin/users/{demo_user['id']}/plan",
        json={"workspace_id": "00000000-0000-0000-0000-000000000000", "plan": "pro"},
        timeout=15,
    )
    assert r.status_code == 400
