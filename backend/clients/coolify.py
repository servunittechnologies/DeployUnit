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
        ok = await self._request("GET", "/health")
        return {"configured": self.configured, "ok": ok is not None}

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

    async def deploy(self, app_uuid: str, force: bool = False) -> Optional[dict]:
        return await self._request("GET", f"/deploy?uuid={app_uuid}&force={'true' if force else 'false'}")

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

    async def list_deployments(self, app_uuid: str) -> list:
        data = await self._request("GET", f"/deployments/applications/{app_uuid}")
        if isinstance(data, dict) and "deployments" in data:
            return data.get("deployments") or []
        if isinstance(data, list):
            return data
        return []

    async def get_deployment(self, deployment_uuid: str) -> Optional[dict]:
        return await self._request("GET", f"/deployments/{deployment_uuid}")


coolify = CoolifyClient()
