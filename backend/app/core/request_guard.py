"""CSRF defenses that run before anything else (design-doc §4, "Slice 1 security checklist"):
the `Origin` check on every mutating request, then the JSON-only check on every request with a
body. Both run before routing, authentication, and body parsing, so a rejected request never
touches a session.
"""

from urllib.parse import SplitResult, urlsplit

from fastapi import status
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.errors import error_response

MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Endpoints that authenticate their caller another way and carry no browser session. Adding
# one needs the owner's approval, recorded in design-doc §4 (only the GitHub webhook, Slice 7).
ORIGIN_EXEMPT_PATHS: frozenset[str] = frozenset()

_DEFAULT_PORTS = {"http": 80, "https": 443}


def _header(scope: Scope, name: bytes) -> str | None:
    """The header's value, or None when it's missing or sent more than once (ambiguous)."""
    values = [value for key, value in scope["headers"] if key == name]
    return values[0].decode("latin-1") if len(values) == 1 else None


def _bare_authority(parts: SplitResult) -> bool:
    """Just a host and an optional port: no user info, path, query, or fragment."""
    return (
        parts.hostname is not None
        and parts.username is None
        and not (parts.path or parts.query or parts.fragment)
    )


def origin_matches_host(origin: str | None, host: str | None) -> bool:
    """Whether `Origin` names this request's own `Host`: equal hostnames (ignoring case) and
    equal ports, a side with no port taking the default of the `Origin`'s scheme. Anything it
    can't compare (missing, `null`, another scheme, unparseable) is a mismatch."""
    if not origin or not host:
        return False
    try:
        origin_parts = urlsplit(origin)
        host_parts = urlsplit(f"//{host}")
        origin_port, host_port = origin_parts.port, host_parts.port
    except ValueError:  # a bad port or bracketed host
        return False
    default_port = _DEFAULT_PORTS.get(origin_parts.scheme)
    if default_port is None or not (_bare_authority(origin_parts) and _bare_authority(host_parts)):
        return False
    return origin_parts.hostname == host_parts.hostname and (
        default_port if origin_port is None else origin_port
    ) == (default_port if host_port is None else host_port)


def _has_body(scope: Scope) -> bool:
    length = _header(scope, b"content-length")
    chunked = any(key == b"transfer-encoding" for key, _ in scope["headers"])
    return chunked or (length is not None and length.strip() != "0")


def _is_json(content_type: str | None) -> bool:
    """`application/json`, with or without parameters such as `; charset=utf-8`."""
    return (
        content_type is not None
        and content_type.split(";", 1)[0].strip().lower() == "application/json"
    )


class RequestGuardMiddleware:
    """403 `origin_rejected` for a mutating request whose `Origin` doesn't match its `Host`
    (unless its path is exempt); then 415 `unsupported_media_type` for a body that isn't JSON."""

    def __init__(self, app: ASGIApp, exempt_paths: frozenset[str] = ORIGIN_EXEMPT_PATHS) -> None:
        self.app = app
        self.exempt_paths = exempt_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if (
            scope["method"] in MUTATING_METHODS
            and scope["path"] not in self.exempt_paths
            and not origin_matches_host(_header(scope, b"origin"), _header(scope, b"host"))
        ):
            response = error_response(
                status.HTTP_403_FORBIDDEN,
                "origin_rejected",
                "This request didn't come from this site.",
            )
        elif _has_body(scope) and not _is_json(_header(scope, b"content-type")):
            response = error_response(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                "unsupported_media_type",
                "Send the request body as JSON.",
            )
        else:
            await self.app(scope, receive, send)
            return
        await response(scope, receive, send)
