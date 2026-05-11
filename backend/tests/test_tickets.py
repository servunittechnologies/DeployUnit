"""End-to-end tests for the Support Ticket System.

Covers:
- User flow: create, list mine, detail, reply, close, 409 on closed reply
- RBAC: 403 on another user's ticket; 403 for non-admin on admin routes
- Admin flow: list w/ filters, stats, detail (user_email/name), PATCH (incl. 400 invalid),
  reply -> status flips to awaiting_user, user reply -> awaiting_support
"""
import os
import uuid
import pytest
import requests
from dotenv import dotenv_values

_fe_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or _fe_env.get("REACT_APP_BACKEND_URL")).rstrip("/")

ADMIN_EMAIL = "admin@deployunit.com"
ADMIN_PASSWORD = "admin123"
USER_EMAIL = "demo@deployunit.com"
USER_PASSWORD = "demo1234"
OTHER_EMAIL = "martijn@servunit.com"
OTHER_PASSWORD = "Reset-NMsS5GTQh-vx4g"


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def user_session():
    return _login(USER_EMAIL, USER_PASSWORD)


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def other_session():
    """Register a fresh non-admin user (martijn is admin per iter13 notes)."""
    s = requests.Session()
    email = f"TEST_other_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/register",
               json={"email": email, "password": "Passw0rd!", "name": "TEST Other"},
               timeout=20)
    if r.status_code not in (200, 201):
        pytest.skip(f"register failed: {r.status_code} {r.text}")
    # Some setups auto-login on register; ensure login works either way.
    s.post(f"{BASE_URL}/api/auth/login",
           json={"email": email, "password": "Passw0rd!"}, timeout=20)
    return s


# ------------------- USER FLOW -------------------

def test_create_ticket_minimum_validation(user_session):
    # message too short
    r = user_session.post(f"{BASE_URL}/api/tickets",
                          json={"subject": "TEST_short", "message": "short", "category": "other"})
    assert r.status_code in (400, 422), r.text


@pytest.fixture(scope="module")
def created_ticket(user_session):
    payload = {
        "subject": f"TEST_subject_{uuid.uuid4().hex[:6]}",
        "message": "This is a TEST ticket created by the regression suite. Please ignore.",
        "category": "technical",
        "priority": "high",
    }
    r = user_session.post(f"{BASE_URL}/api/tickets", json=payload)
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["status"] == "open"
    assert t["subject"] == payload["subject"]
    assert t["priority"] == "high"
    assert t["category"] == "technical"
    assert t["message_count"] == 1
    assert "id" in t
    assert "_id" not in t
    return t


def test_list_my_tickets_contains_new(user_session, created_ticket):
    r = user_session.get(f"{BASE_URL}/api/tickets")
    assert r.status_code == 200
    body = r.json()
    assert "tickets" in body
    ids = [t["id"] for t in body["tickets"]]
    assert created_ticket["id"] in ids


def test_user_detail_has_initial_message(user_session, created_ticket):
    r = user_session.get(f"{BASE_URL}/api/tickets/{created_ticket['id']}")
    assert r.status_code == 200
    d = r.json()
    assert d["ticket"]["id"] == created_ticket["id"]
    assert len(d["messages"]) == 1
    assert d["messages"][0]["author_role"] == "user"


def test_other_user_forbidden(other_session, created_ticket):
    r = other_session.get(f"{BASE_URL}/api/tickets/{created_ticket['id']}")
    assert r.status_code == 403


def test_anonymous_unauthenticated(created_ticket):
    r = requests.get(f"{BASE_URL}/api/tickets/{created_ticket['id']}")
    assert r.status_code in (401, 403)


def test_user_reply_flips_to_awaiting_support(user_session, admin_session, created_ticket):
    # first put it into awaiting_user state via admin so we can flip back
    r0 = admin_session.patch(f"{BASE_URL}/api/admin/tickets/{created_ticket['id']}",
                             json={"status": "awaiting_user"})
    assert r0.status_code == 200
    r = user_session.post(f"{BASE_URL}/api/tickets/{created_ticket['id']}/messages",
                          json={"body": "Follow-up message from TEST user."})
    assert r.status_code == 200, r.text
    detail = user_session.get(f"{BASE_URL}/api/tickets/{created_ticket['id']}").json()
    assert detail["ticket"]["status"] == "awaiting_support"
    assert detail["ticket"]["message_count"] == 2


# ------------------- ADMIN RBAC + FLOW -------------------

