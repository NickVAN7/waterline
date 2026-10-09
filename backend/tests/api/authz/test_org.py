"""Authorization of the org endpoints (build plan, "The workspace and org API", DL-55; the actions,
DL-56): `GET /api/orgs/{id}` for anyone who sees the org (design-doc §4, "Visibility"), with
their `allowed_actions`; renaming it and its slug check for org owners, workspace owners/admins,
and system admins (403 for anyone else who sees it); 404, the same as a missing org and naming
nothing, for whoever can't see it.

Personas are relative to org "Bolt Foods" (bolt-foods) in workspace "Acme Consulting", with
project "Payments" (tests/support/authz.py, `tenancy`).
"""

import uuid

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.org import Organization
from tests.support.authz import Tenancy, persona_user, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

UNSEEN = ["workspace_member", "other_org_owner", "other_workspace_owner", "nobody"]
UPDATERS = ["system_admin", "workspace_owner", "workspace_admin", "org_owner"]
# See the org but may not update it.
VIEWERS_ONLY = [
    "org_admin",
    "org_member",
    "project_admin",
    "project_member",
    "project_viewer",
    "other_project_admin",
]


async def signed_in(client: AsyncClient, who: str) -> Tenancy:
    t = await tenancy()
    await sign_in_as(client, await persona_user(t, who))
    return t


async def stored_name(session: AsyncSession, t: Tenancy) -> str | None:
    return await session.scalar(select(Organization.name).where(Organization.id == t.org.id))


def assert_hidden(response: Response, missing: Response) -> None:
    """404 `not_found`, the same body as for an org that doesn't exist, naming nothing."""
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    assert "Bolt Foods" not in response.text
    assert "bolt-foods" not in response.text


def assert_forbidden(response: Response) -> None:
    assert (response.status_code, response.json()["code"]) == (403, "forbidden")


# --- GET /api/orgs/{id} (org.view) --------------------------------------------------------------


@pytest.mark.parametrize(
    ("who", "expected"),
    [
        ("system_admin", ["org.update", "org.view"]),
        ("workspace_owner", ["org.update", "org.view"]),
        ("workspace_admin", ["org.update", "org.view"]),
        ("org_owner", ["org.update", "org.view"]),
        ("org_admin", ["org.view"]),
        ("org_member", ["org.view"]),
        ("project_viewer", ["org.view"]),
        ("other_project_admin", ["org.view"]),
    ],
)
async def test_anyone_who_sees_the_org_gets_it_with_their_actions(
    client: AsyncClient, who: str, expected: list[str]
) -> None:
    """A project membership on one of its projects shows the org, without an org role."""
    t = await signed_in(client, who)

    response = await client.get(f"/api/orgs/{t.org.id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(t.org.id),
        "workspace_id": str(t.workspace.id),
        "name": "Bolt Foods",
        "slug": "bolt-foods",
        "allowed_actions": expected,
    }


@pytest.mark.parametrize("who", UNSEEN)
async def test_the_org_is_404_to_whoever_cannot_see_it(client: AsyncClient, who: str) -> None:
    """Staff membership alone doesn't show an org (§4); nor does a role elsewhere."""
    t = await signed_in(client, who)

    response = await client.get(f"/api/orgs/{t.org.id}")

    assert_hidden(response, await client.get(f"/api/orgs/{uuid.uuid4()}"))


# --- PATCH /api/orgs/{id} and its slug check (org.update) ---------------------------------------


@pytest.mark.parametrize("who", UPDATERS)
async def test_org_owners_and_the_admins_above_rename_the_org(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)

    response = await client.patch(f"/api/orgs/{t.org.id}", json={"name": "Bolt Kitchens"})

    assert (response.status_code, response.json()["name"]) == (200, "Bolt Kitchens")
    assert await stored_name(session, t) == "Bolt Kitchens"


@pytest.mark.parametrize("who", VIEWERS_ONLY)
async def test_others_who_see_the_org_may_not_rename_it(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """design-doc §5: managing the org itself is an org owner's, not an org admin's."""
    t = await signed_in(client, who)

    response = await client.patch(f"/api/orgs/{t.org.id}", json={"name": "Bolt Kitchens"})

    assert_forbidden(response)
    assert await stored_name(session, t) == "Bolt Foods"


@pytest.mark.parametrize("who", UNSEEN)
async def test_renaming_an_org_the_user_cannot_see_is_404_and_changes_nothing(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)

    response = await client.patch(f"/api/orgs/{t.org.id}", json={"name": "Bolt Kitchens"})

    missing = await client.patch(f"/api/orgs/{uuid.uuid4()}", json={"name": "Bolt Kitchens"})
    assert_hidden(response, missing)
    assert await stored_name(session, t) == "Bolt Foods"


@pytest.mark.parametrize("who", UPDATERS)
async def test_org_owners_and_the_admins_above_check_the_orgs_slug(
    client: AsyncClient, who: str
) -> None:
    """The org's own slug counts as available (DL-55)."""
    t = await signed_in(client, who)

    response = await client.get(f"/api/orgs/{t.org.id}/slug-availability?slug=bolt-foods")

    assert response.status_code == 200
    assert response.json() == {"available": True, "problem": None}


@pytest.mark.parametrize("who", VIEWERS_ONLY)
async def test_others_who_see_the_org_may_not_check_its_slug(client: AsyncClient, who: str) -> None:
    t = await signed_in(client, who)

    response = await client.get(f"/api/orgs/{t.org.id}/slug-availability?slug=bolt-foods")

    assert_forbidden(response)


@pytest.mark.parametrize("who", UNSEEN)
async def test_an_org_slug_check_is_404_to_whoever_cannot_see_the_org(
    client: AsyncClient, who: str
) -> None:
    t = await signed_in(client, who)

    response = await client.get(f"/api/orgs/{t.org.id}/slug-availability?slug=bolt-foods")

    missing = await client.get(f"/api/orgs/{uuid.uuid4()}/slug-availability?slug=bolt-foods")
    assert_hidden(response, missing)
