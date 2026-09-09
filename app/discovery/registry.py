"""Provider registry — the single place that decides which providers exist.

Tests monkeypatch `build_discovery_providers` to inject mocks.
"""

from __future__ import annotations

from collections.abc import Callable

from app.core.logging import get_logger
from app.discovery.base import BusinessDiscoveryProvider
from app.discovery.brave import BraveProvider
from app.discovery.duckduckgo import DuckDuckGoProvider
from app.discovery.google_places import GooglePlacesProvider

log = get_logger(__name__)

_factory: Callable[[], list[BusinessDiscoveryProvider]] | None = None


def set_provider_factory(factory: Callable[[], list[BusinessDiscoveryProvider]] | None) -> None:
    global _factory
    _factory = factory


def build_discovery_providers() -> list[BusinessDiscoveryProvider]:
    if _factory is not None:
        return _factory()
    return [GooglePlacesProvider(), DuckDuckGoProvider(), BraveProvider()]
