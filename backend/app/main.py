"""FastAPI application factory: settings, database, error handlers, router registration.
Run with `uvicorn --factory app.main:create_app`."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from app import models  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers every model
from app.core.base_model import Base
from app.core.constraint_errors import constraint_registry
from app.core.db import SessionMaker, create_engine, create_sessionmaker
from app.core.errors import register_error_handlers
from app.core.request_guard import RequestGuardMiddleware
from app.core.settings import Settings, get_settings
from app.routers import auth, health, org, workspace
from app.rules.identifiers import RESERVED_SLUGS

API_PREFIX = "/api"


def create_app(
    settings: Settings | None = None, *, sessionmaker: SessionMaker | None = None
) -> FastAPI:
    """Build the app. Tests pass their own `sessionmaker` (bound to the test transaction);
    otherwise the app owns an engine for the configured database and disposes it on shutdown."""
    settings = settings or get_settings()
    engine = None
    if sessionmaker is None:
        engine = create_engine(settings.database_url())
        sessionmaker = create_sessionmaker(engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        yield
        if engine is not None:
            await engine.dispose()

    # Everything, docs included, lives under /api so the Vite proxy serves one origin.
    docs = settings.api_docs_enabled
    app = FastAPI(
        title="Waterline",
        openapi_url=f"{API_PREFIX}/openapi.json" if docs else None,
        docs_url=f"{API_PREFIX}/docs" if docs else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.sessionmaker = sessionmaker
    # Every model is imported (app.models), so the registry sees every table's constraints.
    app.state.constraint_errors = constraint_registry(Base.metadata)
    # Added before the error handlers' middleware, so it runs inside it: a crash in the guard
    # still gets the standard 500 body.
    app.add_middleware(RequestGuardMiddleware)
    register_error_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(workspace.router, prefix=API_PREFIX)
    app.include_router(org.router, prefix=API_PREFIX)
    _add_schema_components(app)
    return app


def _add_schema_components(app: FastAPI) -> None:
    """Add to the OpenAPI schema what no route returns but the generated client needs:
    `ReservedSlug`, the top-level routes no slug may take, so the frontend's router test checks
    its routes against them (build plan, Checkpoint 8, DL-55)."""
    build = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            schema = build()
            schema.setdefault("components", {}).setdefault("schemas", {})["ReservedSlug"] = {
                "title": "ReservedSlug",
                "description": "Top-level browser routes: no workspace or org slug may be one.",
                "type": "string",
                "enum": sorted(RESERVED_SLUGS),
            }
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi
