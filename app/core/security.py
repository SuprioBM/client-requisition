"""API-key auth and URL/SSRF safety helpers."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.core.config import get_settings
from app.core.errors import ErrorCode
from app.core.exceptions import UnauthorizedError, WebsiteError

_BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
}
_CLOUD_METADATA_IPS = {"169.254.169.254", "fd00:ec2::254"}


def verify_api_key(provided: str | None) -> None:
    """Raise UnauthorizedError unless the provided key matches (or auth is disabled in dev)."""
    settings = get_settings()
    if not settings.api_key:
        if settings.is_production:
            raise UnauthorizedError(
                "API key is not configured on the server", code=ErrorCode.CONFIG_MISSING
            )
        return  # dev/testing convenience: auth disabled
    if not provided or provided != settings.api_key:
        raise UnauthorizedError("Invalid or missing API key", code=ErrorCode.UNAUTHORIZED)


def _is_private_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
        or ip in _CLOUD_METADATA_IPS
    )


def validate_public_url(raw_url: str) -> str:
    """Validate a URL is http(s) and does not resolve to a private/internal address.

    Returns the normalised URL. Raises WebsiteError on any violation.
    """
    settings = get_settings()
    parsed = urlparse(raw_url.strip())

    if parsed.scheme not in ("http", "https"):
        raise WebsiteError(
            f"Unsupported URL scheme: {parsed.scheme!r}", code=ErrorCode.WEBSITE_INVALID
        )
    host = parsed.hostname
    if not host:
        raise WebsiteError("URL has no host", code=ErrorCode.WEBSITE_INVALID)

    if settings.allow_private_network_research:
        return raw_url.strip()

    if host.lower() in _BLOCKED_HOSTNAMES:
        raise WebsiteError(
            f"Refusing to research internal host {host!r}", code=ErrorCode.WEBSITE_SSRF_BLOCKED
        )

    # If the host is a literal IP, check it directly (no DNS needed).
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        literal = None
    if literal is not None:
        if _is_private_ip(str(literal)):
            raise WebsiteError(
                f"Host {host!r} is a private/internal address",
                code=ErrorCode.WEBSITE_SSRF_BLOCKED,
                context={"host": host},
            )
        return raw_url.strip()

    # In the test environment we never make real network calls (respx intercepts
    # httpx), so skip DNS resolution which would otherwise fail for fake hosts.
    from app.core.config import AppEnv

    if settings.app_env == AppEnv.testing:
        return raw_url.strip()

    # Resolve every A/AAAA record and reject if any is private.
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise WebsiteError(
            f"Could not resolve host {host!r}", code=ErrorCode.WEBSITE_NOT_FOUND, cause=exc
        ) from exc

    for info in infos:
        ip = info[4][0]
        if _is_private_ip(ip):
            raise WebsiteError(
                f"Host {host!r} resolves to a private/internal address ({ip})",
                code=ErrorCode.WEBSITE_SSRF_BLOCKED,
                context={"host": host, "ip": ip},
            )
    return raw_url.strip()
