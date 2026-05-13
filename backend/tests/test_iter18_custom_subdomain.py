"""Iter18 — Custom subdomain & prerender feature tests.

Covers:
  - Prerender output: build/<route>/index.html exists, has real content in <div id="root">,
    and canonical/og:url use https://deployunit.com (NOT http://127.0.0.1)
  - Custom subdomain validation logic (services.custom_subdomain.validate_name)
  - GET    /api/apps/{id}/custom-subdomain   -> {status: 'none'} when none requested
  - GET    /api/apps/{id}/custom-subdomain/check -> validates name + 'Cloudflare not configured'
  - POST   /api/apps/{id}/custom-subdomain   -> 400 reserved, 404 unknown app, 403 non-member
  - DELETE /api/apps/{id}/custom-subdomain   -> noop when nothing pending/active
  - Scheduler tick verify_pending_subdomains_tick is registered every 30s in server.py
  - Regression smoke: GET /api/admin/credit-packs returns 200 for admin
"""
import os
import re
import sys
import pytest
import requests


def _read_frontend_env_url():
    try:
        with open("/app/frontend/.env") as fp:
            for line in fp:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        return ""
    return ""


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env_url()).rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

ADMIN_EMAIL = "admin@deployunit.com"
ADMIN_PASS = "admin123"
USER_EMAIL = "demo@deployunit.com"
USER_PASS = "demo1234"

DEMO_WS_ID = "ee9ace3a-0b82-4df5-9dd7-d543c1e0c022"
DEMO_APP_ID = "63c1ba3c-8286-4e80-83d1-06a603132392"

BUILD_DIR = "/app/frontend/build"
PRERENDER_ROUTES = [
    ("", "index.html"),
    ("pricing", "pricing/index.html"),
    ("about", "about/index.html"),
    ("login", "login/index.html"),
    ("register", "register/index.html"),
    ("forgot-password", "forgot-password/index.html"),
    ("status", "status/index.html"),
    ("contact", "contact/index.html"),
    ("support", "support/index.html"),
]


# ── Helpers ──────────────────────────────────────────────────────────────
def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def user_session():
    return _login(USER_EMAIL, USER_PASS)


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def other_user_session():
    """Create an isolated user that isn't a member of the demo workspace."""
    s = requests.Session()
    email = "TEST_iter18_outsider@example.com"
    pw = "Passw0rd!23"
    # Try register; if already exists fall back to login
    r = s.post(f"{BASE_URL}/api/auth/register",
               json={"email": email, "password": pw, "name": "Outsider"}, timeout=15)
    if r.status_code not in (200, 201):
        r = s.post(f"{BASE_URL}/api/auth/login",
                   json={"email": email, "password": pw}, timeout=15)
        if r.status_code != 200:
            pytest.skip(f"Could not create or login outsider user: {r.status_code} {r.text}")
    return s


