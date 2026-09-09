from __future__ import annotations

import pytest

from app.core.config import Settings, validate_runtime


def test_missing_database_url_is_mandatory():
    s = Settings(database_url="", redis_url="redis://x")
    missing = dict(s.missing_mandatory())
    assert "DATABASE_URL" in missing


def test_production_requires_api_key():
    s = Settings(app_env="production", api_key=None)
    assert any(v == "API_KEY" for v, _ in s.missing_mandatory())


def test_validate_runtime_exits_on_missing(capsys):
    s = Settings(database_url="", redis_url="")
    with pytest.raises(SystemExit):
        validate_runtime(s)
    out = capsys.readouterr().err
    assert "CONFIGURATION ERROR" in out
    assert "DATABASE_URL" in out


def test_postgres_url_normalised_to_async():
    s = Settings(database_url="postgresql://u:p@h:5432/db")
    assert s.database_url.startswith("postgresql+asyncpg://")


def test_capability_summary_reflects_keys():
    s = Settings(google_maps_api_key="k", brave_search_api_key=None, groq_api_key="g")
    caps = s.capability_summary()
    assert caps["google_places_discovery"] is True
    assert caps["brave_discovery"] is False
    assert caps["duckduckgo_discovery"] is True
    assert caps["llm_evaluation_and_outreach"] is True
