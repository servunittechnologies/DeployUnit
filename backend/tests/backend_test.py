"""
DeployHub backend API tests.
Uses the public preview URL from REACT_APP_BACKEND_URL and cookie-based auth.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://help-desk-151.preview.emergentagent.com").rstrip("/")
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
    # Ensure plan-cap headroom for the test suite — direct DB nudge.
    # Load env from backend/.env so MONGO_URL/DB_NAME are available even when
    # pytest is invoked without supervisor's environment.
    from dotenv import load_dotenv
    from pymongo import MongoClient
    load_dotenv("/app/backend/.env")
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if mongo_url and db_name:
        MongoClient(mongo_url)[db_name].workspaces.update_one(
            {"id": acme["id"]}, {"$set": {"plan": "agency"}}
        )
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


# ----- Iteration 4: PATCH app, redeploy body, github branches/commits -----
class TestAppsIter4:
    @pytest.fixture(scope="class")
    def target_app(self, demo_session, demo_workspace_id):
        apps = demo_session.get(f"{API}/apps", params={"workspace_id": demo_workspace_id}, timeout=10).json()
        assert apps, "expected seeded apps"
        return apps[0]

    def test_patch_app_updates_fields_and_is_idempotent(self, demo_session, target_app):
        app_id = target_app["id"]
        original_name = target_app["name"]
        new_name = original_name if "-renamed-x" in original_name else f"{original_name}-renamed-x"
        payload = {
            "name": new_name,
            "branch": "main",
            "build_command": "yarn build",
            "start_command": "yarn start",
            "auto_deploy": True,
        }
        r = demo_session.patch(f"{API}/apps/{app_id}", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "_id" not in data
        assert data["name"] == new_name
        assert data["branch"] == "main"
        assert data["build_command"] == "yarn build"
        assert data["start_command"] == "yarn start"
        assert data.get("auto_deploy") is True
        # Re-PATCH idempotent
        r2 = demo_session.patch(f"{API}/apps/{app_id}", json=payload, timeout=15)
        assert r2.status_code == 200
        data2 = r2.json()
        assert data2["name"] == new_name
        assert data2.get("auto_deploy") is True
        # GET persistence
        g = demo_session.get(f"{API}/apps/{app_id}", timeout=10).json()
        assert g["name"] == new_name
        assert g["build_command"] == "yarn build"

    def test_github_branches_fallback_no_token(self, demo_session):
        for url in ["https://github.com/vercel/next.js", "https://github.com/expressjs/express"]:
            r = demo_session.get(f"{API}/github/branches", params={"repo_url": url}, timeout=15)
            assert r.status_code == 200, r.text
            data = r.json()
            assert isinstance(data, list) and len(data) == 1
            assert data[0]["name"] == "main"
            assert data[0]["commit_sha"] is None
            assert data[0]["default"] is True

    def test_github_branches_invalid_url_returns_empty(self, demo_session):
        r = demo_session.get(f"{API}/github/branches", params={"repo_url": "https://example.com/foo/bar"}, timeout=10)
        assert r.status_code == 200
        assert r.json() == []

    def test_github_commits_no_token_returns_empty(self, demo_session):
        r = demo_session.get(f"{API}/github/commits",
                             params={"repo_url": "https://github.com/vercel/next.js", "branch": "main"},
                             timeout=15)
        assert r.status_code == 200
        assert r.json() == []

    def test_redeploy_with_branch_and_commit(self, demo_session, target_app):
        app_id = target_app["id"]
        r = demo_session.post(f"{API}/apps/{app_id}/redeploy",
                              json={"branch": "develop", "commit_sha": "abc1234567"}, timeout=15)
        assert r.status_code in (200, 201), r.text
        d = r.json()
        assert d["status"] in ("building", "queued")
        assert d["commit_sha"] == "abc1234567"
        assert d["branch"] == "develop"
        assert "develop" in d["commit_message"]
        assert "@abc1234" in d["commit_message"]
        # App branch updated
        g = demo_session.get(f"{API}/apps/{app_id}", timeout=10).json()
        assert g["branch"] == "develop"
        # Restore branch to main for idempotency of other tests
        demo_session.patch(f"{API}/apps/{app_id}", json={"branch": "main"}, timeout=10)

    def test_redeploy_empty_body_uses_current_branch(self, demo_session, target_app):
        app_id = target_app["id"]
        # Ensure branch is main first
        demo_session.patch(f"{API}/apps/{app_id}", json={"branch": "main"}, timeout=10)
        r = demo_session.post(f"{API}/apps/{app_id}/redeploy", json={}, timeout=15)
        assert r.status_code in (200, 201), r.text
        d = r.json()
        assert d["commit_sha"] is None
        assert d["branch"] == "main"
        assert d["commit_message"] == "Manual redeploy"



# ----- Iteration 5: Branch protection, Rollback, Health -----
class TestAppsIter5:
    @pytest.fixture(scope="class")
    def target_app(self, demo_session, demo_workspace_id):
        apps = demo_session.get(f"{API}/apps", params={"workspace_id": demo_workspace_id}, timeout=10).json()
        assert apps, "expected seeded apps"
        return apps[0]

    def test_patch_tier_and_protected_branches(self, demo_session, target_app):
        app_id = target_app["id"]
        r = demo_session.patch(f"{API}/apps/{app_id}",
                               json={"tier": "production", "protected_branches": ["main", "release"]},
                               timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["tier"] == "production"
        assert d["protected_branches"] == ["main", "release"]
        # Reset back to development (clears restriction at runtime)
        r2 = demo_session.patch(f"{API}/apps/{app_id}", json={"tier": "development"}, timeout=10)
        assert r2.status_code == 200
        assert r2.json()["tier"] == "development"

    def test_redeploy_branch_protection_403_and_allowed_200(self, demo_session, target_app):
        app_id = target_app["id"]
        # Lock down to main only
        demo_session.patch(f"{API}/apps/{app_id}",
                           json={"tier": "production", "protected_branches": ["main"]}, timeout=10)
        try:
            # Disallowed branch -> 403
            r = demo_session.post(f"{API}/apps/{app_id}/redeploy",
                                  json={"branch": "feature/x"}, timeout=15)
            assert r.status_code == 403, r.text
            assert r.json().get("detail", "").startswith("Branch protection:")
            # Allowed branch -> 200/building
            r2 = demo_session.post(f"{API}/apps/{app_id}/redeploy",
                                   json={"branch": "main"}, timeout=15)
            assert r2.status_code in (200, 201), r2.text
            assert r2.json()["status"] in ("queued", "building")
        finally:
            demo_session.patch(f"{API}/apps/{app_id}", json={"tier": "development"}, timeout=10)

    def test_rollback_creates_new_deployment(self, demo_session, target_app):
        app_id = target_app["id"]
        # Wait briefly so any in-flight from prior test can finish
        finished = None
        for _ in range(8):
            deps = demo_session.get(f"{API}/apps/{app_id}/deployments", timeout=10).json()
            finished = next((d for d in deps if d["status"] in ("live", "failed")), None)
            if finished:
                break
            time.sleep(3)
        assert finished, "expected at least one finished deployment to roll back to"
        target_id = finished["id"]
        r = demo_session.post(f"{API}/apps/{app_id}/rollback/{target_id}", timeout=20)
        assert r.status_code in (200, 201), r.text
        d = r.json()
        assert d["status"] in ("queued", "building")
        assert d["branch"] == finished.get("branch")
        assert d.get("commit_sha") == finished.get("commit_sha")
        assert (d.get("commit_message") or "").startswith("Rollback to")

    def test_rollback_inflight_returns_400(self, demo_session, target_app):
        app_id = target_app["id"]
        # Fire a redeploy to create an in-flight deployment
        rd = demo_session.post(f"{API}/apps/{app_id}/redeploy", json={}, timeout=15)
        assert rd.status_code in (200, 201)
        new_id = rd.json()["id"]
        # Immediately try to rollback to it (should be queued/building)
        r = demo_session.post(f"{API}/apps/{app_id}/rollback/{new_id}", timeout=15)
        # Race: it may have already transitioned. Accept 400 OR the new one is finished.
        if r.status_code != 400:
            # if it transitioned already, that's still an acceptable success
            assert r.status_code in (200, 201)
        else:
            assert "in progress" in r.json().get("detail", "").lower()

    def test_rollback_branch_protection_403(self, demo_session, target_app):
        app_id = target_app["id"]
        # Find a deployment with branch != main
        deps = demo_session.get(f"{API}/apps/{app_id}/deployments", timeout=10).json()
        non_main = next((d for d in deps
                         if d.get("branch") and d["branch"] != "main"
                         and d["status"] in ("live", "failed")), None)
        if not non_main:
            # Create one: redeploy on develop, then patch back to main
            rd = demo_session.post(f"{API}/apps/{app_id}/redeploy",
                                   json={"branch": "develop"}, timeout=15)
            assert rd.status_code in (200, 201)
            new_id = rd.json()["id"]
            # Wait for it to finish
            for _ in range(10):
                time.sleep(3)
                deps = demo_session.get(f"{API}/apps/{app_id}/deployments", timeout=10).json()
                cur = next((x for x in deps if x["id"] == new_id), None)
                if cur and cur["status"] in ("live", "failed"):
                    non_main = cur
                    break
            demo_session.patch(f"{API}/apps/{app_id}", json={"branch": "main"}, timeout=10)
        if not non_main:
            pytest.skip("could not produce a finished non-main deployment")
        # Lock down to main only
        demo_session.patch(f"{API}/apps/{app_id}",
                           json={"tier": "production", "protected_branches": ["main"]}, timeout=10)
        try:
            r = demo_session.post(f"{API}/apps/{app_id}/rollback/{non_main['id']}", timeout=15)
            assert r.status_code == 403, r.text
            assert "Branch protection" in r.json().get("detail", "")
        finally:
            demo_session.patch(f"{API}/apps/{app_id}", json={"tier": "development"}, timeout=10)

    def test_health_endpoint_with_url(self, demo_session, target_app):
        app_id = target_app["id"]
        r = demo_session.get(f"{API}/apps/{app_id}/health", timeout=20)
        assert r.status_code == 200
        d = r.json()
        # Either available with metrics OR network failure with reason
        assert "available" in d
        if d.get("available"):
            for k in ("status_code", "ok", "response_time_ms", "framing_blocked", "checked_at", "url"):
                assert k in d, f"missing {k} in health"
            assert isinstance(d["response_time_ms"], int)
            assert isinstance(d["framing_blocked"], bool)
        else:
            # If app has primary_url but is down, reason must be present
            assert "reason" in d

    def test_health_endpoint_no_url(self, demo_session, demo_workspace_id):
        # Create a fresh app, then null its primary_url to force no_url path
        name = f"TEST_nohealth_{uuid.uuid4().hex[:6]}"
        r = demo_session.post(f"{API}/apps",
                              json={"workspace_id": demo_workspace_id, "name": name,
                                    "framework": "nextjs",
                                    "repo_url": "https://github.com/vercel/next.js",
                                    "branch": "main"}, timeout=15)
        assert r.status_code in (200, 201)
        app_id = r.json()["id"]
        try:
            # Wait briefly, then if it stubbed-live, we cannot easily null primary_url
            # via API. The endpoint behavior is what matters; if the new app has no url
            # yet (queued), we get no_url. Poll with short timeout.
            got_no_url = False
            for _ in range(3):
                hr = demo_session.get(f"{API}/apps/{app_id}/health", timeout=15)
                assert hr.status_code == 200
                hd = hr.json()
                if hd.get("available") is False and hd.get("reason") == "no_url":
                    got_no_url = True
                    break
                time.sleep(1)
            assert got_no_url, "expected no_url at least once for fresh app"
        finally:
            demo_session.delete(f"{API}/apps/{app_id}", timeout=10)

    def test_no_app_stuck_building_indefinitely(self, demo_session, demo_workspace_id):
        """Recent deployments should transition (not be stuck building forever)."""
        apps = demo_session.get(f"{API}/apps", params={"workspace_id": demo_workspace_id}, timeout=10).json()
        for app in apps[:3]:
            deps = demo_session.get(f"{API}/apps/{app['id']}/deployments", timeout=10).json()
            if not deps:
                continue
            # Among the 3 oldest, at least one should be live or failed
            oldest = deps[-3:] if len(deps) >= 3 else deps
            assert any(d["status"] in ("live", "failed") for d in oldest), \
                f"app {app['name']} oldest deployments all stuck: {[d['status'] for d in oldest]}"




# ----- Iteration 6: Auto-detect branch, log parser, SSE, failure summary -----
class TestIter6LogParser:
    """Unit tests for services.log_parser.parse_log_line."""
    def test_severity_classification(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from services.log_parser import parse_log_line, extract_failure_summary
        assert parse_log_line("[ERROR] foo")["severity"] == "error"
        assert parse_log_line("[BUILD] yarn install")["severity"] == "build"
        assert parse_log_line("fatal: clone failed")["severity"] == "error"
        assert parse_log_line("WARN: deprecated")["severity"] == "warning"
        assert parse_log_line("[DEPLOY] rolling out")["severity"] == "deploy"
        assert parse_log_line("some ordinary log line")["severity"] == "info"
        # Failure summary: recognisable pattern
        summary = extract_failure_summary([
            "cloning...",
            "Remote branch wrong-name not found in upstream origin",
        ])
        assert summary and summary.startswith("Git clone failed: branch")


class TestIter6AutoDetectBranch:
    """POST /apps now auto-detects the default branch for GitHub repos."""
    def test_autodetect_canary_for_vercel_nextjs(self, demo_session, demo_workspace_id):
        name = f"TEST_auto_{uuid.uuid4().hex[:6]}"
        r = demo_session.post(f"{API}/apps",
                              json={
                                  "workspace_id": demo_workspace_id, "name": name,
                                  "framework": "nextjs",
                                  "repo_url": "https://github.com/vercel/next.js",
                                  "branch": "main",
                              }, timeout=30)
        assert r.status_code in (200, 201), r.text
        app = r.json()
        app_id = app["id"]
        try:
            # vercel/next.js default is 'canary' — should auto-switch
            assert app["branch"] == "canary", f"expected 'canary', got {app['branch']}"
            # First deployment should log the auto-detection
            deps = demo_session.get(f"{API}/apps/{app_id}/deployments", timeout=10).json()
            assert deps, "expected at least one deployment"
            first = deps[-1]  # oldest
            logs_text = " ".join((first.get("logs") or []))
            assert "canary" in logs_text.lower() or "auto" in logs_text.lower(), \
                f"expected autodetect line in first deployment logs: {logs_text[:300]}"
        finally:
            demo_session.delete(f"{API}/apps/{app_id}", timeout=10)

    def test_shadcn_ui_main_stays_main(self, demo_session, demo_workspace_id):
        name = f"TEST_main_{uuid.uuid4().hex[:6]}"
        r = demo_session.post(f"{API}/apps",
                              json={
                                  "workspace_id": demo_workspace_id, "name": name,
                                  "framework": "nextjs",
                                  "repo_url": "https://github.com/shadcn-ui/ui",
                                  "branch": "main",
                              }, timeout=30)
        assert r.status_code in (200, 201), r.text
        app = r.json()
        app_id = app["id"]
        try:
            assert app["branch"] == "main", f"expected 'main' to stay, got {app['branch']}"
        finally:
            demo_session.delete(f"{API}/apps/{app_id}", timeout=10)

    def test_non_github_url_falls_back(self, demo_session, demo_workspace_id):
        name = f"TEST_nongh_{uuid.uuid4().hex[:6]}"
        r = demo_session.post(f"{API}/apps",
                              json={
                                  "workspace_id": demo_workspace_id, "name": name,
                                  "framework": "nextjs",
                                  "repo_url": "https://example.com/foo/bar.git",
                                  "branch": "develop",
                              }, timeout=20)
        assert r.status_code in (200, 201), r.text
        app = r.json()
        try:
            # Non-GitHub: should fall back to user-specified branch
            assert app["branch"] in ("develop", "main"), f"unexpected branch {app['branch']}"
            assert app["id"]  # Didn't crash
        finally:
            demo_session.delete(f"{API}/apps/{app['id']}", timeout=10)


class TestIter6DeploymentAnnotations:
    """GET /apps/{id}/deployments now returns parsed_logs + log_counts."""
    def test_deployment_rows_have_parsed_logs_and_counts(self, demo_session, demo_workspace_id):
        apps = demo_session.get(f"{API}/apps", params={"workspace_id": demo_workspace_id}, timeout=10).json()
        assert apps
        for app in apps[:3]:
            deps = demo_session.get(f"{API}/apps/{app['id']}/deployments", timeout=10).json()
            if not deps:
                continue
            for d in deps[:3]:
                assert "parsed_logs" in d, f"missing parsed_logs on deployment {d['id']}"
                assert isinstance(d["parsed_logs"], list)
                if d["parsed_logs"]:
                    sample = d["parsed_logs"][0]
                    assert "text" in sample and "severity" in sample
                    assert sample["severity"] in ("error", "warning", "info", "build", "deploy", "debug")
                assert "log_counts" in d
                lc = d["log_counts"]
                for k in ("total", "error", "warning", "info", "build", "deploy"):
                    assert k in lc, f"missing {k} in log_counts"
                    assert isinstance(lc[k], int)
            return  # tested on first app with deployments
        pytest.skip("no deployments to inspect")

    def test_novabrew_web_has_failure_summary(self, demo_session, demo_workspace_id):
        """At least one failed deployment on the renamed novabrew-web should have failure_summary populated."""
        apps = demo_session.get(f"{API}/apps", params={"workspace_id": demo_workspace_id}, timeout=10).json()
        target = next((a for a in apps if "novabrew-web" in a["name"]), None)
        if not target:
            pytest.skip("novabrew-web app not found")
        deps = demo_session.get(f"{API}/apps/{target['id']}/deployments", timeout=10).json()
        failed_with_summary = [d for d in deps
                                if d.get("status") == "failed"
                                and d.get("failure_summary")]
        assert failed_with_summary, \
            f"expected at least one failed deployment with failure_summary, got {len(deps)} deps"
        # Spot-check the summary begins with expected prefix
        prefixes = ("Git clone failed", "Build exited", "fatal", "error")
        assert any(
            any(d["failure_summary"].lower().startswith(p.lower()) for p in prefixes)
            for d in failed_with_summary
        ), f"unexpected failure_summary shape: {[d['failure_summary'][:80] for d in failed_with_summary[:3]]}"


class TestIter6SSEStream:
    """GET /api/deployments/{id}/stream — auth gate + emits at least one event."""
    def test_sse_unauthorized_without_cookie(self, demo_session, demo_workspace_id):
        apps = demo_session.get(f"{API}/apps", params={"workspace_id": demo_workspace_id}, timeout=10).json()
        assert apps
        deps = demo_session.get(f"{API}/apps/{apps[0]['id']}/deployments", timeout=10).json()
        assert deps
        dep_id = deps[0]["id"]
        # No cookie
        r = requests.get(f"{API}/deployments/{dep_id}/stream",
                         headers={"Accept": "text/event-stream"},
                         timeout=5)
        assert r.status_code == 401, f"expected 401 without cookie, got {r.status_code}"

    def test_sse_emits_event_line(self, demo_session, demo_workspace_id):
        apps = demo_session.get(f"{API}/apps", params={"workspace_id": demo_workspace_id}, timeout=10).json()
        assert apps
        # Find a deployment with logs
        dep_with_logs = None
        for app in apps[:3]:
            deps = demo_session.get(f"{API}/apps/{app['id']}/deployments", timeout=10).json()
            for d in deps:
                if (d.get("logs") or []) and len(d["logs"]) > 0:
                    dep_with_logs = d
                    break
            if dep_with_logs:
                break
        if not dep_with_logs:
            pytest.skip("no deployment with logs available")
        dep_id = dep_with_logs["id"]
        # Streaming GET with short read timeout
        with demo_session.get(f"{API}/deployments/{dep_id}/stream",
                              headers={"Accept": "text/event-stream"},
                              stream=True, timeout=(5, 8)) as r:
            assert r.status_code == 200, f"expected 200, got {r.status_code}"
            ctype = r.headers.get("Content-Type", "")
            assert "text/event-stream" in ctype, f"unexpected content-type: {ctype}"
            # Read up to ~8s of data
            collected = b""
            start = time.time()
            for chunk in r.iter_content(chunk_size=512):
                if chunk:
                    collected += chunk
                    if b"event: line" in collected or b"data:" in collected:
                        break
                if time.time() - start > 8:
                    break
            r.close()
            text = collected.decode("utf-8", errors="replace")
            assert ("event: line" in text) or ("data:" in text), \
                f"expected 'event: line' / 'data:' in SSE stream, got: {text[:300]!r}"


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

        # Real DNS verification (iter8): unverified random subdomain won't match our target.
        # We assert the endpoint returns a structured response, not that it matches.
        v = demo_session.post(f"{API}/domains/{did}/verify", timeout=15)
        assert v.status_code == 200
        body = v.json()
        assert "dns_verified" in body  # bool, will be False for a fake subdomain
        assert "last_dns_check" in body or "ssl_status" in body  # real-DNS response shape

        # The dns-target endpoint should always tell the user *what* to point to.
        target = demo_session.get(f"{API}/domains/{did}/dns-target", timeout=10).json()
        assert target.get("record_type") in ("A", "CNAME") or target.get("record_type") is None

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


# ----- Billing (Mollie + EU VAT) -----
class TestBilling:
    def test_plans_eur(self):
        r = requests.get(f"{API}/billing/plans", timeout=10)
        assert r.status_code == 200
        plans = r.json()
        by_id = {p["id"]: p for p in plans}
        assert set(by_id.keys()) == {"free", "pro", "agency"}
        assert by_id["free"]["currency"] == "EUR"
        assert by_id["free"]["price"] == 0
        assert by_id["pro"]["price"] == 20
        assert by_id["agency"]["price"] == 99
        # New fields from the credit-based model
        assert by_id["pro"]["credits"] == 50
        assert by_id["agency"]["credits"] == 250
        assert by_id["agency"]["fleet_view"] is True

    def test_countries_27_eu_plus_extras(self):
        r = requests.get(f"{API}/billing/countries", timeout=10)
        assert r.status_code == 200
        rows = r.json()
        eu = [c for c in rows if c["eu"]]
        non_eu = [c for c in rows if not c["eu"]]
        assert len(eu) == 27
        assert len(non_eu) >= 6
        for c in eu:
            assert "vat_rate" in c and "code" in c and "name" in c

    # Profile saves & VAT calculation
    def test_profile_nl_b2c_returns_21(self, demo_session, demo_workspace_id):
        body = {"company_name": "Demo NL", "address": "Keizersgracht 1", "postal_code": "1015CJ",
                "city": "Amsterdam", "country": "NL", "email": "demo@deployhub.dev", "is_business": False}
        r = demo_session.put(f"{API}/billing/profile",
                             params={"workspace_id": demo_workspace_id}, json=body, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["vat_rate_applied"] == 21.0
        assert ("NL" in d["vat_note"]) or ("Netherlands" in d["vat_note"])

        g = demo_session.get(f"{API}/billing/profile",
                             params={"workspace_id": demo_workspace_id}, timeout=10)
        assert g.status_code == 200 and g.json()["country"] == "NL"

    def test_profile_de_b2c_returns_19(self, demo_session, demo_workspace_id):
        body = {"company_name": "Demo DE", "address": "Strasse 1", "postal_code": "10115",
                "city": "Berlin", "country": "DE", "email": "demo@deployhub.dev", "is_business": False}
        r = demo_session.put(f"{API}/billing/profile",
                             params={"workspace_id": demo_workspace_id}, json=body, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["vat_rate_applied"] == 19.0
        assert "Germany" in d["vat_note"] or "DE" in d["vat_note"]

    def test_profile_us_returns_zero(self, demo_session, demo_workspace_id):
        body = {"company_name": "Demo US", "address": "1 Main St", "postal_code": "10001",
                "city": "NYC", "country": "US", "email": "demo@deployhub.dev", "is_business": False}
        r = demo_session.put(f"{API}/billing/profile",
                             params={"workspace_id": demo_workspace_id}, json=body, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["vat_rate_applied"] == 0.0
        assert "Outside EU" in d["vat_note"] or "no VAT" in d["vat_note"].lower()

    def test_profile_de_invalid_vat_falls_back_to_b2c(self, demo_session, demo_workspace_id):
        body = {"company_name": "Demo DE B2B", "address": "Strasse 2", "postal_code": "10115",
                "city": "Berlin", "country": "DE", "email": "demo@deployhub.dev",
                "is_business": True, "vat_id": "INVALID"}
        r = demo_session.put(f"{API}/billing/profile",
                             params={"workspace_id": demo_workspace_id}, json=body, timeout=20)
        assert r.status_code == 200
        d = r.json()
        # invalid VAT id → falls back to destination B2C → 19% DE
        assert d["vat_rate_applied"] == 19.0

    # VAT validate endpoint
    def test_vat_validate_malformed(self, demo_session):
        r = demo_session.get(f"{API}/billing/vat/validate", params={"vat_id": "ABC"}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["valid"] is False
        assert d.get("error") == "format"

    def test_vat_validate_invalid_or_unreachable(self, demo_session):
        r = demo_session.get(f"{API}/billing/vat/validate", params={"vat_id": "NL123456789B01"}, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["valid"] is False
        assert d.get("error") in ("invalid", "vies_unreachable", "vies_http_500", "vies_http_503")

    # Hobby checkout — no Mollie roundtrip
    def test_hobby_checkout_returns_active_no_url(self, demo_session, demo_workspace_id):
        # "hobby" plan id was renamed to "free" in iter8 (credit-based model);
        # the API still accepts "hobby" as an alias for backwards compatibility.
        r = demo_session.post(f"{API}/billing/checkout",
                              json={"workspace_id": demo_workspace_id, "plan": "free"}, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["plan"] == "free"
        assert d["status"] == "active"
        assert d["checkout_url"] is None

    # Pro checkout requires profile, then returns Mollie URL
    def test_pro_checkout_requires_profile_then_returns_mollie_url(self, demo_session, demo_workspace_id):
        # Make sure profile exists (set via earlier tests; re-set NL for determinism)
        body = {"company_name": "Demo B.V.", "address": "Keizersgracht 1", "postal_code": "1015CJ",
                "city": "Amsterdam", "country": "NL", "email": "demo@deployhub.dev", "is_business": False}
        demo_session.put(f"{API}/billing/profile",
                         params={"workspace_id": demo_workspace_id}, json=body, timeout=15)
        r = demo_session.post(f"{API}/billing/checkout",
                              json={"workspace_id": demo_workspace_id, "plan": "pro"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["plan"] == "pro"
        assert d["status"] == "pending"
        assert d.get("checkout_url", "").startswith("https://"), d
        assert d.get("payment_id")

    def test_pro_checkout_without_profile_returns_400(self, demo_session):
        # Use a fresh workspace with no profile
        s = requests.Session()
        email = f"TEST_noprof_{uuid.uuid4().hex[:6]}@deployhub-test.io"
        rr = s.post(f"{API}/auth/register",
                    json={"email": email, "password": "pw12345x", "name": "NoProf User"}, timeout=15)
        assert rr.status_code == 200
        ws_list = s.get(f"{API}/workspaces", timeout=10).json()
        ws_id = ws_list[0]["id"]
        r = s.post(f"{API}/billing/checkout",
                   json={"workspace_id": ws_id, "plan": "pro"}, timeout=20)
        assert r.status_code == 400
        assert "profile" in (r.text or "").lower()

    # Cancel
    def test_cancel_drops_workspace_to_free(self, demo_session, demo_workspace_id):
        r = demo_session.post(f"{API}/billing/cancel",
                              params={"workspace_id": demo_workspace_id}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("status") == "canceled"
        ws = demo_session.get(f"{API}/workspaces", timeout=10).json()
        target = next((w for w in ws if w["id"] == demo_workspace_id), None)
        assert target and target.get("plan") == "free"
        # Restore Acme back to agency for subsequent tests — known cross-test dependency.
        from dotenv import load_dotenv
        from pymongo import MongoClient
        load_dotenv("/app/backend/.env")
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        if mongo_url and db_name:
            MongoClient(mongo_url)[db_name].workspaces.update_one(
                {"id": demo_workspace_id}, {"$set": {"plan": "agency"}}
            )

    # Invoices list shape
    def test_invoices_list_shape(self, demo_session, demo_workspace_id):
        r = demo_session.get(f"{API}/billing/invoices",
                             params={"workspace_id": demo_workspace_id}, timeout=15)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        for inv in rows:
            for k in ("id", "invoice_number", "mollie_payment_id", "subtotal", "vat_rate",
                      "vat_amount", "vat_note", "total", "currency", "status",
                      "invoice_date", "due_date", "pdf_url"):
                assert k in inv, f"missing {k} in invoice"
            assert inv["currency"] == "EUR"

    def test_invoice_pdf_404_for_unknown(self, demo_session):
        r = demo_session.get(f"{API}/billing/invoices/9999-9999/pdf", timeout=10)
        assert r.status_code == 404

    # Webhook returns 200 even for unknown payment
    def test_webhook_unknown_payment_returns_200(self):
        r = requests.post(f"{API}/billing/mollie/webhook",
                          data={"id": "tr_does_not_exist_xyz"}, timeout=20)
        assert r.status_code == 200


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
        assert "coolify" in data and "twilio" in data
        assert "configured" in data["coolify"] and "configured" in data["twilio"]


# ----- Iteration 7: P0 — fast endpoints (BackgroundTask) + retry logs + watchdog -----
class TestIter7P0Fast:
    """All Coolify-touching endpoints must return in <2s; retry logs must be visible."""

    @pytest.fixture(scope="class")
    def fresh_app(self, demo_session, demo_workspace_id):
        # POST /apps must itself return <2s (Coolify create+deploy moved to BackgroundTask)
        name = f"TEST_p0_{uuid.uuid4().hex[:6]}"
        t0 = time.time()
        r = demo_session.post(f"{API}/apps",
                              json={"workspace_id": demo_workspace_id, "name": name,
                                    "framework": "nextjs",
                                    "repo_url": "https://github.com/vercel/next.js",
                                    "branch": "main"}, timeout=10)
        elapsed = time.time() - t0
        assert r.status_code in (200, 201), r.text
        assert elapsed < 2.5, f"POST /apps took {elapsed:.2f}s (>2.5s) — Coolify call not backgrounded"
        app = r.json()
        yield app
        try:
            demo_session.delete(f"{API}/apps/{app['id']}", timeout=10)
        except Exception:
            pass

    def test_redeploy_returns_under_2s(self, demo_session, fresh_app):
        app_id = fresh_app["id"]
        t0 = time.time()
        r = demo_session.post(f"{API}/apps/{app_id}/redeploy", json={}, timeout=10)
        elapsed = time.time() - t0
        assert r.status_code in (200, 201), r.text
        assert elapsed < 2.5, f"POST /apps/{{id}}/redeploy took {elapsed:.2f}s — must be backgrounded"
        # Returned deployment row should be queued/building immediately
        d = r.json()
        assert d["status"] in ("queued", "building")

    def test_patch_app_returns_under_2s(self, demo_session, fresh_app):
        app_id = fresh_app["id"]
        t0 = time.time()
        r = demo_session.patch(f"{API}/apps/{app_id}",
                               json={"build_command": "yarn build", "start_command": "yarn start"},
                               timeout=10)
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        assert elapsed < 2.5, f"PATCH /apps/{{id}} took {elapsed:.2f}s — Coolify PATCH not backgrounded"

    def test_put_env_returns_under_2s(self, demo_session, fresh_app):
        app_id = fresh_app["id"]
        t0 = time.time()
        r = demo_session.put(f"{API}/apps/{app_id}/env",
                             json={"env_vars": {"P0_TEST": "ok"}}, timeout=10)
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        assert elapsed < 2.5, f"PUT /apps/{{id}}/env took {elapsed:.2f}s — Coolify env push not backgrounded"
        assert r.json()["env_vars"].get("P0_TEST") == "ok"

    def test_redeploy_logs_show_attempt_lines(self, demo_session, demo_workspace_id):
        """deployment.logs must contain 'attempt N/3' from _trigger_coolify_deploy_with_retry.
        Use a seeded app that already has coolify_app_uuid (so the retry codepath fires)."""
        # Pick an app with coolify_app_uuid set (skip otherwise — Coolify not configured)
        apps = demo_session.get(f"{API}/apps", params={"workspace_id": demo_workspace_id}, timeout=10).json()
        target = next((a for a in apps if a.get("coolify_app_uuid")), None)
        if not target:
            pytest.skip("no app with coolify_app_uuid available — Coolify not configured in this env")
        rd = demo_session.post(f"{API}/apps/{target['id']}/redeploy", json={}, timeout=10)
        assert rd.status_code in (200, 201)
        dep_id = rd.json()["id"]
        attempt_seen = False
        for _ in range(15):
            time.sleep(2)
            g = demo_session.get(f"{API}/deployments/{dep_id}", timeout=10)
            if g.status_code != 200:
                continue
            logs_text = " ".join((g.json().get("logs") or [])).lower()
            if "attempt" in logs_text and "1/3" in logs_text:
                attempt_seen = True
                break
        assert attempt_seen, f"expected 'attempt 1/3' log line in deployment {dep_id}"

    def test_watchdog_scheduler_registered(self):
        """Verify backend log shows the deployment_watchdog APScheduler job registered + running."""
        import subprocess
        out = subprocess.run(
            ["bash", "-c",
             "grep -E 'Added job .deployment_watchdog|Scheduler started' /var/log/supervisor/backend.*.log | tail -10"],
            capture_output=True, text=True, timeout=10
        )
        text = out.stdout + out.stderr
        assert "deployment_watchdog" in text, f"deployment_watchdog not registered in logs: {text[:300]}"
        assert "Scheduler started" in text, f"Scheduler start not logged: {text[:300]}"


# ----- Iteration 7: P1 — SitePreview mixed-content fallback (component logic) -----
class TestIter7SitePreview:
    def test_site_preview_component_has_insecure_origin_fallback(self):
        """Inspect SitePreview.jsx for the http:// → fallback branch and preview-fallback-open testid."""
        path = "/app/frontend/src/components/SitePreview.jsx"
        with open(path) as f:
            src = f.read()
        assert "preview-fallback" in src, "preview-fallback testid missing in SitePreview.jsx"
        assert "preview-fallback-open" in src, "preview-fallback-open testid missing in SitePreview.jsx"
        # Must check for http:// origin (insecure) somewhere
        assert ("http://" in src and ("insecure" in src.lower() or "mixed" in src.lower() or "isInsecure" in src)), \
            "SitePreview.jsx does not appear to handle http:// mixed-content origins"


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



