"""Async Redis accessor with a test-friendly override hook."""

from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

_client: aioredis.Redis | None = None


def set_redis_client(client: aioredis.Redis | None) -> None:
    """Used by tests to inject fakeredis."""
    global _client
    _client = client


def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        url = get_settings().redis_url
        _client = aioredis.from_url(url, encoding="utf-8", decode_responses=True)
        log.info("redis.client.created", url=url.split("@")[-1])
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        finally:
            _client = None


async def ping() -> bool:
    return bool(await get_redis().ping())
