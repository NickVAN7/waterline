"""Authorization of a requirement's history,
`GET /api/projects/{key}/requirements/{number}/activity` (S2-plan, "Actions per row", S2-C3:
`requirement.view`, project viewers and up, inherited admins; build plan, S2-C3 row and "API
conventions": a cursor feed, `{items, next_cursor}`, unknown query parameters a 422; design-doc
§5: unseen entities are 404, not 403; §4 "Visibility"; §9: an archived project is still
browsable):

- 200 with the feed's shape for who holds `requirement.view`, on a live and an archived project;
- 404 (the same body as a missing project, naming nothing) for who can't see the project, on a
  live and an archived project;
- 404 for an unknown requirement number, an unknown key, and a requirement of another project
  reached by this project's key, to a user who can read the right path;
- an unknown query parameter is a 422.

The entries' content and order are the main session's tests. Export control (S2-C4) is not
covered here. Personas are relative to workspace "Acme Consulting", org "Bolt Foods"
(bolt-foods), and project "Payments" (PMT) (tests/support/authz.py, `tenancy`).
"""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.requirement import Requirement
from tests.factories.project import ProjectFactory
from tests.factories.requirement import RequirementFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

INHERITED_ADMINS = ["system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"]
VIEWERS_AND_UP = [*INHERITED_ADMINS, "project_admin", "project_member", "project_viewer"]
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
EMPTY_FEED: dict[str, object] = {"items": [], "next_cursor": None}


def history(key: str, number: int) -> str:
    return f"/api/projects/{key}/requirements/{number}/activity"


async def signed_in(client: AsyncClient, who: str) -> tuple[Tenancy, Requirement]:
    t = await tenancy()
    requirement = await RequirementFactory.create_async(project=t.project, number=7, title=TITLE)
    await sign_in_as(client, await persona_user(t, who))
    return t, requirement


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
async def test_viewers_and_up_and_inherited_admins_read_a_requirements_history(
    client: AsyncClient, who: str
) -> None:
    await signed_in(client, who)

    response = await client.get(history("PMT", 7))

    assert (response.status_code, response.json()) == (200, EMPTY_FEED)


@pytest.mark.parametrize("who", VIEWERS_AND_UP)
async def test_a_requirements_history_stays_readable_in_an_archived_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5 step 1 denies mutations only; §9: an archived project is still browsable."""
    t, _ = await signed_in(client, who)
    await archive(session, t)

    response = await client.get(history("PMT", 7))

    assert (response.status_code, response.json()) == (200, EMPTY_FEED)


# --- Denied: 404 to who can't see the project --------------------------------------------------


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_a_requirements_history_is_404_to_who_cannot_see_the_project(
    client: AsyncClient, who: str
) -> None:
    await signed_in(client, who)

    response = await client.get(history("PMT", 7))

    assert_hidden(response, await client.get(history("NOPE", 7)))


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_an_archived_projects_requirement_history_is_404_to_who_cannot_see_it(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    await archive(session, t)

    response = await client.get(history("PMT", 7))

    assert_hidden(response, await client.get(history("NOPE", 7)))


# --- 404 for what doesn't resolve, to a user who reads the right path --------------------------


async def test_an_unknown_requirement_number_is_404(client: AsyncClient) -> None:
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


async def test_another_projects_requirement_is_404_through_this_projects_key(
    client: AsyncClient,
) -> None:
    """RQ-12 exists only in Ledger (LDG); the org admin sees both projects, so the 404 on PMT
    comes from the number resolving inside the key's project, not from access."""
    t, _ = await signed_in(client, "org_admin")
    ledger = await ProjectFactory.create_async(organization=t.org, key="LDG", name="Ledger")
    await RequirementFactory.create_async(project=ledger, number=12, title="Ledger close rules")

    own = await client.get(history("LDG", 12))
    other = await client.get(history("PMT", 12))

    assert (own.status_code, own.json()) == (200, EMPTY_FEED)
    assert (other.status_code, other.json()["code"]) == (404, "not_found")
    assert "Ledger" not in other.text


# --- Query parameters (build plan, "API conventions") ------------------------------------------


async def test_an_unknown_query_parameter_is_a_422(client: AsyncClient) -> None:
    await signed_in(client, "project_viewer")

    response = await client.get(history("PMT", 7), params={"befor": "x"})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert [(f["loc"], f["type"]) for f in response.json()["details"]["fields"]] == [
        (["query", "befor"], "extra_forbidden")
    ]
