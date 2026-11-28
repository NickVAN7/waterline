"""Authorization of a task's history, `GET /api/projects/{key}/tasks/{number}/activity` (S3-plan,
"Actions per row", S3-C12: `task.view`, viewers and up, inherited admins, content; build plan,
S3-C12 row: "the task's History, as the requirement's"; "API conventions": a cursor feed,
`{items, next_cursor}`, unknown query parameters a 422; design-doc §5: unseen entities are 404,
not 403; §3.1: content needs an explicit membership on an export-controlled project; §9: an
archived project is still browsable):

- 200 with the feed's shape for who holds `task.view`, on a live and an archived project;
- 404 (the same body as a missing project, naming nothing) for who can't see the project, live
  and archived;
- 404 for an unknown task number, an unknown key, and a task of another project reached by this
  project's key, to a user who can read the right path;
- on an export-controlled project: 404 to inherited admins without an explicit membership, 200
  to explicit members;
- an unknown query parameter is a 422.

The entries' content and order are the main session's tests; the factories log nothing, so the
feed is empty. Personas are relative to workspace "Acme Consulting", org "Bolt Foods"
(bolt-foods), and project "Payments" (PMT) (tests/support/authz.py, `tenancy`).
"""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories.org import OrganizationFactory
from tests.factories.project import ProjectFactory
from tests.factories.task import TaskFactory
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
TITLE = "Sign-in throttling"
EMPTY_FEED: dict[str, object] = {"items": [], "next_cursor": None}


def history(key: str, number: int) -> str:
    return f"/api/projects/{key}/tasks/{number}/activity"


async def signed_in(client: AsyncClient, who: str) -> Tenancy:
    t = await tenancy()
    await TaskFactory.create_async(project=t.project, number=7, title=TITLE)
    await sign_in_as(client, await persona_user(t, who))
    return t


async def ec_signed_in(client: AsyncClient, who: str) -> None:
    """As `signed_in`, with "Payments" export-controlled."""
    workspace = await WorkspaceFactory.create_async(name="Acme Consulting", slug="acme")
    org = await OrganizationFactory.create_async(
        workspace=workspace, name="Bolt Foods", slug="bolt-foods"
    )
    project = await ProjectFactory.create_async(
        organization=org, key="PMT", name="Payments", restriction_categories=["export_controlled"]
    )
    await TaskFactory.create_async(project=project, number=7, title=TITLE)
    await sign_in_as(client, await persona_user(Tenancy(workspace, org, project), who))


async def archive(session: AsyncSession, t: Tenancy) -> None:
    t.project.archived_at = ARCHIVED_AT
    await session.flush()


def assert_hidden(response: Response, missing: Response) -> None:
    """404 `not_found`, the same body as for a project that doesn't exist, naming nothing."""
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    for name in ("Bolt Foods", "bolt-foods", "Payments", "PMT", TITLE):
        assert name not in response.text


# --- Allowed: project viewers and up, inherited admins -----------------------------------------


@pytest.mark.parametrize("who", VIEWERS_AND_UP)
async def test_viewers_and_up_and_inherited_admins_read_a_tasks_history(
    client: AsyncClient, who: str
) -> None:
    await signed_in(client, who)

    response = await client.get(history("PMT", 7))

    assert (response.status_code, response.json()) == (200, EMPTY_FEED)


@pytest.mark.parametrize("who", VIEWERS_AND_UP)
async def test_a_tasks_history_stays_readable_in_an_archived_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5 step 1 denies mutations only; §9: an archived project is still browsable."""
    t = await signed_in(client, who)
    await archive(session, t)

    response = await client.get(history("PMT", 7))

    assert (response.status_code, response.json()) == (200, EMPTY_FEED)


# --- Denied: 404 to who can't see the project --------------------------------------------------


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_a_tasks_history_is_404_to_who_cannot_see_the_project(
    client: AsyncClient, who: str
) -> None:
    await signed_in(client, who)

    response = await client.get(history("PMT", 7))

    assert_hidden(response, await client.get(history("NOPE", 7)))


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_an_archived_projects_task_history_is_404_to_who_cannot_see_it(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)
    await archive(session, t)

    response = await client.get(history("PMT", 7))

    assert_hidden(response, await client.get(history("NOPE", 7)))


# --- 404 for what doesn't resolve, to a user who reads the right path --------------------------


async def test_an_unknown_task_number_is_404(client: AsyncClient) -> None:
    await signed_in(client, "project_viewer")

    found = await client.get(history("PMT", 7))
    missing = await client.get(history("PMT", 8))

    assert found.status_code == 200
    assert (missing.status_code, missing.json()["code"]) == (404, "not_found")


async def test_an_unknown_project_key_is_404(client: AsyncClient) -> None:
    await signed_in(client, "project_viewer")

    found = await client.get(history("PMT", 7))
    missing = await client.get(history("NOPE", 7))

    assert found.status_code == 200
    assert (missing.status_code, missing.json()["code"]) == (404, "not_found")


async def test_another_projects_task_is_404_through_this_projects_key(
    client: AsyncClient,
) -> None:
    """TA-12 exists only in Ledger (LDG); the org admin sees both projects, so the 404 on PMT
    comes from the number resolving inside the key's project, not from access."""
    t = await signed_in(client, "org_admin")
    ledger = await ProjectFactory.create_async(organization=t.org, key="LDG", name="Ledger")
    await TaskFactory.create_async(project=ledger, number=12, title="Bank feeds")

    own = await client.get(history("LDG", 12))
    other = await client.get(history("PMT", 12))

    assert (own.status_code, own.json()) == (200, EMPTY_FEED)
    assert (other.status_code, other.json()["code"]) == (404, "not_found")
    assert "Ledger" not in other.text
    assert "Bank feeds" not in other.text


# --- Export control (§3.1: tasks are content) ---------------------------------------------------


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_a_tasks_history_is_404_to_inherited_admins_on_an_ec_project(
    client: AsyncClient, who: str
) -> None:
    await ec_signed_in(client, who)

    response = await client.get(history("PMT", 7))

    assert_hidden(response, await client.get(history("NOPE", 7)))


@pytest.mark.parametrize("who", EXPLICIT_MEMBERS)
async def test_explicit_members_read_a_tasks_history_on_an_ec_project(
    client: AsyncClient, who: str
) -> None:
    await ec_signed_in(client, who)

    response = await client.get(history("PMT", 7))

    assert (response.status_code, response.json()) == (200, EMPTY_FEED)


# --- Query parameters (build plan, "API conventions") ------------------------------------------


async def test_an_unknown_query_parameter_is_a_422(client: AsyncClient) -> None:
    await signed_in(client, "project_viewer")

    response = await client.get(history("PMT", 7), params={"befor": "x"})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert [(f["loc"], f["type"]) for f in response.json()["details"]["fields"]] == [
        (["query", "befor"], "extra_forbidden")
    ]
