from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest

# Configure environment BEFORE app modules import settings.
# Force a hermetic config: tests must never touch real external APIs, even if a
# developer has a populated .env on disk (pydantic-settings reads it otherwise).
os.environ["APP_ENV"] = "testing"
os.environ["DEBUG"] = "true"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_requisition.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["API_KEY"] = "test-key"
os.environ["RUN_EMBEDDED_WORKER"] = "false"
os.environ["ALLOW_PRIVATE_NETWORK_RESEARCH"] = "false"
os.environ["RETRY_BASE_DELAY_SECONDS"] = "0"
os.environ["MAX_RETRY_DELAY_SECONDS"] = "0"
os.environ["PLAYWRIGHT_ENABLED"] = "false"
for _k in ("GOOGLE_MAPS_API_KEY", "BRAVE_SEARCH_API_KEY", "TAVILY_API_KEY", "GROQ_API_KEY"):
    os.environ[_k] = ""

import fakeredis.aioredis  # noqa: E402

from app.core import redis as redis_mod  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db import session as db_session_mod  # noqa: E402
from app.db.models import Base  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
async def _database() -> AsyncIterator[None]:
    engine = db_session_mod.get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
def _no_real_providers():
    """Default: no discovery providers. Tests that need them set their own factory."""
    from app.discovery.registry import set_provider_factory

    set_provider_factory(lambda: [])
    yield
    set_provider_factory(None)


@pytest.fixture(autouse=True)
async def _fake_redis() -> AsyncIterator[None]:
    from app.workers import queue as queue_mod

    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    redis_mod.set_redis_client(client)
    queue_mod.set_queue_backend(None)
    yield
    await client.aclose()
    redis_mod.set_redis_client(None)
    queue_mod.set_queue_backend(None)


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:  # noqa: F821
    import httpx

    from app.main import create_app

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers={"X-API-Key": "test-key"}
    ) as c:
        # trigger lifespan manually
        async with app.router.lifespan_context(app):
            yield c


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:  # noqa: F821
    maker = db_session_mod.get_sessionmaker()
    async with maker() as s:
        yield s
