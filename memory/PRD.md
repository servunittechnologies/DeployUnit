# DeployUnit — PRD

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
- `.env.example` auto-import from GitHub repo on first deploy.
- Multi-region deployment selection.
- Coupon system on checkout.

## Test credentials
- Admin: `admin@deployunit.com` / `admin123`
- Demo: `demo@deployunit.com` / `demo1234`

## Changelog
- **2026-05-12 — Auto-SSL trigger via `force_https` flag (Coolify v4)**
  - **Symptoom na vorige fix**: Traefik-route werkte na force-redeploy (route OK, app bereikbaar), maar **Let's Encrypt cert werd niet uitgegeven** → browser bleef "TRAEFIK DEFAULT CERT" laten zien. Voorzijde leek werkend, maar HTTPS gaf certwaarschuwing.
  - **Root cause**: Coolify v4 vereist een **expliciete `force_https: true` flag** in de PATCH body om de Traefik labels te voorzien van `tls.certresolver=letsencrypt` + HTTP→HTTPS redirect. Zonder die flag genereert Coolify alleen een HTTP-router en wordt het cert nooit aangevraagd. Bron: [coollabsio/coolify#1880](https://github.com/coollabsio/coolify/issues/1880).
  - **Fix** — `clients/coolify.py::set_domains()`: stuurt nu ZOWEL `force_https:true` ALS `is_https_forced:true` (Coolify v4.x heeft twee veldnamen voor hetzelfde concept tussen patchversies — beide tegelijk sturen werkt op alle subversies). Het effect:
    1. `domains` met `https://` prefix → Traefik krijgt HTTPS-router
    2. `force_https:true` → Traefik labels krijgen `tls.certresolver=letsencrypt` → cert wordt aangevraagd
    3. HTTP-router krijgt automatisch een 308-redirect naar HTTPS
  - **Update flow**: zowel de create flow (`routers/apps.py`) als de healer (`services/routing_healer.py`) gebruiken nu `set_domains()` → SSL wordt voortaan altijd auto-aangevraagd voor elke nieuwe + elke gehealde app.
  - **Inspect endpoint uitgebreid**: `/api/admin/routing/inspect?fqdn=...` toont nu ook `force_https` + `is_https_forced` + `redirect` velden zodat in één call zichtbaar is of de flags correct gezet zijn.
  - **Required infra-check** (eenmalig, in Coolify UI op de server zelf): Settings → Servers → [your server] → Proxy → "Generate Let's Encrypt SSL" moet AAN staan. Als dit uit staat zal NIETS van bovenstaande werken — Traefik heeft dan geen ACME-resolver geconfigureerd. Dit is de enige stap die op server-niveau moet en niet via de DeployUnit API te zetten is.
  - **Resultaat**: na de volgende redeploy van productie worden alle nieuwe deploys + elke "Heal routing"-actie voorzien van:
    - HTTPS-router in Traefik (✓)
    - Let's Encrypt cert resolver (✓ — `force_https` flag)
    - 308-redirect HTTP → HTTPS (✓ — automatisch)
    - Cert wordt uitgegeven in 30-90s na deploy (✓ — ACME HTTP-01 challenge)


- **2026-05-12 — Routing healer v2: ECHTE fix na Coolify v4 quirk + probe blind spot**
  - **Bug 1 — fout PATCH veld**: `coolify.update_application({fqdn: "https://..."})` werd door Coolify v4 **stilletjes genegeerd**. Coolify v4 verwacht **`domains`** (komma-gescheiden, met `https://` prefix), zie [coollabsio/coolify#6281](https://github.com/coollabsio/coolify/issues/6281). De PATCH gaf 200 OK terug maar `fqdn` werd niet opgeslagen → Traefik kreeg nooit een route. Fix: nieuwe `coolify.set_domains(uuid, fqdn)` helper + auto-vertaling `{fqdn}` → `{domains}` in `update_application` voor backwards-compat.
  - **Bug 2 — restart regenereert geen labels**: Coolify slaat Traefik labels op als base64-encoded blob in de DB (`custom_labels`). Een container-restart leest de OUDE labels van de DB → Traefik blijft de oude (lege) route serveren. Pas een **`deploy(force=true)`** triggert Coolify om labels te regenereren vanuit de nieuwe `domains`. Healer doet nu force-redeploy i.p.v. restart.
  - **Bug 3 — `restart` endpoint method**: Coolify v4 wil **POST** voor `/applications/{uuid}/restart` (oudere versies accepteerden GET). Geüpdatet in `clients/coolify.py`.
  - **Bug 4 — probe blind spot**: oude `_probe_traefik_route` keek alleen naar (a) TLS default cert via httpx-internals (onbetrouwbaar) en (b) 404+Traefik-body. Maar 503/502/504 (backend down, route exists) werd geclassificeerd als `routed:true` → de healer triggerde nooit op echte productie cases. Probe herschreven met:
    - Directe `asyncio.open_connection` TLS handshake (geen httpx internals)
    - 502/503/504 → `reason: backend_down`
    - HTTP fallback wanneer HTTPS faalt
    - Probe getest tegen live productie URL `8rrwaumc.deployunit.app` → correct `routed:false, reason:no_route, status:404`
  - **Nieuwe diagnostic endpoint** `GET /api/admin/routing/inspect?fqdn=...`: returnt DNS resolution + Traefik probe + DeployUnit app + pool entry + Coolify raw record (fqdn/domains/status/is_running/custom_labels_set). In één call zie je waar de keten breekt.
  - **Heal flow**: `heal_app()` keert nu direct terug na het triggeren van de force-redeploy (geen 6s sleep meer want Coolify build duurt 30-90s). Response bevat `eta_seconds:60` + duidelijke message. Pool widget polling (15s) detecteert auto wanneer probe routed:true wordt.
  - **Files**: `clients/coolify.py` (set_domains + auto-vertaling + restart POST), `services/routing_healer.py` (probe rewrite + force-redeploy strategie), `routers/admin.py` (+`/admin/routing/inspect` endpoint), `routers/apps.py` (create flow gebruikt set_domains).
  - **Voor de gebruiker**: na "Save to GitHub" + redeploy productie zal de scheduler binnen 2 min `8rrwaumc.deployunit.app` (en alle andere broken URLs) detecteren, force-redeployen en in 30-90s zijn ze live met Let's Encrypt SSL.


- **2026-05-12 — Routing self-healer: permanent fix voor "no available server" / no SSL (11/11 backend green)**
  - **Probleem in productie**: `8rrwaumc.deployunit.app` (een geclaimde pool-URL) toonde `404 page not found` (Traefik) + `CN=TRAEFIK DEFAULT CERT`. DNS resolveerde correct naar `149.12.246.205`, poorten 80/443 open, Coolify draait — **Traefik miste alleen de route-labels op de container**. Klassiek symptoom: `coolify.update_application({fqdn})` PATCHt het veld in Coolify maar de live container heeft de docker-labels niet bijgewerkt (labels worden enkel bij container-start gelezen).
  - **Permanente fix** — nieuwe `services/routing_healer.py`:
    - `_probe_traefik_route(fqdn)` detecteert het symptoom via TLS-handshake peek (`CN=TRAEFIK DEFAULT CERT`) + body-fingerprint (`404 page not found`). Returns `{routed, reason}`.
    - `_push_fqdn_and_restart(app)` doet PATCH+verify+restart: PATCH `{fqdn}` → GET om te bevestigen dat het landde → `coolify.restart()` zodat de container met de juiste Traefik-labels opnieuw start (de stap die het EIGENLIJK fixt).
    - `heal_app(app_id)` public entrypoint voor de admin-knop: probe → heal → 6s wachten → re-probe.
    - `cleanup_orphan_pool_entries()` reapt DNS records van apps die verwijderd zijn (DNS bestaat, geen app meer).
    - `routing_healer_tick()` scheduler-job: walks alle `status:live` + `cloudflare_fqdn` apps (cap 25/tick), probet parallel, healt sequentieel om Coolify rate-limits te respecteren. 3-retries/uur cap met cooldown.
  - **Hardening van create-pad** (`routers/apps.py`): na `update_application({fqdn})` doet de code nu een directe `get_application()` om te VERIFIËREN dat de FQDN landde, met re-PATCH bij mismatch. Coolify v4 200't soms op rejected fields stilletjes — dit vangt het.
  - **Scheduler** (`server.py`): `routing_healer_tick` elke 2 min, `max_instances=1` zodat de healer nooit overlappende ticks heeft.
  - **Admin endpoints**:
    - `POST /api/admin/apps/{id}/heal-routing` — handmatige fix voor één app
    - `POST /api/admin/routing-healer/run` — full sweep nu
  - **Admin UI**: nieuwe **"Heal routing"** knop (groen, emerald accent) naast "Refill now" in de SubdomainPoolWidget. Toast feedback: `Healer fixed N apps · released M orphan DNS records` / `All N apps routing OK` / `No live apps with managed FQDNs to check`.
  - **Tests**: 11/11 pytest groen (`/app/backend/tests/test_routing_healer.py`), RBAC (401/403/200), graceful zonder Cloudflare, geseede fake app met fake coolify-UUID crasht niet, regression op pool endpoints. UI integration getest in /app/admin → Platform Domain tab.
  - **Resultaat voor user**: zodra hij de "Heal routing" knop drukt op productie, scant het systeem alle apps met een managed FQDN, ontdekt `8rrwaumc.deployunit.app` als broken (default cert), herhaalt FQDN-push + container-restart, en Traefik heeft binnen 6s de juiste route + Let's Encrypt-cert flow begint. Vanaf nu loopt dezelfde check ELKE 2 MINUTEN automatisch in de achtergrond — dit kan dus nooit meer kapot blijven.
  - **Files**: nieuw `services/routing_healer.py`; aangepast `routers/admin.py` (+2 endpoints), `routers/apps.py` (FQDN-verify), `server.py` (scheduler), `pages/dashboard/Admin.jsx` (Heal-knop).


- **2026-05-12 — Pre-warmed Cloudflare DNS pool (Instant URLs P0 COMPLETE — 13/13 backend, UI testids green)**
  - **Probleem**: Nieuw aangemaakte apps kregen een random `{slug}.deployunit.app` toegewezen, maar het Cloudflare DNS-record was nét aangemaakt → resolvers wereldwijd hadden de record nog niet → eerste paar minuten resulteerde elke klik op de app-URL in een dode link of NXDOMAIN.
  - **Fix** — `services/subdomains.py`: nieuwe collection `cloudflare_subdomain_pool` met N **pre-aangemaakte** DNS records. Bij app-creatie doet `provision_subdomain(app)` een atomic `find_one_and_update({status:"free"}, ...)` (FIFO, oudste eerst → meest gepropageerd) en heeft de gebruiker een URL die wereldwijd al resolvet vanaf seconde 0. Pool-empty fallback maakt on-demand een record (degraded — propagatie nodig).
  - **Scheduler** (`server.py`): `refill_pool` job elke 3 min houdt de pool op target. Initial fill bij lifespan startup via `asyncio.create_task` zodat de eerste deploy na een restart niet hoeft te wachten.
  - **Admin tunable**: nieuw veld `subdomain_pool_target` in `platform_settings` (default 10, clamp `[0, 50]`). 0 schakelt de pool uit. Read-side clamp in `_pool_target()` zodat slechte input (999, -5) niet de Cloudflare-quota brandt. Pydantic `int | None` valideert type-strict → 422 op `"abc"`.
  - **Admin endpoints**:
    - `GET /api/admin/subdomain-pool` → `{free, claimed, target, hard_max:50, cloudflare_ready, zone_name, upcoming[]}` voor diagnostics
    - `POST /api/admin/subdomain-pool/refill` → handmatige refill, returns `{added, ...stats}`
  - **Frontend** (`pages/dashboard/Admin.jsx`): nieuwe `SubdomainPoolWidget` sectie in Platform Domain tab — 3 KPI cards (free/target met progress bar, claimed counter, health pill), target-input (0–50), "Refill now" knop (disabled als `cloudflare_ready=false`), live "Next in line" FIFO preview van komende 5 free FQDNs. Polls elke 15s. Toast feedback op refill (success met aantal toegevoegd, error als CF niet geconfigureerd, info als pool al vol).
  - **Graceful degradation**: in preview env (geen CF token) blijft alles werken — refill is no-op, widget toont "Cloudflare not configured", apps kunnen alsnog deployed worden zonder pooled URL.
  - **Tests**: 13/13 backend pytest green (`/app/backend/tests/test_subdomain_pool.py`), 401/403/200 RBAC, clamp behaviour, persistence, regression op andere admin endpoints. Frontend testids `admin-subdomain-pool`, `pool-free-count`, `pool-health-label`, `admin-pool-target`, `admin-pool-refill` geverifieerd. Pool target persistentie via reload bevestigd.
  - **Files**: `services/subdomains.py` (rewrite — pool collection, FIFO claim, admin-tunable target), `routers/admin.py` (+`subdomain_pool_target` field, +2 endpoints), `server.py` (refill_pool scheduler + initial fill), `pages/dashboard/Admin.jsx` (SubdomainPoolWidget component).


- **2026-05-12 — Mobile-friendly nav + dashboard drawer**
  - **Marketing**: `MarketingNav` (About/Contact/Support pages) en de eigen `Nav` op `Landing.jsx` hebben nu een hamburger-knop (`md:hidden`) die een fullscreen overlay-drawer opent met grote tap-targets (text-xl). Body-scroll lock terwijl open, auto-sluit op route-change, CTA "Deploy now" prominent onderaan in de drawer.
  - **Dashboard**: `DashboardLayout` heeft een hamburger-knop linksboven in de topbar (`lg:hidden`) die een slide-in drawer opent met de volledige zijbalk (workspace switcher + alle nav-items + admin-link). Backdrop-tap én elke nav-tap sluit de drawer automatisch. Sidebar `SidebarContent` is geëxtraheerd zodat dezelfde content op desktop én in de mobile drawer gebruikt wordt — één bron van waarheid.
  - **Topbar mobile fit**: search-box blijft `hidden md:flex`, CreditsPill `hidden md:inline-flex`, dus op iPhone-formaat (390px) zien gebruikers alleen hamburger + klein logo + bell + user-menu. Geen overflow.
  - **CSS**: nieuwe `@keyframes slide-in-left` in `index.css` voor de drawer-animatie (0.18s ease-out).
  - **E2E getest** (Playwright iPhone 13 emulatie): hamburger zichtbaar + drawer opent + nav-klik navigeert + drawer auto-sluit + backdrop-tap sluit — alle interacties groen.

- **2026-05-12 — GitHub OAuth: dynamic per-host redirect_uri**
  - **Bug**: `_redirect_uri()` en `_frontend_origin()` lazen statisch uit env-vars die de preview-URL bevatten. Op productie stuurde de OAuth-start GitHub dus naar de preview-callback, en de eindredirect ging naar het preview-domein. Op productie resulteerde dat in een Cloudflare 520.
  - **Fix** (`routers/github_oauth.py`): nieuwe `_request_origin(request)` leidt de origin af uit `X-Forwarded-Host`/`X-Forwarded-Proto`. `/start` slaat `origin` + `redirect_uri` op in `oauth_states`. `/callback` gebruikt de opgeslagen `redirect_uri` voor de token-exchange (GitHub vereist exacte match) en stuurt de gebruiker terug naar dezelfde origin. Werkt voor preview, productie én elk custom domein zonder env-wijziging.

- **2026-05-12 — Productie "Network Error" + Coolify 404-spam opgelost**
  - **Frontend `lib/api.js`**: backend-URL wordt nu runtime resolved via `window.location.origin` voor élk niet-localhost domein. Same-origin = geen CORS preflight nodig = geen "Network Error" meer.
  - **Backend `server.py`**: CORS gebruikt `allow_origin_regex=".*"` met credentials, zodat de ingress de request-Origin echoet ipv onbruikbare `*` wildcard.
  - **Workers `monitor.py`**: `sync_deployments` backfill-loop stempelt dode externe deployments nu eenmalig met `failure_summary` zodat ze uit de query-set vallen. Eind aan de oneindige 404-spam in productielogs.

- **2026-05-11 — Support Ticket System (P0 COMPLETE — 19/19 backend, frontend E2E green)**
  - **Backend `routers/tickets.py`**: full user CRUD (`POST/GET /api/tickets`, `GET /api/tickets/{id}`, `POST /api/tickets/{id}/messages`, `POST /api/tickets/{id}/close`) + admin endpoints (`GET /api/admin/tickets` with status/priority/q filters + pagination, `GET /api/admin/tickets/stats` aggregates open/awaiting_*/resolved/closed/needs_attention, `GET /api/admin/tickets/{id}`, `POST /api/admin/tickets/{id}/messages`, `PATCH /api/admin/tickets/{id}` for status+priority+category updates). RBAC: non-admins get 403 on all `/admin/tickets*` routes (explicit `_require_admin` guard, including defense-in-depth on `admin_add_message`). State machine: user reply flips status → `awaiting_support`; admin reply flips → `awaiting_user`; closed ticket replies return 409.
  - **Email notifications via MailerSend** (BackgroundTasks, fire-and-forget): new ticket → emails all platform admins; admin reply → emails ticket owner; user reply → emails admins (excluding the author if they're admin). All emails branded via shared `_BASE_CSS`/`_shell` chrome in `services/emails.py`. Gracefully skipped when MailerSend not configured.
  - **Frontend `/app/tickets`** (default Tickets page): list view with empty-state CTA, new-ticket form with subject+category+priority+message (min-10-char) validation, thread view with chat-style messages (Support replies styled in cyan with ★ tag), close action, status pill + priority tag legend. `useEffect(() => { if (!id) load(); }, [id])` ensures the list re-fetches when returning from a thread (fix for v1 list-stale bug).
  - **Frontend `DashboardLayout`**: new "Support" sidebar entry (LifeBuoy icon), positioned between Audit log and Roadmap.
  - **Frontend `Admin Console`**: new "Support tickets" tab — 4 KPI cards (needs attention / open / awaiting user / resolved total), status + priority + free-text search filters, sortable row list. Clicking a row opens the shared `TicketThread` component in admin mode (with user email/name header + Manage sidebar to edit status & priority in-place).
  - **MailerSend mocked**: real send fires when `platform_settings.mailersend_api_key_enc` is set; otherwise logged as `status='skipped'` in `notification_sends` collection — no exception thrown.

- **2026-05-11 — Real container metrics via agent (CPU/Mem/Disk/Network — live + history)**
  - **`services/metrics.py`**: agent-key auth (sha256-hashed in `platform_settings.metrics_agent`), `ingest_samples()` (resolves `coolify_app_uuid` → app), `downsample_and_gc()` (30s raw → 5m rollup after 24h, drop after 30d), `app_metrics_series(app, window)`.
  - **`routers/metrics.py`**: `POST /api/metrics/ingest` (X-Agent-Key auth), `GET/POST /api/admin/metrics/agent[/rotate]`, `GET /api/agent/install.sh` (public installer), `GET /api/agent/agent.py` (public python script), `GET /api/apps/{id}/metrics`.
  - **Metrics agent**: 60-lijns Python script in een `python:3.11-slim` docker-compose container met read-only `/var/run/docker.sock` mount. Filtert op `coolify.applicationId` label, berekent CPU%/Memory%/Network/Disk per 30s, POST naar DeployUnit.
  - **Frontend `AppMetricsCharts.jsx`**: 4 KPI tiles (CPU now, Memory now, Net in/out, Disk I/O) + 6 SVG sparklines (CPU%, Mem%, Net rx/tx, Disk read/write). Auto-refresh 30s. Falls back to "Install agent" CTA als geen samples.
  - **Frontend `AppAnalyticsPanel`**: metrics-section toegevoegd bovenaan, naast existing uptime/response/timeline.
  - **Admin → Integrations → Metrics agent**: statusbadge (live/stale/awaiting), last-sample-count, install-command met copy, "Generate/Rotate key" knop met one-time reveal.
  - **Scheduler**: nieuwe `downsample_and_gc` job elke uur. Geen kans op DB-bloat.
  - **Eindgebruiker-flow**: 1) Rotate key in Admin → 2) Run `curl … | bash` op Coolify VPS → 3) Paste key → 4) charts vullen binnen 30s.

