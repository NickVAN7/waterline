"""Authorization of S2-C5's requirement endpoints (S2-plan, "Actions per row"; design-doc §5,
"The choke point", "Role capabilities"; §3.1, export-controlled projects; §4 "Visibility"; §9:
archived is read-only, still browsable):

- `POST /api/projects/{key}/requirements` (`requirement.create`, content): 201 for project
  members and up and inherited admins; 403 for a project viewer, and for everyone who sees an
  archived project; 404 (naming nothing) for who can't see the project; on an export-controlled
  project, 404 for inherited admins without an explicit membership, 201 for explicit members and
  admins, 403 for an explicit viewer. A denied create stores nothing;
- `GET /api/projects/{key}/requirements` and `GET /api/projects/{key}/requirements/{number}`
  (`requirement.view`, content): 200 for project viewers and up and inherited admins, live and
  archived; 404 for who can't see the project; on an export-controlled project, 404 for
  inherited admins without an explicit membership, 200 for explicit members;
- the requirement read's `allowed_actions` carry `requirement.create` and `requirement.view` for
  a project member, and no `requirement.create` for a project viewer.

Only authorization outcomes are asserted; numbering, revisions, and rank are the main session's
tests. Personas are relative to workspace "Acme Consulting", org "Bolt Foods" (bolt-foods), and
project "Payments" (PMT) (tests/support/authz.py, `tenancy`, `persona_user`).
"""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.requirement import Requirement
from tests.factories.org import OrganizationFactory
from tests.factories.project import ProjectFactory
from tests.factories.requirement import RequirementFactory
from tests.factories.workspace import WorkspaceFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

INHERITED_ADMINS = ["system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"]
EXPLICIT_MEMBERS = ["project_admin", "project_member", "project_viewer"]
CREATORS = [*INHERITED_ADMINS, "project_admin", "project_member"]
VIEWERS_AND_UP = [*INHERITED_ADMINS, *EXPLICIT_MEMBERS]
PROJECT_UNSEEN = [
    "org_member",
    "other_project_admin",
    "workspace_member",
    "other_org_owner",
    "other_workspace_owner",
    "nobody",
]

ARCHIVED_AT = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
TITLE = "Refunds above the card limit"
NEW_TITLE = "Partial refunds to a closed card"
LIST = "/api/projects/PMT/requirements"
READ = "/api/projects/PMT/requirements/7"


async def signed_in(client: AsyncClient, who: str, *, export_controlled: bool = False) -> Tenancy:
    """`who` signed in, relative to "Payments" (PMT), which holds RQ-7 ("Refunds above the card
    limit")."""
    workspace = await WorkspaceFactory.create_async(name="Acme Consulting", slug="acme")
    org = await OrganizationFactory.create_async(
        workspace=workspace, name="Bolt Foods", slug="bolt-foods"
    )
    project = await ProjectFactory.create_async(
        organization=org,
        key="PMT",
        name="Payments",
        restriction_categories=["export_controlled"] if export_controlled else [],
    )
    t = Tenancy(workspace, org, project)
    await RequirementFactory.create_async(project=project, number=7, title=TITLE)
    await sign_in_as(client, await persona_user(t, who))
    return t


async def archive(session: AsyncSession, t: Tenancy) -> None:
    t.project.archived_at = ARCHIVED_AT
    await session.flush()


async def create(client: AsyncClient, key: str = "PMT") -> Response:
    return await client.post(f"/api/projects/{key}/requirements", json={"title": NEW_TITLE})


async def created_count(session: AsyncSession) -> int:
    """Requirements titled NEW_TITLE, re-read from the database."""
    query = select(func.count()).select_from(Requirement).where(Requirement.title == NEW_TITLE)
    return (await session.execute(query)).scalar_one()


def assert_hidden(response: Response, missing: Response) -> None:
    """404 `not_found`, the same body as for a project that doesn't exist, naming nothing."""
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    for name in ("Bolt Foods", "bolt-foods", "Payments", "PMT", TITLE):
        assert name not in response.text


def assert_forbidden(response: Response) -> None:
    assert (response.status_code, response.json()["code"]) == (403, "forbidden")


def assert_tree(response: Response) -> None:
    assert response.status_code == 200
    body = response.json()
    assert ([item["number"] for item in body["items"]], body["truncated"]) == ([7], False)


def assert_requirement(response: Response) -> None:
    assert response.status_code == 200
    assert (response.json()["number"], response.json()["title"]) == (7, TITLE)


# --- POST …/requirements (requirement.create) ----------------------------------------------------


