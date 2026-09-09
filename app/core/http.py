"""Shared async HTTP helpers (provider API calls + website research use these)."""

from __future__ import annotations

import httpx

from app.core.config import get_settings

_DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=8.0)


def build_client(
    *,
    timeout: float | httpx.Timeout | None = None,
    headers: dict[str, str] | None = None,
    follow_redirects: bool = True,
    max_redirects: int = 5,
) -> httpx.AsyncClient:
    settings = get_settings()
    hdrs = {"User-Agent": settings.research_user_agent}
    if headers:
        hdrs.update(headers)
    return httpx.AsyncClient(
        timeout=timeout or _DEFAULT_TIMEOUT,
        headers=hdrs,
        follow_redirects=follow_redirects,
        max_redirects=max_redirects,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )


def classify_http_error(exc: Exception) -> tuple[str, str]:
    """Map an httpx exception to (error_code, human message). Import ErrorCode lazily."""
    from app.core.errors import ErrorCode

    if isinstance(exc, httpx.TimeoutException):
        return ErrorCode.PROVIDER_TIMEOUT.value, f"Request timed out: {exc}"
    if isinstance(exc, httpx.ConnectError):
        return ErrorCode.PROVIDER_UNAVAILABLE.value, f"Connection failed: {exc}"
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (401, 403):
            return ErrorCode.PROVIDER_AUTH_FAILED.value, f"Auth/permission denied (HTTP {code})"
        if code == 429:
            return ErrorCode.PROVIDER_RATE_LIMITED.value, "Rate limited (HTTP 429)"
        if 500 <= code < 600:
            return ErrorCode.PROVIDER_UNAVAILABLE.value, f"Upstream error (HTTP {code})"
        return ErrorCode.PROVIDER_BAD_RESPONSE.value, f"Unexpected response (HTTP {code})"
    return ErrorCode.PROVIDER_UNAVAILABLE.value, f"{type(exc).__name__}: {exc}"