- **2026-05-11 — Usage Analytics (Live + Historical) in Overview & Monitoring**
  - **App-level analytics** (`GET /api/apps/{id}/analytics?window=1h|24h|7d|30d`):
    - Uptime %, avg + p95 response time, # samples
    - Bucketed time-series (response_ms, uptime_pct) → SVG line chart
    - Status timeline (live/down/building windows) als horizontal coloured stripes
    - Deployments in window + status breakdown + total build minutes
    - Currently allocated resources (cpu/mem/storage + addon cost)
  - **Account-wide analytics** (`GET /api/account/analytics?window=30d`):
    - Totaal: apps_live / apps_total, CPU/memory/storage allocated, monthly resource cost, build minutes, deployments
    - Credit burn breakdown by `ref_type` (resource_addon, admin_adjustment, etc) + time-series
    - Per-app breakdown sorted by monthly cost
  - **Status sampler worker**: nieuwe `workers/monitor.status_sampler` scheduler (5 min interval) — snapshot van iedere app's status naar `app_status_samples`. Auto-GC voor entries ouder dan 31 dagen.
  - **Frontend `AppAnalyticsPanel`**: vervangt de oude Monitoring tab, KPI-tiles + custom SVG line chart + status timeline bar + allocated resources card. Auto-refresh elke 30s.
  - **Frontend `AccountAnalyticsPanel`**: gepland in Overview pagina, toont accountwide totalen + credit burn met visuele category bars.
  - **Transparant labelen**: omdat Coolify geen container-level CPU/memory stats exposeert, tonen we "allocated resources" (de gegarandeerde limit) i.p.v. een fake usage %. Wel exact gemeten: uptime probes, response times, build minutes, credit consumption.

