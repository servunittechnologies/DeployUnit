"""Auto-injector for the analytics tracking snippet.

Architecture
============
At build-time, inside the customer's container (Nixpacks/Docker), we prepend
a tiny Node.js preflight to the build command. The preflight detects the
framework from `package.json` + file layout, then patches exactly one
template/HTML file with the analytics `<script>` tag. The original
`build_command` is then executed unchanged.

Failure is logged + reported, never blocks the deploy.

Supported frameworks:
  * Next.js App Router  → app/layout.{tsx,jsx,ts,js}
  * Next.js Pages Router→ pages/_document.{...}  (creates one if missing)
  * Nuxt 3              → drops a client plugin under plugins/
  * SvelteKit           → src/app.html
  * Astro               → first src/layouts/*.astro with </head>
  * Remix               → app/root.{tsx,jsx,ts,js}
  * Vite / CRA / Static → index.html (root or public/)
"""
from __future__ import annotations

import hashlib
import hmac
import json as _json
import logging
import os
from typing import Optional

from db import get_db

logger = logging.getLogger(__name__)

# Marker that goes into every patched file so re-runs are idempotent.
INJECTION_MARKER = "deployunit-auto-injected"


def _hmac_token(app_id: str) -> str:
    secret = (
        os.environ.get("AUTO_INJECT_SECRET")
        or os.environ.get("JWT_SECRET")
        or "deployunit-auto-inject"
    ).encode()
    return hmac.new(secret, app_id.encode(), hashlib.sha256).hexdigest()[:24]


def verify_token(app_id: str, token: str) -> bool:
    return hmac.compare_digest(_hmac_token(app_id), token or "")


def _public_base() -> str:
    base = (
        os.environ.get("FRONTEND_URL")
        or os.environ.get("PUBLIC_FRONTEND_URL")
        or os.environ.get("REACT_APP_BACKEND_URL")
        or "https://deployunit.com"
    ).rstrip("/")
    return base


def short_preflight_url(app_id: str) -> str:
    """Compact preflight URL using path params so the full wrapped
    build_command fits inside Coolify v4's 255-char limit on the
    `build_command` field."""
    return f"{_public_base()}/api/aij/{app_id}/{_hmac_token(app_id)}"


def preflight_url(app_id: str) -> str:
    return f"{_public_base()}/api/auto-inject/preflight.js?app={app_id}&token={_hmac_token(app_id)}"


def report_url(app_id: str) -> str:
    return f"{_public_base()}/api/auto-inject/result?app={app_id}&token={_hmac_token(app_id)}"


# Coolify v4 rejects:
#   * any `;` in build_command  → "field format is invalid" (422)
#   * build_command strings > 255 chars → HTTP 500 (DB column overflow)
# So our wrap MUST fit in 255 chars and use `&&`/`||` only.
COOLIFY_BUILD_CMD_MAX = 255


def wrap_build_command(app_id: str, base_command: str | None) -> str:
    """Prepend a compact preflight invocation to the user's build command.

    Layout (always ASCII, no semicolons, fits in 255 chars for typical
    URLs + bases):

        curl -fsSL "<short_url>" -o /tmp/i && node /tmp/i || true && <base>

    If the resulting string would exceed Coolify's 255-char limit we fall
    back to returning the user's base command unchanged and emit a
    warning in the logs — auto-injection silently degrades rather than
    breaking the deploy with a 422.
    """
    base = (base_command or "").strip() or "yarn build || npm run build"
    pre = f'curl -fsSL "{short_preflight_url(app_id)}" -o /tmp/i && node /tmp/i || true'
    wrapped = f"{pre} && {base}"
    if len(wrapped) > COOLIFY_BUILD_CMD_MAX:
        logger.warning(
            "auto-inject wrap exceeds Coolify build_command limit (%d > %d) for app %s — falling back to base",
            len(wrapped), COOLIFY_BUILD_CMD_MAX, app_id,
        )
        return base
    return wrapped


