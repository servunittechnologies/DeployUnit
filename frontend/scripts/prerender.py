#!/usr/bin/env python3
"""Prerender public marketing routes to static HTML so the site loads
without JavaScript.

How it works
------------
1. Spin up a tiny HTTP server on the built `build/` folder (which is
   what production serves anyway).
2. Use Playwright (already available in the container) to visit every
   public route in a headless Chromium.
3. Wait for the page to settle (network idle + a short tick so
   framer-motion has reached its resting state).
4. Read `document.documentElement.outerHTML` and write it to
   `build/<route>/index.html` (or `build/index.html` for `/`).
5. The original SPA bundle is still embedded in those snapshots, so
   when JS *is* available React 19 hydrates the static markup
   transparently (`hydrateRoot` in `src/index.js`).

For no-JS visitors (slow connections, screen readers, search engines)
they get a complete, readable page immediately. For JS-enabled visitors
nothing changes — they just see the page paint faster because the HTML
is already there before the bundle parses.
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket
import sys
import threading
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# Public marketing routes that should be readable without JS. The dashboard
# (`/app/*`) and auth-walled flows are intentionally excluded — they are
# only useful with JS anyway.
ROUTES: list[str] = [
    "/",
    "/pricing",
    "/about",
    "/contact",
    "/support",
    "/status",
    "/login",
    "/register",
    "/forgot-password",
]

BUILD_DIR = Path(__file__).resolve().parent.parent / "build"
TIMEOUT_MS = 30_000  # per-page navigation timeout
SETTLE_MS = 800       # extra time after networkidle for animations / fonts

# Public origin to bake into prerendered <link rel="canonical">, og:url,
# twitter:url and any other absolute URLs the SPA writes via useSeo.
# Override with PRERENDER_ORIGIN env var (e.g. on a staging build).
PUBLIC_ORIGIN = os.environ.get("PRERENDER_ORIGIN", "https://deployunit.com").rstrip("/")

logging.basicConfig(
    level=logging.INFO,
    format="[prerender] %(message)s",
)
log = logging.getLogger("prerender")


def _free_port() -> int:
    """Pick an unused localhost port for the static server."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _SilentHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with an SPA fallback to `index.html`.

    This mimics the production static-host behavior (try_files $uri
    $uri/ /index.html) so unknown routes still render the shell.
    """

    def log_message(self, format, *args):  # silence the noisy stdout log
        return

    def do_GET(self):  # noqa: N802
        # Strip query string, decode
        raw_path = self.path.split("?", 1)[0]
        # Map URL to a file under BUILD_DIR
        rel = raw_path.lstrip("/")
        full = BUILD_DIR / rel
        if not rel or not full.exists() or full.is_dir():
            # Serve the SPA shell so client-side router can take over.
            self.path = "/index.html"
        return super().do_GET()


def _start_static_server(port: int) -> HTTPServer:
    handler = partial(_SilentHandler, directory=str(BUILD_DIR))
    httpd = HTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def _normalize_html(html: str, local_origin: str) -> str:
    """Rewrite the snapshot to look like it came from production:
      * replace the temporary localhost origin we used for crawling with
        the configured PUBLIC_ORIGIN
      * collapse duplicate posthog script tags (PostHog's snippet inserts
        itself once at runtime, and our shell already loads it — the
        snapshot ends up with two copies)
    """
    if local_origin and local_origin in html:
        html = html.replace(local_origin, PUBLIC_ORIGIN)
    # Drop duplicate inline posthog-array.js script tags. The first one
    # the SPA shell ships with is enough; subsequent identical clones
    # are noise that would double-count pageviews.
    posthog_marker = '<script type="text/javascript" crossorigin="anonymous" async="" src="https://us-assets.i.posthog.com/static/array.js"></script>'
    if html.count(posthog_marker) > 1:
        # keep the first occurrence, drop the rest
        first = html.find(posthog_marker)
        head, _, tail = html.partition(posthog_marker)
        html = head + posthog_marker + tail.replace(posthog_marker, "")
        _ = first  # quiet linters
    return html


async def _snapshot_route(browser, base: str, route: str) -> str | None:
    """Open one route, wait for it to settle, return final HTML."""
    page = await browser.new_page(viewport={"width": 1280, "height": 800})
    try:
        # Tell the app it's being prerendered so it can short-circuit
        # animations / network calls if it wants to.
        await page.add_init_script("window.__PRERENDER__ = true;")
        url = f"{base}{route}"
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        except Exception as e:
            log.warning("goto failed for %s: %s", route, e)
            return None
        # Wait for the SPA to finish rendering. We don't strictly need
        # networkidle (we have no XHR on public pages) but it's a cheap
        # safety net for fonts/images.
        try:
            await page.wait_for_load_state("networkidle", timeout=8_000)
        except Exception:
            pass
        # Belt-and-braces: poll for the React root to have content.
        try:
            await page.wait_for_function(
                "document.getElementById('root') && document.getElementById('root').children.length > 0",
                timeout=8_000,
            )
        except Exception:
            log.warning("root never populated for %s — emitting shell only", route)
        # Give framer-motion a beat to land on its final keyframe.
        await page.wait_for_timeout(SETTLE_MS)
        html = await page.content()
        return html
    finally:
        await page.close()


def _write_snapshot(route: str, html: str) -> Path:
    """Write the snapshot to disk at the right path so the static host
    serves it for that route."""
    if route in ("", "/"):
        target = BUILD_DIR / "index.html"
    else:
        slug = route.strip("/")
        out_dir = BUILD_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / "index.html"
    target.write_text(html, encoding="utf-8")
    return target


async def main() -> int:
    if not BUILD_DIR.exists():
        log.error("build/ not found — run `yarn build` first")
        return 1
    if not (BUILD_DIR / "index.html").exists():
        log.error("build/index.html missing — the build is incomplete")
        return 1

    port = _free_port()
    httpd = _start_static_server(port)
    base = f"http://127.0.0.1:{port}"
    log.info("static server on %s, prerendering %d routes", base, len(ROUTES))

    from playwright.async_api import async_playwright

    fail = 0
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(args=["--no-sandbox"])
            for route in ROUTES:
                log.info("→ %s", route)
                html = await _snapshot_route(browser, base, route)
                if not html:
                    fail += 1
                    continue
                html = _normalize_html(html, base)
                out = _write_snapshot(route, html)
                size_kb = out.stat().st_size / 1024
                log.info("  ✓ wrote %s (%.1f KB)", out.relative_to(BUILD_DIR.parent), size_kb)
            await browser.close()
    finally:
        httpd.shutdown()

    if fail:
        log.warning("%d route(s) failed — site still works, just falls back to JS-only there", fail)
    log.info("done")
    # Never fail the build because of a flaky prerender — production
    # always has a working SPA fallback.
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
