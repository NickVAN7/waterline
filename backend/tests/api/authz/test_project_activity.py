"""Authorization of the project activity feed, `GET /api/projects/{key}/activity` (S3-plan,
"Actions per row", S3-C12, and Q10: `project.view_activity`, viewers and up, content; build
plan, S3-C12 row: cursor-paged, declared filters; "API conventions": a cursor feed,
`{items, next_cursor}`, unknown query parameters a 422; design-doc §5: unseen entities are 404,
not 403, and "The project activity feed is content"; §3.1, "Export-controlled projects (who sees
content)"; §9: an archived project is still browsable):

- 200 with the feed's shape for project viewers and up and inherited admins, live and archived;
- 404 (the same body as a missing project, naming nothing) for who can't see the project, live
  and archived;
- on an export-controlled project: 404 to inherited admins without an explicit membership, live
  and archived; 200 to explicit members, and to an inherited admin who holds one;
- an unknown query parameter is a 422.

Entries, filters, and naming are the main session's tests; the factories log nothing, so the
feed is empty. Personas are relative to workspace "Acme Consulting", org "Bolt Foods"
(bolt-foods), and project "Payments" (PMT) (tests/support/authz.py, `tenancy`).
"""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ProjectRole
from app.models.user import User
from tests.factories.org import OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.workspace import WorkspaceFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

INHERITED_ADMINS = ["system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"]
EXPLICIT_MEMBERS = ["project_admin", "project_member", "project_viewer"]
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
EMPTY_FEED: dict[str, object] = {"items": [], "next_cursor": None}
FEED = "/api/projects/PMT/activity"
MISSING = "/api/projects/NOPE/activity"


async def signed_in(client: AsyncClient, who: str) -> Tenancy:
    t = await tenancy()
    await sign_in_as(client, await persona_user(t, who))
    return t


async def ec_signed_in(client: AsyncClient, who: str) -> tuple[Tenancy, User]:
    """As `signed_in`, with "Payments" export-controlled."""
    workspace = await WorkspaceFactory.create_async(name="Acme Consulting", slug="acme")
    org = await OrganizationFactory.create_async(
        workspace=workspace, name="Bolt Foods", slug="bolt-foods"
    )
    project = await ProjectFactory.create_async(
        organization=org, key="PMT", name="Payments", restriction_categories=["export_controlled"]
    )
    t = Tenancy(workspace, org, project)
    user = await persona_user(t, who)
    await sign_in_as(client, user)
    return t, user


async def archive(session: AsyncSession, t: Tenancy) -> None:
    t.project.archived_at = ARCHIVED_AT
    await session.flush()


def assert_hidden(response: Response, missing: Response) -> None:
    """404 `not_found`, the same body as for a project that doesn't exist, naming nothing."""
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    for name in ("Bolt Foods", "bolt-foods", "Payments", "PMT"):
        assert name not in response.text


# --- Allowed: project viewers and up, inherited admins -----------------------------------------


@pytest.mark.parametrize("who", VIEWERS_AND_UP)
async def test_viewers_and_up_and_inherited_admins_read_the_project_feed(
    client: AsyncClient, who: str
) -> None:
    await signed_in(client, who)

    response = await client.get(FEED)

    assert (response.status_code, response.json()) == (200, EMPTY_FEED)


@pytest.mark.parametrize("who", VIEWERS_AND_UP)
async def test_the_project_feed_stays_readable_in_an_archived_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5 step 1 denies mutations only; §9: an archived project is still browsable."""
    t = await signed_in(client, who)
    await archive(session, t)

    response = await client.get(FEED)

    assert (response.status_code, response.json()) == (200, EMPTY_FEED)


# --- Denied: 404 to who can't see the project --------------------------------------------------


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_the_project_feed_is_404_to_who_cannot_see_the_project(
    client: AsyncClient, who: str
) -> None:
    await signed_in(client, who)

    response = await client.get(FEED)

    assert_hidden(response, await client.get(MISSING))


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_an_archived_projects_feed_is_404_to_who_cannot_see_it(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)
    await archive(session, t)

    response = await client.get(FEED)

    assert_hidden(response, await client.get(MISSING))


async def test_an_unknown_project_key_is_404(client: AsyncClient) -> None:
    await signed_in(client, "org_admin")

    found = await client.get(FEED)
    missing = await client.get(MISSING)

    assert found.status_code == 200
    assert (missing.status_code, missing.json()["code"]) == (404, "not_found")


# --- Export control (§3.1; §5 "The project activity feed is content"; Q10) ----------------------


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_the_feed_is_404_to_inherited_admins_on_an_ec_project(
    client: AsyncClient, who: str
) -> None:
    """The whole feed is content, project entries included (Q10)."""
    await ec_signed_in(client, who)

    response = await client.get(FEED)

    assert_hidden(response, await client.get(MISSING))


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_an_archived_ec_projects_feed_is_404_to_inherited_admins(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await ec_signed_in(client, who)
    await archive(session, t)

    response = await client.get(FEED)

    assert_hidden(response, await client.get(MISSING))


@pytest.mark.parametrize("who", EXPLICIT_MEMBERS)
async def test_explicit_members_read_an_ec_projects_feed(client: AsyncClient, who: str) -> None:
    await ec_signed_in(client, who)

    response = await client.get(FEED)

    assert (response.status_code, response.json()) == (200, EMPTY_FEED)


@pytest.mark.parametrize("who", EXPLICIT_MEMBERS)
async def test_explicit_members_read_an_archived_ec_projects_feed(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await ec_signed_in(client, who)
    await archive(session, t)

    response = await client.get(FEED)

    assert (response.status_code, response.json()) == (200, EMPTY_FEED)


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_an_inherited_admin_with_an_explicit_membership_reads_an_ec_projects_feed(
    client: AsyncClient, who: str
) -> None:
    t, user = await ec_signed_in(client, who)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.VIEWER
    )

    response = await client.get(FEED)

    assert (response.status_code, response.json()) == (200, EMPTY_FEED)


# --- Query parameters (build plan, "API conventions") ------------------------------------------


async def test_an_unknown_query_parameter_is_a_422(client: AsyncClient) -> None:
    await signed_in(client, "project_viewer")

    response = await client.get(FEED, params={"befor": "x"})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert [(f["loc"], f["type"]) for f in response.json()["details"]["fields"]] == [
        (["query", "befor"], "extra_forbidden")
    ]
