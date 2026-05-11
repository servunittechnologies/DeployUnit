# DeployHub — PRD

## Original problem statement
Build a one-stop SaaS hosting platform (Vercel-like) for Next.js & Node apps, **on top of Coolify** (deployment engine) and **Mollie** (direct billing, replacing WHMCS). Designed for individuals AND agencies, with workspaces, projects, apps, deployments, domains, monitoring, alerts, billing, and notifications.

## Stack
- **Frontend**: React + Tailwind + shadcn/ui + **framer-motion** (as of 2026-05-06) — terminal/IDE Swiss-high-contrast aesthetic, Outfit / IBM Plex Sans / JetBrains Mono. Futuristic revamp layer added on landing/auth with canvas constellation, aurora blobs, typewriter, scramble text, spotlight hover, 3D parallax.
- **Backend**: FastAPI + MongoDB (Motor async, UUID `id` fields, no `_id` in responses)
- **Workers**: APScheduler in-process
  - `monitor_tick` every 60s
  - `deploy_sync` every 15s
  - **`deployment_watchdog` every 30s** (NEW — self-heals stuck Coolify deploys)
- **Auth**: JWT + bcrypt, httpOnly + secure + SameSite=None cookies, Bearer fallback
- **Integrations** (LIVE):
  - Coolify v1 — http://149.12.246.205:8000
  - Mollie v2 (Subscriptions)
  - GitHub OAuth
- **Legacy**: `clients/whmcs.py` retained in code (dormant — still referenced by domains.py/settings.py for domain-WHOIS + health-check display only).

## User personas
- **Solo founder** (Hobby plan): 1 app, hands-off deploys.
- **Indie dev** (Pro plan): up to 10 apps, custom domains, alerts.
- **Agency** (Agency plan): workspaces with projects, team roles (owner / admin / developer / billing / viewer), white-label invoices.

## Core requirements (static)
1. Sign up, log in, manage account.
2. Pick a plan; create Mollie customer + subscription.
3. Create workspaces (Solo or Agency); invite members with roles.
4. Group apps into projects (agency feature).
5. Deploy a Next.js / Node app from a Git repo via Coolify.
6. Link custom domains; auto-SSL.
7. Realtime monitoring (uptime + response time) + alert rules → in-app notifications.
8. View invoices in-dashboard (PDF, EU VAT compliant).

## Implemented — snapshot as of 2026-05-06
### Backend (`/app/backend`)
- `server.py` — FastAPI app with lifespan, APScheduler (3 jobs), CORS.
- `auth_utils.py`, `crypto_utils.py` — bcrypt, JWT, httpOnly cookies, Fernet token encryption.
- Routers: `auth`, `github_oauth`, `workspaces`, `projects`, `apps`, `deployments`, `domains`, `monitoring`, `alerts`, `billing`, `notifications`, `settings`, `github`.
- `clients/coolify.py` — Coolify v1 client.
- `clients/mollie.py` — Mollie v2 raw httpx client (customers, subscriptions, mandates, payments).
- `services/vat.py` — EU VAT + VIES SOAP validation.
- `services/invoice.py` — reportlab PDF invoice generator with reverse-charge + sequential numbering (`YYYY-NNNN`).
- `services/log_parser.py` — severity tagging (error/warning/build/deploy/info) + failure-summary extraction.
- `services/github_helpers.py` — default-branch auto-detect.
- `workers/monitor.py` — uptime probe, Coolify deploy-sync, **deployment_watchdog** (NEW).
- `seed.py` — admin + demo users, seeded workspace + apps + notification.

### Frontend (`/app/frontend/src`)
- Marketing landing — **REBUILT 2026-05-06 (futuristic revamp)**: aurora-blob background, canvas constellation, typewriter hero lead, animated terminal, live-latency HUD, 7-card bento grid with mouse-spotlight hover, 3D parallax "deploy playground", scroll-linked stat strip, tech marquee.
- Pricing — **REBUILT** with framer-motion reveals, pulse-glow on recommended, spotlight cards.
- Auth (Login/Register) — **REBUILT** with canvas constellation panel, scramble-text welcome, motion reveals. GitHub OAuth buttons intact.
- Checkout, Billing, Dashboard (Overview, Projects, NewApp wizard, AppDetail tabs×6, Domains, Monitoring, Alerts, Settings, Notifications).
- `SitePreview.jsx` — HTTP mixed-content fallback (NEW 2026-05-06): detects `http://` primary_url and renders a `preview-fallback-open` link instead of a broken iframe.
- Components: `ConstellationCanvas.jsx` (canvas particles + connecting lines), `Logo`, `GitHubButton`, `ProtectedRoute`, `TerminalLog`, `BuildErrorPanel`, `DeploymentStatus`, `DeployModal`, `EnvVarsEditor`, `AppCard`, `StatusBadge`, `DashboardLayout`.
- Hooks: `useTypewriter`, `useScrambleText`, `useSpotlight`, `useDeploymentStream`.

