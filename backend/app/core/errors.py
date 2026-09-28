"""HTTP error responses in the standard `{code, message, details}` shape.

S0-C5 adds the 409 for stale versions; S0-C6 builds the rest of the error format and handlers
(404, 403, 422) here.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm.exc import StaleDataError


def error_body(
    code: str, message: str, details: dict[str, object] | None = None
) -> dict[str, object]:
    return {"code": code, "message": message, "details": details or {}}


async def stale_version_handler(_request: Request, _exc: Exception) -> JSONResponse:
    """Someone else saved the item after this client loaded it; the UI prompts a reload."""
    return JSONResponse(
        status_code=409,
        content=error_body(
            "stale_version",
            "This item was changed by someone else after you loaded it. Reload it and try again.",
        ),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StaleDataError, stale_version_handler)
