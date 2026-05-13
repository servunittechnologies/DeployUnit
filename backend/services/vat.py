"""EU VAT calculation + VIES validation.

- Company location: platform_settings.company_country (admin-editable, default NL)
- EU B2B with valid VAT ID → 0% (reverse charge)
- EU B2C → destination country standard rate
- Same-country (regardless of B2B/B2C) → home-country standard rate
- Non-EU → 0%
"""
import re
import logging
import httpx

logger = logging.getLogger(__name__)


# Standard EU VAT rates as of 2026
EU_VAT_RATES = {
    "AT": 20.0, "BE": 21.0, "BG": 20.0, "HR": 25.0, "CY": 19.0,
    "CZ": 21.0, "DK": 25.0, "EE": 24.0, "FI": 25.5, "FR": 20.0,
    "DE": 19.0, "GR": 24.0, "HU": 27.0, "IE": 23.0, "IT": 22.0,
    "LV": 21.0, "LT": 21.0, "LU": 17.0, "MT": 18.0, "NL": 21.0,
    "PL": 23.0, "PT": 23.0, "RO": 19.0, "SK": 20.0, "SI": 22.0,
    "ES": 21.0, "SE": 25.0,
}

COUNTRY_NAMES = {
    "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "HR": "Croatia", "CY": "Cyprus",
    "CZ": "Czech Republic", "DK": "Denmark", "EE": "Estonia", "FI": "Finland", "FR": "France",
    "DE": "Germany", "GR": "Greece", "HU": "Hungary", "IE": "Ireland", "IT": "Italy",
    "LV": "Latvia", "LT": "Lithuania", "LU": "Luxembourg", "MT": "Malta", "NL": "Netherlands",
    "PL": "Poland", "PT": "Portugal", "RO": "Romania", "SK": "Slovakia", "SI": "Slovenia",
    "ES": "Spain", "SE": "Sweden", "US": "United States", "GB": "United Kingdom",
    "CA": "Canada", "CH": "Switzerland", "NO": "Norway", "AU": "Australia",
}


def home_country() -> str:
    """Synchronous fallback used by code paths that can't await — returns
    the hardcoded default. For accurate runtime resolution use
    `effective_home_country()` which reads `platform_settings` in MongoDB."""
    return "NL"


async def effective_home_country() -> str:
    """Resolve the configured home country, preferring the admin-editable
    `platform_settings.company_country` over the static env default."""
    try:
        from db import get_db
        db = get_db()
        doc = await db.platform_settings.find_one(
            {"id": "platform-singleton"}, {"_id": 0, "company_country": 1}
        )
        cc = (doc or {}).get("company_country")
        if cc:
            return cc.upper()
    except Exception:
        pass
    return home_country()


def is_eu(country: str) -> bool:
    return (country or "").upper() in EU_VAT_RATES


def normalize_vat_id(vat_id: str) -> tuple[str, str] | None:
    """Return (country_code, number) or None."""
    if not vat_id:
        return None
    cleaned = re.sub(r"[\s\-\.]", "", vat_id.upper())
    m = re.match(r"^([A-Z]{2})([A-Z0-9]{2,})$", cleaned)
    if not m:
        return None
    return m.group(1), m.group(2)


async def validate_vies(vat_id: str) -> dict:
    """Query VIES SOAP service. Returns {valid: bool, name: str|None, address: str|None, error: str|None}."""
    parsed = normalize_vat_id(vat_id)
    if not parsed:
        return {"valid": False, "error": "format"}
    cc, number = parsed
    if cc not in EU_VAT_RATES:
        return {"valid": False, "error": "not_eu"}

    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:urn="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
  <soapenv:Header/>
  <soapenv:Body>
    <urn:checkVat>
      <urn:countryCode>{cc}</urn:countryCode>
      <urn:vatNumber>{number}</urn:vatNumber>
    </urn:checkVat>
  </soapenv:Body>
</soapenv:Envelope>"""
    try:
        async with httpx.AsyncClient(timeout=12.0) as cli:
            r = await cli.post(
                "https://ec.europa.eu/taxation_customs/vies/services/checkVatService",
                content=body.encode("utf-8"),
                headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": ""},
            )
    except Exception as e:
        logger.warning("VIES unreachable: %s", e)
        return {"valid": False, "error": "vies_unreachable"}

    if r.status_code != 200:
        return {"valid": False, "error": f"vies_http_{r.status_code}"}
    text = r.text
    # VIES responses have a namespace prefix (e.g. <ns2:valid>) — we have to
    # tolerate it. Older VIES versions emit plain <valid>; both forms must
    # match. "countryCode" is unique enough to skip any "invalidVatNumber"
    # element found in a fault response.
    valid = bool(re.search(r"<(?:[A-Za-z0-9]+:)?valid>\s*true\s*</(?:[A-Za-z0-9]+:)?valid>", text, re.I))
    name_match = re.search(r"<(?:[A-Za-z0-9]+:)?name>([^<]*)</(?:[A-Za-z0-9]+:)?name>", text, re.I)
    addr_match = re.search(r"<(?:[A-Za-z0-9]+:)?address>([^<]*)</(?:[A-Za-z0-9]+:)?address>", text, re.I | re.S)
    name = (name_match.group(1).strip() if name_match else None) or None
    # VIES returns literal "---" for privacy-suppressed names; treat as None
    if name in ("---", ""):
        name = None
    address = (addr_match.group(1).strip() if addr_match else None) or None
    if address in ("---", ""):
        address = None
    return {
        "valid": valid,
        "name": name,
        "address": address,
        "error": None if valid else "invalid",
    }


def compute_vat(*, country: str, is_business: bool, has_valid_vat_id: bool, home_cc: str | None = None) -> dict:
    """Return {rate: float, note: str, kind: home|domestic|b2b_reverse|b2c_destination|non_eu|unknown}.

    `home_cc` (ISO 2-letter) overrides the env default. Pass the result of
    `await effective_home_country()` so admin-edited platform settings are
    respected.
    """
    cc = (country or "").upper()
    home = (home_cc or home_country()).upper()

    if not cc:
        return {"rate": EU_VAT_RATES.get(home, 21.0), "note": f"{home} VAT (default)", "kind": "home"}

    if cc == home:
        return {"rate": EU_VAT_RATES.get(home, 21.0), "note": f"{home} VAT", "kind": "domestic"}

    if cc in EU_VAT_RATES:
        if is_business and has_valid_vat_id:
            return {
                "rate": 0.0,
                "note": "Reverse charge - VAT to be accounted for by the recipient",
                "kind": "b2b_reverse",
            }
        # B2C EU — destination country rate under OSS/MOSS
        return {"rate": EU_VAT_RATES[cc], "note": f"{COUNTRY_NAMES.get(cc, cc)} VAT ({EU_VAT_RATES[cc]}%)", "kind": "b2c_destination"}

    return {"rate": 0.0, "note": "Outside EU — no VAT", "kind": "non_eu"}


def compute_totals(*, subtotal: float, vat_rate: float) -> dict:
    vat_amount = round(subtotal * (vat_rate / 100.0), 2)
    total = round(subtotal + vat_amount, 2)
    return {"subtotal": round(subtotal, 2), "vat_rate": vat_rate, "vat_amount": vat_amount, "total": total}