- **2026-05-11 — Resources + Credit-billed Addons + DB↔App Connections (Iter13, 14/14 backend GREEN, 24/24 iter11 regression)**
  - **DB → App attach**: meerdere databases per app met user-editable env-var naam (`DATABASE_URL` default, A-Z0-9_ ge-clamped). Bij attach pusht DeployUnit de `connection_string` direct als env-var naar de build engine via `coolify.update_env`. Detach zet env-var leeg op de volgende deploy.
  - **Per-app resource limieten (HARD enforced)**: CPU/memory worden bij elke deploy via `coolify.update_application({limits_cpus, limits_memory, limits_memory_swap})` op de container gezet. Plan defaults (Free=0.25 vCPU/256MB/1GB, Pro=0.5/512MB/5GB, Agency=1/1GB/20GB) zijn alle admin-editable.
  - **Credit-based addons**: per app slidersaurus voor +vCPU/+MB RAM/+GB storage. Pricing in admin (100cr/0.5vCPU, 50cr/512MB, 25cr/5GB per maand). Bij upgrade pro-rated credit-charge, bij downgrade pro-rated refund. **Verificatie**: upgrade 150cr → onmiddellijke downgrade gaf 145cr refund (29 dagen ongebruikt).
  - **Monthly billing tick**: nieuwe `services.resources.charge_due_addons` hourly scheduler — apps met `monthly_resource_cost > 0` en `resource_addons_charged_at` ≥30 dagen oud krijgen de credit-charge. Bij ontoereikende credits: **auto-downgrade naar plan defaults + notification met `kind=resource_downgrade`**.
  - **Plan downgrade refund**: `services.resources.refund_plan_downgrade` berekent pro-rata ongebruikt deel van OLD plan price → terug naar credit wallet (1 credit ≈ €0.10). Geintegreerd in `routers/account.py::plan_checkout` voor free/hobby downgrades.
  - **Admin Resources & Limits tab** in `/app/admin`: editable plan-default tabel + 3 addon-pricing cards met €-equivalents + Save/Revert. `GET /api/admin/resource-defaults` levert built-in baseline voor revert.
  - **Bonus fix admin credits adjust**: `routers/admin_users.py::adjust_credits` schreef naar legacy `workspaces.credits_balance` — nu via `grant_credits`/`consume_credits` op `users.credits_balance` met correcte transaction log.
  - **API endpoints**: GET/PUT `/apps/{id}/resources`, GET `/apps/{id}/connections`, POST `/apps/{id}/connections`, DELETE `/apps/{id}/connections/{conn_id}`, GET/PUT `/admin/resource-config`, GET `/admin/resource-defaults`.

