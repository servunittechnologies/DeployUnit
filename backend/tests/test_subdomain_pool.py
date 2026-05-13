"""Backend tests for Cloudflare subdomain pool admin endpoints.

Covers:
  * GET  /api/admin/subdomain-pool  (admin / non-admin / anonymous)
  * POST /api/admin/subdomain-pool/refill (admin, returns added:0 in this preview env)
  * PUT  /api/admin/platform-settings — subdomain_pool_target persistence, clamp, floor
  * Regression: GET/PUT /api/admin/platform-settings, GET /api/admin/integrations
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://addon-showcase-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@deployunit.com"
ADMIN_PASS = "admin123"
USER_EMAIL = "demo@deployunit.com"
USER_PASS = "demo1234"


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def admin_session() -> requests.Session:
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def user_session() -> requests.Session:
    return _login(USER_EMAIL, USER_PASS)


@pytest.fixture(scope="module")
def original_target(admin_session):
    """Capture original subdomain_pool_target so we restore at end."""
    r = admin_session.get(f"{API}/admin/platform-settings", timeout=15)
    assert r.status_code == 200
    val = r.json().get("subdomain_pool_target", 10)
    yield val
    # restore
    admin_session.put(f"{API}/admin/platform-settings", json={"subdomain_pool_target": val}, timeout=15)


# --- GET /admin/subdomain-pool -------------------------------------------------

class TestSubdomainPoolAccess:
    def test_get_pool_anonymous_401(self):
        r = requests.get(f"{API}/admin/subdomain-pool", timeout=15)
        assert r.status_code == 401, f"expected 401 for anon, got {r.status_code}"

    def test_get_pool_non_admin_403(self, user_session):
        r = user_session.get(f"{API}/admin/subdomain-pool", timeout=15)
        assert r.status_code == 403, f"expected 403 for non-admin, got {r.status_code}"

    def test_get_pool_admin_ok(self, admin_session):
        r = admin_session.get(f"{API}/admin/subdomain-pool", timeout=15)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        for key in ("free", "claimed", "target", "hard_max", "cloudflare_ready", "zone_name", "upcoming"):
            assert key in data, f"missing field {key} in {data}"
        assert isinstance(data["free"], int)
        assert isinstance(data["claimed"], int)
        assert isinstance(data["target"], int)
        assert data["hard_max"] == 50
        assert isinstance(data["cloudflare_ready"], bool)
        assert isinstance(data["upcoming"], list)


# --- POST /admin/subdomain-pool/refill ----------------------------------------

class TestSubdomainPoolRefill:
    def test_refill_non_admin_403(self, user_session):
        r = user_session.post(f"{API}/admin/subdomain-pool/refill", timeout=15)
        assert r.status_code == 403

    def test_refill_admin_no_cloudflare_returns_zero(self, admin_session):
        r = admin_session.post(f"{API}/admin/subdomain-pool/refill", timeout=20)
        assert r.status_code == 200, f"refill should not 500: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert "added" in data
        # In preview env Cloudflare is not configured → added:0 is correct
        assert data["added"] == 0
        # Should include pool stats merged in
        assert "cloudflare_ready" in data
        assert data["cloudflare_ready"] is False
        assert "free" in data and "target" in data


# --- PUT /admin/platform-settings — subdomain_pool_target validation -----------

class TestSubdomainPoolTargetPersistence:
    def test_set_target_20_persists(self, admin_session, original_target):
        r = admin_session.put(f"{API}/admin/platform-settings", json={"subdomain_pool_target": 20}, timeout=15)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert body.get("subdomain_pool_target") == 20
        # verify via pool endpoint
        pool = admin_session.get(f"{API}/admin/subdomain-pool", timeout=15).json()
        assert pool["target"] == 20

    def test_set_target_999_clamps_to_50(self, admin_session, original_target):
        r = admin_session.put(f"{API}/admin/platform-settings", json={"subdomain_pool_target": 999}, timeout=15)
        assert r.status_code == 200
        # stored as 999 (raw), but pool stats clamps to hard_max=50
        pool = admin_session.get(f"{API}/admin/subdomain-pool", timeout=15).json()
        assert pool["target"] == 50, f"expected clamp to 50, got {pool['target']}"

    def test_set_target_negative_clamps_to_0(self, admin_session, original_target):
        r = admin_session.put(f"{API}/admin/platform-settings", json={"subdomain_pool_target": -5}, timeout=15)
        assert r.status_code == 200
        pool = admin_session.get(f"{API}/admin/subdomain-pool", timeout=15).json()
        assert pool["target"] == 0, f"expected clamp to 0, got {pool['target']}"

    def test_set_target_zero_disables_pool(self, admin_session, original_target):
        r = admin_session.put(f"{API}/admin/platform-settings", json={"subdomain_pool_target": 0}, timeout=15)
        assert r.status_code == 200
        pool = admin_session.get(f"{API}/admin/subdomain-pool", timeout=15).json()
        assert pool["target"] == 0

    def test_set_target_invalid_type_returns_422(self, admin_session, original_target):
        r = admin_session.put(f"{API}/admin/platform-settings", json={"subdomain_pool_target": "abc"}, timeout=15)
        # Pydantic should reject non-int
        assert r.status_code in (400, 422), f"expected 422, got {r.status_code} {r.text[:200]}"


# --- Regression: existing admin endpoints still work --------------------------

class TestAdminRegression:
    def test_get_platform_settings_ok(self, admin_session):
        r = admin_session.get(f"{API}/admin/platform-settings", timeout=15)
        assert r.status_code == 200
        body = r.json()
        # should never leak the raw encrypted token field
        assert "cloudflare_api_token_enc" not in body
        assert "cloudflare_api_token_set" in body

    def test_put_platform_settings_without_pool_target_works(self, admin_session, original_target):
        # update an unrelated field — pool target should NOT be reset
        admin_session.put(f"{API}/admin/platform-settings", json={"subdomain_pool_target": 15}, timeout=15)
        r = admin_session.put(
            f"{API}/admin/platform-settings",
            json={"company_name": "DeployUnit BV TEST"},
            timeout=15,
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("company_name") == "DeployUnit BV TEST"
        # pool target preserved
        assert body.get("subdomain_pool_target") == 15

    def test_get_integrations_ok(self, admin_session):
        r = admin_session.get(f"{API}/admin/integrations", timeout=20)
        assert r.status_code == 200
        body = r.json()
        for key in ("build_engine", "mollie", "github_oauth", "twilio", "mailersend"):
            assert key in body, f"missing key {key} in integrations"
