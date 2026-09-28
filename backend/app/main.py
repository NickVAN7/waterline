"""FastAPI application: router registration (and, from S0-C6, error handlers)."""

from fastapi import FastAPI

from app.routers import health

API_PREFIX = "/api"


def create_app() -> FastAPI:
    # Everything, docs included, lives under /api so the Vite proxy serves one origin.
    app = FastAPI(
        title="Waterline",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )
    app.include_router(health.router, prefix=API_PREFIX)
    return app


app = create_app()
