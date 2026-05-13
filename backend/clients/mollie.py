"""Mollie API v2 client — raw httpx, no SDK.

Covers the surface we need for SaaS subscription billing:
- Customers
- Payments (first + recurring)
- Subscriptions (create / update / cancel / list)
- Mandates
"""
import os
import logging
from typing import Any, Optional
import httpx

logger = logging.getLogger(__name__)


class MollieClient:
    def __init__(self):
        self.base = "https://api.mollie.com/v2"
        self.api_key = os.environ.get("MOLLIE_API_KEY") or ""

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _req(self, method: str, path: str, *, json: Optional[dict] = None, params: Optional[dict] = None) -> Optional[dict]:
        if not self.configured:
            raise RuntimeError("Mollie not configured")
        url = f"{self.base}{path}"
        try:
            async with httpx.AsyncClient(timeout=20.0) as cli:
                r = await cli.request(method, url, headers=self._headers(), json=json, params=params)
        except Exception as e:
            logger.warning("Mollie %s %s failed: %s", method, path, e)
            raise

        if r.status_code == 204:
            return {}
        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text}
        if r.status_code >= 400:
            logger.warning("Mollie %s %s -> %s %s", method, path, r.status_code, r.text[:400])
            err = (data or {}).get("detail") or (data or {}).get("title") or r.text
            raise MollieError(f"mollie_{r.status_code}: {err}", status=r.status_code, body=data)
        return data

    # ---- Customers ----
    async def create_customer(self, *, name: str, email: str, metadata: dict | None = None) -> dict:
        return await self._req("POST", "/customers", json={
            "name": name, "email": email, "metadata": metadata or {},
        })

    async def get_customer(self, customer_id: str) -> dict:
        return await self._req("GET", f"/customers/{customer_id}")

    async def list_customer_mandates(self, customer_id: str) -> list:
        data = await self._req("GET", f"/customers/{customer_id}/mandates")
        return (data or {}).get("_embedded", {}).get("mandates", [])

    # ---- Payments ----
    async def create_payment(self, *, payload: dict) -> dict:
        return await self._req("POST", "/payments", json=payload)

    async def get_payment(self, payment_id: str) -> dict:
        return await self._req("GET", f"/payments/{payment_id}")

    async def list_customer_payments(self, customer_id: str, limit: int = 25) -> list:
        data = await self._req("GET", "/payments", params={"customerId": customer_id, "limit": limit})
        return (data or {}).get("_embedded", {}).get("payments", [])

    # ---- Subscriptions ----
    async def create_subscription(self, customer_id: str, *, payload: dict) -> dict:
        return await self._req("POST", f"/customers/{customer_id}/subscriptions", json=payload)

    async def update_subscription(self, customer_id: str, subscription_id: str, *, payload: dict) -> dict:
        """PATCH a subscription — typically to change `amount`, `description`,
        or `metadata` when a user upgrades/downgrades. Mollie applies the new
        price on the next billing cycle."""
        return await self._req("PATCH", f"/customers/{customer_id}/subscriptions/{subscription_id}", json=payload)

    async def get_subscription(self, customer_id: str, subscription_id: str) -> dict:
        return await self._req("GET", f"/customers/{customer_id}/subscriptions/{subscription_id}")

    async def cancel_subscription(self, customer_id: str, subscription_id: str) -> dict:
        return await self._req("DELETE", f"/customers/{customer_id}/subscriptions/{subscription_id}")

    async def list_methods(self) -> list:
        data = await self._req("GET", "/methods")
        return (data or {}).get("_embedded", {}).get("methods", [])


class MollieError(Exception):
    def __init__(self, message: str, status: int = 500, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


mollie = MollieClient()
