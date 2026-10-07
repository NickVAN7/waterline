"""HTTP error responses in the standard `{code, message, details}` shape (build-plan, "API
foundations").

Services and repositories raise an `AppError` subclass; the handlers registered here turn it,
FastAPI's request validation errors, Starlette's own HTTP errors (unknown route, wrong method),
and SQLAlchemy's stale-row errors into that shape; anything else becomes a 500 in the same shape.
Clients branch on `code`, never on `message`.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, ClassVar, cast

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.base_model import StaleVersionError, VersionMixin

logger = logging.getLogger(__name__)


class ErrorBody(BaseModel):
    """The body of every error response. `details` depends on `code` (e.g. `fields` for
    `validation_error`)."""

    code: str
    message: str
    details: dict[str, Any]


def error_body(
    code: str, message: str, details: dict[str, object] | None = None
) -> dict[str, object]:
    return {"code": code, "message": message, "details": details or {}}


def error_response(
    status_code: int, code: str, message: str, details: dict[str, object] | None = None
) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=error_body(code, message, details))


# --- Errors the app raises --------------------------------------------------------------------


@dataclass(frozen=True)
class FieldError:
    """One invalid field: where it is (`("query", "sort")`, `("body", "email")`), what's wrong in
    words, and a machine-readable type (`taken`, `invalid_sort`, ...)."""

    loc: tuple[str | int, ...]
    message: str
    type: str


class AppError(Exception):
    """Base for errors that map to an HTTP response. Subclasses set the status, code, and
    default message; a raise site may pass a more specific message, code, or details."""

    status_code: ClassVar[int] = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: ClassVar[str] = "internal_error"
    message: ClassVar[str] = "Something went wrong."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        self.error_message = message or self.message
        self.error_code = code or self.code
        self.details = details or {}
        super().__init__(self.error_message)


class NotFoundError(AppError):
    """The entity doesn't exist, or the caller may not see it (404, not 403, so existence
    isn't leaked; design-doc §5)."""

    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "Not found."


class ForbiddenError(AppError):
    """The caller can see the entity but may not do this to it. A specific code (e.g.
    `password_change_required`) tells the client what to do next."""

    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    message = "You don't have permission to do this."


class ValidationFailedError(AppError):
    """422 `validation_error` raised by the app (a query value the endpoint can't use, a
    constraint violation), in the same shape as FastAPI's request validation: one
    `{loc, message, type}` entry per field in `details.fields`, so the frontend has one parser."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "validation_error"
    message = "The request is invalid."

    def __init__(self, fields: list[FieldError], message: str | None = None) -> None:
        super().__init__(
            message,
            details={
                "fields": [
                    {"loc": list(field.loc), "message": field.message, "type": field.type}
                    for field in fields
                ]
            },
        )


class ServiceUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "service_unavailable"
    message = "The service is temporarily unavailable."


# --- Stale rows: 409 for a version conflict, 404 for a row that's gone -------------------------

STALE_VERSION_MESSAGE = (
    "This item was changed by someone else after you loaded it. Reload it and try again."
)

# SQLAlchemy's wording when an UPDATE or DELETE by primary key matches fewer rows than expected.
_STALE_TABLE = re.compile(r"^(?:UPDATE|DELETE) statement on table '([^']+)' expected to")


def stale_table(exc: StaleDataError) -> str | None:
    """The table named in SQLAlchemy's stale-row error, or None if the wording can't be read."""
    match = _STALE_TABLE.match(str(exc))
    return match.group(1) if match else None


def versioned_class_for(table: str) -> type[VersionMixin] | None:
    """The `VersionMixin` model mapped to `table`, if any."""
    pending: list[type] = [VersionMixin]
    while pending:
        cls = pending.pop()
        pending.extend(cls.__subclasses__())
        mapped = getattr(cls, "__table__", None)
        if mapped is not None and mapped.name == table:
            return cls
    return None


def is_version_conflict(exc: StaleDataError) -> bool:
    """True when the stale row is on a versioned table (someone saved it after this client
    loaded it); False when a non-versioned row matched nothing, i.e. it's gone (e.g. hard-deleted
    meanwhile). An error whose table can't be read is treated as a version conflict."""
    if isinstance(exc, StaleVersionError):
        return True
    table = stale_table(exc)
    return table is None or versioned_class_for(table) is not None