def unwrap_build_command(wrapped: str | None) -> str:
    """Inverse of wrap_build_command — returns the user's original build
    command when toggling auto-inject OFF."""
    if not wrapped:
        return ""
    # Compact wrap (current): `curl ... && node /tmp/i || true && <base>`
    if "node /tmp/i || true && " in wrapped:
        return wrapped.split("node /tmp/i || true && ", 1)[1].strip()
    # Legacy verbose wrap markers (kept for migration safety).
    for marker in (
        "[deployunit] preflight skipped (non-fatal)",
        "[deployunit] auto-inject preflight skipped (non-fatal)",
    ):
        if marker in wrapped:
            idx = wrapped.find(marker)
            for sep in (' && ', ' ; '):
                pos = wrapped.find(sep, idx)
                if pos > -1:
                    return wrapped[pos + len(sep):].strip()
    return wrapped.strip()


async def is_enabled(app_id: str) -> bool:
    db = get_db()
    cfg = await db.app_analytics_config.find_one(
        {"app_id": app_id}, {"_id": 0, "auto_inject_enabled": 1}
    )
    return bool((cfg or {}).get("auto_inject_enabled"))


# ───────────────────── Status tracking ─────────────────────


async def record_result(app_id: str, payload: dict) -> dict:
    db = get_db()
    safe = {
        "status": str(payload.get("status") or "unknown")[:32],
        "framework": str(payload.get("framework") or "")[:32],
        "file": str(payload.get("file") or "")[:240],
        "error": str(payload.get("error") or "")[:500],
        "skipped_reason": str(payload.get("skipped_reason") or "")[:240],
        "at": payload.get("at"),
    }
    await db.app_analytics_config.update_one(
        {"app_id": app_id},
        {"$set": {"last_injection_result": safe}},
        upsert=True,
    )
    return safe


async def get_last_result(app_id: str) -> Optional[dict]:
    db = get_db()
    cfg = await db.app_analytics_config.find_one(
        {"app_id": app_id}, {"_id": 0, "last_injection_result": 1}
    )
    return (cfg or {}).get("last_injection_result")


# ───────────────────── Preflight Node.js script ─────────────────────


def render_preflight_js(
    *,
    app_id: str,
    site_id: str,
    snippet_url: str,
    collect_url: str,
) -> str:
    """Render the Node.js preflight with per-app values baked in via JSON
    literals (always valid, no escaping issues)."""
    snippet_html = (
        f'<script defer data-site="{site_id}" '
        f'data-endpoint="{collect_url}" '
        f'src="{snippet_url}"></script>'
    )
    replacements = {
        "__DPU_APP_ID__": _json.dumps(app_id),
        "__DPU_SITE_ID__": _json.dumps(site_id),
        "__DPU_SNIPPET_URL__": _json.dumps(snippet_url),
        "__DPU_COLLECT_URL__": _json.dumps(collect_url),
        "__DPU_REPORT_URL__": _json.dumps(report_url(app_id)),
        "__DPU_MARKER__": _json.dumps(INJECTION_MARKER),
        "__DPU_SNIPPET__": _json.dumps(snippet_html),
    }
    out = _PREFLIGHT_TEMPLATE
    for k, v in replacements.items():
        out = out.replace(k, v)
    return out


