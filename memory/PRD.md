# DeployHub — PRD

## Original problem statement
Build a one-stop SaaS hosting platform (Vercel-like) for Next.js & Node apps, **on top of Coolify** (deployment engine) and **WHMCS** (hidden billing backend). Designed for individuals AND agencies, with workspaces, projects, apps, deployments, domains, monitoring, alerts, billing, and notifications.

## Stack
- **Frontend**: React + Tailwind + shadcn/ui (terminal/IDE Swiss-high-contrast aesthetic, Outfit / IBM Plex Sans / JetBrains Mono)
- **Backend**: FastAPI + MongoDB (Motor async, UUID `id` fields, no `_id` in responses)
- **Workers**: APScheduler in-process (`monitor_tick` every 60s, `deploy_sync` every 15s)
- **Auth**: JWT + bcrypt, httpOnly + secure + SameSite=None cookies, Bearer fallback
- **Integrations** (LIVE):
  - Coolify v1 — http://149.12.246.205:8000
  - WHMCS — https://my.servunit.com (`/includes/api.php`)
- **Mocked**: GitHub OAuth → `/api/github/repos` returns 5 sample repos. User opted in (no GitHub keys yet).

## User personas
- **Solo founder** (Hobby plan): 1 app, hands-off deploys.
- **Indie dev** (Pro plan): up to 10 apps, custom domains, alerts.
- **Agency** (Agency plan): workspaces with projects, team roles (owner / admin / developer / billing / viewer), white-label invoices.

## Core requirements (static)
1. Sign up, log in, manage account.
2. Pick a plan; create WHMCS client + invoice silently behind the scenes.
3. Create workspaces (Solo or Agency); invite members with roles.
4. Group apps into projects (agency feature).
5. Deploy a Next.js / Node app from a Git repo via Coolify.
6. Link custom domains; auto-SSL.
7. Realtime monitoring (uptime + response time) + alert rules → in-app notifications.
8. View invoices in-dashboard (synced from WHMCS).

## Implemented (MVP — 2026-05-06)
- **Backend** (`/app/backend`):
  - `server.py` — FastAPI app with lifespan, APScheduler, CORS.
  - `auth_utils.py` — bcrypt password, JWT access/refresh, httpOnly cookies, `get_current_user`, `require_workspace_member` (role-aware).
  - Routers: `auth`, `workspaces`, `projects`, `apps`, `deployments`, `domains`, `monitoring`, `alerts`, `billing`, `notifications`, `settings`, `github_mock`.
  - `clients/coolify.py` — Coolify v1 client (servers, projects, public-app create, deploy, env, restart, deployments).
  - `clients/whmcs.py` — WHMCS API client (AddClient, AddOrder, GetInvoices, DomainWhois).
  - `workers/monitor.py` — uptime checks + alert evaluation, deployment-status sync (Coolify reconcile + stub fallback).
  - `seed.py` — admin + demo users, sample workspace ("Acme Studio") + project (NovaBrew) + 3 sample apps + welcome notification.
- **Frontend** (`/app/frontend/src`):
  - Marketing landing (hero with terminal demo + monitoring strip + tech marquee + features bento + how-it-works + agency section + footer CTA).
  - Auth pages (Login / Register with side-by-side terminal callouts).
  - Pricing + Checkout pages.
  - Dashboard layout (sidebar + workspace switcher + topbar with search + notifications bell + user menu).
  - Pages: Overview (stats + grid-border app cards), Projects (+ detail), NewApp (2-step deploy wizard), AppDetail (6 tabs: overview, deployments, domains, env, monitoring, settings), Domains, Monitoring, Alerts (with rule modal), Billing (plan switch + invoices), Settings (profile / password / members / integrations health).
- **Tests**: 25/25 backend pytest pass; full frontend playwright sweep passed.

## P1 backlog (next)
- Real GitHub OAuth (need creds) — list user's repos, deploy from any branch, preview environments.
- Email notifications (need Resend / SendGrid key).
- Logs streaming via SSE/WebSocket from Coolify.
- Rollbacks (pin a deployment as live).
- Custom build commands + start commands per app.
- Billing webhooks from WHMCS (auto-mark invoice paid).
- White-label / branding for agency workspaces.
- Resource usage alerts.

## P2 backlog
- Slack + Discord alert channels.
- Multi-region selection.
- Coupon system on checkout.
- Audit log.

## Test credentials
- Admin: `admin@deployhub.dev` / `admin123`
- Demo:  `demo@deployhub.dev`  / `demo1234`

## Latest dates
- 2026-05-06 — Phase 1 MVP shipped, full-stack tested green (25/25 backend, all frontend flows).
