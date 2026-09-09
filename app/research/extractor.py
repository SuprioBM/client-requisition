"""Clean main-content text extraction via Trafilatura.

Keeps the LLM input small: we send compact extracted text, never raw HTML.
"""

from __future__ import annotations

from app.core.logging import get_logger

log = get_logger(__name__)

_MAX_CHARS = 12_000


def extract_main_text(html: str, url: str) -> str | None:
    try:
        import trafilatura

        text = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            favor_precision=True,
            no_fallback=False,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("research.extract.failed", url=url, error=str(exc))
        return None
    if not text:
        return None
    text = text.strip()
    return text[:_MAX_CHARS] if len(text) > _MAX_CHARS else text