## P1 backlog (next)
- **One-click templates** — pre-built Coolify launch presets for Next.js SaaS starter, blog, e-commerce, marketing landing. No GitHub OAuth required for first deploy.
- **`.env.example` auto-import** from GitHub repo on first deploy — parse and seed the env vars editor automatically.
- Email notifications (need Resend / SendGrid key) — replaces the current in-app stub in send_alert.
- White-label / branding for agency workspaces — custom logo + accent color per workspace.
- Resource usage alerts (CPU / RAM / bandwidth limits hitting plan ceilings).

## P2 backlog
- PR Preview Deploys (Vercel-style) — ephemeral apps per PR.
- `.env.example` auto-import from GitHub repo on first deploy.
- Cron/scheduled tasks management.
- Postgres/Redis as-a-service.
- Slack + Discord alert channels.
- Multi-region deployment selection.
- Coupon system on checkout.
- Audit log.

## Test credentials
- Admin: `admin@deployhub.dev` / `admin123`
- Demo: `demo@deployhub.dev` / `demo1234`

## Changelog
- **2026-05-11 — White-label rebrand: WHMCS gone, Coolify hidden**
  - **WHMCS volledig verwijderd**: `clients/whmcs.py` deleted; imports + `whmcs.health()` weggehaald uit `routers/settings.py`; `GET /api/domains/whois` endpoint verwijderd uit `routers/domains.py`; tests bijgewerkt; Landing.jsx "No WHMCS screens" copy weggehaald.
  - **Coolify onzichtbaar voor eindgebruiker**:
    - Footers in Landing/Pricing/Register: "Built on Coolify · Powered by Mollie" → "Hosting for Next.js & Node"
    - Landing hero tagline: "Built on Coolify" verwijderd
    - `BuildErrorPanel.jsx`: docs-link `coolify.io/docs/troubleshoot` → `docs.nixpacks.com/troubleshooting`
    - `SitePreview.jsx`: "Enable SSL on Coolify" → "Enable SSL for this app"
    - Backend `_append_log` strings in `routers/apps.py` + `workers/monitor.py`: alle "coolify" → "build engine" / "application created" (zichtbaar in deployment TerminalLog)
    - `_fail_deploy` foutmeldingen: "no coolify server" → "no build server"
  - **Admin Console**: Coolify blijft zichtbaar onder Admin → Integrations (interne ops tooling, alleen voor de eigenaar).
  - **Files touched**: `routers/settings.py`, `routers/domains.py`, `routers/apps.py`, `workers/monitor.py`, `tests/backend_test.py`; `pages/Landing.jsx`, `pages/Pricing.jsx`, `pages/Register.jsx`, `components/BuildErrorPanel.jsx`, `components/SitePreview.jsx`. Deleted: `clients/whmcs.py`.

- **2026-05-11 — Sprint 4: 3 sales-growth features (Iter9)**
  - **🌐 Cloudflare auto-subdomain**: nieuwe `clients/cloudflare.py` + `services/subdomains.py`. Wanneer admin Cloudflare configureert (zone_id + token + target ip/host), krijgt elke app automatisch een gratis `{slug}.{zone_name}` DNS-record + `primary_url`. Coolify wordt op de hoogte gebracht via `fqdn` zodat Traefik SSL uitgeeft. Cleanup gebeurt automatisch bij app-delete. Graceful: zonder Cloudflare config blijft alles werken.
  - **🔁 GitHub Webhooks (auto-deploy on push)**: nieuwe `routers/webhooks.py` + `services/github_webhooks.py`. Per-app webhook_secret (64-char hex, secrets.token_hex(32)), HMAC-SHA256 verificatie met `hmac.compare_digest` (constant-time), branch-matching, fire-and-forget redeploy via `_redeploy_background`. Auto-registratie bij `create_app` als de gebruiker GitHub OAuth heeft gekoppeld; manueel via `POST /api/apps/{id}/webhook/register` als hij later koppelt. UI in AppDetail → Settings → "Auto-deploy on push": webhook URL copy, secret reveal/copy/rotate, enable/disable toggle, manual setup instructies.
  - **🏢 Agency Fleet View**: nieuwe `routers/fleet.py` + `pages/dashboard/Fleet.jsx`. Multi-workspace dashboard met problem-first sorting (broken apps bubblen naar boven), 5 KPI-cards (workspaces · apps total · broken · live · monthly recurring), bulk-redeploy knop voor alle broken apps tegelijk (cap 50). Gated op `plan.fleet_view=true` (alleen Agency plan); andere users zien een upgrade-paywall. Nav-link enkel zichtbaar voor agency-workspaces.
  - **Tests**: 21/22 GREEN op iter9. Fix toegepast op enige cosmetic issue: webhook ping/ignored returns nu HTTP 200 (was 202 door foutieve route default), queued path blijft 202 via `JSONResponse`. Datetime parsing in fleet sort gehard met try/except. `bulk_redeploy` rapporteert ook `skipped` count voor apps zonder build-engine UUID. 
  - **Files touched**: nieuw — `routers/{webhooks,fleet}.py`, `services/{subdomains,github_webhooks}.py`, `clients/cloudflare.py`, `pages/dashboard/Fleet.jsx`. Aangepast — `server.py`, `routers/apps.py`, `App.js`, `components/DashboardLayout.jsx`, `pages/dashboard/AppDetail.jsx`.