# --- Handlers ---------------------------------------------------------------------------------


async def app_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    return app_error_handler_response(cast(AppError, exc))  # registered for AppError only


async def stale_data_handler(_request: Request, exc: Exception) -> JSONResponse:
    exc = cast(StaleDataError, exc)
    if is_version_conflict(exc):
        return error_response(status.HTTP_409_CONFLICT, "stale_version", STALE_VERSION_MESSAGE)
    return error_response(status.HTTP_404_NOT_FOUND, NotFoundError.code, NotFoundError.message)


def violated_constraint(exc: IntegrityError) -> str | None:
    """The name of the constraint an `IntegrityError` reports (psycopg's diagnostics), if any."""
    diag = getattr(exc.orig, "diag", None)
    name = getattr(diag, "constraint_name", None)
    return name if isinstance(name, str) else None


async def integrity_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """A constraint violation the registry maps (`app.state.constraint_errors`, built from each
    constraint's `user_error(...)`) is a 422 field error; any other is a 500, logged, as if
    unhandled (build plan, "Errors from constraints")."""
    exc = cast(IntegrityError, exc)
    registry: dict[str, Any] = getattr(request.app.state, "constraint_errors", {})
    name = violated_constraint(exc)
    mapped = registry.get(name) if name else None
    if mapped is None:
        # Only the constraint name and Postgres's primary message: its DETAIL, and the
        # traceback's statement text, can hold the clashing value (a token's hash, an email).
        diag = getattr(exc.orig, "diag", None)
        logger.error(
            "Unmapped constraint violation (%s: %s) on %s %s",
            name,
            getattr(diag, "message_primary", None),
            request.method,
            request.url.path,
        )
        return error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR, AppError.code, AppError.message
        )
    return app_error_handler_response(ValidationFailedError([mapped.as_field_error()]))


def app_error_handler_response(exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.error_code, exc.error_message, exc.details)


async def validation_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """422 with one entry per invalid field, so the UI can show each next to its input."""
    exc = cast(RequestValidationError, exc)
    fields = [
        {"loc": list(error["loc"]), "message": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "validation_error",
        "The request is invalid.",
        {"fields": jsonable_encoder(fields)},
    )


_HTTP_CODES: dict[int, tuple[str, str]] = {
    status.HTTP_404_NOT_FOUND: (NotFoundError.code, NotFoundError.message),
    status.HTTP_405_METHOD_NOT_ALLOWED: ("method_not_allowed", "Method not allowed."),
}


async def http_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Starlette's own errors (an unknown route, a wrong method) in the standard shape."""
    exc = cast(StarletteHTTPException, exc)
    code, message = _HTTP_CODES.get(exc.status_code, ("http_error", str(exc.detail)))
    response = error_response(exc.status_code, code, message)
    if exc.headers:
        response.headers.update(exc.headers)
    return response


class UnhandledErrorMiddleware:
    """An exception no handler covers becomes a 500 `internal_error` in the standard body, and is
    logged here with its traceback; nothing about it reaches the client. (Starlette's fallback
    returns plain text.) If the response has already started, the status can't change: the
    exception is re-raised for the server to log and close the connection."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def send_tracking_start(message: Message) -> None:
            nonlocal started
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, receive, send_tracking_start)
        except Exception:
            if started:
                raise
            logger.exception("Unhandled error on %s %s", scope["method"], scope["path"])
            response = error_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR, AppError.code, AppError.message
            )
            await response(scope, receive, send)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StaleDataError, stale_data_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_middleware(UnhandledErrorMiddleware)
