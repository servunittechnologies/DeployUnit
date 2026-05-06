"""WHMCS API client.

WHMCS exposes a single POST endpoint at /includes/api.php that accepts an
identifier + secret and an "action" parameter. We wrap a few actions used by
the SaaS billing flow.

Docs: https://developers.whmcs.com/api/
"""
import os
import logging
import httpx
from typing import Any, Optional

logger = logging.getLogger(__name__)


class WHMCSClient:
    def __init__(self):
        self.base = (os.environ.get("WHMCS_BASE_URL") or "").rstrip("/")
        self.identifier = os.environ.get("WHMCS_API_IDENTIFIER") or ""
        self.secret = os.environ.get("WHMCS_API_SECRET") or ""
        self.product_id = os.environ.get("WHMCS_DEFAULT_PRODUCT_ID") or ""

    @property
    def configured(self) -> bool:
        return bool(self.base and self.identifier and self.secret)

    async def call(self, action: str, **params) -> dict:
        if not self.configured:
            return {"result": "error", "message": "whmcs_not_configured"}
        url = f"{self.base}/includes/api.php"
        payload = {
            "identifier": self.identifier,
            "secret": self.secret,
            "action": action,
            "responsetype": "json",
            **{k: v for k, v in params.items() if v is not None},
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as cli:
                r = await cli.post(url, data=payload)
                if r.status_code >= 400:
                    logger.warning("WHMCS %s -> HTTP %s %s", action, r.status_code, r.text[:300])
                    return {"result": "error", "message": f"http_{r.status_code}"}
                try:
                    return r.json()
                except Exception:
                    return {"result": "error", "message": "invalid_json", "raw": r.text[:300]}
        except Exception as e:
            logger.warning("WHMCS %s failed: %s", action, e)
            return {"result": "error", "message": str(e)}

    # --- Clients ---
    async def add_client(
        self,
        *,
        firstname: str,
        lastname: str,
        email: str,
        password: str,
        country: str = "US",
        currency: int = 1,
    ) -> dict:
        return await self.call(
            "AddClient",
            firstname=firstname,
            lastname=lastname,
            email=email,
            password2=password,
            country=country,
            currency=currency,
            address1="N/A",
            city="N/A",
            state="N/A",
            postcode="00000",
            phonenumber="0000000000",
            skipvalidation=True,
        )

    async def get_clients_details(self, clientid: int) -> dict:
        return await self.call("GetClientsDetails", clientid=clientid, stats=True)

    # --- Orders / services ---
    async def add_order(
        self,
        *,
        clientid: int,
        pid: Optional[int] = None,
        billingcycle: str = "monthly",
        domain: Optional[str] = None,
        paymentmethod: str = "banktransfer",
    ) -> dict:
        params = {
            "clientid": clientid,
            "billingcycle": billingcycle,
            "paymentmethod": paymentmethod,
            "noinvoice": False,
            "noinvoiceemail": True,
            "noemail": True,
        }
        if pid:
            params["pid"] = pid
        if domain:
            params["domain"] = domain
        return await self.call("AddOrder", **params)

    async def get_orders(self, clientid: int) -> dict:
        return await self.call("GetOrders", userid=clientid)

    # --- Invoices ---
    async def get_invoices(self, clientid: int, limit: int = 25) -> dict:
        return await self.call("GetInvoices", userid=clientid, limitnum=limit)

    async def get_invoice(self, invoiceid: int) -> dict:
        return await self.call("GetInvoice", invoiceid=invoiceid)

    # --- Domains ---
    async def domain_whois(self, domain: str) -> dict:
        return await self.call("DomainWhois", domain=domain)

    async def get_products(self) -> dict:
        return await self.call("GetProducts")

    async def health(self) -> dict:
        if not self.configured:
            return {"configured": False, "ok": False}
        # WHMCS doesn't have a true ping; reuse GetProducts as a connectivity check.
        res = await self.call("GetProducts")
        return {"configured": True, "ok": res.get("result") == "success"}


whmcs = WHMCSClient()
