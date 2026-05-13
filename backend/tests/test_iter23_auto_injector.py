"""Iter23 — Build-time auto-injector for the analytics snippet.

The feature: at build-time the platform prepends a Node.js preflight to
the customer's build command that patches their framework's template
file with the analytics <script> tag, then their build runs unchanged.

These tests cover:
  * Endpoint contracts (toggle, get state, preflight.js, result callback)
  * HMAC token verification
  * wrap_build_command / unwrap_build_command round-trip
  * Each supported framework actually patches the right file
    (executed via Node in a subprocess against fixture directories).
"""
import json
import os
import shutil
import subprocess
import tempfile
import textwrap

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://addon-showcase-1.preview.emergentagent.com").rstrip("/")
DEMO_EMAIL = "demo@deployunit.com"
DEMO_PASS = "demo1234"
APP_ID = "63c1ba3c-8286-4e80-83d1-06a603132392"


# ───────────────────── helpers ─────────────────────


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200
    return s


@pytest.fixture(scope="module")
def demo():
    return _login(DEMO_EMAIL, DEMO_PASS)


@pytest.fixture(scope="module", autouse=True)
def reset_toggle(demo):
    """Leave the toggle in OFF state regardless of how the suite ran."""
    yield
    demo.post(f"{BASE_URL}/api/apps/{APP_ID}/auto-inject/toggle", json={"enabled": False}, timeout=15)


@pytest.fixture(scope="module")
def preflight_path(demo):
    """Toggle ON, harvest the preflight URL from the active_build_command,
    download the script to a local tempfile and return its path."""
    r = demo.post(f"{BASE_URL}/api/apps/{APP_ID}/auto-inject/toggle", json={"enabled": True}, timeout=15)
    assert r.status_code == 200
    cmd = r.json()["active_build_command"]
    # Pull out the preflight URL.
    import re
    m = re.search(r'"(https?://[^"]+/auto-inject/preflight\.js[^"]+)"', cmd)
    assert m, f"No preflight URL found in: {cmd}"
    url = m.group(1)
    out = tempfile.NamedTemporaryFile(suffix=".js", delete=False)
    rr = requests.get(url, timeout=15)
    assert rr.status_code == 200, rr.text
    assert "fs.readFileSync" in rr.text, "preflight body doesn't look like a node script"
    out.write(rr.content); out.close()
    # Sanity: Node parses it.
    subprocess.check_output(["node", "-c", out.name], stderr=subprocess.STDOUT)
    return out.name


# ───────────────────── endpoint contracts ─────────────────────


def test_get_state_default_disabled(demo):
    r = demo.get(f"{BASE_URL}/api/apps/{APP_ID}/auto-inject", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert "enabled" in body
    assert isinstance(body["supported_frameworks"], list)
    assert "nextjs-app-router" in body["supported_frameworks"]


def test_toggle_round_trip(demo):
    on = demo.post(f"{BASE_URL}/api/apps/{APP_ID}/auto-inject/toggle", json={"enabled": True}, timeout=15)
    assert on.status_code == 200 and on.json()["enabled"] is True
    assert "preflight.js" in on.json()["active_build_command"]
    off = demo.post(f"{BASE_URL}/api/apps/{APP_ID}/auto-inject/toggle", json={"enabled": False}, timeout=15)
    assert off.status_code == 200 and off.json()["enabled"] is False
    assert "preflight.js" not in (off.json().get("active_build_command") or "")


def test_preflight_bad_token_403():
    r = requests.get(f"{BASE_URL}/api/auto-inject/preflight.js", params={"app": APP_ID, "token": "deadbeef"}, timeout=10)
    assert r.status_code == 403


def test_preflight_unknown_app_403():
    # Unknown app id — token verification fails first so 403.
    r = requests.get(f"{BASE_URL}/api/auto-inject/preflight.js", params={"app": "nope", "token": "x"}, timeout=10)
    assert r.status_code == 403


def test_result_callback_persists(demo, preflight_path):
    # Run preflight against a minimal Next.js App Router fixture and check
    # that the last_result row gets populated.
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "app"))
        with open(os.path.join(td, "package.json"), "w") as f:
            f.write('{"name":"t","dependencies":{"next":"14"}}')
        with open(os.path.join(td, "app", "layout.tsx"), "w") as f:
            f.write("export default function L({children}:{children:any}){return(<html><body>{children}</body></html>);}")
        subprocess.check_output(["node", preflight_path], cwd=td)
    r = demo.get(f"{BASE_URL}/api/apps/{APP_ID}/auto-inject", timeout=15)
    last = r.json().get("last_result") or {}
    assert last.get("status") == "injected"
    assert last.get("framework") == "nextjs-app-router"


