"""Safe website fetching for research.

- SSRF guard on the initial URL and on every redirect hop.
- Hard timeout, capped response size, content-type allow-list.
- Never hangs; never follows a redirect into a private network.
- Returns a FetchResult with a classified WebsiteStatus instead of raising for
  ordinary HTTP failures.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from app.core.config import get_settings
from app.core.errors import ErrorCode
from app.core.exceptions import WebsiteError
from app.core.logging import get_logger
from app.core.security import validate_public_url
from app.db.models.enums import WebsiteStatus

log = get_logger(__name__)

_HTML_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
_BLOCKED_TYPES = ("application/pdf", "application/octet-stream", "image/", "video/", "audio/")


@dataclass
class FetchResult:
    requested_url: str
    final_url: str | None = None
    status: WebsiteStatus = WebsiteStatus.UNKNOWN
    http_status: int | None = None
    html: str | None = None
    content_type: str | None = None
    redirected: bool = False
    redirect_chain: list[str] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    elapsed_ms: int = 0

    @property
    def usable_html(self) -> bool:
        return self.status in (WebsiteStatus.ACTIVE, WebsiteStatus.REDIRECTED) and bool(self.html)


def _classify_status(code: int) -> WebsiteStatus:
    if code in (200, 201, 202, 203, 206):
        return WebsiteStatus.ACTIVE
    if code in (301, 302, 303, 307, 308):
        return WebsiteStatus.REDIRECTED
    if code in (401, 403, 429):
        return WebsiteStatus.FORBIDDEN
    if code == 404 or code == 410:
        return WebsiteStatus.NOT_FOUND
    if 500 <= code < 600:
        return WebsiteStatus.SERVER_ERROR
    return WebsiteStatus.UNKNOWN


async def fetch(url: str, *, max_bytes: int | None = None) -> FetchResult:
    settings = get_settings()
    max_bytes = max_bytes or settings.research_max_response_bytes
    timeout = settings.research_http_timeout_seconds
    result = FetchResult(requested_url=url)

    try:
        safe_url = validate_public_url(url)
    except WebsiteError as exc:
        result.status = WebsiteStatus.INVALID
        result.error_code = exc.code.value
        result.error_message = exc.message
        return result

    import time

    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=min(8.0, timeout)),
            headers={
                "User-Agent": settings.research_user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en;q=0.9",
            },
            follow_redirects=False,
            limits=httpx.Limits(max_connections=10),
        ) as client:
            current = safe_url
            for _hop in range(6):
                resp = await client.get(current)
                result.http_status = resp.status_code
                if resp.is_redirect:
                    loc = resp.headers.get("location")
                    if not loc:
                        break
                    current = str(httpx.URL(resp.url).join(loc))
                    try:
                        validate_public_url(current)
                    except WebsiteError as exc:
                        result.status = WebsiteStatus.INVALID
                        result.error_code = ErrorCode.WEBSITE_SSRF_BLOCKED.value
                        result.error_message = f"redirect blocked: {exc.message}"
                        return result
                    result.redirect_chain.append(current)
                    result.redirected = True
                    continue
                break
            else:
                result.status = WebsiteStatus.INVALID
                result.error_message = "too many redirects"
                return result

            result.final_url = str(resp.url)
            result.content_type = (resp.headers.get("content-type") or "").split(";")[0].strip()
            result.status = _classify_status(resp.status_code)

            if any(result.content_type.startswith(b) for b in _BLOCKED_TYPES):
                result.status = WebsiteStatus.INVALID
                result.error_code = ErrorCode.WEBSITE_INVALID.value
                result.error_message = f"non-HTML content-type: {result.content_type}"
                return result

            if result.status in (WebsiteStatus.ACTIVE, WebsiteStatus.REDIRECTED):
                body = b""
                async for chunk in resp.aiter_bytes():
                    body += chunk
                    if len(body) > max_bytes:
                        result.error_code = ErrorCode.WEBSITE_TOO_LARGE.value
                        result.error_message = f"response exceeded {max_bytes} bytes"
                        break
                encoding = resp.encoding or "utf-8"
                try:
                    result.html = body.decode(encoding, errors="replace")
                except (LookupError, UnicodeDecodeError):
                    result.html = body.decode("utf-8", errors="replace")

    except httpx.TimeoutException as exc:
        result.status = WebsiteStatus.TIMEOUT
        result.error_code = ErrorCode.WEBSITE_TIMEOUT.value
        result.error_message = str(exc)
    except httpx.HTTPError as exc:
        result.status = WebsiteStatus.UNKNOWN
        result.error_code = ErrorCode.WEBSITE_INVALID.value
        result.error_message = f"{type(exc).__name__}: {exc}"
    finally:
        result.elapsed_ms = int((time.perf_counter() - t0) * 1000)

    log.info(
        "research.fetch.completed",
        url=url,
        final_url=result.final_url,
        status=result.status.value,
        http_status=result.http_status,
        bytes=len(result.html or ""),
        elapsed_ms=result.elapsed_ms,
    )
    return result