@pytest.mark.parametrize("who", CREATORS)
async def test_members_and_up_and_inherited_admins_create_a_requirement(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    await signed_in(client, who)

    response = await create(client)

    assert (response.status_code, response.json()["title"]) == (201, NEW_TITLE)
    assert await created_count(session) == 1


async def test_a_project_viewer_may_not_create_a_requirement(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The viewer sees the project, so it's a 403 (§5)."""
    await signed_in(client, "project_viewer")

    response = await create(client)

    assert_forbidden(response)
    assert await created_count(session) == 0


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_creating_a_requirement_is_404_to_who_cannot_see_the_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    await signed_in(client, who)

    response = await create(client)

    assert_hidden(response, await create(client, "NOPE"))
    assert await created_count(session) == 0


@pytest.mark.parametrize("who", VIEWERS_AND_UP)
async def test_nobody_creates_a_requirement_in_an_archived_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5 step 1: every mutation inside an archived project is denied, system admins included;
    they see it, so a 403."""
    t = await signed_in(client, who)
    await archive(session, t)

    response = await create(client)

    assert_forbidden(response)
    assert await created_count(session) == 0


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_creating_in_an_archived_project_is_404_to_who_cannot_see_it(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)
    await archive(session, t)

    response = await create(client)

    assert_hidden(response, await create(client, "NOPE"))
    assert await created_count(session) == 0


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_creating_on_an_ec_project_is_404_to_inherited_admins(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§3.1: "Every content action denied to them, read or mutation, is a 404"."""
    await signed_in(client, who, export_controlled=True)

    response = await create(client)

    assert_hidden(response, await create(client, "NOPE"))
    assert await created_count(session) == 0


@pytest.mark.parametrize("who", ["project_admin", "project_member"])
async def test_explicit_members_create_on_an_ec_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    await signed_in(client, who, export_controlled=True)

    response = await create(client)

    assert (response.status_code, response.json()["title"]) == (201, NEW_TITLE)
    assert await created_count(session) == 1


async def test_an_explicit_viewer_may_not_create_on_an_ec_project(
    client: AsyncClient, session: AsyncSession
) -> None:
    await signed_in(client, "project_viewer", export_controlled=True)

    response = await create(client)

    assert_forbidden(response)
    assert await created_count(session) == 0


# --- GET …/requirements and GET …/requirements/{number} (requirement.view) ----------------------


@pytest.mark.parametrize("who", VIEWERS_AND_UP)
async def test_viewers_and_up_and_inherited_admins_list_the_requirements(
    client: AsyncClient, who: str
) -> None:
    await signed_in(client, who)

    assert_tree(await client.get(LIST))


@pytest.mark.parametrize("who", VIEWERS_AND_UP)
async def test_viewers_and_up_and_inherited_admins_read_a_requirement(
    client: AsyncClient, who: str
) -> None:
    await signed_in(client, who)

    assert_requirement(await client.get(READ))


@pytest.mark.parametrize("who", VIEWERS_AND_UP)
async def test_the_requirement_list_stays_readable_in_an_archived_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§9: an archived project is still browsable."""
    t = await signed_in(client, who)
    await archive(session, t)

    assert_tree(await client.get(LIST))


@pytest.mark.parametrize("who", VIEWERS_AND_UP)
async def test_a_requirement_stays_readable_in_an_archived_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)
    await archive(session, t)

    assert_requirement(await client.get(READ))


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_the_requirement_list_is_404_to_who_cannot_see_the_project(
    client: AsyncClient, who: str
) -> None:
    await signed_in(client, who)

    response = await client.get(LIST)

    assert_hidden(response, await client.get("/api/projects/NOPE/requirements"))


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_a_requirement_is_404_to_who_cannot_see_the_project(
    client: AsyncClient, who: str
) -> None:
    await signed_in(client, who)

    response = await client.get(READ)

    assert_hidden(response, await client.get("/api/projects/NOPE/requirements/7"))


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_the_requirement_list_on_an_ec_project_is_404_to_inherited_admins(
    client: AsyncClient, who: str
) -> None:
    await signed_in(client, who, export_controlled=True)

    response = await client.get(LIST)

    assert_hidden(response, await client.get("/api/projects/NOPE/requirements"))


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_a_requirement_on_an_ec_project_is_404_to_inherited_admins(
    client: AsyncClient, who: str
) -> None:
    await signed_in(client, who, export_controlled=True)

    response = await client.get(READ)

    assert_hidden(response, await client.get("/api/projects/NOPE/requirements/7"))


@pytest.mark.parametrize("who", EXPLICIT_MEMBERS)
async def test_explicit_members_list_the_requirements_on_an_ec_project(
    client: AsyncClient, who: str
) -> None:
    await signed_in(client, who, export_controlled=True)

    assert_tree(await client.get(LIST))


@pytest.mark.parametrize("who", EXPLICIT_MEMBERS)
async def test_explicit_members_read_a_requirement_on_an_ec_project(
    client: AsyncClient, who: str
) -> None:
    await signed_in(client, who, export_controlled=True)

    assert_requirement(await client.get(READ))


# --- allowed_actions on the requirement read ---------------------------------------------------


async def test_a_project_members_requirement_actions_include_create_and_view(
    client: AsyncClient,
) -> None:
    """design-doc §5, "The UI asks the server": evaluated through `authorize()`."""
    await signed_in(client, "project_member")

    response = await client.get(READ)

    assert response.status_code == 200
    actions = response.json()["allowed_actions"]
    assert ("requirement.create" in actions, "requirement.view" in actions) == (True, True)


async def test_a_project_viewers_requirement_actions_have_view_but_not_create(
    client: AsyncClient,
) -> None:
    await signed_in(client, "project_viewer")

    response = await client.get(READ)

    assert response.status_code == 200
    actions = response.json()["allowed_actions"]
    assert ("requirement.create" in actions, "requirement.view" in actions) == (False, True)
