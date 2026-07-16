# DeployUnit — deployment

DeployUnit has two parts with different hosting needs:

- **Frontend** (`frontend/`) — a static React SPA. **Perfect for Vercel.**
- **Backend** (`backend/`) — FastAPI + MongoDB **plus ~18 always-on background
  jobs** (deploy sync every 15s, the routing self-healer every 2 min that
  auto-recovers apps that lose their Traefik route, the Cloudflare subdomain
  pool, credit grants, billing renewals, …). These need a **persistent
  process** — which serverless platforms like Vercel do not provide.

So the recommended split is **frontend on Vercel, backend on an always-on host**
(your Coolify is ideal — DeployUnit already runs on it). A full-Vercel option
is documented at the bottom for completeness.

MongoDB must be a hosted database reachable from wherever the backend runs
(MongoDB Atlas free tier works). `localhost` Mongo only works for local dev.

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
