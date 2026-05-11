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
        url = f"{self.base}/api/v1{path}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as cli:
                r = await cli.request(method, url, headers=self._headers(), **kwargs)
                if r.status_code >= 400:
                    logger.warning("Coolify %s %s -> %s %s", method, path, r.status_code, r.text[:300])
                    return None
                if not r.content:
                    return {}
                return r.json()
        except Exception as e:
            logger.warning("Coolify %s %s failed: %s", method, path, e)
            return None

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
        return await self._request("PATCH", f"/applications/{app_uuid}", json=payload)

    async def restart(self, app_uuid: str) -> Optional[dict]:
        return await self._request("GET", f"/applications/{app_uuid}/restart")

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