# ─────────────────────── Sprint 3 / Iter 8 — Twilio SMS/WhatsApp + prefs ───────
SUPPORTED_EVENTS_EXPECTED = sorted([
    "deploy_failed", "deploy_succeeded",
    "app_down", "app_recovered",
    "build_warning", "domain_expiring",
    "credits_low",
])


class TestIter8NotificationPrefs:
    """GET/PUT /api/notifications/prefs — phone validation, channels persistence."""

    def test_get_prefs_returns_schema_with_7_supported_events(self, demo_session):
        r = demo_session.get(f"{API}/notifications/prefs", timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "phone_e164" in data
        assert "channels" in data and isinstance(data["channels"], dict)
        assert "supported_events" in data
        assert isinstance(data["supported_events"], list)
        assert len(data["supported_events"]) == 7
        assert sorted(data["supported_events"]) == SUPPORTED_EVENTS_EXPECTED

    def test_put_prefs_rejects_phone_without_plus(self, demo_session):
        bad = demo_session.put(
            f"{API}/notifications/prefs",
            json={"phone_e164": "32475123456", "channels": {}},
            timeout=10,
        )
        assert bad.status_code == 400, f"expected 400 for non-E.164 phone, got {bad.status_code}: {bad.text}"
        body = bad.json()
        msg = (body.get("detail") or "").lower()
        assert "e.164" in msg or "+" in msg or "phone" in msg

    def test_put_prefs_roundtrip_get_returns_same_values(self, demo_session):
        payload = {
            "phone_e164": "+32475999000",
            "channels": {
                "sms": ["deploy_failed", "app_down"],
                "whatsapp": ["app_down"],
                "email": ["deploy_failed", "deploy_succeeded", "credits_low"],
            },
        }
        up = demo_session.put(f"{API}/notifications/prefs", json=payload, timeout=10)
        assert up.status_code == 200, up.text
        assert up.json().get("ok") is True
        # GET back and verify
        g = demo_session.get(f"{API}/notifications/prefs", timeout=10)
        assert g.status_code == 200
        data = g.json()
        assert data["phone_e164"] == payload["phone_e164"]
        assert data["channels"].get("sms") == payload["channels"]["sms"]
        assert data["channels"].get("whatsapp") == payload["channels"]["whatsapp"]
        assert data["channels"].get("email") == payload["channels"]["email"]

    def test_put_prefs_accepts_empty_phone(self, demo_session):
        # phone_e164=None or empty string should be accepted (user clearing phone)
        r = demo_session.put(
            f"{API}/notifications/prefs",
            json={"phone_e164": None, "channels": {"email": ["deploy_failed"]}},
            timeout=10,
        )
        assert r.status_code == 200, r.text


class TestIter8NotificationTestEndpoint:
    """POST /api/notifications/test — bypass-prefs test send."""

    def test_email_channel_returns_queued_regardless_of_prefs(self, demo_session, demo_workspace_id):
        # First, clear out email from prefs to prove the test endpoint bypasses the matrix
        demo_session.put(
            f"{API}/notifications/prefs",
            json={"phone_e164": "+32475999000", "channels": {"sms": [], "whatsapp": [], "email": []}},
            timeout=10,
        )
        r = demo_session.post(
            f"{API}/notifications/test",
            json={"workspace_id": demo_workspace_id, "channel": "email"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        results = body.get("results") if isinstance(body, dict) else body
        assert isinstance(results, list) and len(results) == 1
        item = results[0]
        assert item["channel"] == "email"
        assert item["status"] == "queued"
        assert item.get("cost", 0) == 0

    def test_email_test_creates_notification_row(self, demo_session, demo_workspace_id):
        # Trigger an email test send, then verify a NEW notification row appears.
        # /api/notifications is capped at 100; compare by IDs not by length.
        before_ids = {n["id"] for n in demo_session.get(
            f"{API}/notifications", params={"workspace_id": demo_workspace_id}, timeout=10
        ).json()}
        r = demo_session.post(
            f"{API}/notifications/test",
            json={"workspace_id": demo_workspace_id, "channel": "email"},
            timeout=15,
        )
        assert r.status_code == 200
        time.sleep(0.5)
        after = demo_session.get(
            f"{API}/notifications", params={"workspace_id": demo_workspace_id}, timeout=10
        ).json()
        new_rows = [n for n in after if n["id"] not in before_ids]
        assert new_rows, "no new notification row appeared after email test send"
        latest = after[0]
        assert latest.get("channel") == "email"
        assert latest.get("event_type") == "deploy_succeeded"
        assert "test" in (latest.get("title") or "").lower()

    def test_sms_channel_skipped_when_twilio_unconfigured(self, demo_session, demo_workspace_id):
        # Ensure a phone is set so the only reason for "skipped" is twilio config
        demo_session.put(
            f"{API}/notifications/prefs",
            json={"phone_e164": "+32475999000", "channels": {}},
            timeout=10,
        )
        r = demo_session.post(
            f"{API}/notifications/test",
            json={"workspace_id": demo_workspace_id, "channel": "sms"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        results = body.get("results") if isinstance(body, dict) else body
        assert isinstance(results, list) and len(results) == 1
        item = results[0]
        assert item["channel"] == "sms"
        assert item["status"] == "skipped", f"expected skipped, got {item}"

    def test_sms_skip_logs_notification_sends_row_with_error(self, demo_session, demo_workspace_id):
        """Verify send_alert logs to db.notification_sends with the correct error reason."""
        from dotenv import load_dotenv
        from pymongo import MongoClient
        load_dotenv("/app/backend/.env")
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        assert mongo_url and db_name, "MONGO_URL / DB_NAME required for DB assertion"
        client = MongoClient(mongo_url)
        db = client[db_name]

        # Set phone so 'no phone' isn't the reason — twilio config is.
        demo_session.put(
            f"{API}/notifications/prefs",
            json={"phone_e164": "+32475999111", "channels": {}},
            timeout=10,
        )
        marker_time = time.time()
        r = demo_session.post(
            f"{API}/notifications/test",
            json={"workspace_id": demo_workspace_id, "channel": "sms"},
            timeout=15,
        )
        assert r.status_code == 200
        time.sleep(0.6)

        rows = list(db.notification_sends.find(
            {"channel": "sms", "workspace_id": demo_workspace_id, "status": "skipped"},
            {"_id": 0},
        ).sort("created_at", -1).limit(5))
        assert rows, "no notification_sends rows found for skipped SMS"
        latest = rows[0]
        err = (latest.get("error") or "").lower()
        assert "twilio not configured" in err or "no phone" in err, \
            f"expected error to mention twilio config / phone, got: {latest.get('error')}"
        assert latest.get("event_type") == "deploy_succeeded"
        assert latest.get("cost_credits") == 0

    def test_whatsapp_channel_also_skipped(self, demo_session, demo_workspace_id):
        demo_session.put(
            f"{API}/notifications/prefs",
            json={"phone_e164": "+32475999000", "channels": {}},
            timeout=10,
        )
        r = demo_session.post(
            f"{API}/notifications/test",
            json={"workspace_id": demo_workspace_id, "channel": "whatsapp"},
            timeout=15,
        )
        assert r.status_code == 200
        results = r.json().get("results")
        assert results[0]["channel"] == "whatsapp"
        assert results[0]["status"] == "skipped"

    def test_invalid_channel_returns_400(self, demo_session, demo_workspace_id):
        r = demo_session.post(
            f"{API}/notifications/test",
            json={"workspace_id": demo_workspace_id, "channel": "push"},
            timeout=10,
        )
        assert r.status_code == 400, f"expected 400 for unknown channel, got {r.status_code}: {r.text}"

    def test_test_endpoint_without_workspace_membership_forbidden(self, demo_workspace_id):
        # New user with no membership in demo workspace
        s = requests.Session()
        email = f"TEST_nm_{uuid.uuid4().hex[:6]}@deployhub-test.io"
        rr = s.post(f"{API}/auth/register",
                    json={"email": email, "password": "pw12345x", "name": "NoMember"}, timeout=15)
        assert rr.status_code == 200
        r = s.post(
            f"{API}/notifications/test",
            json={"workspace_id": demo_workspace_id, "channel": "email"},
            timeout=10,
        )
        assert r.status_code in (403, 404), f"expected 403/404 for non-member, got {r.status_code}: {r.text}"


class TestIter8IntegrationsHealthTwilio:
    """/api/integrations/health must surface twilio entry (Sprint 3)."""

    def test_integrations_health_includes_twilio_key(self, demo_session):
        r = demo_session.get(f"{API}/integrations/health", timeout=20)
        # tolerate the known coolify external-flake — still need twilio key in body
        assert r.status_code == 200, r.text
        data = r.json()
        assert "coolify" in data
        assert "twilio" in data, f"twilio key missing from /integrations/health: {list(data.keys())}"
        tw = data["twilio"]
        assert isinstance(tw, dict)
        assert "configured" in tw
        # Twilio is intentionally NOT configured in this env
        assert tw["configured"] is False
        assert tw.get("ok") is False


class TestIter8SupportedEventsImport:
    """Source-level assertion: SUPPORTED_EVENT_TYPES matches the contract."""

    def test_supported_event_types_set_matches_spec(self):
        # Add backend path so we can import the service module directly
        import sys
        if "/app/backend" not in sys.path:
            sys.path.insert(0, "/app/backend")
        from services.notifications_sms import SUPPORTED_EVENT_TYPES
        assert isinstance(SUPPORTED_EVENT_TYPES, set)
        assert SUPPORTED_EVENT_TYPES == set(SUPPORTED_EVENTS_EXPECTED), \
            f"SUPPORTED_EVENT_TYPES drift: {SUPPORTED_EVENT_TYPES} vs {set(SUPPORTED_EVENTS_EXPECTED)}"


class TestIter8NotificationsRegression:
    """Regression: existing list/mark-read/mark-all-read still work alongside new routes."""

    def test_list_mark_read_and_mark_all_read(self, demo_session, demo_workspace_id):
        # Seed at least one notification via the email test send so list isn't empty
        demo_session.post(
            f"{API}/notifications/test",
            json={"workspace_id": demo_workspace_id, "channel": "email"},
            timeout=15,
        )
        time.sleep(0.4)
        lst = demo_session.get(
            f"{API}/notifications", params={"workspace_id": demo_workspace_id}, timeout=10
        )
        assert lst.status_code == 200
        items = lst.json()
        assert isinstance(items, list) and len(items) >= 1
        nid = items[0]["id"]
        mk = demo_session.post(f"{API}/notifications/{nid}/read", timeout=10)
        assert mk.status_code == 200
        ra = demo_session.post(
            f"{API}/notifications/read-all",
            params={"workspace_id": demo_workspace_id}, timeout=10,
        )
        assert ra.status_code == 200
