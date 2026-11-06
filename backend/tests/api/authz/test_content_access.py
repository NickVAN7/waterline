"""The export-control gate over HTTP (S2-C4; design-doc §3.1, "Export-controlled projects (who
sees content)"; §5, "The choke point": the gate, personal actions, 404 not 403;
testing-strategy.md, "Security": inherited admins without an explicit membership get 404 for
every content action, read or mutation, and are allowed management actions; explicit members are
allowed), through the test-only content router in tests/support/content.py.

Each persona is a real user relative to the export-controlled project "Payments" (PMT) of org
"Bolt Foods" in workspace "Acme Consulting" (tests/support/authz.py, `persona_user`).
"""

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionMaker
from app.core.settings import Settings
from app.enums import ProjectRole
from app.main import create_app
from app.models.project import Project
from app.models.user import User
from tests.factories.org import OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.workspace import WorkspaceFactory
from tests.support.api import api_client
from tests.support.authz import Tenancy, persona_user, sign_in_as
from tests.support.content import register_content_actions, router

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

INHERITED_ADMINS = ["system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"]
DESCRIPTION = "Card refunds"


@pytest.fixture
async def client(
    settings: Settings, sessionmaker: SessionMaker, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    register_content_actions(monkeypatch)
    app = create_app(settings, sessionmaker=sessionmaker)
    app.include_router(router)
    async with api_client(app) as c:
        yield c


async def ec_tenancy() -> Tenancy:
    """ "Payments" (PMT) is export-controlled; "Operations" (OPS), in the same org, isn't."""
    workspace = await WorkspaceFactory.create_async(name="Acme Consulting", slug="acme")
    org = await OrganizationFactory.create_async(
        workspace=workspace, name="Bolt Foods", slug="bolt-foods"
    )
    project = await ProjectFactory.create_async(
        organization=org,
        key="PMT",
        name="Payments",
        description=DESCRIPTION,
        restriction_categories=["export_controlled"],
    )
    await ProjectFactory.create_async(
        organization=org, key="OPS", name="Operations", restriction_categories=[]
    )
    return Tenancy(workspace, org, project)


async def signed_in(client: AsyncClient, who: str) -> tuple[Tenancy, User]:
    t = await ec_tenancy()
    user = await persona_user(t, who)
    await sign_in_as(client, user)
    return t, user


async def with_viewer_membership(t: Tenancy, user: User) -> None:
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.VIEWER
    )


async def stored(session: AsyncSession, t: Tenancy) -> tuple[str, str | None]:
    """The project's name and description, read again from the database."""
    row = (
        await session.execute(
            select(Project.name, Project.description).where(Project.id == t.project.id)
        )
    ).one()
    return row.name, row.description


def items(t: Tenancy) -> str:
    return f"/test/content/projects/{t.project.id}/items"


def missing_items() -> str:
    return f"/test/content/projects/{uuid.uuid4()}/items"


def assert_hidden(response: Response, missing: Response) -> None:
    """404 `not_found`, the same body as for a project that doesn't exist, naming nothing."""
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    for name in ("Bolt Foods", "bolt-foods", "Payments", "PMT", DESCRIPTION):
        assert name not in response.text


# --- Content read ------------------------------------------------------------------------------


@pytest.mark.parametrize("who", ["project_admin", "project_member", "project_viewer"])
async def test_explicit_members_read_an_export_controlled_projects_content(
    client: AsyncClient, who: str
) -> None:
    t, _ = await signed_in(client, who)

    response = await client.get(items(t))

    assert (response.status_code, response.json()) == (
        200,
        {"id": str(t.project.id), "name": "Payments"},
    )


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_inherited_admins_get_404_reading_an_export_controlled_projects_content(
    client: AsyncClient, who: str
) -> None:
    t, _ = await signed_in(client, who)

    response = await client.get(items(t))

    assert_hidden(response, await client.get(missing_items()))


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_an_inherited_admin_with_an_explicit_membership_reads_the_content(
    client: AsyncClient, who: str
) -> None:
    t, user = await signed_in(client, who)
    await with_viewer_membership(t, user)

    response = await client.get(items(t))

    assert (response.status_code, response.json()["name"]) == (200, "Payments")


# --- Content mutation --------------------------------------------------------------------------