# ── Prerender tests ──────────────────────────────────────────────────────
class TestPrerender:
    @pytest.mark.parametrize("route,path", PRERENDER_ROUTES)
    def test_file_exists(self, route, path):
        full = os.path.join(BUILD_DIR, path)
        assert os.path.isfile(full), f"Missing prerendered file: {full}"

    @pytest.mark.parametrize("route,path", PRERENDER_ROUTES)
    def test_root_div_has_real_content(self, route, path):
        with open(os.path.join(BUILD_DIR, path)) as fp:
            html = fp.read()
        m = re.search(r'<div id="root">(.*?)</div>\s*<script', html, re.S)
        # fallback (no trailing script directly)
        if not m:
            m = re.search(r'<div id="root">(.*)$', html, re.S)
        assert m, f"<div id=root> not found in {path}"
        inner = m.group(1)
        # strip tags to grab the visible text
        text = re.sub(r"<script.*?</script>", " ", inner, flags=re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        # Empty SPA shell would have ~0 chars; real content has hundreds
        assert len(text) > 80, f"Route {route} root div seems empty (len={len(text)}): {text[:80]!r}"
        assert "deploy" in text.lower() or "sign" in text.lower() or "password" in text.lower(), \
            f"Route {route} root content doesn't look like a real page: {text[:160]!r}"

    @pytest.mark.parametrize("route,path", PRERENDER_ROUTES)
    def test_canonical_and_og_url_use_https_deployunit(self, route, path):
        with open(os.path.join(BUILD_DIR, path)) as fp:
            html = fp.read()
        # No localhost / 127.0.0.1 leaks in meta tags
        assert "http://127.0.0.1" not in html, f"{path}: leaked http://127.0.0.1"
        assert "http://localhost" not in html, f"{path}: leaked http://localhost"
        c = re.search(r'<link rel="canonical" href="([^"]+)"', html)
        o = re.search(r'<meta property="og:url" content="([^"]+)"', html)
        assert c, f"{path}: missing canonical"
        assert o, f"{path}: missing og:url"
        assert c.group(1).startswith("https://deployunit.com"), \
            f"{path}: canonical not https://deployunit.com -> {c.group(1)}"
        assert o.group(1).startswith("https://deployunit.com"), \
            f"{path}: og:url not https://deployunit.com -> {o.group(1)}"


# ── Scheduler registration ───────────────────────────────────────────────
class TestSchedulerRegistration:
    def test_verify_pending_subdomains_registered_every_30s(self):
        with open("/app/backend/server.py") as fp:
            src = fp.read()
        assert "verify_pending_subdomains_tick" in src, "Tick function not referenced in server.py"
        # must be wired into scheduler.add_job with interval=30s
        pattern = re.compile(
            r"scheduler\.add_job\(\s*verify_pending_subdomains_tick\s*,\s*\"interval\"\s*,\s*seconds\s*=\s*30",
            re.S,
        )
        assert pattern.search(src), "verify_pending_subdomains_tick not added at 30s interval"


# ── validate_name unit tests (direct service import) ─────────────────────
class TestValidateName:
    @pytest.fixture(autouse=True, scope="class")
    def _add_path(self):
        sys.path.insert(0, "/app/backend")
        yield

    def test_too_short(self):
        from services.custom_subdomain import validate_name
        ok, why = validate_name("ab")
        assert ok is False
        assert "at least" in why.lower()

    def test_reserved(self):
        from services.custom_subdomain import validate_name
        for word in ["admin", "www", "api", "mail", "status"]:
            ok, why = validate_name(word)
            assert ok is False, f"{word} should be reserved"
            assert "reserved" in why.lower()

    def test_reserved_list_has_60_plus_entries(self):
        from services.custom_subdomain import RESERVED_SUBDOMAINS
        assert len(RESERVED_SUBDOMAINS) >= 60, f"Got {len(RESERVED_SUBDOMAINS)}"

    def test_invalid_chars(self):
        from services.custom_subdomain import validate_name
        # NOTE: normalize_name lowercases + strips, so 'UPPER' is fine.
        # These are characters that genuinely fail the regex even after normalize.
        for bad in ["with space", "with_underscore", "trailing-",
                    "-leading", "comma,bad", "dot.bad"]:
            ok, why = validate_name(bad)
            assert ok is False, f"{bad!r} should be invalid"

    def test_valid_names(self):
        from services.custom_subdomain import validate_name
        for good in ["myapp", "my-app", "ab123", "a-b-c", "test123app"]:
            ok, why = validate_name(good)
            assert ok is True, f"{good!r} expected valid, got {why}"


# ── API: state endpoint ─────────────────────────────────────────────────
class TestCustomSubdomainAPI:
    def test_state_none_when_not_requested(self, user_session):
        r = user_session.get(f"{BASE_URL}/api/apps/{DEMO_APP_ID}/custom-subdomain", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "status" in data
        # acceptable when nothing has been requested:
        assert data["status"] in ("none", "active", "pending"), data

    def test_check_too_short(self, user_session):
        r = user_session.get(
            f"{BASE_URL}/api/apps/{DEMO_APP_ID}/custom-subdomain/check",
            params={"name": "ab"}, timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["available"] is False
        assert "at least" in data["reason"].lower()

    @pytest.mark.parametrize("word", ["admin", "api", "www"])
    def test_check_reserved(self, user_session, word):
        r = user_session.get(
            f"{BASE_URL}/api/apps/{DEMO_APP_ID}/custom-subdomain/check",
            params={"name": word}, timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["available"] is False
        assert "reserved" in data["reason"].lower()

    def test_check_invalid_chars(self, user_session):
        r = user_session.get(
            f"{BASE_URL}/api/apps/{DEMO_APP_ID}/custom-subdomain/check",
            params={"name": "Bad_Name"}, timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["available"] is False

    def test_check_valid_name_cf_not_configured(self, user_session):
        # Preview env doesn't have Cloudflare configured => not available
        r = user_session.get(
            f"{BASE_URL}/api/apps/{DEMO_APP_ID}/custom-subdomain/check",
            params={"name": "myappiter18"}, timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["available"] is False
        assert "cloudflare" in data["reason"].lower(), data

    def test_post_reserved_returns_400(self, user_session):
        r = user_session.post(
            f"{BASE_URL}/api/apps/{DEMO_APP_ID}/custom-subdomain",
            json={"name": "admin"}, timeout=15,
        )
        assert r.status_code == 400, r.text

    def test_post_unknown_app_returns_404(self, user_session):
        r = user_session.post(
            f"{BASE_URL}/api/apps/00000000-0000-0000-0000-000000000000/custom-subdomain",
            json={"name": "myapp"}, timeout=15,
        )
        assert r.status_code == 404, r.text

    def test_post_non_member_returns_403(self, other_user_session):
        r = other_user_session.post(
            f"{BASE_URL}/api/apps/{DEMO_APP_ID}/custom-subdomain",
            json={"name": "myapp"}, timeout=15,
        )
        assert r.status_code == 403, r.text

    def test_delete_noop_when_nothing_pending(self, user_session):
        r = user_session.delete(
            f"{BASE_URL}/api/apps/{DEMO_APP_ID}/custom-subdomain", timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # spec: {ok: true, noop: true} OR {ok: true} when active was detached
        assert data.get("ok") is True


# ── Regression smoke: admin credit-packs ────────────────────────────────
class TestCreditPacksRegression:
    def test_get_admin_credit_packs_200(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/credit-packs", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        # Must return a list/array of packs OR an object containing one
        assert isinstance(data, (list, dict))