- **2026-05-11 — UX hygiene (Iter8)**
  - Settings.jsx: Coolify/WHMCS/Twilio platform-integrations grid verwijderd uit user-facing pagina; alleen "Connected accounts" (GitHub) blijft.
  - Admin → Platform Domain: Twilio config-sectie toegevoegd (Account SID, Auth Token Fernet-encrypted, From phone, Messaging Service SID, WhatsApp sender, Status callback URL, Test mode). `twilio_auth_token_set` boolean redacted naar frontend.
  - Coolify integratie-status in Admin: nu drie duidelijke states (connected / configured-but-unreachable / not-configured) met foutreden inline. Geen misleidende "offline" meer.
  - Billing: 4 stale €0 free-plan Mollie-payment records uit DB verwijderd; `/api/billing/subscription` filtert nu €0/free/hobby records weg uit de `payments` lijst; Billing.jsx erkent zowel "free" als legacy "hobby" voor subscription-status. Free plan kan nu nooit meer "expired" lijken.

- **2026-05-11 — Sprint 3: Twilio SMS + WhatsApp notifications**
  - **Backend**: `clients/twilio.py` (async httpx, creds from `platform_settings`, Fernet-decrypted), `services/notifications_sms.py` (per-event dispatch, atomic credit consume/refund, Twilio status webhook handler), `routers/notifications.py` (GET/PUT `/api/notifications/prefs`, POST `/api/notifications/test`, POST `/api/notifications/twilio/status` webhook). Test-send bypasses prefs matrix so the user can validate each channel explicitly.
  - **Frontend**: `pages/dashboard/Settings.jsx` — Notification Preferences section: E.164 phone input, 7×3 toggle matrix (events × {SMS, WhatsApp, Email}), credit-cost legend, Test SMS / Test WhatsApp buttons.
  - **Pricing**: SMS EU = 1 cr (~€0.10), SMS intl = 2 cr, WhatsApp = 1 cr, Email = free (in-app).
  - **Graceful degradation**: when Twilio is not configured, sends return `status:'skipped'` with a precise error reason (`'no phone'` / `'twilio not configured'`); never crashes the alert flow. Credits are refunded on TwilioError responses.
  - **Tests**: 14/14 new Iter8 backend assertions green. Full suite 77/78. Report at `/app/test_reports/iteration_8.json`.

## Changelog (older)
- **2026-05-06 — Futuristic revamp + P0 deploy-retry hardening (Iter7)**
  - **P0 fix — silent Coolify deploys**: Split `create_public_app(instant_deploy=True)` → `create_public_app(instant_deploy=False)` + explicit `coolify.deploy()` with 3× exponential backoff retries (2s→4s→8s) in `_trigger_coolify_deploy_with_retry`. Each attempt is logged to `deployment.logs` so users can see retries in the TerminalLog UI.
  - **Watchdog** — new APScheduler job `deployment_watchdog` every 30s picks up deployments stuck in `queued`/`building` >90s without a `coolify_deployment_uuid` and retries once. `max_instances=2` to prevent scheduler starvation.
  - **Response-time SLA** — all Coolify I/O (`/apps` POST, `/apps/{id}/redeploy`, PATCH `/apps/{id}`, PUT `/apps/{id}/env`) now runs in `BackgroundTasks` so API responds in <2s.
  - **Landing page revamp** — futuristic hero with animated terminal + typewriter + response-latency HUD + orbital ornament + canvas constellation + aurora blobs. 7-card bento platform grid with mouse-tracked spotlight. 3D-parallax dashboard playground. Scroll-linked stat strip. Ring-glow magnetic buttons.
  - **Pricing revamp** — framer-motion reveal, spotlight cards, pulse-glow on recommended plan.
  - **Login/Register revamp** — ConstellationCanvas side panel, scramble-text welcome, motion-reveal form.
  - **P1 fix — SitePreview HTTP fallback** — detects `http://` primary_url (mixed-content blocked by browser) and renders `preview-fallback` UI with a "Open full site" link instead of a blank iframe. New testid: `preview-fallback-open`.
  - Added: `framer-motion@12`, 3 new hooks (`useTypewriter`, `useScrambleText`, `useSpotlight`), `ConstellationCanvas` component.
  - Tests: 63/64 green (only pre-existing `/api/integrations/health` flake when Coolify host is slow). Iter7 test report at `/app/test_reports/iteration_7.json`.

- 2026-05-06 — Iter6 — Auto-detect branch, severity-tagged logs, BuildErrorPanel, SSE log stream (58/58 backend green).
- 2026-05-06 — Iter5 — Branch protection, rollback, site preview, production tier.
- 2026-05-06 — Iter4 — AppDetail advanced controls (editable settings, env vars editor, deploy modal).
- 2026-05-06 — Iter3 — Mollie billing migration + EU VAT + PDF invoices.
- 2026-05-06 — Iter2 — GitHub OAuth wired live (Fernet-encrypted tokens, CSRF state).
- 2026-05-06 — Phase 1 MVP shipped (25/25 backend, all frontend flows green).