@pytest.mark.parametrize("who", ["project_admin", "project_member"])
async def test_explicit_members_change_an_export_controlled_projects_content(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)

    response = await client.post(items(t), json={"text": "Edited"})

    assert response.status_code == 200
    assert await stored(session, t) == ("Payments", "Edited")


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_inherited_admins_get_404_changing_content_and_nothing_changes(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)

    response = await client.post(items(t), json={"text": "Edited"})

    assert_hidden(response, await client.post(missing_items(), json={"text": "Edited"}))
    assert await stored(session, t) == ("Payments", DESCRIPTION)


async def test_a_viewer_gets_403_changing_content_and_nothing_changes(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A viewer sees the content but may not edit it: 403, not 404."""
    t, _ = await signed_in(client, "project_viewer")

    response = await client.post(items(t), json={"text": "Edited"})

    assert (response.status_code, response.json()["code"]) == (403, "forbidden")
    assert await stored(session, t) == ("Payments", DESCRIPTION)


# --- Personal action ---------------------------------------------------------------------------


def own_item(t: Tenancy, author: uuid.UUID) -> str:
    return f"/test/content/projects/{t.project.id}/own-item?author={author}"


async def test_an_explicit_viewer_takes_a_personal_action_on_their_own_item(
    client: AsyncClient, session: AsyncSession
) -> None:
    t, user = await signed_in(client, "project_viewer")

    response = await client.post(own_item(t, user.id), json={"text": "Mine"})

    assert response.status_code == 200
    assert await stored(session, t) == ("Payments", "Mine")


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_an_inherited_admin_gets_404_for_a_personal_action_without_content_access(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5: the relationship holds, but content access on an export-controlled project needs an
    explicit membership."""
    t, user = await signed_in(client, who)

    response = await client.post(own_item(t, user.id), json={"text": "Mine"})

    missing = await client.post(
        f"/test/content/projects/{uuid.uuid4()}/own-item?author={user.id}", json={"text": "Mine"}
    )
    assert_hidden(response, missing)
    assert await stored(session, t) == ("Payments", DESCRIPTION)


async def test_an_explicit_member_gets_403_for_someone_elses_item(
    client: AsyncClient, session: AsyncSession
) -> None:
    t, _ = await signed_in(client, "project_admin")

    response = await client.post(own_item(t, uuid.uuid4()), json={"text": "Mine"})

    assert (response.status_code, response.json()["code"]) == (403, "forbidden")
    assert await stored(session, t) == ("Payments", DESCRIPTION)


# --- Management action -------------------------------------------------------------------------


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_inherited_admins_manage_an_export_controlled_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§3.1: inherited admins keep management access."""
    t, _ = await signed_in(client, who)

    response = await client.post(
        f"/test/content/projects/{t.project.id}/manage", json={"text": "Payments Hub"}
    )

    assert (response.status_code, response.json()["name"]) == (200, "Payments Hub")
    assert await stored(session, t) == ("Payments Hub", DESCRIPTION)


async def test_a_member_gets_403_managing_the_project(
    client: AsyncClient, session: AsyncSession
) -> None:
    t, _ = await signed_in(client, "project_member")

    response = await client.post(
        f"/test/content/projects/{t.project.id}/manage", json={"text": "Payments Hub"}
    )

    assert (response.status_code, response.json()["code"]) == (403, "forbidden")
    assert await stored(session, t) == ("Payments", DESCRIPTION)


# --- Content-scoped list -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("who", "expected"),
    [
        ("system_admin", ["OPS"]),
        ("workspace_owner", ["OPS"]),
        ("workspace_admin", ["OPS"]),
        ("org_owner", ["OPS"]),
        ("org_admin", ["OPS"]),
        ("project_admin", ["PMT"]),
        ("project_viewer", ["PMT"]),
    ],
)
async def test_the_content_list_holds_export_controlled_projects_only_for_explicit_members(
    client: AsyncClient, who: str, expected: list[str]
) -> None:
    await signed_in(client, who)

    response = await client.get("/test/content/projects")

    assert (response.status_code, response.json()["keys"]) == (200, expected)


async def test_the_content_list_holds_the_project_for_an_admin_with_an_explicit_membership(
    client: AsyncClient,
) -> None:
    t, user = await signed_in(client, "org_admin")
    await with_viewer_membership(t, user)

    response = await client.get("/test/content/projects")

    assert (response.status_code, response.json()["keys"]) == (200, ["OPS", "PMT"])
