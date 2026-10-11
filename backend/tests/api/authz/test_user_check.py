"""Authorization of the user check, `GET /api/workspaces/{workspace_id}/user-check` (build plan,
"The user check", DL-66; "The org members API", DL-67; the action `user.check`, DL-68): one
audience for every form (email, username, name): workspace owners/admins, owners/admins of an org
in the workspace, explicit admins of one of its projects that isn't archived, and system admins.
Anyone else gets a 404, the same as a missing workspace and naming nothing, as for the workspace
pages (design-doc §4, "Visibility").

Personas are relative to workspace "Acme Consulting" (acme), its org "Bolt Foods", and that org's
project "Payments" (tests/support/authz.py, `tenancy`).
"""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient, Response

from app.enums import OrgRole, ProjectRole
from app.models.user import User
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

# `other_project_admin`: an explicit admin of another project in the org; `other_org_owner`: the
# owner of another org in the same workspace.
CHECKERS = [
    "system_admin",
    "workspace_owner",
    "workspace_admin",
    "org_owner",
    "org_admin",
    "project_admin",
    "other_project_admin",
    "other_org_owner",
]
NOT_CHECKERS = [
    "workspace_member",
    "org_member",
    "project_member",
    "project_viewer",
    "other_workspace_owner",
    "nobody",
]
# One request per form of the check.
FORMS = [{"email": "jane@cove.example"}, {"username": "jane-doe"}, {"name": "Jane Doe"}]


async def signed_in(client: AsyncClient, who: str) -> Tenancy:
    t = await tenancy()
    await sign_in_as(client, await persona_user(t, who))
    return t


async def jane() -> User:
    return await UserFactory.create_async(email="jane@cove.example", name="Jane Cove")


def check_url(workspace_id: uuid.UUID) -> str:
    return f"/api/workspaces/{workspace_id}/user-check"


def assert_hidden(response: Response, missing: Response) -> None:
    """404 `not_found`, the same body as for a workspace that doesn't exist, naming nothing."""
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    assert "Acme Consulting" not in response.text
    assert "acme" not in response.text
    assert "exists" not in response.text


@pytest.mark.parametrize("who", CHECKERS)
async def test_those_who_may_add_a_person_check_an_email(client: AsyncClient, who: str) -> None:
    t = await signed_in(client, who)
    await jane()

    response = await client.get(check_url(t.workspace.id), params={"email": "jane@cove.example"})

    assert response.status_code == 200
    assert response.json() == {"email": "jane@cove.example", "exists": True}


@pytest.mark.parametrize("who", ["org_admin", "project_admin"])
@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"username": "jane-doe"}, {"available": True, "problem": None}),
        ({"name": "Jane Doe"}, {"suggestion": "jane-doe"}),
    ],
)
async def test_the_same_audience_checks_a_username_and_a_name(
    client: AsyncClient, who: str, params: dict[str, str], expected: dict[str, object]
) -> None:
    """One audience for every form (DL-66), through the targeted rule as through a role."""
    t = await signed_in(client, who)

    response = await client.get(check_url(t.workspace.id), params=params)

    assert (response.status_code, response.json()) == (200, expected)


@pytest.mark.parametrize("who", NOT_CHECKERS)
@pytest.mark.parametrize("params", FORMS)
async def test_the_user_check_is_404_to_everyone_else(
    client: AsyncClient, who: str, params: dict[str, str]
) -> None:
    t = await signed_in(client, who)
    await jane()

    response = await client.get(check_url(t.workspace.id), params=params)

    assert_hidden(response, await client.get(check_url(uuid.uuid4()), params=params))


# --- Roles that don't count: an archived project, another workspace -----------------------------


async def test_an_admin_of_an_archived_project_only_gets_a_404(client: AsyncClient) -> None:
    """An archived project takes no new members, so its admin isn't in the audience."""
    t = await tenancy()
    archived = await ProjectFactory.create_async(
        organization=t.org, key="OLD", name="Old", archived_at=datetime(2026, 10, 1, tzinfo=UTC)
    )
    user = await UserFactory.create_async(is_system_admin=False)
    await ProjectMembershipFactory.create_async(project=archived, user=user, role=ProjectRole.ADMIN)
    await sign_in_as(client, user)
    params = {"email": "jane@cove.example"}

    response = await client.get(check_url(t.workspace.id), params=params)

    assert_hidden(response, await client.get(check_url(uuid.uuid4()), params=params))


async def test_an_admin_of_a_live_project_is_heard_beside_an_archived_one(
    client: AsyncClient,
) -> None:
    t = await tenancy()
    archived = await ProjectFactory.create_async(
        organization=t.org, key="OLD", name="Old", archived_at=datetime(2026, 10, 1, tzinfo=UTC)
    )
    user = await UserFactory.create_async(is_system_admin=False)
    await ProjectMembershipFactory.create_async(project=archived, user=user, role=ProjectRole.ADMIN)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.ADMIN
    )
    await sign_in_as(client, user)

    response = await client.get(check_url(t.workspace.id), params={"email": "jane@cove.example"})

    assert (response.status_code, response.json()) == (
        200,
        {"email": "jane@cove.example", "exists": False},
    )


@pytest.mark.parametrize("role", [OrgRole.OWNER, OrgRole.ADMIN])
async def test_an_org_admin_in_another_workspace_gets_a_404(
    client: AsyncClient, role: OrgRole
) -> None:
    t = await tenancy()
    elsewhere = await OrganizationFactory.create_async(
        workspace=await WorkspaceFactory.create_async(name="Delta Partners", slug="delta"),
        name="Echo Labs",
        slug="echo-labs",
    )
    user = await UserFactory.create_async(is_system_admin=False)
    await MembershipFactory.create_async(organization=elsewhere, user=user, role=role)
    await sign_in_as(client, user)
    params = {"email": "jane@cove.example"}

    response = await client.get(check_url(t.workspace.id), params=params)

    assert_hidden(response, await client.get(check_url(uuid.uuid4()), params=params))


async def test_a_project_admin_in_another_workspace_gets_a_404(client: AsyncClient) -> None:
    t = await tenancy()
    org = await OrganizationFactory.create_async(
        workspace=await WorkspaceFactory.create_async(name="Delta Partners", slug="delta"),
        name="Echo Labs",
        slug="echo-labs",
    )
    user = await UserFactory.create_async(is_system_admin=False)
    await ProjectMembershipFactory.create_async(
        project=await ProjectFactory.create_async(organization=org, key="ECH", name="Echo"),
        user=user,
        role=ProjectRole.ADMIN,
    )
    await sign_in_as(client, user)
    params = {"email": "jane@cove.example"}

    response = await client.get(check_url(t.workspace.id), params=params)

    assert_hidden(response, await client.get(check_url(uuid.uuid4()), params=params))


async def test_an_org_admin_checks_in_their_own_workspace_only(client: AsyncClient) -> None:
    """The org admin of Bolt Foods may check in Acme Consulting, and gets a 404 in Delta."""
    t = await signed_in(client, "org_admin")
    delta = await WorkspaceFactory.create_async(name="Delta Partners", slug="delta")
    params = {"email": "jane@cove.example"}

    own = await client.get(check_url(t.workspace.id), params=params)
    other = await client.get(check_url(delta.id), params=params)

    assert own.status_code == 200
    assert (other.status_code, other.json()["code"]) == (404, "not_found")
    assert "Delta Partners" not in other.text
