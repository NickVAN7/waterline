"""Shared router dependencies (`app/routers/deps.py`) not covered by the authz spec tests: the
authorization context is loaded once per request, however many dependencies use it (build plan,
"Authorization (§5)": "loaded once per request and reused by every check"), and `authorized`
authenticates before its loader runs."""

import uuid
from typing import Annotated

import pytest
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.context import AuthzContext
from app.authz.target import Target
from app.core.db import SessionMaker
from app.core.errors import NotFoundError
from app.core.settings import Settings
from app.main import create_app
from app.models.project import Project
from app.routers.deps import AuthzContextDep, authorized
from app.services.auth import AuthService, SignedInUser
from tests.factories.user import UserFactory
from tests.support.api import api_client
from tests.support.authz import sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.security]


async def test_the_authorization_context_is_loaded_once_per_request(
    settings: Settings,
    sessionmaker: SessionMaker,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loads: list[SignedInUser] = []
    load = AuthService.authz_context

    async def counting(self: AuthService, user: SignedInUser) -> AuthzContext:
        loads.append(user)
        return await load(self, user)

    monkeypatch.setattr(AuthService, "authz_context", counting)
    app = create_app(settings, sessionmaker=sessionmaker)

    async def first(ctx: AuthzContextDep) -> AuthzContext:
        return ctx

    @app.get("/api/test/two-uses")
    async def two_uses(
        a: Annotated[AuthzContext, Depends(first)], b: AuthzContextDep
    ) -> dict[str, bool]:
        return {"same": a is b}

    user = await UserFactory.create_async()
    async with api_client(app) as client:
        await sign_in_as(client, user)
        response = await client.get("/api/test/two-uses")

    assert response.json() == {"same": True}
    assert len(loads) == 1


async def test_authorized_authenticates_before_it_loads_anything(
    settings: Settings, sessionmaker: SessionMaker, session: AsyncSession
) -> None:
    """Design-doc §5's order (authenticate, then authorize): an unauthenticated request never
    reaches the loader, so even a loader raising its own 404 can't tell a caller with no session
    which IDs exist."""
    calls: list[uuid.UUID] = []

    async def strict_loader(project_id: uuid.UUID) -> tuple[Project, Target] | None:
        calls.append(project_id)
        raise NotFoundError

    app = create_app(settings, sessionmaker=sessionmaker)

    @app.get("/api/test/strict/{project_id}")
    async def strict(
        project: Annotated[Project, Depends(authorized(strict_loader, "test_project.view"))],
    ) -> None:
        pass

    async with api_client(app) as client:
        response = await client.get(f"/api/test/strict/{uuid.uuid4()}")

    assert (response.status_code, response.json()["code"]) == (401, "not_authenticated")
    assert calls == []