- **2026-05-11 — Logs UX overhaul + auto-heal voor verloren build-engine apps**
  - **ServUnit hersteld**: app stond op stale `coolify_app_uuid` (uitgewist op de build engine). Nieuwe `/api/apps/{id}/reinstall` endpoint maakt een verse Coolify-app aan met de opgeslagen `repo_url` + `branch`. Auto-heal in `redeploy()`: pre-flight `coolify.app_exists()` check, valt automatisch terug op het create-app pad als de UUID dood is.
  - **Heldere foutmeldingen**: pre-flight in `_coolify_deploy` detecteert private GitHub repos zonder OAuth-token en faalt FAST met "This is a private GitHub repo. Connect GitHub on your Account page…" — geen opaque Coolify "No such container" stacktrace meer.
  - **`probe_repo_visibility()` upgrade**: accepteert nu `token` argument zodat we GitHub rate-limits omzeilen en correct detecteren of een repo écht privé is.
  - **Nieuwe Coolify client methodes**: `_request_meta()` (data, status, error_text), `app_exists()` (404-check), `application_logs(uuid, lines)` (runtime container logs).
  - **Nieuwe API endpoints**:
    - `POST /api/apps/{id}/reinstall` — recreate build-engine app
    - `GET /api/apps/{id}/console-logs?lines=N` — runtime stdout/stderr met `reason=build_engine_missing` hint
  - **Frontend `BuildErrorPanel`** is nu pattern-aware: "private repo" → **Connect GitHub** CTA, "missing on build engine" → **Reinstall** CTA, "plan limit" → **Upgrade plan** CTA. Plus secundaire actions: redeploy, branch-hint, troubleshooting link.
  - **`AppDetail.jsx` upgrades**:
    - Nieuwe **Console tab**: live runtime logs viewer met 100/200/500/1000 lines, pause/resume, refresh, severity-coloring, 5s auto-poll.
    - Nieuwe **DeploymentRow component**: elke deployment-rij is uitklapbaar — klik → fetch volledige logs + parsed_logs met severity, failure_summary banner bovenaan voor failed deploys, "raw json" link.
    - Trigger-tag (`· REINSTALL`, `· auto-webhook`, etc.) in de branch-kolom.

- **2026-05-11 — Account vs Workspace settings split (Iter12, 18/18 backend GREEN)**
  - **Plan, credits & notifications zijn nu account-niveau** (één plan, één wallet, één meldingen-inbox per gebruiker — toegepast over alle workspaces die de gebruiker bezit).
  - **Nieuwe `/app/account` pagina** met sticky sectie-nav: Profile, Plan & usage (met grafische usage-bars + plan-grid), Credits wallet (balance, monthly grant, recent activity, koop-packs), Billing & invoices (profile + PDF lijst), Notification preferences (matrix events × kanalen), Security (password change).
  - **`/app/settings` strak gemaakt**: alleen workspace-zaken (name, type, members, audit-log link, danger-zone delete) + een "snapshot" tile met workspace-specifieke usage + verwijzing naar Account voor plan.
  - **Backend**:
    - Nieuw `routers/account.py` met 12 endpoints (`/account`, `/account/profile`, `/account/password`, `/account/plan{,/checkout,/cancel}`, `/account/credits{,/history,/packs,/checkout}`, `/account/billing{,/profile}`).
    - `services/account_migration.py` draait éénmalig bij startup: highest-plan-wins (demo+martijn → agency, admin → free), credits-balances gesummeerd, oudste `credits_period_start` overgenomen, billing-profile gekopieerd naar `users.billing_profile`.
    - `services/plans.py` heruitgevonden: `user_plan(user_id)` is bron, `workspace_plan(workspace_id)` lost op via `workspace.owner_id`; nieuw `account_usage(user_id)` voor totaal-aggregatie; `assert_limit(workspace_id, resource)` checkt nu tegen account-wide totaal.
    - `services/credits.py` herschreven: wallet leeft op `users.credits_balance`. Oude callers (`consume_credits(workspace_id, ...)`) blijven werken via een `_resolve_user_id` shim die workspace-id naar owner-user resolved. `credit_transactions` rijen krijgen nu `user_id` + optionele `workspace_id` context.
    - `routers/billing.py` Mollie webhook ondersteunt `meta.user_id` (account-level checkout) naast `meta.workspace_id` (legacy).
    - 2 nano-fixes uit code review: downgrade naar "hobby" zet nu correct `plan="hobby"` (was hardcoded "free"); payments filter gebruikt `$exists: True` om legacy rijen zonder plan-veld te skippen.
  - **Frontend**:
    - `DashboardLayout`: sidebar split — workspace-NAV bovenaan eindigt met "Workspace" (renamed from Settings); onderaan "Personal" sectie met "Account". User-menu (top-right avatar) heeft Account + Workspace links.
    - `Account.jsx` — 6 secties met sticky in-page nav, plan-grid met Upgrade/Switch-down knoppen, credit-pack koop-tiles, transaction-history tabel, billing-profile editor met EU-country select, full notif-matrix met Slack/Discord test-knoppen.
  - **Migration data verified**: demo plan=agency credits=10, admin plan=free, martijn plan=agency. NL billing profile op demo opnieuw geladen.

