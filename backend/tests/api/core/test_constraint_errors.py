"""A constraint violation over HTTP (build plan, "Errors from constraints"): mapped → 422 in the
standard field-error shape; unmapped → a logged 500, the request rolled back."""

import logging
import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import Base
from app.core.constraint_errors import constraint_registry
from app.core.db import SessionDep, SessionMaker
from app.core.settings import Settings
from app.main import create_app
from app.models.user import User
from tests.support.api import api_client
from tests.support.models import Record, SupportBase, Widget

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("support_tables")]


def build_app(settings: Settings, sessionmaker: SessionMaker) -> FastAPI:
    app = create_app(settings, sessionmaker=sessionmaker)
    app.state.constraint_errors = constraint_registry(Base.metadata, SupportBase.metadata)

    @app.post("/widgets")
    async def add_widget(name: str, session: SessionDep) -> None:
        session.add(Widget(name=name))
        await session.flush()

    @app.post("/widgets/at-commit")
    async def add_widget_without_flushing(name: str, session: SessionDep) -> None:
        # The violation first fires at the request's commit, in get_session.
        session.add(Widget(name=name))

    @app.post("/widgets/negative")
    async def add_negative_widget(session: SessionDep) -> None:
        session.add(Widget(name="negative", quantity=-1))
        await session.flush()

    @app.post("/records")
    async def add_record(name: str, session: SessionDep) -> None:
        session.add(Record(tenant="mine", name=name))
        await session.flush()

    return app


@pytest.fixture
async def client(settings: Settings, sessionmaker: SessionMaker) -> AsyncIterator[AsyncClient]:
    app = build_app(settings, sessionmaker)
    async with api_client(app) as c:
        yield c


async def test_a_mapped_violation_is_a_422_field_error(
    client: AsyncClient, session: AsyncSession
) -> None:
    await client.post("/widgets?name=bolt")

    response = await client.post("/widgets?name=bolt")

    assert response.status_code == 422
    assert response.json() == {
        "code": "validation_error",
        "message": "The request is invalid.",
        "details": {
            "fields": [{"loc": ["body", "name"], "message": "This name is taken.", "type": "taken"}]
        },
    }
    assert await session.scalar(select(func.count()).select_from(Widget)) == 1


async def test_a_violation_at_commit_is_a_422_field_error(client: AsyncClient) -> None:
    await client.post("/widgets/at-commit?name=nut")

    response = await client.post("/widgets/at-commit?name=nut")

    assert response.status_code == 422
    assert response.json()["details"]["fields"] == [
        {"loc": ["body", "name"], "message": "This name is taken.", "type": "taken"}
    ]


async def test_a_mapped_check_violation_is_a_422_field_error(client: AsyncClient) -> None:
    response = await client.post("/widgets/negative")

    assert response.status_code == 422
    assert response.json()["details"]["fields"] == [
        {
            "loc": ["body", "quantity"],
            "message": "The quantity can't be negative.",
            "type": "out_of_range",
        }
    ]


async def test_an_unmapped_violation_is_a_logged_500(
    client: AsyncClient, session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    await client.post("/records?name=zq7-clash")

    with caplog.at_level(logging.ERROR, logger="app.core.errors"):
        response = await client.post("/records?name=zq7-clash")

    assert response.status_code == 500
    assert response.json() == {
        "code": "internal_error",
        "message": "Something went wrong.",
        "details": {},
    }
    assert "uq_support_record_tenant_name" in caplog.text
    # The clashing value never reaches the log (Postgres's DETAIL names it: "Key (tenant,
    # name)=(mine, zq7-clash)"), nor do bound values: for a session, the token's hash.
    assert "zq7-clash" not in caplog.text
    assert await session.scalar(select(func.count()).select_from(Record)) == 1


async def test_the_real_app_maps_its_own_constraints(
    settings: Settings, sessionmaker: SessionMaker, session: AsyncSession
) -> None:
    # A plain create_app: no registry override. A duplicate email is a field error, not a 500.
    app = create_app(settings, sessionmaker=sessionmaker)

    @app.post("/users")
    async def add_user(email: str, username: str, session: SessionDep) -> None:
        session.add(User(email=email, username=username, name="Ann", hashed_password="x"))
        await session.flush()

    async with api_client(app) as c:
        await c.post("/users?email=ann@example.com&username=ann")
        response = await c.post("/users?email=ann@example.com&username=ann-2")

    assert response.status_code == 422
    assert response.json()["details"]["fields"] == [
        {"loc": ["body", "email"], "message": "This email is already in use.", "type": "taken"}
    ]


async def test_an_unhandled_database_error_never_logs_bound_values(
    settings: Settings, sessionmaker: SessionMaker, caplog: pytest.LogCaptureFixture
) -> None:
    # Any unhandled error is logged with its traceback (UnhandledErrorMiddleware); the engine's
    # hide_parameters keeps SQLAlchemy's copy of the bound values (a token's hash, say) out of
    # it. The error here (division by zero) doesn't quote the value itself, as Postgres would
    # for, e.g., a type error on that value.
    app = create_app(settings, sessionmaker=sessionmaker)
    # Made at runtime, so the traceback's quoted source lines can't contain it.
    sentinel = uuid.uuid4().hex

    @app.get("/broken")
    async def broken(session: SessionDep) -> None:
        await session.execute(text("SELECT length(:value) / :zero"), {"value": sentinel, "zero": 0})

    async with api_client(app) as c:
        with caplog.at_level(logging.ERROR):
            response = await c.get("/broken")

    assert response.status_code == 500
    assert "division by zero" in caplog.text  # the error was logged
    assert sentinel not in caplog.text
