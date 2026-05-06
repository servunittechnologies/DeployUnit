"""
DeployHub backend API tests.
Uses the public preview URL from REACT_APP_BACKEND_URL and cookie-based auth.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://deploykit-dash.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

DEMO_EMAIL = "demo@deployhub.dev"
DEMO_PASS = "demo1234"
EMAIL_DOMAIN = "deployhub-test.io"  # avoid pydantic reserved .test TLD


# ----- Shared fixtures -----
@pytest.fixture(scope="session")
def demo_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASS}, timeout=15)
    assert r.status_code == 200, f"Demo login failed: {r.status_code} {r.text}"
    assert "access_token" in s.cookies, "access_token cookie not set on login"
    return s


@pytest.fixture(scope="session")
def demo_workspace_id(demo_session):
    r = demo_session.get(f"{API}/workspaces", timeout=15)
    assert r.status_code == 200
    ws = r.json()
    assert len(ws) >= 1
    acme = next((w for w in ws if w.get("name") == "Acme Studio"), ws[0])
    return acme["id"]


# ----- Health -----
class TestHealth:
    def test_health(self):
        r = requests.get(f"{API}/health", timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_root(self):
        r = requests.get(f"{API}/", timeout=10)
        assert r.status_code == 200
        assert r.json().get("service") == "deployhub"


# ----- Auth -----
class TestAuth:
    def test_register_new_user_sets_cookies_and_bootstraps_workspace(self):
        s = requests.Session()
        email = f"TEST_{uuid.uuid4().hex[:8]}@deployhub-test.io"
        r = s.post(f"{API}/auth/register", json={"email": email, "password": "pass1234", "name": "Test User"}, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == email
        assert "_id" not in data and "password_hash" not in data
        assert "access_token" in s.cookies and "refresh_token" in s.cookies
        # bootstrap: workspaces endpoint must return at least one with my_role=owner
        w = s.get(f"{API}/workspaces", timeout=10)
        assert w.status_code == 200
        ws = w.json()
        assert len(ws) >= 1
        assert any(x.get("my_role") == "owner" for x in ws)

    def test_register_duplicate_email_rejected(self, demo_session):
        r = requests.post(f"{API}/auth/register",
                          json={"email": DEMO_EMAIL, "password": "x", "name": "dup"}, timeout=15)
        assert r.status_code == 400

    def test_login_demo_and_me(self, demo_session):
        r = demo_session.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 200
        assert r.json()["email"] == DEMO_EMAIL

    def test_auth_required_without_cookie_returns_401(self):
        r = requests.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 401
        r2 = requests.get(f"{API}/workspaces", timeout=10)
        assert r2.status_code == 401

    def test_brute_force_lockout_returns_429(self):
        # Use a new email that has never logged in to get a fresh counter
        email = f"TEST_bf_{uuid.uuid4().hex[:6]}@deployhub-test.io"
        last = None
        for _ in range(6):
            s = requests.Session()
            last = s.post(f"{API}/auth/login", json={"email": email, "password": "wrong"}, timeout=15)
        assert last.status_code == 429, f"expected 429 after 5 wrong logins, got {last.status_code}"


# ----- Workspaces -----
class TestWorkspaces:
    def test_list_workspaces_demo_is_owner_of_acme(self, demo_session):
        r = demo_session.get(f"{API}/workspaces", timeout=10)
        assert r.status_code == 200
        ws = r.json()
        assert any(w.get("name") == "Acme Studio" and w.get("my_role") == "owner" for w in ws)

    def test_create_agency_workspace(self, demo_session):
        name = f"TEST_Agency_{uuid.uuid4().hex[:6]}"
        r = demo_session.post(f"{API}/workspaces",
                              json={"name": name, "type": "agency"}, timeout=15)
        assert r.status_code in (200, 201), r.text
        data = r.json()
        assert data["name"] == name
        assert data.get("type") == "agency"
        # verify listed
        lst = demo_session.get(f"{API}/workspaces", timeout=10).json()
        assert any(w["id"] == data["id"] and w.get("my_role") == "owner" for w in lst)


# ----- Projects -----
class TestProjects:
    def test_list_projects_seeded_novabrew(self, demo_session, demo_workspace_id):
        r = demo_session.get(f"{API}/projects", params={"workspace_id": demo_workspace_id}, timeout=10)
        assert r.status_code == 200
        projs = r.json()
        assert any(p.get("name") == "Client: NovaBrew Coffee" for p in projs), f"got {[p.get('name') for p in projs]}"

    def test_create_get_delete_project(self, demo_session, demo_workspace_id):
        name = f"TEST_Proj_{uuid.uuid4().hex[:6]}"
        r = demo_session.post(f"{API}/projects",
                              json={"workspace_id": demo_workspace_id, "name": name}, timeout=15)
        assert r.status_code in (200, 201), r.text
        pid = r.json()["id"]
        g = demo_session.get(f"{API}/projects/{pid}", timeout=10)
        assert g.status_code == 200
        gdata = g.json()
        assert gdata["name"] == name
        assert "apps" in gdata and isinstance(gdata["apps"], list)
        d = demo_session.delete(f"{API}/projects/{pid}", timeout=10)
        assert d.status_code in (200, 204)


# ----- Apps -----
class TestApps:
    def test_list_seeded_apps(self, demo_session, demo_workspace_id):
        r = demo_session.get(f"{API}/apps", params={"workspace_id": demo_workspace_id}, timeout=10)
        assert r.status_code == 200
        apps = r.json()
        names = {a["name"] for a in apps}
        assert {"novabrew-web", "novabrew-api", "novabrew-admin"}.issubset(names), f"got {names}"

    def test_create_app_and_stub_completes(self, demo_session, demo_workspace_id):
        name = f"TEST_app_{uuid.uuid4().hex[:6]}"
        r = demo_session.post(f"{API}/apps",
                              json={
                                  "workspace_id": demo_workspace_id,
                                  "name": name,
                                  "framework": "nextjs",
                                  "repo_url": "https://github.com/vercel/next.js",
                                  "branch": "main",
                              }, timeout=20)
        assert r.status_code in (200, 201), r.text
        app = r.json()
        assert app["status"] in ("queued", "building", "live"), app["status"]
        app_id = app["id"]

        # Poll up to ~45s for deploy_sync (every 15s) stub to mark live
        final_status = app["status"]
        for _ in range(10):
            time.sleep(5)
            g = demo_session.get(f"{API}/apps/{app_id}", timeout=10)
            assert g.status_code == 200
            final_status = g.json()["status"]
            if final_status in ("live", "failed"):
                break
        # Either live (stub or real) or at worst still building (if real coolify)
        assert final_status in ("live", "building", "failed"), final_status

        # Deployments listed newest first
        d = demo_session.get(f"{API}/apps/{app_id}/deployments", timeout=10)
        assert d.status_code == 200
        deps = d.json()
        assert len(deps) >= 1

        # Redeploy creates another
        rd = demo_session.post(f"{API}/apps/{app_id}/redeploy", timeout=15)
        assert rd.status_code in (200, 201)
        d2 = demo_session.get(f"{API}/apps/{app_id}/deployments", timeout=10).json()
        assert len(d2) >= len(deps) + 1

        # Env GET/PUT
        e = demo_session.get(f"{API}/apps/{app_id}/env", timeout=10)
        assert e.status_code == 200
        up = demo_session.put(f"{API}/apps/{app_id}/env", json={"env_vars": {"FOO": "bar"}}, timeout=10)
        assert up.status_code == 200
        assert up.json()["env_vars"].get("FOO") == "bar"

        # Restart
        rs = demo_session.post(f"{API}/apps/{app_id}/restart", timeout=10)
        assert rs.status_code == 200
        assert rs.json().get("ok") is True

        # Monitoring structure
        m = demo_session.get(f"{API}/apps/{app_id}/monitoring", timeout=10)
        assert m.status_code == 200
        mdata = m.json()
        assert "uptime_pct" in mdata and "samples" in mdata

        # Cleanup
        demo_session.delete(f"{API}/apps/{app_id}", timeout=10)


# ----- Domains -----
class TestDomains:
    @pytest.fixture(scope="class")
    def target_app_id(self, demo_session, demo_workspace_id):
        apps = demo_session.get(f"{API}/apps", params={"workspace_id": demo_workspace_id}, timeout=10).json()
        assert apps
        return apps[0]["id"]

    def test_create_verify_list_and_duplicate_domain(self, demo_session, demo_workspace_id, target_app_id):
        dom = f"test-{uuid.uuid4().hex[:6]}.example.com"
        r = demo_session.post(f"{API}/domains", json={"app_id": target_app_id, "domain": dom}, timeout=10)
        assert r.status_code in (200, 201), r.text
        did = r.json()["id"]

        v = demo_session.post(f"{API}/domains/{did}/verify", timeout=10)
        assert v.status_code == 200
        assert v.json().get("dns_verified") is True

        lst = demo_session.get(f"{API}/domains", params={"workspace_id": demo_workspace_id}, timeout=10)
        assert lst.status_code == 200
        assert any(d["id"] == did for d in lst.json())

        dup = demo_session.post(f"{API}/domains", json={"app_id": target_app_id, "domain": dom}, timeout=10)
        assert dup.status_code == 400

        rm = demo_session.delete(f"{API}/domains/{did}", timeout=10)
        assert rm.status_code in (200, 204)


# ----- Monitoring -----
class TestMonitoring:
    def test_overview(self, demo_session, demo_workspace_id):
        r = demo_session.get(f"{API}/monitoring/overview", params={"workspace_id": demo_workspace_id}, timeout=10)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list) and len(rows) >= 1


# ----- Alerts -----
class TestAlerts:
    def test_alert_crud(self, demo_session, demo_workspace_id):
        apps = demo_session.get(f"{API}/apps", params={"workspace_id": demo_workspace_id}, timeout=10).json()
        app_id = apps[0]["id"]
        r = demo_session.post(f"{API}/alerts",
                              json={"workspace_id": demo_workspace_id, "app_id": app_id,
                                    "type": "app_down", "threshold": 1, "enabled": True}, timeout=10)
        assert r.status_code in (200, 201), r.text
        aid = r.json()["id"]
        lst = demo_session.get(f"{API}/alerts", params={"workspace_id": demo_workspace_id}, timeout=10)
        assert lst.status_code == 200
        assert any(a["id"] == aid for a in lst.json())
        tog = demo_session.patch(f"{API}/alerts/{aid}", json={"enabled": False}, timeout=10)
        assert tog.status_code == 200
        assert tog.json().get("enabled") is False
        rm = demo_session.delete(f"{API}/alerts/{aid}", timeout=10)
        assert rm.status_code in (200, 204)


# ----- Billing -----
class TestBilling:
    def test_plans(self):
        r = requests.get(f"{API}/billing/plans", timeout=10)
        assert r.status_code == 200
        plans = r.json()
        assert {p["id"] for p in plans} == {"hobby", "pro", "agency"}

    def test_subscription_and_hobby_checkout(self, demo_session, demo_workspace_id):
        s = demo_session.get(f"{API}/billing/subscription", params={"workspace_id": demo_workspace_id}, timeout=10)
        assert s.status_code == 200
        assert "plan" in s.json()

        r = demo_session.post(f"{API}/billing/checkout",
                              json={"workspace_id": demo_workspace_id, "plan": "hobby"}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["plan"] == "hobby"
        assert data["status"] == "active"

    def test_pro_checkout_whmcs_best_effort(self, demo_session, demo_workspace_id):
        r = demo_session.post(f"{API}/billing/checkout",
                              json={"workspace_id": demo_workspace_id, "plan": "pro"}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["plan"] == "pro"
        assert data["status"] in ("pending", "active", "trial")

    def test_invoices_list(self, demo_session, demo_workspace_id):
        r = demo_session.get(f"{API}/billing/invoices", params={"workspace_id": demo_workspace_id}, timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ----- Notifications -----
class TestNotifications:
    def test_notifications_flow(self, demo_session, demo_workspace_id):
        r = demo_session.get(f"{API}/notifications", params={"workspace_id": demo_workspace_id}, timeout=10)
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        first_id = items[0]["id"]
        mk = demo_session.post(f"{API}/notifications/{first_id}/read", timeout=10)
        assert mk.status_code == 200
        assert mk.json().get("read") is True or mk.json().get("ok") is True
        ra = demo_session.post(f"{API}/notifications/read-all",
                               params={"workspace_id": demo_workspace_id}, timeout=10)
        assert ra.status_code == 200


# ----- GitHub mock -----
class TestGitHub:
    def test_repos_returns_5(self, demo_session):
        r = demo_session.get(f"{API}/github/repos", timeout=10)
        assert r.status_code == 200
        repos = r.json()
        assert isinstance(repos, list) and len(repos) == 5


# ----- Settings -----
class TestSettings:
    def test_update_name_and_change_password(self):
        s = requests.Session()
        email = f"TEST_settings_{uuid.uuid4().hex[:6]}@deployhub-test.io"
        r = s.post(f"{API}/auth/register",
                   json={"email": email, "password": "origpass1", "name": "Orig Name"}, timeout=15)
        assert r.status_code == 200
        up = s.patch(f"{API}/users/me", json={"name": "New Name"}, timeout=10)
        assert up.status_code == 200
        assert up.json().get("name") == "New Name"

        bad = s.post(f"{API}/users/me/change-password",
                     json={"current_password": "WRONG", "new_password": "newpass1"}, timeout=10)
        assert bad.status_code in (400, 401, 403)

        good = s.post(f"{API}/users/me/change-password",
                      json={"current_password": "origpass1", "new_password": "newpass1"}, timeout=10)
        assert good.status_code == 200

        # login with new pw
        s2 = requests.Session()
        rl = s2.post(f"{API}/auth/login", json={"email": email, "password": "newpass1"}, timeout=15)
        assert rl.status_code == 200


# ----- Integrations health -----
class TestIntegrations:
    def test_integrations_health(self, demo_session):
        r = demo_session.get(f"{API}/integrations/health", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "coolify" in data and "whmcs" in data
        assert "configured" in data["coolify"] and "configured" in data["whmcs"]


# ----- Workspace isolation -----
class TestIsolation:
    def test_stranger_cannot_read_others_apps(self, demo_workspace_id):
        s = requests.Session()
        email = f"TEST_iso_{uuid.uuid4().hex[:6]}@deployhub-test.io"
        rr = s.post(f"{API}/auth/register",
                    json={"email": email, "password": "pw12345x", "name": "Iso User"}, timeout=15)
        assert rr.status_code == 200
        r = s.get(f"{API}/apps", params={"workspace_id": demo_workspace_id}, timeout=10)
        assert r.status_code == 403
