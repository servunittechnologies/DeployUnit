"""Coolify HTTP API client.

Docs: https://coolify.io/docs/api-reference
We use a small surface area: list servers, list/create projects, create-and-deploy
applications from a public Git repo, list deployments, fetch logs, restart.
Failures are logged and the higher level service degrades to a "queued" stub
state so the SaaS UX never breaks even when the infra is offline.
"""
import os
import logging
import httpx
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CoolifyClient:
    def __init__(self):
        self.base = (os.environ.get("COOLIFY_BASE_URL") or "").rstrip("/")
        self.token = os.environ.get("COOLIFY_API_TOKEN") or ""
        self.server_uuid = os.environ.get("COOLIFY_SERVER_UUID") or ""

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    @property
    def configured(self) -> bool:
        return bool(self.base and self.token)

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        if not self.configured:
            return None
        data, _status, _err = await self._request_meta(method, path, **kwargs)
        return data

    async def _request_meta(self, method: str, path: str, **kwargs) -> tuple[Any, int, str]:
        """Like _request but also returns (data, status_code, error_text).
        Used by callers that need to distinguish 404 (resource gone) from
        500 (build engine down) etc. so they can show helpful messages."""
        if not self.configured:
            return None, 0, "build engine not configured"
        url = f"{self.base}/api/v1{path}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as cli:
                r = await cli.request(method, url, headers=self._headers(), **kwargs)
                if r.status_code >= 400:
                    logger.warning("Coolify %s %s -> %s %s", method, path, r.status_code, r.text[:300])
                    err = r.text[:500] if r.text else f"HTTP {r.status_code}"
                    return None, r.status_code, err
                if not r.content:
                    return {}, r.status_code, ""
                return r.json(), r.status_code, ""
        except Exception as e:
            logger.warning("Coolify %s %s failed: %s", method, path, e)
            return None, 0, str(e)[:200]

    async def app_exists(self, app_uuid: str) -> bool:
        """Quick existence check — returns False on 404 from build engine."""
        if not self.configured or not app_uuid:
            return False
        _data, status, _err = await self._request_meta("GET", f"/applications/{app_uuid}")
        return 200 <= status < 300

    async def health(self) -> dict:
        """Coolify v4 exposes /api/health (no /v1 prefix). Use a direct call
        instead of _request so we don't accidentally prepend /v1."""
        if not self.configured:
            return {"configured": False, "ok": False}
        try:
            async with httpx.AsyncClient(timeout=5.0) as cli:
                r = await cli.get(f"{self.base}/api/health")
            ok = 200 <= r.status_code < 300
            return {"configured": True, "ok": ok}
        except Exception as e:
            logger.warning("Coolify health failed: %s", e)
            return {"configured": True, "ok": False, "error": str(e)[:120]}

    async def list_servers(self) -> list:
        data = await self._request("GET", "/servers")
        return data or []

    async def get_default_server_uuid(self) -> Optional[str]:
        if self.server_uuid:
            return self.server_uuid
        servers = await self.list_servers()
        if servers and isinstance(servers, list):
            return servers[0].get("uuid")
        return None

    async def list_projects(self) -> list:
        data = await self._request("GET", "/projects")
        return data or []

    async def create_project(self, name: str, description: str = "") -> Optional[dict]:
        return await self._request("POST", "/projects", json={"name": name, "description": description})

    async def create_public_app(
        self,
        *,
        project_uuid: str,
        server_uuid: str,
        name: str,
        git_repository: str,
        git_branch: str = "main",
        build_pack: str = "nixpacks",
        ports_exposes: str = "3000",
        environment_name: str = "production",
        instant_deploy: bool = True,
    ) -> Optional[dict]:
        payload = {
            "project_uuid": project_uuid,
            "server_uuid": server_uuid,
            "environment_name": environment_name,
            "name": name,
            "git_repository": git_repository,
            "git_branch": git_branch,
            "build_pack": build_pack,
            "ports_exposes": ports_exposes,
            "instant_deploy": instant_deploy,
        }
        return await self._request("POST", "/applications/public", json=payload)

    async def create_private_key(self, *, name: str, private_key: str, description: str = "") -> Optional[dict]:
        """Register a Git-related SSH private key in Coolify so applications can
        clone private repos. Returns {uuid, ...} on success."""
        return await self._request(
            "POST",
            "/security/keys",
            json={
                "name": name,
                "description": description,
                "private_key": private_key,
                "is_git_related": True,
            },
        )

    async def delete_private_key(self, uuid: str) -> Optional[dict]:
        return await self._request("DELETE", f"/security/keys/{uuid}")

    async def create_private_deploy_key_app(
        self,
        *,
        project_uuid: str,
        server_uuid: str,
        name: str,
        git_repository: str,
        git_branch: str = "main",
        private_key_uuid: str,
        build_pack: str = "nixpacks",
        ports_exposes: str = "3000",
        environment_name: str = "production",
        instant_deploy: bool = False,
    ) -> Optional[dict]:
        """Create an application that clones a private repo via an SSH deploy key
        registered in Coolify (is_git_related=true). git_repository must be the
        SSH form: git@github.com:owner/repo.git"""
        payload = {
            "project_uuid": project_uuid,
            "server_uuid": server_uuid,
            "environment_name": environment_name,
            "name": name,
            "git_repository": git_repository,
            "git_branch": git_branch,
            "build_pack": build_pack,
            "ports_exposes": ports_exposes,
            "private_key_uuid": private_key_uuid,
            "instant_deploy": instant_deploy,
        }
        return await self._request("POST", "/applications/private-deploy-key", json=payload)

    async def deploy(self, app_uuid: str, force: bool = False) -> Optional[dict]:
        """Trigger a deploy. Returns the parsed Coolify deployment object
        ({deployment_uuid, message, resource_uuid}) on success; None on failure."""
        res = await self._request("GET", f"/deploy?uuid={app_uuid}&force={'true' if force else 'false'}")
        if not res:
            return None
        if isinstance(res, dict) and isinstance(res.get("deployments"), list) and res["deployments"]:
            head = res["deployments"][0]
            if isinstance(head, dict):
                return head
        if isinstance(res, dict) and res.get("deployment_uuid"):
            return res
        return None

    async def get_application(self, app_uuid: str) -> Optional[dict]:
        return await self._request("GET", f"/applications/{app_uuid}")

    async def list_applications(self) -> list[dict]:
        """Return every application the build engine knows about. Used by the
        reconcile job to detect drift between Coolify and DeployUnit (e.g.
        apps deleted out of band)."""
        res = await self._request("GET", "/applications")
        if isinstance(res, list):
            return res
        if isinstance(res, dict) and isinstance(res.get("data"), list):
            return res["data"]
        return []

    async def update_env(self, app_uuid: str, env_vars: dict) -> Optional[dict]:
        # Coolify takes one variable at a time via /applications/{uuid}/envs
        results = []
        for key, value in (env_vars or {}).items():
            res = await self._request(
                "POST",
                f"/applications/{app_uuid}/envs",
                json={"key": key, "value": value, "is_preview": False, "is_build_time": False, "is_literal": True},
            )
            results.append(res)
        return {"updated": results}

    async def update_application(self, app_uuid: str, payload: dict) -> Optional[dict]:
        """PATCH an application. Coolify v4 quirk: to update the FQDN you MUST
        send `domains` (comma-separated, with https:// prefix), NOT `fqdn`.
        We auto-translate `fqdn` → `domains` here so callers don't have to
        remember. Note: even after a successful PATCH Coolify does NOT
        regenerate the Traefik labels — a subsequent deploy(force=True) is
        required for the new domain to actually start serving traffic.
        See: github.com/coollabsio/coolify/issues/6281
        """
        body = dict(payload or {})
        if "fqdn" in body and "domains" not in body:
            body["domains"] = body.pop("fqdn")
        data, status, err = await self._request_meta("PATCH", f"/applications/{app_uuid}", json=body)
        if status and (status < 200 or status >= 300):
            logger.warning("Coolify update_application(%s) -> %s: %s (payload keys=%s)",
                           app_uuid, status, (err or "")[:200], list(body.keys()))
        return data

    async def set_domains(self, app_uuid: str, domains: str | list[str], *, force_https: bool = True) -> Optional[dict]:
        """Set the application's public domains AND turn on Force HTTPS in
        one call. Coolify v4 needs both signals to:
          1) Route the FQDN through Traefik (`domains` with https:// prefix)
          2) Request a Let's Encrypt cert + redirect HTTP→HTTPS (`force_https`)

        Without `force_https` Coolify will still SERVE the domain over plain
        HTTP and never request a cert — the user sees the Traefik default
        self-signed cert forever.
        """
        if isinstance(domains, list):
            csv = ",".join(d.strip() for d in domains if d and d.strip())
        else:
            csv = (domains or "").strip()
        if not csv:
            return None
        body: dict = {"domains": csv}
        if force_https:
            # Coolify uses two fields for the same concept across versions;
            # send both so we work on v4.x regardless.
            body["force_https"] = True
            body["is_https_forced"] = True
        return await self._request("PATCH", f"/applications/{app_uuid}", json=body)

    async def restart(self, app_uuid: str) -> Optional[dict]:
        """Restart the application container. Coolify v4 uses POST for this
        (older versions accepted GET). Use this to bounce a container when
        only env-vars or labels changed."""
        return await self._request("POST", f"/applications/{app_uuid}/restart")

    async def stop(self, app_uuid: str) -> Optional[dict]:
        """Stop the running app container. Used to clear stale state before a
        force redeploy when the build engine references a missing helper
        container ("No such container: <uuid>") — Coolify holds onto that
        UUID until the app is explicitly stopped or restarted."""
        return await self._request("GET", f"/applications/{app_uuid}/stop")

    async def delete_application(self, app_uuid: str) -> Optional[dict]:
        """Remove an application from Coolify (also tears down its container)."""
        return await self._request(
            "DELETE",
            f"/applications/{app_uuid}?cleanup=true&delete_configurations=true&delete_volumes=true&delete_connected_networks=false&docker_cleanup=true",
        )

    async def list_deployments(self, app_uuid: str) -> list:
        data = await self._request("GET", f"/deployments/applications/{app_uuid}")
        if isinstance(data, dict) and "deployments" in data:
            return data.get("deployments") or []
        if isinstance(data, list):
            return data
        return []

    async def get_deployment(self, deployment_uuid: str) -> Optional[dict]:
        return await self._request("GET", f"/deployments/{deployment_uuid}")

    async def application_logs(self, app_uuid: str, *, lines: int = 200) -> tuple[list[str], str]:
        """Pull runtime container logs (stdout/stderr) for an application.

        Returns (lines, error_text). Coolify v4 exposes `/applications/{uuid}/logs`
        which returns either a list of {"output":..., "timestamp":...} entries
        or a plain text blob — we normalise into a list of strings.

        On 404 (app gone) returns ([], "build-engine-missing") so the caller
        can show a clean "needs reinstall" message instead of a raw 404."""
        if not self.configured or not app_uuid:
            return [], "not-configured"
        data, status, err = await self._request_meta(
            "GET", f"/applications/{app_uuid}/logs", params={"lines": lines}
        )
        if status == 404:
            return [], "build-engine-missing"
        if status >= 400 or data is None:
            return [], err or f"HTTP {status}"
        # Possible shapes from Coolify:
        #   1) list of {"output":"foo","timestamp":"..."}
        #   2) {"logs": [...]} dict
        #   3) plain string blob
        entries = data.get("logs") if isinstance(data, dict) else data
        if isinstance(entries, str):
            return [ln for ln in entries.splitlines() if ln.strip()], ""
        if not isinstance(entries, list):
            return [], "unsupported log shape"
        out = []
        for e in entries:
            if isinstance(e, str):
                out.append(e)
            elif isinstance(e, dict):
                ts = e.get("timestamp") or e.get("time") or ""
                txt = e.get("output") or e.get("message") or e.get("line") or ""
                tag = (e.get("type") or e.get("stream") or "").lower()
                prefix = f"{ts[:19]} " if ts else ""
                if tag == "stderr":
                    prefix += "[stderr] "
                out.append(prefix + str(txt))
        return out, ""

    # ─────────────────── Scheduled tasks (cron jobs) ───────────────────
    async def list_scheduled_tasks(self, app_uuid: str) -> list:
        data = await self._request("GET", f"/applications/{app_uuid}/scheduled-tasks")
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return []

    async def create_scheduled_task(self, app_uuid: str, *, name: str, command: str, frequency: str) -> Optional[dict]:
        """Coolify scheduled task. `frequency` is a cron expression like '0 3 * * *'."""
        return await self._request(
            "POST", f"/applications/{app_uuid}/scheduled-tasks",
            json={"name": name, "command": command, "frequency": frequency},
        )

    async def update_scheduled_task(self, app_uuid: str, task_uuid: str, *, name: str, command: str, frequency: str) -> Optional[dict]:
        return await self._request(
            "PATCH", f"/applications/{app_uuid}/scheduled-tasks/{task_uuid}",
            json={"name": name, "command": command, "frequency": frequency},
        )

    async def delete_scheduled_task(self, app_uuid: str, task_uuid: str) -> Optional[dict]:
        return await self._request("DELETE", f"/applications/{app_uuid}/scheduled-tasks/{task_uuid}")

    # ─────────────────── Managed databases (Postgres / Redis) ───────────────────
    async def create_database(self, *, server_uuid: str, project_uuid: str, environment_name: str,
                              db_type: str, name: str, version: Optional[str] = None) -> Optional[dict]:
        """db_type in {postgresql, mysql, mariadb, mongodb, redis, keydb, dragonfly}. Coolify auto-generates
        the connection string + credentials and returns the uuid for follow-up calls.

        Note: Coolify v4 (Nov 2025) rejects an explicit `version` field on this endpoint
        — the image tag is chosen by Coolify based on `db_type`. We keep the param in
        our signature for forward-compat but don't forward it."""
        body = {
            "server_uuid": server_uuid,
            "project_uuid": project_uuid,
            "environment_name": environment_name,
            "name": name,
        }
        return await self._request("POST", f"/databases/{db_type}", json=body)

    async def get_database(self, db_uuid: str) -> Optional[dict]:
        return await self._request("GET", f"/databases/{db_uuid}")

    async def start_database(self, db_uuid: str) -> Optional[dict]:
        return await self._request("GET", f"/databases/{db_uuid}/start")

    async def stop_database(self, db_uuid: str) -> Optional[dict]:
        return await self._request("GET", f"/databases/{db_uuid}/stop")

    async def delete_database(self, db_uuid: str) -> Optional[dict]:
        return await self._request(
            "DELETE",
            f"/databases/{db_uuid}?delete_configurations=true&delete_volumes=true",
        )


coolify = CoolifyClient()
