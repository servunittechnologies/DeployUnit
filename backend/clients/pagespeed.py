"""Google PageSpeed Insights v5 client.

Free tier: 25k requests/day. No SDK — REST only.
Docs: https://developers.google.com/speed/docs/insights/v5/get-started
"""
import os
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BASE = "https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed"


def configured() -> bool:
    return bool(os.environ.get("GOOGLE_PAGESPEED_API_KEY"))


async def run_audit(url: str, *, strategy: str = "mobile") -> Optional[dict]:
    """Trigger one PageSpeed audit. Returns a compact summary, or None on error.

    `strategy` is `mobile` or `desktop`.
    """
    api_key = os.environ.get("GOOGLE_PAGESPEED_API_KEY")
    if not api_key:
        logger.warning("pagespeed: GOOGLE_PAGESPEED_API_KEY not set")
        return None
    params = [
        ("url", url),
        ("strategy", strategy),
        ("key", api_key),
        ("category", "performance"),
        ("category", "accessibility"),
        ("category", "best-practices"),
        ("category", "seo"),
    ]
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.get(BASE, params=params)
        if r.status_code >= 300:
            logger.warning("pagespeed http %s for %s: %s", r.status_code, url, r.text[:200])
            return {"error": f"http_{r.status_code}", "message": r.text[:300]}
        data = r.json()
    except Exception as e:
        logger.error("pagespeed run %s: %s", url, e)
        return {"error": "request_failed", "message": str(e)}
    return _compact(data, strategy)


def _compact(data: dict, strategy: str) -> dict:
    """Pull the bits we actually plot."""
    lh = data.get("lighthouseResult") or {}
    cats = lh.get("categories") or {}
    audits = lh.get("audits") or {}

    def pct(cat: str) -> Optional[int]:
        c = cats.get(cat) or {}
        s = c.get("score")
        return round(s * 100) if isinstance(s, (int, float)) else None

    def num(audit_id: str, field: str = "numericValue") -> Optional[float]:
        a = audits.get(audit_id) or {}
        v = a.get(field)
        return float(v) if isinstance(v, (int, float)) else None

    loadexp = data.get("loadingExperience") or {}
    metrics = (loadexp.get("metrics") or {})
    def cwv(key: str) -> Optional[dict]:
        m = metrics.get(key)
        if not m:
            return None
        return {"p75": m.get("percentile"), "category": m.get("category")}

    return {
        "strategy": strategy,
        "final_url": lh.get("finalDisplayedUrl") or lh.get("finalUrl"),
        "fetched_at": lh.get("fetchTime"),
        "scores": {
            "performance": pct("performance"),
            "accessibility": pct("accessibility"),
            "best_practices": pct("best-practices"),
            "seo": pct("seo"),
        },
        "lab_metrics": {
            "lcp_ms": num("largest-contentful-paint"),
            "fcp_ms": num("first-contentful-paint"),
            "cls": num("cumulative-layout-shift"),
            "tbt_ms": num("total-blocking-time"),
            "ttfb_ms": num("server-response-time"),
            "speed_index_ms": num("speed-index"),
            "interactive_ms": num("interactive"),
        },
        "field_cwv": {
            "lcp": cwv("LARGEST_CONTENTFUL_PAINT_MS"),
            "fcp": cwv("FIRST_CONTENTFUL_PAINT_MS"),
            "cls": cwv("CUMULATIVE_LAYOUT_SHIFT_SCORE"),
            "inp": cwv("INTERACTION_TO_NEXT_PAINT"),
            "ttfb": cwv("EXPERIMENTAL_TIME_TO_FIRST_BYTE"),
        },
        "overall_category": loadexp.get("overall_category"),
    }
