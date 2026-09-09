"""Tavily — SELECTIVE research fallback.

Only called when direct website research fails or is insufficient. Never part of
primary discovery. Disabled cleanly when TAVILY_API_KEY is absent.
"""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.core.errors import ErrorCode
from app.core.logging import get_logger

log = get_logger(__name__)


def available() -> bool:
    return bool(get_settings().tavily_api_key)


async def search(query: str, *, max_results: int = 5) -> tuple[list[dict], str | None]:
    """Return (results, error_code). results: [{title,url,content,score}]."""
    settings = get_settings()
    if not settings.tavily_api_key:
        return [], ErrorCode.CONFIG_MISSING.value

    def _call() -> list[dict]:
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.tavily_api_key)
        resp = client.search(query=query, max_results=max_results, search_depth="basic")
        return resp.get("results", []) or []

    try:
        results = await asyncio.to_thread(_call)
        log.info("research.tavily.completed", query=query, results=len(results))
        return results, None
    except Exception as exc:  # noqa: BLE001
        log.warning("research.tavily.failed", query=query, error=str(exc))
        msg = str(exc).lower()
        if "401" in msg or "unauthor" in msg or "api key" in msg:
            return [], ErrorCode.LLM_AUTH_FAILED.value
        if "429" in msg or "rate" in msg:
            return [], ErrorCode.PROVIDER_RATE_LIMITED.value
        return [], ErrorCode.PROVIDER_UNAVAILABLE.value