def test_non_admin_forbidden_on_admin_routes(user_session):
    for path in ("/api/admin/tickets", "/api/admin/tickets/stats"):
        r = user_session.get(f"{BASE_URL}{path}")
        assert r.status_code == 403, f"{path} -> {r.status_code}"


def test_admin_list_filters_and_pagination(admin_session, created_ticket):
    r = admin_session.get(f"{BASE_URL}/api/admin/tickets",
                          params={"status": "awaiting_support", "limit": 50})
    assert r.status_code == 200
    body = r.json()
    assert "tickets" in body and "total" in body and "limit" in body and "offset" in body
    assert all(t["status"] == "awaiting_support" for t in body["tickets"])
    # search filter
    r2 = admin_session.get(f"{BASE_URL}/api/admin/tickets",
                           params={"q": created_ticket["subject"][:20]})
    assert r2.status_code == 200
    assert any(t["id"] == created_ticket["id"] for t in r2.json()["tickets"])


def test_admin_stats_keys(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/tickets/stats")
    assert r.status_code == 200
    s = r.json()
    for key in ("open", "awaiting_support", "awaiting_user",
                "resolved", "closed", "total", "needs_attention"):
        assert key in s, f"missing key {key}"
        assert isinstance(s[key], int)
    assert s["needs_attention"] == s["open"] + s["awaiting_support"]


def test_admin_detail_includes_user_email(admin_session, created_ticket):
    r = admin_session.get(f"{BASE_URL}/api/admin/tickets/{created_ticket['id']}")
    assert r.status_code == 200
    d = r.json()
    assert d["ticket"]["user_email"] == USER_EMAIL
    assert d["ticket"].get("user_name")


def test_admin_reply_flips_to_awaiting_user(admin_session, user_session, created_ticket):
    r = admin_session.post(
        f"{BASE_URL}/api/admin/tickets/{created_ticket['id']}/messages",
        json={"body": "TEST admin reply — please ignore."},
    )
    assert r.status_code == 200, r.text
    detail = user_session.get(f"{BASE_URL}/api/tickets/{created_ticket['id']}").json()
    assert detail["ticket"]["status"] == "awaiting_user"
    assert detail["ticket"]["last_msg_role"] == "admin"
    # message visible to user, tagged as admin
    assert any(m["author_role"] == "admin" for m in detail["messages"])


def test_admin_patch_invalid_status_400(admin_session, created_ticket):
    r = admin_session.patch(f"{BASE_URL}/api/admin/tickets/{created_ticket['id']}",
                            json={"status": "bogus_state"})
    # Pydantic Literal -> 422; explicit check inside also raises 400. Accept either.
    assert r.status_code in (400, 422), r.text


def test_admin_patch_valid_updates(admin_session, created_ticket):
    r = admin_session.patch(f"{BASE_URL}/api/admin/tickets/{created_ticket['id']}",
                            json={"status": "resolved", "priority": "low"})
    assert r.status_code == 200
    t = r.json()
    assert t["status"] == "resolved"
    assert t["priority"] == "low"


# ------------------- CLOSE + 409 -------------------

def test_user_close_own_ticket_then_reply_blocked(user_session, created_ticket):
    r = user_session.post(f"{BASE_URL}/api/tickets/{created_ticket['id']}/close")
    assert r.status_code == 200
    # verify status
    d = user_session.get(f"{BASE_URL}/api/tickets/{created_ticket['id']}").json()
    assert d["ticket"]["status"] == "closed"
    # 409 on reply to closed
    r2 = user_session.post(f"{BASE_URL}/api/tickets/{created_ticket['id']}/messages",
                           json={"body": "should be blocked"})
    assert r2.status_code == 409, r2.text


def test_stats_reflect_closed(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/tickets/stats")
    assert r.status_code == 200
    assert r.json()["closed"] >= 1


# ------------------- REGRESSION SANITY -------------------

@pytest.mark.parametrize("path", [
    "/api/auth/me",
    "/api/account",
])
def test_regression_user_endpoints(user_session, path):
    r = user_session.get(f"{BASE_URL}{path}")
    assert r.status_code == 200, f"{path} -> {r.status_code}"


@pytest.mark.parametrize("path", [
    "/api/admin/users",
    "/api/admin/tickets/stats",
])
def test_regression_admin_endpoints(admin_session, path):
    r = admin_session.get(f"{BASE_URL}{path}")
    assert r.status_code == 200, f"{path} -> {r.status_code}"
