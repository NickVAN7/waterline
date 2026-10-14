"""The `Origin` and JSON-only checks (design-doc §4; testing-strategy.md, "Specialized tests"),
on the middleware alone, with raw ASGI requests (so a missing `Host` can be sent)."""

import json

import pytest
from starlette.types import Message, Receive, Scope, Send

from app.core.request_guard import RequestGuardMiddleware, origin_matches_host

pytestmark = [pytest.mark.anyio, pytest.mark.security]


@pytest.mark.parametrize(
    ("host", "origin"),
    [
        ("x", "https://x"),
        ("x", "http://x"),
        ("x:443", "https://x"),
        ("x:80", "http://x"),
        ("x", "https://x:443"),
        ("x:8000", "http://x:8000"),
        ("X", "https://x"),
        ("x", "HTTPS://X"),
        ("[::1]:8000", "http://[::1]:8000"),
    ],
)
def test_an_origin_naming_the_requests_own_host_matches(host: str, origin: str) -> None:
    assert origin_matches_host(origin, host) is True


@pytest.mark.parametrize(
    ("host", "origin"),
    [
        ("x", "https://y"),
        ("x.example", "https://x.example.evil"),
        ("x:8000", "https://x"),
        ("x", "https://x:8000"),
        ("x:443", "http://x"),
        ("x", "null"),
        ("x", "file://x"),
        ("x", "ftp://x"),
        ("x", "https://x:99999"),
        ("x", "https://x:port"),
        ("x", "https://[::1"),
        ("x", "https://"),
        ("x", "https://x/path"),
        ("x", "https://x?q=1"),
        ("x", "https://user@x"),
        ("x", "x"),
        ("x", ""),
        ("x:port", "https://x"),
        ("x/path", "https://x"),
        ("user@x", "https://x"),
        ("", "https://x"),
    ],
)
def test_an_origin_that_cant_be_compared_or_differs_is_rejected(host: str, origin: str) -> None:
    assert origin_matches_host(origin, host) is False


def test_a_missing_origin_or_host_is_rejected() -> None:
    assert origin_matches_host(None, "x") is False
    assert origin_matches_host("https://x", None) is False


class Downstream:
    """The app behind the middleware: records whether a request reached it."""

    def __init__(self) -> None:
        self.reached = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.reached = True
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})


async def call(
    method: str,
    headers: list[tuple[str, str]],
    *,
    path: str = "/api/anything",
    exempt_paths: frozenset[str] = frozenset(),
) -> tuple[int, dict[str, object] | None, bool]:
    """Send one request through the middleware: the status, the JSON body (if any), and whether
    it reached the app."""
    downstream = Downstream()
    middleware = RequestGuardMiddleware(downstream, exempt_paths=exempt_paths)
    scope: Scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [(name.encode(), value.encode()) for name, value in headers],
    }
    sent: list[Message] = []

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        sent.append(message)

    await middleware(scope, receive, send)
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return sent[0]["status"], json.loads(body) if body else None, downstream.reached


MATCHING = [("host", "x"), ("origin", "https://x")]


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_every_mutating_method_with_a_matching_origin_passes(method: str) -> None:
    status, _, reached = await call(method, MATCHING)

    assert (status, reached) == (200, True)


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize(
    "headers",
    [
        [("host", "x"), ("origin", "https://y")],
        [("host", "x")],
        [("host", "x"), ("origin", "null")],
        [("origin", "https://x")],
        [("host", "x"), ("origin", "https://x"), ("origin", "https://x")],
        [("host", "x"), ("host", "x"), ("origin", "https://x")],
    ],
    ids=["other-host", "no-origin", "null-origin", "no-host", "two-origins", "two-hosts"],
)
async def test_every_mutating_method_without_a_matching_origin_is_403(
    method: str, headers: list[tuple[str, str]]
) -> None:
    status, body, reached = await call(method, headers)

    assert (status, reached) == (403, False)
    assert body is not None
    assert body["code"] == "origin_rejected"


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
async def test_a_safe_method_needs_no_origin(method: str) -> None:
    status, _, reached = await call(method, [("host", "x")])

    assert (status, reached) == (200, True)


async def test_an_exempt_path_needs_no_origin() -> None:
    status, _, reached = await call(
        "POST", [("host", "x")], path="/api/hook", exempt_paths=frozenset({"/api/hook"})
    )

    assert (status, reached) == (200, True)


async def test_the_exemption_list_is_empty_until_the_github_webhook() -> None:
    """design-doc §4: an exempt endpoint needs the owner's approval; none exists before Slice 7."""
    status, _, reached = await call("POST", [("host", "x")], path="/api/github/webhook")

    assert (status, reached) == (403, False)


@pytest.mark.parametrize(
    "content_type",
    ["application/json", "application/json; charset=utf-8", "Application/JSON"],
)
async def test_a_json_body_passes(content_type: str) -> None:
    headers = [*MATCHING, ("content-length", "2"), ("content-type", content_type)]

    status, _, reached = await call("POST", headers)

    assert (status, reached) == (200, True)


@pytest.mark.parametrize(
    "headers",
    [
        [("content-length", "9"), ("content-type", "application/x-www-form-urlencoded")],
        [("content-length", "9"), ("content-type", "text/plain")],
        [("content-length", "9"), ("content-type", "multipart/form-data; boundary=b")],
        [("content-length", "9"), ("content-type", "application/jsonp")],
        [("content-length", "9")],
        [("transfer-encoding", "chunked"), ("content-type", "text/plain")],
    ],
    ids=["form", "text", "multipart", "jsonp", "no-type", "chunked"],
)
async def test_a_body_that_isnt_json_is_415(headers: list[tuple[str, str]]) -> None:
    status, body, reached = await call("POST", [*MATCHING, *headers])

    assert (status, reached) == (415, False)
    assert body is not None
    assert body["code"] == "unsupported_media_type"


@pytest.mark.parametrize(
    "headers", [[], [("content-length", "0")], [("content-length", "0"), ("content-type", "x/y")]]
)
async def test_a_mutation_with_no_body_passes(headers: list[tuple[str, str]]) -> None:
    status, _, reached = await call("DELETE", [*MATCHING, *headers])

    assert (status, reached) == (200, True)


async def test_the_origin_check_runs_before_the_json_check() -> None:
    headers = [("host", "x"), ("content-length", "9"), ("content-type", "text/plain")]

    status, body, _ = await call("POST", headers)

    assert status == 403
    assert body is not None
    assert body["code"] == "origin_rejected"


async def test_non_http_scopes_pass_through() -> None:
    reached: list[str] = []

    async def lifespan_app(scope: Scope, receive: Receive, send: Send) -> None:
        reached.append(scope["type"])

    middleware = RequestGuardMiddleware(lifespan_app)

    async def receive() -> Message:
        return {"type": "lifespan.startup"}

    async def send(message: Message) -> None:
        pass

    await middleware({"type": "lifespan"}, receive, send)

    assert reached == ["lifespan"]
