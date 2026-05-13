"""Tests for Admin Credit-Pricing Editor (iter17).

Covers:
  - GET  /api/admin/credit-packs (admin only; defaults when nothing saved)
  - PUT  /api/admin/credit-packs (validation + persistence)
  - POST /api/admin/credit-packs/reset (clears custom packs)
  - Public GET /api/account/credits/packs
  - Public GET /api/credits/packs
  - POST /api/account/credits/checkout uses dynamic pack id
  - 403 for non-admin
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://app-test-build-2.preview.emergentagent.com").rstrip("/")
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


@pytest.fixture(scope="module", autouse=True)
def cleanup_after(admin_session):
    """Reset packs to defaults before AND after the entire module so we
    leave the system in a clean state."""
    admin_session.post(f"{BASE_URL}/api/admin/credit-packs/reset", timeout=15)
    yield
    admin_session.post(f"{BASE_URL}/api/admin/credit-packs/reset", timeout=15)


# ─── GET /admin/credit-packs (defaults) ────────────────────────────────────
class TestAdminListPacks:
    def test_admin_get_returns_defaults_after_reset(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/credit-packs", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        ids = {p["id"] for p in data}
        assert {"small", "medium", "large"}.issubset(ids), f"Missing defaults, got {ids}"
        # validate shape
        for p in data:
            assert "id" in p and "label" in p
            assert isinstance(p["credits"], int) and p["credits"] > 0
            assert isinstance(p["price_eur"], (int, float)) and p["price_eur"] > 0

    def test_non_admin_forbidden(self, user_session):
        r = user_session.get(f"{BASE_URL}/api/admin/credit-packs", timeout=15)
        assert r.status_code == 403

    def test_anonymous_forbidden(self):
        r = requests.get(f"{BASE_URL}/api/admin/credit-packs", timeout=15)
        assert r.status_code in (401, 403)


# ─── PUT /admin/credit-packs validation ────────────────────────────────────
class TestAdminUpdateValidation:
    def test_reject_empty_list(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/admin/credit-packs",
                              json={"packs": []}, timeout=15)
        assert r.status_code == 400
        assert "at least one" in r.json().get("detail", "").lower()

    def test_reject_duplicate_ids(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/admin/credit-packs", json={"packs": [
            {"id": "dup", "label": "A", "credits": 10, "price_eur": 1.0},
            {"id": "dup", "label": "B", "credits": 20, "price_eur": 2.0},
        ]}, timeout=15)
        assert r.status_code == 400
        assert "duplicate" in r.json().get("detail", "").lower()

    def test_reject_zero_credits(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/admin/credit-packs", json={"packs": [
            {"id": "zero", "label": "Z", "credits": 0, "price_eur": 1.0},
        ]}, timeout=15)
        assert r.status_code == 400
        assert "positive credits" in r.json().get("detail", "").lower()

    def test_reject_zero_price(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/admin/credit-packs", json={"packs": [
            {"id": "freepack", "label": "Free", "credits": 10, "price_eur": 0},
        ]}, timeout=15)
        assert r.status_code == 400
        assert "positive price" in r.json().get("detail", "").lower()

    def test_reject_invalid_id_chars(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/admin/credit-packs", json={"packs": [
            {"id": "bad id!", "label": "Bad", "credits": 10, "price_eur": 1.0},
        ]}, timeout=15)
        assert r.status_code == 400
        assert "invalid" in r.json().get("detail", "").lower()

    def test_non_admin_cannot_put(self, user_session):
        r = user_session.put(f"{BASE_URL}/api/admin/credit-packs", json={"packs": [
            {"id": "x", "label": "X", "credits": 1, "price_eur": 1.0},
        ]}, timeout=15)
        assert r.status_code == 403


# ─── PUT /admin/credit-packs persistence + public endpoints ────────────────
class TestPersistenceAndPublic:
    custom = [
        {"id": "starter", "label": "Starter Pack", "credits": 30, "price_eur": 3.5, "bonus_pct": 0},
        {"id": "pro_pack", "label": "Pro ⭐", "credits": 500, "price_eur": 40.0, "bonus_pct": 15},
        {"id": "mega-pack", "label": "Mega", "credits": 2000, "price_eur": 150.0},
    ]

    def test_put_persists_custom_catalog(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/admin/credit-packs",
                              json={"packs": self.custom}, timeout=15)
        assert r.status_code == 200, r.text
        saved = r.json()
        assert len(saved) == 3
        assert [p["id"] for p in saved] == ["starter", "pro_pack", "mega-pack"]
        assert saved[1]["bonus_pct"] == 15
        assert saved[0]["credits"] == 30
        assert saved[0]["price_eur"] == 3.5
        # bonus_pct=0 should NOT appear in the output (normalized away)
        assert "bonus_pct" not in saved[0] or saved[0].get("bonus_pct") in (0, None)

    def test_admin_get_returns_saved_catalog(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/credit-packs", timeout=15)
        assert r.status_code == 200
        ids = [p["id"] for p in r.json()]
        assert ids == ["starter", "pro_pack", "mega-pack"]

    def test_account_credits_packs_public(self, user_session):
        r = user_session.get(f"{BASE_URL}/api/account/credits/packs", timeout=15)
        assert r.status_code == 200
        ids = [p["id"] for p in r.json()]
        assert "starter" in ids and "pro_pack" in ids and "mega-pack" in ids

    def test_credits_packs_public(self):
        # No auth required at all
        r = requests.get(f"{BASE_URL}/api/credits/packs", timeout=15)
        assert r.status_code == 200
        ids = [p["id"] for p in r.json()]
        assert "starter" in ids and "mega-pack" in ids

    def test_checkout_accepts_custom_pack_id(self, user_session):
        """The CreditPackCheckoutIn.pack used to be a Literal['small','medium','large'].
        Verify it now accepts custom ids — failure mode would be 422 unprocessable."""
        r = user_session.post(f"{BASE_URL}/api/account/credits/checkout",
                              json={"pack": "mega-pack"}, timeout=15)
        # Must NOT be 422 (Pydantic Literal mismatch). Can be:
        #   - 503 Payments not configured (Mollie missing)
        #   - 400 'Fill in your billing profile first' / 'Unknown pack' if catalog wasn't saved
        #   - 200 if Mollie is somehow configured
        assert r.status_code != 422, f"Literal type still rejecting custom pack: {r.text}"
        assert r.status_code in (200, 400, 503), f"unexpected status {r.status_code}: {r.text}"
        if r.status_code == 400:
            # must NOT be 'unknown pack' — the catalog has it
            detail = r.json().get("detail", "").lower()
            assert "unknown pack" not in detail, f"pack 'mega-pack' not found in catalog: {detail}"

    def test_checkout_unknown_pack_returns_400(self, user_session):
        r = user_session.post(f"{BASE_URL}/api/account/credits/checkout",
                              json={"pack": "nonexistent-pack-xyz"}, timeout=15)
        assert r.status_code == 400
        assert "unknown pack" in r.json().get("detail", "").lower()


# ─── POST /admin/credit-packs/reset ─────────────────────────────────────────
class TestReset:
    def test_reset_restores_defaults(self, admin_session):
        # First, save a custom catalog
        admin_session.put(f"{BASE_URL}/api/admin/credit-packs", json={"packs": [
            {"id": "tempx", "label": "Temp", "credits": 10, "price_eur": 1.0},
        ]}, timeout=15)
        # Verify it is saved
        r = admin_session.get(f"{BASE_URL}/api/admin/credit-packs", timeout=15)
        assert "tempx" in {p["id"] for p in r.json()}
        # Reset
        r = admin_session.post(f"{BASE_URL}/api/admin/credit-packs/reset", timeout=15)
        assert r.status_code == 200
        ids = {p["id"] for p in r.json()}
        assert {"small", "medium", "large"}.issubset(ids)
        assert "tempx" not in ids
        # GET should also return defaults
        r2 = admin_session.get(f"{BASE_URL}/api/admin/credit-packs", timeout=15)
        ids2 = {p["id"] for p in r2.json()}
        assert "tempx" not in ids2
        assert {"small", "medium", "large"}.issubset(ids2)

    def test_non_admin_cannot_reset(self, user_session):
        r = user_session.post(f"{BASE_URL}/api/admin/credit-packs/reset", timeout=15)
        assert r.status_code == 403
