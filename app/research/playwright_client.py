"""Playwright fallback for JavaScript-rendered sites.

Used ONLY when the plain HTTP fetch returns thin/near-empty content that looks
JS-rendered. Bounded concurrency; every browser/context/page is closed.
"""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.core.errors import ErrorCode
from app.core.exceptions import WebsiteError
from app.core.logging import get_logger
from app.core.security import validate_public_url

log = get_logger(__name__)

_sem: asyncio.Semaphore | None = None


def _semaphore() -> asyncio.Semaphore:
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(max(1, get_settings().research_concurrency // 2 or 1))
    return _sem


async def render(url: str, *, wait_ms: int = 2500) -> tuple[str | None, str | None]:
    """Return (html, error_code). Never raises for runtime failures."""
    settings = get_settings()
    if not settings.playwright_enabled:
        return None, ErrorCode.PLAYWRIGHT_FAILED.value

    try:
        validate_public_url(url)
    except WebsiteError as exc:
        return None, exc.code.value

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None, ErrorCode.PLAYWRIGHT_FAILED.value

    async with _semaphore():
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=settings.playwright_headless)
                try:
                    context = await browser.new_context(
                        user_agent=settings.research_user_agent,
                        viewport={"width": 1280, "height": 900},
                    )
                    page = await context.new_page()
                    await page.goto(url, wait_until="domcontentloaded",
                                    timeout=settings.research_http_timeout_seconds * 1000 * 2)
                    await page.wait_for_timeout(wait_ms)
                    html = await page.content()
                    return html, None
                finally:
                    await browser.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("research.playwright.failed", url=url, error=str(exc))
            return None, ErrorCode.PLAYWRIGHT_FAILED.value


def looks_js_rendered(html: str | None, text_length: int) -> bool:
    if not html:
        return True
    if text_length >= 500:
        return False
    lowered = html.lower()
    markers = ("<div id=\"root\"", "<div id=\"app\"", "__next_data__", "window.__nuxt__",
               "ng-version", "data-reactroot")
    return any(m in lowered for m in markers) or len(html) < 2000
