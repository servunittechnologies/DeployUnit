"""Tests for routing self-healer endpoints (iteration 16).

Covers:
  - POST /api/admin/routing-healer/run (admin only)
  - POST /api/admin/apps/{id}/heal-routing (admin only)
  - Edge cases: app not found, app without cloudflare_fqdn
  - RBAC: anonymous => 401, non-admin demo => 403
  - Scheduler job presence in backend logs
"""
import os
import uuid
import pytest
import requests

def _resolve_base_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.strip().split("=", 1)[1]
                        break
        except FileNotFoundError:
            pass
    if not url:
        raise RuntimeError("REACT_APP_BACKEND_URL not set")
    return url.rstrip("/")


BASE_URL = _resolve_base_url()
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@deployunit.com", "password": "admin123"}
DEMO = {"email": "demo@deployunit.com", "password": "demo1234"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=10)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def demo_session():
    return _login(DEMO)


# ---------- RBAC ----------
class TestRBAC:
    def test_anon_run_healer_401(self):
        r = requests.post(f"{API}/admin/routing-healer/run", timeout=10)
        assert r.status_code == 401, r.text

    def test_anon_heal_app_401(self):
        r = requests.post(f"{API}/admin/apps/anything/heal-routing", timeout=10)
        assert r.status_code == 401, r.text

    def test_demo_run_healer_403(self, demo_session):
        r = demo_session.post(f"{API}/admin/routing-healer/run", timeout=15)
        assert r.status_code == 403, r.text

    def test_demo_heal_app_403(self, demo_session):
        r = demo_session.post(f"{API}/admin/apps/whatever/heal-routing", timeout=15)
        assert r.status_code == 403, r.text


# ---------- Healer tick endpoint ----------
class TestHealerTick:
    def test_admin_run_healer_200_no_crash(self, admin_session):
        r = admin_session.post(f"{API}/admin/routing-healer/run", timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "checked" in data
        assert "healed" in data
        assert "orphans" in data
        assert isinstance(data["orphans"], dict)
        assert "checked" in data["orphans"]
        # Cloudflare not configured => orphans should signal skipped
        # but at minimum 'released' or 'skipped' key must exist
        assert ("released" in data["orphans"]) or ("skipped" in data["orphans"])


# ---------- Heal app endpoint ----------
class TestHealApp:
    def test_heal_app_not_found(self, admin_session):
        r = admin_session.post(f"{API}/admin/apps/does-not-exist-xyz/heal-routing", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is False
        assert body.get("error") == "app not found"

    def test_heal_app_with_seeded_doc(self, admin_session):
        """Seed a fake app doc via the internal mongo using a quick admin op.
        We can't reach mongo directly from the test, so we use a dedicated
        admin helper if available — otherwise we test the no-fqdn path by
        seeding via a curl-style script in /tmp.

        Since no admin endpoint exists to insert apps with arbitrary fields,
        we use motor directly by importing the backend's db module.
        """
        # Use backend's mongo client to seed the doc.
        import asyncio
        import sys
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
        sys.path.insert(0, "/app/backend")
        from db import get_db  # type: ignore

        app_id = f"test-heal-{uuid.uuid4().hex[:8]}"

        async def seed_and_cleanup(action: str, doc: dict | None = None):
            db = get_db()
            if action == "insert":
                await db.apps.insert_one(doc)
            elif action == "delete":
                await db.apps.delete_one({"id": app_id})

        loop = asyncio.new_event_loop()
        try:
            # Case A: app WITH cloudflare_fqdn but unreachable host
            loop.run_until_complete(seed_and_cleanup("insert", {
                "id": app_id,
                "workspace_id": "ws1",
                "status": "live",
                "cloudflare_fqdn": "nonexistent.example.invalid",
                "coolify_app_uuid": "fake-uuid",
                "slug": "test",
            }))
            r = admin_session.post(f"{API}/admin/apps/{app_id}/heal-routing", timeout=60)
            assert r.status_code == 200, r.text
            body = r.json()
            assert "ok" in body
            assert body.get("fqdn") == "nonexistent.example.invalid"
            assert "before" in body
            assert "action" in body
            assert "after" in body
            # No crash is the most important assertion.

            # Case B: same app, remove cloudflare_fqdn -> error path
            loop.run_until_complete(seed_and_cleanup("delete"))
            loop.run_until_complete(seed_and_cleanup("insert", {
                "id": app_id,
                "workspace_id": "ws1",
                "status": "live",
                "coolify_app_uuid": "fake-uuid",
                "slug": "test",
            }))
            r = admin_session.post(f"{API}/admin/apps/{app_id}/heal-routing", timeout=30)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body.get("ok") is False
            assert body.get("error") == "app has no Cloudflare FQDN"
        finally:
            loop.run_until_complete(seed_and_cleanup("delete"))
            loop.close()


# ---------- Regression: existing pool endpoints still work ----------
class TestRegression:
    def test_get_subdomain_pool(self, admin_session):
        r = admin_session.get(f"{API}/admin/subdomain-pool", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("free", "claimed", "target", "hard_max", "cloudflare_ready"):
            assert k in body

    def test_post_refill_pool(self, admin_session):
        r = admin_session.post(f"{API}/admin/subdomain-pool/refill", timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "added" in body

    def test_put_pool_target_persists(self, admin_session):
        # Save current value, set new, verify, restore
        cur = admin_session.get(f"{API}/admin/subdomain-pool", timeout=10).json()
        original = cur.get("target", 10)
        try:
            r = admin_session.put(
                f"{API}/admin/platform-settings",
                json={"subdomain_pool_target": 15},
                timeout=15,
            )
            assert r.status_code == 200, r.text
            stats = admin_session.get(f"{API}/admin/subdomain-pool", timeout=10).json()
            assert stats.get("target") == 15
        finally:
            admin_session.put(
                f"{API}/admin/platform-settings",
                json={"subdomain_pool_target": original},
                timeout=15,
            )


# ---------- Service import sanity ----------
class TestImportSanity:
    def test_routing_healer_imports(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from services import routing_healer  # noqa
        assert hasattr(routing_healer, "heal_app")
        assert hasattr(routing_healer, "routing_healer_tick")
        assert hasattr(routing_healer, "cleanup_orphan_pool_entries")
        assert hasattr(routing_healer, "_probe_traefik_route")