_PREFLIGHT_TEMPLATE = r"""#!/usr/bin/env node
/* eslint-disable */
// DeployUnit auto-inject preflight — runs inside the customer build container
// BEFORE the user's build command. Patches one source file with the analytics
// snippet, then exits. Failure is logged but never breaks the build.

const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

const APP_ID = __DPU_APP_ID__;
const SITE_ID = __DPU_SITE_ID__;
const SNIPPET_URL = __DPU_SNIPPET_URL__;
const COLLECT_URL = __DPU_COLLECT_URL__;
const REPORT_URL = __DPU_REPORT_URL__;
const MARKER = __DPU_MARKER__;
const SNIPPET = __DPU_SNIPPET__;

const CWD = process.cwd();

function log(level, msg) { console.log('[deployunit:' + level + '] ' + msg); }
function exists(...p) { try { return fs.existsSync(path.join(CWD, ...p)); } catch { return false; } }
function read(...p) { try { return fs.readFileSync(path.join(CWD, ...p), 'utf8'); } catch { return null; } }
function write(rel, content) { fs.writeFileSync(path.join(CWD, rel), content, 'utf8'); }
function firstExisting(rels) { for (const r of rels) { if (exists(r)) return r; } return null; }
function loadPkg() { const raw = read('package.json'); if (!raw) return null; try { return JSON.parse(raw); } catch { return null; } }
function alreadyInjected(s) { return typeof s === 'string' && s.includes(MARKER); }
function hasDep(pkg, name) {
  if (!pkg) return false;
  return !!((pkg.dependencies && pkg.dependencies[name]) || (pkg.devDependencies && pkg.devDependencies[name]));
}

// ───────────── Strategies ─────────────

function nextAppRouter(pkg) {
  if (!hasDep(pkg, 'next')) return null;
  const file = firstExisting([
    'app/layout.tsx','app/layout.jsx','app/layout.ts','app/layout.js',
    'src/app/layout.tsx','src/app/layout.jsx','src/app/layout.ts','src/app/layout.js',
  ]);
  if (!file) return null;
  return { framework: 'nextjs-app-router', patch: () => {
    const src = read(file);
    if (alreadyInjected(src)) return { ok: true, file, framework: 'nextjs-app-router', skipped: 'already-injected' };
    if (!/<\/body>/.test(src)) return { ok: false, file, framework: 'nextjs-app-router', error: 'no </body> in layout' };
    let out = src;
    if (!/from\s+['"]next\/script['"]/.test(out)) {
      out = "import Script from 'next/script';\n/* " + MARKER + " */\n" + out;
    }
    const tag = '\n        <Script src=' + JSON.stringify(SNIPPET_URL) +
                ' data-site=' + JSON.stringify(SITE_ID) +
                ' data-endpoint=' + JSON.stringify(COLLECT_URL) +
                ' strategy="afterInteractive" />';
    const patched = out.replace(/<\/body>/, tag + '\n      </body>');
    write(file, patched);
    return { ok: true, file, framework: 'nextjs-app-router' };
  } };
}

function nextPagesRouter(pkg) {
  if (!hasDep(pkg, 'next')) return null;
  // Skip if App Router exists (avoid double-patching).
  if (exists('app/layout.tsx') || exists('app/layout.jsx') || exists('app/layout.ts') || exists('app/layout.js') ||
      exists('src/app/layout.tsx') || exists('src/app/layout.jsx')) return null;
  const doc = firstExisting([
    'pages/_document.tsx','pages/_document.jsx','pages/_document.ts','pages/_document.js',
    'src/pages/_document.tsx','src/pages/_document.jsx',
  ]);
  if (doc) {
    return { framework: 'nextjs-pages-router', patch: () => {
      const src = read(doc);
      if (alreadyInjected(src)) return { ok: true, file: doc, framework: 'nextjs-pages-router', skipped: 'already-injected' };
      if (!/<Head>/.test(src)) return { ok: false, file: doc, framework: 'nextjs-pages-router', error: 'no <Head> in _document' };
      const tag = '\n          {/* ' + MARKER + ' */}\n          <script defer src=' + JSON.stringify(SNIPPET_URL) +
                  ' data-site=' + JSON.stringify(SITE_ID) +
                  ' data-endpoint=' + JSON.stringify(COLLECT_URL) + '></script>';
      const patched = src.replace(/<\/Head>/, tag + '\n        </Head>');
      write(doc, patched);
      return { ok: true, file: doc, framework: 'nextjs-pages-router' };
    } };
  }
  // No _document — create a minimal one.
  return { framework: 'nextjs-pages-router', patch: () => {
    const dir = exists('pages') ? 'pages' : exists('src/pages') ? 'src/pages' : null;
    if (!dir) return { ok: false, file: '(missing)', framework: 'nextjs-pages-router', error: 'no pages/ directory' };
    const target = dir + '/_document.js';
    const tpl = '// ' + MARKER + '\n' +
                "import Document, { Html, Head, Main, NextScript } from 'next/document';\n" +
                'export default class extends Document {\n' +
                '  render() {\n' +
                '    return (\n' +
                '      <Html>\n' +
                '        <Head>\n' +
                '          <script defer src=' + JSON.stringify(SNIPPET_URL) +
                          ' data-site=' + JSON.stringify(SITE_ID) +
                          ' data-endpoint=' + JSON.stringify(COLLECT_URL) + '></script>\n' +
                '        </Head>\n' +
                '        <body><Main /><NextScript /></body>\n' +
                '      </Html>\n' +
                '    );\n' +
                '  }\n' +
                '}\n';
    write(target, tpl);
    return { ok: true, file: target, framework: 'nextjs-pages-router', created: true };
  } };
}

function nuxt3(pkg) {
  if (!hasDep(pkg, 'nuxt') && !hasDep(pkg, 'nuxt3')) return null;
  if (!firstExisting(['nuxt.config.ts','nuxt.config.js','nuxt.config.mjs'])) return null;
  return { framework: 'nuxt3', patch: () => {
    // Drop a client-only plugin — Nuxt auto-registers anything in plugins/.
    const target = 'plugins/deployunit-analytics.client.ts';
    const existing = read(target);
    if (alreadyInjected(existing)) return { ok: true, file: target, framework: 'nuxt3', skipped: 'already-injected' };
    try { fs.mkdirSync(path.join(CWD, 'plugins'), { recursive: true }); } catch {}
    const code = '// ' + MARKER + '\n' +
                 'export default defineNuxtPlugin(() => {\n' +
                 "  if (typeof document === 'undefined') return;\n" +
                 "  const s = document.createElement('script');\n" +
                 '  s.defer = true;\n' +
                 '  s.src = ' + JSON.stringify(SNIPPET_URL) + ';\n' +
                 "  s.setAttribute('data-site', " + JSON.stringify(SITE_ID) + ");\n" +
                 "  s.setAttribute('data-endpoint', " + JSON.stringify(COLLECT_URL) + ");\n" +
                 '  document.head.appendChild(s);\n' +
                 '});\n';
    write(target, code);
    return { ok: true, file: target, framework: 'nuxt3', created: true };
  } };
}

function sveltekit(pkg) {
  if (!hasDep(pkg, '@sveltejs/kit')) return null;
  const file = firstExisting(['src/app.html']);
  if (!file) return null;
  return { framework: 'sveltekit', patch: () => {
    const src = read(file);
    if (alreadyInjected(src)) return { ok: true, file, framework: 'sveltekit', skipped: 'already-injected' };
    if (!/<\/head>/i.test(src)) return { ok: false, file, framework: 'sveltekit', error: 'no </head> in src/app.html' };
    const tag = '    <!-- ' + MARKER + ' -->\n    ' + SNIPPET + '\n  ';
    const patched = src.replace(/<\/head>/i, tag + '</head>');
    write(file, patched);
    return { ok: true, file, framework: 'sveltekit' };
  } };
}

function astro(pkg) {
  if (!hasDep(pkg, 'astro')) return null;
  const dir = exists('src/layouts') ? path.join(CWD, 'src/layouts') : null;
  if (!dir) return null;
  let target = null;
  for (const entry of fs.readdirSync(dir)) {
    if (!entry.endsWith('.astro')) continue;
    const rel = path.join('src/layouts', entry);
    const src = read(rel);
    if (src && /<\/head>/i.test(src)) { target = rel; break; }
  }
  if (!target) return null;
  return { framework: 'astro', patch: () => {
    const src = read(target);
    if (alreadyInjected(src)) return { ok: true, file: target, framework: 'astro', skipped: 'already-injected' };
    const tag = '  <!-- ' + MARKER + ' -->\n  ' + SNIPPET + '\n  ';
    const patched = src.replace(/<\/head>/i, tag + '</head>');
    write(target, patched);
    return { ok: true, file: target, framework: 'astro' };
  } };
}

function remix(pkg) {
  if (!hasDep(pkg, '@remix-run/react') && !hasDep(pkg, '@remix-run/node')) return null;
  const file = firstExisting(['app/root.tsx','app/root.jsx','app/root.ts','app/root.js']);
  if (!file) return null;
  return { framework: 'remix', patch: () => {
    const src = read(file);
    if (alreadyInjected(src)) return { ok: true, file, framework: 'remix', skipped: 'already-injected' };
    if (!/<Links\s*\/>|<Meta\s*\/>/.test(src)) return { ok: false, file, framework: 'remix', error: 'no <Meta/> or <Links/> in root' };
    const tag = '\n        {/* ' + MARKER + ' */}\n        <script defer src=' + JSON.stringify(SNIPPET_URL) +
                ' data-site=' + JSON.stringify(SITE_ID) +
                ' data-endpoint=' + JSON.stringify(COLLECT_URL) + '></script>';
    let patched = src;
    if (/<Links\s*\/>/.test(patched)) patched = patched.replace(/<Links\s*\/>/, '<Links />' + tag);
    else patched = patched.replace(/<Meta\s*\/>/, '<Meta />' + tag);
    write(file, patched);
    return { ok: true, file, framework: 'remix' };
  } };
}

function viteOrCRA(pkg) {
  // Skip if Next.js is detected — we handle that above.
  if (exists('pages') || exists('app/layout.tsx') || exists('src/app/layout.tsx')) return null;
  const file = firstExisting(['index.html','public/index.html']);
  if (!file) return null;
  const isVite = hasDep(pkg, 'vite');
  const isCRA = hasDep(pkg, 'react-scripts');
  const fw = isVite ? 'vite' : isCRA ? 'cra' : 'static-html';
  return { framework: fw, patch: () => {
    const src = read(file);
    if (alreadyInjected(src)) return { ok: true, file, framework: fw, skipped: 'already-injected' };
    if (!/<\/head>/i.test(src)) return { ok: false, file, framework: fw, error: 'no </head> in index.html' };
    const tag = '    <!-- ' + MARKER + ' -->\n    ' + SNIPPET + '\n  ';
    const patched = src.replace(/<\/head>/i, tag + '</head>');
    write(file, patched);
    return { ok: true, file, framework: fw };
  } };
}

// ───────────── Main ─────────────
async function main() {
  const pkg = loadPkg();
  const strategies = [nextAppRouter, nextPagesRouter, nuxt3, sveltekit, remix, astro, viteOrCRA];
  let result = null;
  for (const s of strategies) {
    const strat = s(pkg);
    if (!strat) continue;
    try {
      result = strat.patch() || { ok: false, framework: strat.framework, error: 'patch returned nothing' };
    } catch (e) {
      result = { ok: false, framework: strat.framework, error: String((e && e.message) || e).slice(0, 400) };
    }
    break;
  }
  if (!result) result = { ok: false, framework: 'unknown', skipped: 'no matching framework strategy' };
  if (result.ok) log('ok', 'injected → ' + result.file + ' (' + result.framework + ')' + (result.skipped ? ' [' + result.skipped + ']' : ''));
  else log('warn', 'not injected (' + result.framework + '): ' + (result.error || result.skipped || 'unknown'));
  try { await report(result); } catch (e) { log('warn', 'report failed: ' + e.message); }
}

function report(result) {
  return new Promise((resolve) => {
    try {
      const url = new URL(REPORT_URL);
      const lib = url.protocol === 'https:' ? https : http;
      const body = JSON.stringify({
        status: result.ok ? (result.skipped ? 'skipped' : 'injected') : 'failed',
        framework: result.framework || null,
        file: result.file || null,
        error: result.error || null,
        skipped_reason: result.skipped || null,
        at: new Date().toISOString(),
      });
      const req = lib.request({
        method: 'POST', protocol: url.protocol, hostname: url.hostname,
        port: url.port || (url.protocol === 'https:' ? 443 : 80),
        path: url.pathname + url.search,
        headers: { 'content-type': 'application/json', 'content-length': Buffer.byteLength(body) },
        timeout: 8000,
      }, (res) => { res.resume(); res.on('end', resolve); });
      req.on('error', () => resolve());
      req.on('timeout', () => { req.destroy(); resolve(); });
      req.write(body); req.end();
    } catch { resolve(); }
  });
}

main().catch(e => { log('warn', 'preflight crashed: ' + ((e && e.message) || e)); process.exit(0); });
"""
