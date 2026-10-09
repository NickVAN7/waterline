"""The API test client (testing-strategy.md, "Specialized tests")."""

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# https: httpx won't send the `Secure` session cookie over http, which would make a signed-in
# test silently unauthenticated.
BASE_URL = "https://testserver"


def api_client(app: FastAPI) -> AsyncClient:
    """A client for `app` that, like a browser, sends this site's `Origin` with every request,
    so mutating requests pass the `Origin` check. A test of the check overrides the header."""
    return AsyncClient(
        transport=ASGITransport(app=app), base_url=BASE_URL, headers={"Origin": BASE_URL}
    )
