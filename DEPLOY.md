# DeployUnit — deployment

DeployUnit has two parts with different hosting needs:

- **Frontend** (`frontend/`) — a static React SPA. **Perfect for Vercel.**
- **Backend** (`backend/`) — FastAPI + MongoDB **plus ~18 always-on background
  jobs** (deploy sync every 15s, the routing self-healer every 2 min that
  auto-recovers apps that lose their Traefik route, the Cloudflare subdomain
  pool, credit grants, billing renewals, …). These need a **persistent
  process** — which serverless platforms like Vercel do not provide.

You can run **everything on Vercel** (one project — see below), or split
**frontend on Vercel + backend on an always-on host** (your Coolify; the most
robust option). Either way MongoDB must be a hosted database reachable from
the functions (MongoDB Atlas free tier works). `localhost` Mongo is dev-only.

---

## Everything on Vercel (one project, one deploy)

The repo root is set up so you can **import the repo into Vercel and deploy** —
the React frontend builds as static output and `api/index.py` serves the
FastAPI app as a Python serverless function (same origin, so auth cookies work
with no proxy config). `vercel.json` wires it all, including the cron jobs.

1. Import the repo in Vercel → Deploy. (Root Directory = repo root; the root
   `vercel.json` handles build + functions + rewrites + crons.)
2. Set the environment variables (see `backend/.env.example`) in the Vercel
   project. **Required:** `MONGO_URL` (Atlas), `DB_NAME`, `JWT_SECRET`,
   `ENCRYPTION_KEY`, `DEPLOYUNIT_ENV=production`, `FRONTEND_URL` (your Vercel
   URL), `COOLIFY_*`, `INTERNAL_API_KEY`, and **`CRON_SECRET`** (any random
   string — protects the cron endpoints).
3. Redeploy so the env vars apply.

**Background jobs on Vercel = cron.** Vercel injects `VERCEL=1`, so the
in-process scheduler is off; instead Vercel Cron calls `/api/cron/frequent`
(every minute), `/api/cron/hourly` and `/api/cron/daily`. Two caveats you must
accept with this setup:

- **Vercel Cron needs the Pro plan** (Hobby runs crons only once/day). And its
  minimum interval is 1 minute — so the natively sub-minute jobs (deploy sync
  15s, watchdog/verify 30s) run at most once a minute. Deploy-status and
  routing self-healing are therefore ~1-minute-coarse, not real-time.
- Each cron invocation runs a batch of jobs within the function's `maxDuration`
  (60s). If you have very many apps this can get tight.

If real-time monitoring / instant routing recovery matters, run one always-on
`worker.py` (below) against the same MongoDB and drop the `crons` from
vercel.json — that's the split setup, which is why it's recommended.

---

## Recommended: frontend on Vercel + backend on Coolify

### 1. Backend on Coolify (or any container host)

Deploy `backend/` as an application. It ships a `Dockerfile` (web tier with the
scheduler ON — one container serves the API *and* runs all jobs).

Environment variables (see `backend/.env.example`):

| Var | Notes |
|---|---|
| `MONGO_URL` | e.g. an Atlas connection string |
| `DB_NAME` | e.g. `deployunit` |
| `JWT_SECRET` | 48+ random chars |
| `ENCRYPTION_KEY` | Fernet key (`python -c "import base64,secrets;print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"`) |
| `DEPLOYUNIT_ENV` | `production` (below this, all Coolify/Cloudflare/Mollie/mail writes are env-guarded off) |
| `FRONTEND_URL` | the Vercel URL, e.g. `https://app.deployunit.com` |
| `COOLIFY_BASE_URL` / `COOLIFY_API_TOKEN` / `COOLIFY_SERVER_UUID` | the build engine |
| `INTERNAL_API_KEY` | enables the WHMCS provisioning API (`/api/internal/*`); unset = disabled |
| `WHMCS_LOGIN_URL` | optional; shows the "Continue with ServUnit" button |
| `MOLLIE_API_KEY`, `GITHUB_CLIENT_ID/SECRET`, `GOOGLE_PAGESPEED_API_KEY` | as needed |

The API listens on port 8000.

**Scaling note:** if you run more than one web replica, set
`DISABLE_SCHEDULER=1` on the web containers and run **exactly one** worker
(`Dockerfile.worker`, or `python worker.py`) so the jobs don't run N times.

### 2. Frontend on Vercel

Create a Vercel project with **Root Directory = `frontend`**. `frontend/vercel.json`
handles the SPA routing and proxies `/api/*` to the backend so auth cookies stay
first-party.

Edit `frontend/vercel.json` and replace `REPLACE-WITH-YOUR-BACKEND-HOST` with
your backend host (e.g. `deployunit-api.yourdomain.com`). Then deploy — Vercel
auto-detects the CRA build. Point `FRONTEND_URL` on the backend at the resulting
Vercel URL.

---

## Alternative: everything on Vercel (web serverless + separate worker)

Only if you specifically want the API on Vercel too. `server.py` detects
`VERCEL=1` and runs **web-only** (scheduler off), so you **must** run the worker
elsewhere or the platform's automation stops.

1. **Backend as its own Vercel project** — Root Directory = `backend`.
   `backend/vercel.json` routes every request into the FastAPI app
   (`backend/api/index.py`). Set the same env vars as above. Vercel injects
   `VERCEL=1`, so the scheduler stays off.
2. **Frontend Vercel project** — point the `/api` rewrite at the backend
   Vercel deployment URL.
3. **Worker** — run `backend/worker.py` (or `Dockerfile.worker`) on an
   always-on host against the same MongoDB. Without it: no deploy-status sync,
   no routing self-healer, no subdomain pool, no credit/billing jobs.

Caveats: Vercel function execution limits (≤300s) and cold starts; the sub-minute
real-time jobs cannot be replaced by Vercel Cron (1-minute minimum). This is why
the split above is recommended.