- **2026-05-11 — Workspace Settings polish + watchdog hardening (Fork verify pass)**
  - **Fix — Settings page data mapping**: `Settings.jsx` las `wsUsage.plan` als string en `wsUsage.apps_used`/`credits_balance`/`databases_used` als platte velden, maar de API geeft `{plan:{...}, usage:{apps,domains,databases,team}, credits:{balance,monthly_grant,...}}`. Frontend toonde daardoor altijd "0 apps", "0 credits", `[object Object]` voor plan, en de Delete-warning zag nooit databases. Frontend nu correct gemapt; plan-card toont {plan.name, €price/mo, apps/limit, credits +monthly_grant/mo, members/limit}.
  - **Fix — `services/plans.py::workspace_usage`**: (a) added `databases` count so the Delete warning enumerates real DB risk, (b) fixed members double-count bug (`members_used = 1 + member_rows` was wrong because the owner is already a workspace_members row). Now `members_used = max(member_rows, 1)`. `usage.team` now matches `members.length`.
  - **Fix — `workers/monitor.py::deployment_watchdog`**: was retrying `coolify.deploy()` forever (every 30s) when the build-engine app had been deleted out-of-band, spamming logs. Now does a pre-flight `coolify.get_application()` and marks deployment failed if the app is gone, plus a hard cap of 5 retries before giving up. Cleaned 2 stale stuck deployments from the demo DB.
  - **Polish — `routers/workspaces.py::delete_workspace`**: audit row now carries `workspace_id` (was None) for consistency with `workspace.update`.
  - **Verified E2E (Playwright + curl)**: workspace last-guard (400), force=false+resources (409), empty delete (200), rename via PUT, prompt-cancel/wrong-name/correct-name flows, auto-switch to next workspace on delete. iter11 suite 24/24 GREEN, no regressions.

