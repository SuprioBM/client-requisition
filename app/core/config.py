"""Centralised configuration.

Loaded once at startup. `validate_runtime()` produces the human-readable
"CONFIGURATION ERROR" terminal banner for missing *mandatory* settings and a
capability summary for optional/feature-specific ones.
"""

from __future__ import annotations

import sys
from enum import Enum
from functools import lru_cache
from typing import Literal

from pydantic import ValidationError as PydanticValidationError
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(str, Enum):
    development = "development"
    testing = "testing"
    production = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # ---- application ----
    app_env: AppEnv = AppEnv.development
    debug: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    api_key: str | None = None
    # comma-separated allowed origins for the browser dashboard
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # ---- database ----
    database_url: str = "postgresql+asyncpg://requisition:requisition@localhost:5432/requisition"
    supabase_url: str | None = None
    supabase_key: str | None = None

    # ---- redis ----
    redis_url: str = "redis://localhost:6379/0"

    # ---- providers ----
    google_maps_api_key: str | None = None
    brave_search_api_key: str | None = None
    tavily_api_key: str | None = None

    # ---- llm ----
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"

    # ---- research ----
    playwright_headless: bool = True
    playwright_enabled: bool = True
    research_http_timeout_seconds: float = 15.0
    research_max_response_bytes: int = 3_000_000
    research_cache_ttl_seconds: int = 604_800
    research_user_agent: str = "ClientRequisitionAgent/1.0"
    allow_private_network_research: bool = False

    # ---- concurrency / cost ----
    discovery_provider_concurrency: int = 3
    research_concurrency: int = 4
    worker_job_lease_seconds: int = 900
    max_queries_per_plan: int = 6
    retry_base_delay_seconds: float = 2.0
    max_retry_delay_seconds: float = 60.0

    # ---- langgraph ----
    langgraph_checkpoint_db: str | None = None

    # ---- worker ----
    # None -> embedded worker runs inside the API process unless production.
    run_embedded_worker: bool | None = None

    def embedded_worker_enabled(self) -> bool:
        if self.run_embedded_worker is not None:
            return self.run_embedded_worker
        return self.app_env == AppEnv.development

    @field_validator("database_url")
    @classmethod
    def _check_async_driver(cls, v: str) -> str:
        if v.startswith("postgresql://"):
            # normalise to async driver rather than silently failing later
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # ---- capability helpers ----
    @property
    def is_production(self) -> bool:
        return self.app_env == AppEnv.production

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_maps_api_key)

    @property
    def brave_enabled(self) -> bool:
        return bool(self.brave_search_api_key)

    @property
    def tavily_enabled(self) -> bool:
        return bool(self.tavily_api_key)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.groq_api_key)

    def capability_summary(self) -> dict[str, bool]:
        return {
            "google_places_discovery": self.google_enabled,
            "brave_discovery": self.brave_enabled,
            "duckduckgo_discovery": True,  # no key required
            "tavily_research_fallback": self.tavily_enabled,
            "llm_evaluation_and_outreach": self.llm_enabled,
        }

    def missing_mandatory(self) -> list[tuple[str, str]]:
        """Return (env_var, feature) pairs that MUST be present to boot."""
        missing: list[tuple[str, str]] = []
        if not self.database_url:
            missing.append(("DATABASE_URL", "system of record (Postgres/Supabase)"))
        if not self.redis_url:
            missing.append(("REDIS_URL", "job queue and cache"))
        if self.is_production and not self.api_key:
            missing.append(("API_KEY", "authenticated mutating/send endpoints (production)"))
        return missing


def _print_config_banner(missing: list[tuple[str, str]]) -> None:
    line = "=" * 60
    print(line, file=sys.stderr)
    print("CONFIGURATION ERROR", file=sys.stderr)
    print(line, file=sys.stderr)
    for var, feature in missing:
        print(f"\nMissing environment variable:\n  {var}", file=sys.stderr)
        print(f"Feature affected:\n  {feature}", file=sys.stderr)
        print(f"Suggested action:\n  Add {var} to .env", file=sys.stderr)
    print(f"\n{line}", file=sys.stderr)


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except PydanticValidationError as exc:  # malformed values
        line = "=" * 60
        print(f"{line}\nCONFIGURATION ERROR\n{line}", file=sys.stderr)
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            print(f"  {loc}: {err['msg']}", file=sys.stderr)
        print(line, file=sys.stderr)
        raise SystemExit(1) from exc


def validate_runtime(settings: Settings | None = None) -> Settings:
    """Fail fast with a readable banner if mandatory config is missing."""
    settings = settings or get_settings()
    missing = settings.missing_mandatory()
    if missing:
        _print_config_banner(missing)
        raise SystemExit(1)
    return settings
