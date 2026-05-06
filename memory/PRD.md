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
  - `auth_utils.py` + `crypto_utils.py` — bcrypt password, JWT access/refresh, httpOnly cookies, `get_current_user`, `require_workspace_member` (role-aware), Fernet token encryption.
  - Routers: `auth`, `github_oauth`, `workspaces`, `projects`, `apps`, `deployments`, `domains`, `monitoring`, `alerts`, `billing`, `notifications`, `settings`, `github`.
  - `clients/coolify.py` — Coolify v1 client.
  - `clients/mollie.py` — **Mollie v2 client (raw httpx)** — customers, payments, subscriptions, mandates.
  - `clients/whmcs.py` — retained in codebase but no longer used by billing (safe to delete later).
  - `services/vat.py` — **EU VAT rates + VIES SOAP validation** (NL/destination/reverse-charge/non-EU).
  - `services/invoice.py` — **reportlab PDF invoice generator** with reverse-charge note + sequential numbering (`YYYY-NNNN`).
  - `workers/monitor.py` — uptime checks + alert evaluation, Coolify deploy-sync.
  - `seed.py` — admin + demo users, seeded workspace + apps + notification.
- **Frontend** (`/app/frontend/src`):
  - Marketing landing, auth (with GitHub OAuth button), Pricing (€), Checkout (inline billing profile + direct Mollie redirect).
  - Dashboard layout + all pages (Overview, Projects, NewApp wizard, AppDetail tabs×6, Domains, Monitoring, Alerts, Billing, Settings, Notifications).
  - **Billing page rewritten**: current plan, editable billing profile (VIES check), plan cards in €, payment history, PDF invoice table.
  - `BillingProfileForm` reusable component (company/address/country/email/VAT ID with VIES validate button).
  - GitHub OAuth — Login + Register + NewApp + Settings connect/disconnect.
- **Tests**: 35/36 backend pytest pass (only a cosmetic VAT regex edge-case, now fixed). Frontend playwright full sweep green.

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
- 2026-05-06 — **GitHub OAuth wired live** (`/api/auth/github/start` + `/api/auth/github/callback`). Buttons on Login + Register; per-user repo listing on NewApp; Connect/Disconnect on Settings. Real repos replace mocked samples once the user links. Tokens encrypted at rest with Fernet (`ENCRYPTION_KEY` in .env). State CSRF token stored in `oauth_states` collection with 10-min TTL.
- 2026-05-06 — **Billing migrated from WHMCS to Mollie Subscriptions**. Full EU VAT handling (NL 21%, destination rate for B2C EU, 0% reverse-charge for VIES-valid B2B EU, 0% for non-EU). reportlab-rendered PDF invoices with sequential numbering (`YYYY-NNNN`). Webhook handler idempotent on `mollie_payment_id`. `.env` extended with `MOLLIE_API_KEY`, `MOLLIE_WEBHOOK_URL`, `MOLLIE_REDIRECT_URL`, `COMPANY_*`. Billing page + Checkout fully rewritten — inline billing-profile form with VIES verify button.