- **2026-05-11 — Sprint 5: 5 P2 features (Iter10, 31/31 GREEN after one-line fix)**
  - **🔍 Audit log**: `services/audit.py` fire-and-forget logger + `routers/audit.py` workspace-scoped + platform-wide read APIs. Wired into auth.login, app.{create,delete}, cron.{create,update,delete}, database.{create,start,stop,delete,reveal_connection}. UI: new `/app/audit` page with action filter dropdown, cursor pagination, expandable meta JSON.
  - **💬 Slack/Discord alert channels**: `clients/chat_webhooks.py` (Slack attachment + Discord embed, color-coded per event type); `services/notifications_sms.py` extended with slack/discord dispatch branches; `routers/notifications.py` adds `slack_webhook_url` / `discord_webhook_url` fields + URL prefix validation. Settings.jsx UI: matrix grows to events × 5 channels, 2 webhook URL inputs, Test Slack / Test Discord buttons. Fix toegepast post-test: `SUPPORTED_CHANNELS` is nu single source of truth in `notifications_sms.py`, available-channels iterator omvat alle 5 (was alleen sms/whatsapp/email — slack/discord skipped-no-url branch was onbereikbaar).
  - **⏰ Cron tasks**: `routers/cron.py` CRUD op `db.cron_jobs` met 5-field cron regex validatie, best-effort sync naar Coolify scheduled-tasks API. Coolify client uitgebreid met `{list,create,update,delete}_scheduled_task`. UI: AppDetail → Settings krijgt "Scheduled jobs" sectie met inline create/edit form + cron expression hints.
  - **🗄️ Postgres/Redis as-a-service**: `routers/databases.py` ondersteunt 5 engines (postgresql/redis/mysql/mariadb/mongodb), Coolify client uitgebreid met `{create,get,start,stop,delete}_database`. Connection strings Fernet-encrypted at rest, revealable via `/databases/{id}/reveal` (audit-logged). Nieuwe `/app/databases` pagina met type select, version field, status badges (provisioning/running/stopped), masked-reveal-copy flow.
  - **🔀 PR Preview Deploys**: `services/pr_previews.py` + `routers/pr_previews.py`. GitHub webhook subscribet nu op `pull_request` events (push + pull_request). `opened|synchronize|reopened` → child ephemeral app op `{parent_slug}-pr-{number}.{zone}` (auto-subdomain geërfd), `is_pr_preview=true`. `closed` → child app + Cloudflare DNS + Coolify resources opgeruimd. AppDetail → Settings krijgt "PR Preview deploys" lijst met status badges + manual teardown.
  - **Files touched**: nieuw — `services/{audit,pr_previews}.py`, `routers/{audit,cron,databases,pr_previews}.py`, `clients/chat_webhooks.py`, `pages/dashboard/{AuditLog,Databases}.jsx`. Aangepast — `server.py`, `services/notifications_sms.py`, `routers/{auth,apps,notifications,webhooks}.py`, `services/github_webhooks.py`, `clients/coolify.py`, `App.js`, `components/DashboardLayout.jsx`, `pages/dashboard/{Settings,AppDetail}.jsx`.

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
  - **2026-05-11 — About / Contact / Support pages + drop "white-label" claim**
  - **3 new marketing pages** live at `/about`, `/contact`, `/support`. All wrap a shared `<MarketingLayout>` with synced `MarketingNav` (Features · Compare · About · Pricing · Support · Contact · Login) and 3-column footer (Product · Resources · Company) — links between pages now navigate consistently.
  - **About** (`pages/About.jsx`): hero "Built by people who ship for a living", 4-stat strip (EU · 70%+ renewable · 240+ agencies · 99.99% uptime), 4-value grid (EU-first · Sustainability as a metric · Built for agencies · Boringly transparent), founding-timeline rail (`#sustainability` deep-anchor still works from old footer links), Team Trees commitment block, dual-CTA bottom.
  - **Contact** (`pages/Contact.jsx`): hero "Talk to a human. Quickly.", left column = 4 contact tiles (email · ServUnit Technologies BV office · EU regions · phone) + green response-time pill (`~4h sales · ≤24h support`), right column = full form with 5 message-kind pills (General / Sales / Support / Partnership / Press), name + email + company + subject + 5-row message textarea, submits to `POST /api/contact`. Success state replaces the form with a confirmation tile.
  - **Support** (`pages/Support.jsx`): hero "How can we help?", live FAQ search box (filters in-page), 6 topic cards (Getting started · Deploys & builds · Domains & DNS · Billing & credits · Security & teams · Troubleshooting), 8-item accordion FAQ, 3 quick-links (Status · Email · About), bottom "Open a ticket" CTA strip linking to /contact.
  - **Backend `/api/contact`** added in `routers/contact.py`: public POST with name + email + company + kind + subject + message, IP-rate-limited (5/hour), saved to `contact_messages` collection with `status="new"`, source IP, UA, optional `user_id` if logged in. Admin-only `GET /api/admin/contact` returns the inbox. E2E verified — returns `{"ok": true, "id": ...}` on valid submission.
  - **All customer-facing "white-label" wording removed**:
    - Hero body copy: `Zero config, full white-label, EU-hosted` → `Zero config, fully managed, EU-hosted`
    - Hero pill: `100% white-label` → `first-party data`
    - Comparison-table row: `100% white-label` → `Agency-grade multi-tenant`
    - Roadmap feature name: `White-label client reports` → `Branded client reports` (both in `Landing.jsx` roadmap teaser, `pages/dashboard/Roadmap.jsx`, and `routers/roadmap.py` `KNOWN_FEATURES`)
  - **Note on internals**: `services/whitelabel.py` (Coolify log sanitizer) is intentionally **kept** — it's an internal scrubber that strips Coolify/WHMCS/Twilio mentions from API responses + logs before they reach customer UIs. The filename is internal; nothing of it is user-visible.


  - **New `/status` route** — fully public (no auth), auto-refreshes every 30 seconds in the browser. Live at the same domain (no separate subdomain yet) and linked from the landing-page footer under "Resources".
  - **Background ping orchestrator**: APScheduler `status_ping_tick` runs every 60s, concurrently pings all 10 components via `asyncio.gather`, persists `status_pings` rows (component_id, ts, day, ok, latency_ms, error). 95-day retention with auto-GC.
  - **10 components monitored** in 3 groups:
    - **Core**: DeployUnit API (self-test) · Database (Mongo ping) · Web analytics (`tracker.js` GET) · Metrics ingest (`install.sh` GET)
    - **Infrastructure**: Coolify (reads `platform_settings.coolify_base_url` → `/api/health`; skipped if not configured)
    - **Integrations**: GitHub (`api.github.com/zen`) · Cloudflare (`api.cloudflare.com/client/v4/`) · Mollie (`api.mollie.com/v2/`) · MailerSend (`api.mailersend.com/v1/`) · Twilio (`status.twilio.com/api/v2/status.json`)
  - **Auto-incident logic**: after 2 consecutive failed pings on the same component, a `status_incidents` row is auto-opened with severity `major` (for api/db/tracker) or `minor` (other). First successful ping auto-resolves the incident with `resolved_at`. No flapping.
  - **State derivation**: latest ping → `operational` (<1500 ms latency) / `degraded` (≥1500 ms or 4xx) / `down` (5xx or exception). Overall page state = worst component state.
  - **Public endpoints** (no auth): `GET /api/status` (summary + components + open + recent incidents), `GET /api/status/components` (flat list), `GET /api/status/history?days=90` (daily uptime buckets per component for the histogram).
  - **Frontend** (`pages/Status.jsx`): cyberpunk-dark layout consistent with the dashboard — animated pulse-dot state indicators, latency in ms, **90-day uptime histogram** (each day = a colored vertical bar, green ≥99.5%, yellow ≥95%, red below, zinc-900 for no-data), rolling uptime % per component, per-group section headers (Core · Infrastructure · Integrations). Active + recently-resolved incidents grid. Refresh button + auto-poll every 30s.
  - **Verified E2E**: one ping cycle ran 10/10 components green, `/api/status` returns full operational tree, browser screenshots confirm rendering.


  - **Density compressed from 11 → 5 cards** by introducing internal tab switches inside each big card. Same surface, ~50% less vertical scroll.
  - **Card 1 · Live observability** (2-col span): tabbed switcher between **Metrics** / **PageSpeed** / **Alerts** — all three reused from the previous individual cards, lazy-mounted on tab change.
  - **Card 2 · Web analytics** (1-col): tabbed **Visitors** / **Heatmap** (with `soon` badge). The new **HeatmapPreview** is a fake-page wireframe (header dots + content blocks) overlaid with 6 pulsing radial-gradient heat blobs (red/orange/yellow/green) using `mix-blend-mode: screen` — looks exactly like a real heatmap export. Bottom-left legend: `3 hot · 1 mid · 1 cool`.
  - **Card 3 · Build pipeline**: cycles through 5 phases (`QUEUED → CLONING → BUILDING → DEPLOYING → LIVE`) every 1.8s with progress bar, step indicators with cyan glow on active, framework-chip strip that lights up when "BUILDING".
  - **Card 4 · Agency workspaces**: unchanged interactive workspace switcher.
  - **Card 5 · Audit & schedule**: combined cron toggles + live audit log feed in one card.
  - **Below the bento**: dense "Also in the box" strip (6 capabilities in a single horizontal row, no boxes, just icon + label) — replaces the 6 small bordered cards. Saves another 200px of vertical space.
  - **Reusable `TabbedCard` primitive** added — mono-uppercase tab buttons, cyan underline on active, animated content swap with `motion.div` keyed on active tab id.


  - Every bento feature card now feels "alive" — continuous animations + on-click interactivity.
  - **MetricsGraphMock**: `setInterval` ticks every 1.6s, shifts the time-series and appends a new randomised CPU/MEM point. Header shows `● live · 1.6s tick · CPU 22% MEM 64%` (real-time). Hover pauses the loop with a `paused` badge.
  - **PageSpeedGauge**: added "↺ Re-run audit" button that resets to 0 and re-animates to a fresh random target (89-99). `isAnimationActive={false}` on Line for snappy real-time feel.
  - **VisitorMapMock**: dots randomly fade in/out every 0.9s, visitor count tabular-nums increments stochastically. Hover scales individual dots; `● live` indicator top-right.
  - **AlertsMock**: pool of 7 alerts; new one prepends to the top every 3.5s, list capped at 3, oldest scrolls out. Fresh timestamp on each tick.
  - **WorkspaceSwitcherMock**: each row is a `<button>` — click switches active workspace, dot animates `scale: 1.2` with cyan glow, header live-updates to that workspace's `deploys / 30d` count.
  - **BentoCard wrapper**: hover lifts `y: -3` + brand-tinted box-shadow glow + cyan border. Background blob breathes continuously (`scale + opacity` loop, 8s).
  - **Small cards** also got interactivity: **IlluAudit** prepends a new event every 4.5s, **IlluCron** each row is now a clickable toggle pill (clicked rows show `paused` + line-through + on/off switch knob slides).
  - Shared `nowMin()` helper produces fresh `HH:MM` timestamps so every live tick has a current-clock time.


  - **Green-energy claim updated** to honest "70%+ renewable today. Climbing every day." (was "100% wind & solar"). Body copy reworked to emphasise quarterly improvement & no carbon-offset accounting. Stat grid updated: `70%+ renewable today · ↑ climbing daily · EU datacenters · ISO 14001 partners`. Circular badge reads "Carbon Conscious by default" (was "Carbon Neutral").
  - **Team Trees partnership block** added under the Sustainability section: emerald gradient panel with three columns — (1) animated leaf badge "Partner · Team Trees · 1 deploy = 1 tree.", (2) body copy linking to `teamtrees.org`, (3) live-counting tree counter that climbs 0→1,247 on viewport (cubic easing). Decorative SVG tree-grove sits in the bottom-right. Pulsing emerald dot on the leaf icon for life.
  - **Small feature tiles** got their own micro-illustrations matching the bento style: PR previews → SVG main+branch git graph with `pr-42 live` badge, Managed databases → status rows for postgres/redis/mysql attachments, Custom domains+DNS → A/CNAME/MX record stub with TLS lock, Audit log → timestamped event rows, Resource limits → 3 animated progress bars (vCPU/RAM/Disk), Custom cron → 3 cron-expression rows with last-run timestamps. All animated, all first-party.
  - **Tech note**: tree-counter uses `useInView` + `requestAnimationFrame`; counter target wired as constant (`TARGET_TREES = 1247`) — easy swap for real `/api/sustainability/trees-planted` count later if wired to app deploys.


  - **Goal**: rebuild marketing site so "de SaaS zichzelf verkoopt" — show real features that actually exist, comparison vs competitors, green-energy USP, lots of motion, terminal-cyberpunk aesthetic.
  - **Design blueprint** generated by `design_agent_full_stack` and saved to `/app/design_guidelines.json` — strict dark/terminal with cyan brand + emerald green-USP accent, sharp `rounded-none` edges, Outfit display + JetBrains Mono accents, bento grid for features, no rounded corners.
  - **Page structure** (in order, all animated, scroll-triggered staggers):
    1. **Sticky nav** with backdrop-blur, brand logo, Features/Compare/Green/Pricing/Login + Deploy-now CTA
    2. **Hero** — animated split layout: left = "Deploy anything. Faster. Greener." H1 with cyan+emerald accents, EU-hosted/green/GDPR/white-label mono pills, primary + outline CTAs · right = animated terminal (`HeroTerminal`) streaming a realistic 8-line deploy log (`deployunit deploy --repo servunit/web → … → ✓ 100% green energy`) over a `ConstellationCanvas` background.
    3. **Logo strip** — auto-detected frameworks (Next.js 14 · Node · Bun · TS · Postgres · Redis · Docker · Tailwind · Prisma · Nixpacks).
    4. **How it works** — 3-step grid (Connect GitHub · Auto-detect stack · Ship + observe). Each step has its own live mini-animation: GitHub sync pill, framework-tag stagger reveal, Recharts CPU sparkline drawing in.
    5. **Features bento** — 5 big tiles + 6 small capability tiles, all with REAL DeployUnit data viz:
       - **Live container metrics** (2-col span) → Recharts CPU+MEM dual-line chart (cyan + emerald) drawing on scroll
       - **Google PageSpeed** → animated SVG ring gauge spinning to score 98 + Core Web Vitals breakdown
       - **Cookieless analytics** → grid-pattern visitor "dot map" with 15 cyan dots animating in
       - **Alerts everywhere** → Slack/Discord/SMS message rows sliding in
       - **Agency multi-tenant** → workspace switcher mock with 4 customer workspaces
       - 6 small tiles: PR previews · Managed databases · Custom domains+DNS · Audit log+RBAC · Per-app resource limits · Custom cron tasks
    6. **Comparison table** — DeployUnit vs Vercel vs Render vs Coolify (DIY) on 10 capabilities. DeployUnit column highlighted in cyan-950 with cyan border. Lucide check/x icons, "partial"/"self-host"/"DIY" mono labels for nuance. Row stagger reveal.
    7. **Green Energy spotlight** — full-bleed unsplash wind-turbine bg with emerald overlay + black gradient, "100% wind & solar powered" massive H2 (emerald accent), 4-stat grid (100% renewable · 0g CO₂ · EU-only · ISO 14001), rotating Wind icon "Carbon Neutral by default" circular badge on right, 14 floating emerald particles animating upward continuously.
    8. **Roadmap teaser** — 8 coming-soon tiles (dashed borders, Lucide icons, "SOON" mono labels) linking to /login → /app/roadmap.
    9. **Stats marquee** — infinite-scroll mono ticker (1.2M deploys · 99.99% uptime · 47ms response · 0g CO₂ · EU regions · 14-day money back · From €9/mo · 240+ agencies).
    10. **Final CTA** — "Stop managing infrastructure. Start building." over second `ConstellationCanvas` field with primary + outline buttons.
    11. **Footer** — 4-column grid with green-energy + GDPR mono pills, "Crafted in the EU", "Built on wind & solar".
  - **Motion budget**: Framer Motion scroll-triggered fade-up + stagger throughout. Custom keyframe animations for terminal, particles, gauge, dot-map, marquee. Respects `prefers-reduced-motion`.
  - **No video files** — every "video-like" demo is CSS/SVG/Recharts on a loop.