# ───────────────────── per-framework injection ─────────────────────


FRAMEWORK_FIXTURES = [
    # (name, files: {path: content}, expected_patch_path, expected_framework)
    (
        "nextjs-app-router",
        {
            "package.json": '{"dependencies":{"next":"14"}}',
            "app/layout.tsx": "export default function L({children}:{children:any}){return(<html><body>{children}</body></html>);}",
        },
        "app/layout.tsx",
        "nextjs-app-router",
    ),
    (
        "nextjs-pages-router",
        {
            "package.json": '{"dependencies":{"next":"14"}}',
            "pages/_document.tsx": "import {Html,Head,Main,NextScript} from 'next/document';\nexport default function D(){return(<Html><Head><meta/></Head><body><Main/><NextScript/></body></Html>);}",
        },
        "pages/_document.tsx",
        "nextjs-pages-router",
    ),
    (
        "nuxt3",
        {
            "package.json": '{"dependencies":{"nuxt":"^3"}}',
            "nuxt.config.ts": "export default defineNuxtConfig({});",
        },
        "plugins/deployunit-analytics.client.ts",
        "nuxt3",
    ),
    (
        "sveltekit",
        {
            "package.json": '{"devDependencies":{"@sveltejs/kit":"^2"}}',
            "src/app.html": "<!DOCTYPE html><html><head><meta charset='utf-8'/></head><body></body></html>",
        },
        "src/app.html",
        "sveltekit",
    ),
    (
        "vite",
        {
            "package.json": '{"devDependencies":{"vite":"^5"}}',
            "index.html": "<!DOCTYPE html><html><head><title>x</title></head><body></body></html>",
        },
        "index.html",
        "vite",
    ),
    (
        "cra",
        {
            "package.json": '{"dependencies":{"react-scripts":"5"}}',
            "public/index.html": "<!DOCTYPE html><html><head></head><body></body></html>",
        },
        "public/index.html",
        "cra",
    ),
    (
        "astro",
        {
            "package.json": '{"dependencies":{"astro":"^4"}}',
            "src/layouts/Main.astro": "---\n---\n<html><head><title>x</title></head><body><slot/></body></html>",
        },
        "src/layouts/Main.astro",
        "astro",
    ),
    (
        "remix",
        {
            "package.json": '{"dependencies":{"@remix-run/react":"^2"}}',
            "app/root.tsx": "import {Meta,Links,Outlet} from '@remix-run/react';\nexport default function A(){return(<html><head><Meta/><Links/></head><body><Outlet/></body></html>);}",
        },
        "app/root.tsx",
        "remix",
    ),
    (
        "static-html",
        {
            "package.json": '{"name":"x"}',
            "index.html": "<!DOCTYPE html><html><head></head><body></body></html>",
        },
        "index.html",
        "static-html",
    ),
]


@pytest.mark.parametrize("name,files,expected_path,expected_fw", FRAMEWORK_FIXTURES, ids=[f[0] for f in FRAMEWORK_FIXTURES])
def test_framework_injection(preflight_path, name, files, expected_path, expected_fw):
    with tempfile.TemporaryDirectory() as td:
        for rel, content in files.items():
            full = os.path.join(td, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w") as f:
                f.write(content)
        out = subprocess.check_output(["node", preflight_path], cwd=td, text=True, stderr=subprocess.STDOUT)
        assert f"[deployunit:ok] injected → {expected_path} ({expected_fw})" in out, out
        with open(os.path.join(td, expected_path)) as f:
            patched = f.read()
        assert "deployunit-auto-injected" in patched, f"marker missing in {expected_path}:\n{patched}"
        # Run a SECOND time to confirm idempotency.
        out2 = subprocess.check_output(["node", preflight_path], cwd=td, text=True, stderr=subprocess.STDOUT)
        assert "already-injected" in out2, out2


def test_no_framework_match_does_not_crash(preflight_path):
    """An empty directory should yield an 'unknown framework' result with
    no crash and exit 0 (so the build never breaks)."""
    with tempfile.TemporaryDirectory() as td:
        out = subprocess.check_output(["node", preflight_path], cwd=td, text=True, stderr=subprocess.STDOUT)
        assert "not injected (unknown)" in out, out
