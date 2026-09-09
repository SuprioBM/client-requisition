from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app import __version__
from app.api.errors import install_exception_handlers
from app.api.routes import api_router
from app.core.config import get_settings, validate_runtime
from app.core.logging import bind_contextvars, clear_contextvars, configure_logging, get_logger

log = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = validate_runtime()
    caps = settings.capability_summary()
    log.info("app.startup", version=__version__, env=settings.app_env.value, capabilities=caps)
    for name, enabled in caps.items():
        if not enabled:
            log.warning("capability.disabled", capability=name, reason="missing API key / config")

    if settings.embedded_worker_enabled():
        from app.workers import embedded

        await embedded.start()

    yield

    if settings.embedded_worker_enabled():
        from app.workers import embedded

        await embedded.stop()

    from app.core.redis import close_redis
    from app.db.session import dispose_engine

    await close_redis()
    await dispose_engine()
    log.info("app.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Client Requisition Agent",
        version=__version__,
        description=(
            "Discovers businesses, researches them, detects evidence-backed pain points, "
            "maps them to services, scores the opportunity, and drafts outreach for human approval."
        ),
        lifespan=lifespan,
        debug=settings.debug,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list if settings.is_production else ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def _request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = rid
        clear_contextvars()
        bind_contextvars(request_id=rid, path=request.url.path, method=request.method)
        try:
            response = await call_next(request)
        finally:
            clear_contextvars()
        response.headers["X-Request-ID"] = rid
        return response

    install_exception_handlers(app)
    app.include_router(api_router)

    # minimal operator UI
    _frontend = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
    if _frontend.exists():
        @app.get("/", include_in_schema=False)
        async def _index() -> FileResponse:
            return FileResponse(_frontend)

    return app


app = create_app()