- **2026-05-11 — Roadmap v2: 8 features + category navigation**
  - **Added 4 new high-value coming-soon features** based on competitive-differentiation brainstorm: **Database branching** (Neon-style per-PR snapshots), **AI Code Co-pilot** (GPT-5.2-powered context-aware assistant in console), **Visual deploy diffs** (auto-screenshot + side-by-side per-page), **White-label client reports** (auto-emailed branded PDFs for agencies). Roadmap now totals 8 features.
  - **Page redesign for density**: replaced 2-col mega-cards with a 3-col grid of compact cards. Hero now shows live `total waiting` counter on the right. New **category tab bar** filters: All / Analytics & Insights / Developer experience / Business tools / Infrastructure with per-category counts. When "All" selected, features grouped by category section with header dividers.
  - **Compact card spec**: 5px padding, brand icon tile, "soon" badge top-right, 1-line tagline, 3 bullets max, inline email + `Notify` button on a single row. Hover border lights up brand color.
  - **Backend**: `KNOWN_FEATURES` expanded to `heatmaps · branching · copilot · visualdiff · api · reports · mailserver · dns`. Idempotent waitlist signup logic unchanged.


- **2026-05-11 — Clarity removed + public Roadmap with waitlist signups**
  - **Clarity fully removed** from code: `clarity_project_id` field gone from `PlatformSettingsUpdate`, `services/analytics.get_config` & `routers/analytics.get_app_analytics_config` simplified back to first-party only (snippet has no `data-clarity`, no `clarity_deeplink`, no `HEATMAPS_FEATURE_LIVE` flag, no `set_clarity_project` helper). Cleared the leftover `clarity_project_id` value from `platform_settings` document. Admin → Integrations → "Heatmaps & session recordings" section gone.
  - **New `/app/roadmap` page**: beautiful "What we're shipping next" grid with 4 coming-soon features — Native heatmaps & session replays · Mailserver hosting · DNS Manager · Developers API. Each card: gradient hover backdrop, grid texture, brand-themed icon tile, tagline, rich body copy, 5 feature bullets, **waitlist email signup** (auto-filled with the logged-in user's email when available), live "N developers waiting" counter, "coming soon" badge.
  - **Sidebar**: new "Roadmap" entry (Sparkles icon + brand-themed "soon" badge) inserted between Audit log and Settings.
  - **Backend**: new `routers/roadmap.py`. Endpoints — `GET /api/roadmap/features` (public — labels + waitlist counts), `POST /api/roadmap/waitlist` (public, idempotent on email+feature, captures user_id if logged in + source_ip), `GET /api/admin/roadmap/waitlist` (admin-only, grouped by feature with full export). Whitelist of `KNOWN_FEATURES = {heatmaps, mailserver, dns, api}` keeps the schema stable.
  - **Verified**: E2E via curl — features list, signup, idempotent re-signup (`already_signed_up: true`), counter increments, admin endpoint returns grouped rows. UI screenshot confirms layout renders cleanly.


- **2026-05-11 — Heatmaps: hold + coming-soon white-label**
  - **Pivot**: Customer-facing Heatmaps is now a "coming soon" feature, fully white-label, zero third-party leaks. Native engine (rrweb session-replay + canvas click heatmap on auto-captured page screenshots) is on the roadmap as the next big web-analytics ship.
  - **Backend**: new `HEATMAPS_FEATURE_LIVE = False` flag in `routers/analytics.py`. While `False`: `data-clarity` is NOT injected into customer snippets, no `clarity_deeplink` is emitted, customer's HTML stays 100% first-party. Flipping to `True` re-enables the auto-injection without further code changes.
  - **Customer UI**: `HeatmapsPane` replaced with a polished "coming soon" splash — grid backdrop, brand-glow blob, 3 feature cards (Click heatmaps · Session replays · Rage & dead clicks), disabled waitlist button "You're on the waitlist · shipping next · all Pro & Agency apps unlock automatically". Sub-tab navigation also shows a `soon` badge.
  - **Admin UI**: Clarity project-id field still works but now labelled "Reserved · admin only · coming soon"; status pill switches from `not configured` → `reserved · not yet live`. Clear note "Visible to customers: No (waitlist UI only)".
  - **Verified**: GET `/api/apps/{id}/web-analytics/config` returns `heatmaps_active=false, heatmaps_coming_soon=true, clarity_deeplink=null`, snippet contains no `data-clarity` attribute.


- **2026-05-11 — Heatmaps: platform-wide Clarity infra (superseded by hold above)**
  - **What**: Platform admin enters **one** Microsoft Clarity project id in Admin → Integrations → "Heatmaps & session recordings". From that moment on, the Clarity recording tag auto-injects on every Pro+ app, completely white-label, without the customer touching a single setting.
  - **Plan availability widened**: Heatmaps now unlock at **Pro** (previously Agency-only) — no per-customer cost since Clarity is free + unlimited and shares one platform project.
  - **Backend**: `platform_settings.clarity_project_id` added to `PlatformSettingsUpdate` (no encryption needed — public id). `services/analytics.get_config` now pulls the platform-level id instead of per-app. `app_analytics_config.clarity_project_id` is no longer surfaced or settable from the customer-facing PUT.
  - **Plan seed sync**: `seed_default_plans` now expands `features_block` on every boot — newly-shipped feature flags (like `heatmaps: True` on Pro) light up on existing platforms transparently without overwriting admin overrides.
  - **Frontend**: new `HeatmapsIntegrationSection` on Admin (status pill + project id field + save + open dashboard ↗). `HeatmapsPane` in customer app-detail refactored: removed Clarity input field, shows 3 states — (1) "not yet enabled on this platform" warning, (2) "tracker not yet reporting" hint with Setup-tab link, (3) "Recording active" with privacy/retention KPIs + pre-filtered "Open recordings dashboard ↗" deeplink. The word "Clarity" no longer appears anywhere in customer-facing copy.
  - **Auto deep-link filter**: When admin → opens a customer app's heatmap, the link goes directly to `clarity.microsoft.com/projects/view/{id}/dashboard?filters=URL+contains+{host}` — scoped to that app's primary host.
  - **E2E verified**: Admin PUT platform settings → customer GET web-analytics/config returns `heatmaps_active=true` + `clarity_deeplink`, snippet includes `data-clarity` attribute automatically.


- **2026-05-11 — Web Analytics: PageSpeed + Visitors (initial cut)**
  - **Google PageSpeed Insights** integration (free tier, API key in `.env`): mobile + desktop audits with Performance / Accessibility / Best Practices / SEO scores, Core Web Vitals (LCP/FCP/CLS/TBT/TTFB lab + field p75 from CrUX), 30-day score trend.
  - **Self-hosted, cookieless pageview tracking**: tiny `~1 KB` `/api/analytics/tracker.js` auto-tracks initial pageview + SPA navigation (pushState/replaceState/popstate hooks) + outbound clicks via `sendBeacon`. Cookie-free visitor identity via `sha256(ip+ua+site+utc_day)` that rotates daily; country from `cf-ipcountry` / `x-vercel-ip-country` edge headers; bot filtering via UA regex.
  - **Microsoft Clarity heatmaps**: Clarity project-id field, auto-loads Clarity tag alongside our pageview tracker via the same `<script>`. Agency plan only.
  - **Plan-tier gating** via new `features_block` map on plans: `{pageviews, pagespeed, heatmaps}`; Free=pageviews only, Pro=+pagespeed, Agency=+heatmaps. Backfill on seed so existing platforms upgrade transparently. 402 returned with marketing copy when locked.
  - **Backend**: `clients/pagespeed.py`, `services/pagespeed.py`, `services/analytics.py`, `routers/analytics.py`. New collections: `pagespeed_runs`, `analytics_events`, `app_analytics_config`. APScheduler jobs: 12h `daily_pagespeed_tick` + 24h `analytics_gc` (90-day retention).
  - **New endpoints**: `GET /api/analytics/tracker.js` (public, CORS *), `POST /api/analytics/collect` (public, 204 No Content), `GET|PUT /api/apps/{id}/web-analytics/config`, `GET /api/apps/{id}/web-analytics?window=24h|7d|30d|90d`, `POST /api/apps/{id}/pagespeed/run`, `GET /api/apps/{id}/pagespeed/latest|history`. Route path is `web-analytics` to avoid collision with the existing usage-analytics endpoint.
  - **Frontend**: new `components/AppWebAnalyticsTab.jsx` mounted on `AppDetail` as `analytics` tab. 4 sub-tabs: Visitors (KPIs + Recharts area chart + top-pages/refs/devices/browsers/countries), Speed Insights (ScoreCircle SVG ring per category + CWV cards + 30-day trend line, with mobile/desktop toggle), Heatmaps (Clarity project setup + deep-link to Clarity dashboard), Setup (1-line `<head>` snippet + Next.js App-Router snippet with copy buttons).
  - **E2E verified**: config creation (`dh_…` site_id), 5x synthetic POSTs → 204 → summary aggregation returns correct pageviews/uniques/top-pages, Clarity project save round-trips. Plan-gating 402 surfaced as "requires Pro/Agency" panel + upgrade CTA in UI.
  - **Caveat — auto-injection**: the snippet must be pasted once in the user's `<head>` (1 line). Truly zero-config auto-injection would require a Traefik body-rewrite plugin on the Coolify VPS; flagged as future enhancement.


- **2026-05-11 — Metrics Agent UUID-mapping P0 fix + diagnostics**
  - **Problem**: Live container metrics agent on user's Coolify VPS was pinging `/api/metrics/ingest` (heartbeat OK) but `last_sample_count` stuck at 0. Coolify v4 stores integer DB id in `coolify.applicationId` label, not the UUID, and the prior name-regex `^([a-z0-9]{20,32})(?:-\d+)?$` rejected newer Coolify revision suffixes that are alphanumeric.
  - **Fix**: Robuster UUID extraction — try `coolify.applicationUUID` / `coolify.application.uuid` / `coolify.databaseUUID` / `coolify.serviceUUID` / `coolify.resource.uuid` labels first, then fall back to relaxed regex `^([a-z0-9]{20,32})(?:-[a-z0-9]+)?$`. Skip known Coolify infra container prefixes explicitly.
  - **Diagnostics**: Agent now logs per-tick summary (`tick: managed=N sampled=M skipped_no_uuid=K`) and per-sample line so user can see exactly what's found/skipped via `docker logs deployunit-metrics-agent`. Server-side ingest logs unmapped UUIDs and surfaces last 10 of them in `GET /api/admin/metrics/agent` response.
  - **UI**: Admin → Metrics agent section now shows `accepted / skipped of seen` triplet plus a yellow "unmapped containers detected" panel listing UUIDs that don't match any DeployUnit app/database.
  - **Heartbeat**: Server now updates `last_seen_at` even on empty batches so the admin can tell "agent is alive but found no containers".
  - **Verified**: Full ingest flow E2E via curl — wrong UUID → skipped + surfaced in `last_skipped_uuids`; correct UUID → accepted, stored in `container_metrics_samples`, app metrics query returns data.
  - **Action required from user**: Reinstall the agent on the VPS to pick up the new `agent.py` and rotate to a fresh agent key (old key still valid in DB; only needed if user wants forced rotation).


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
