"""`?q=` on the lists the pickers load (build plan, S3-C13; TD-41, TD-38): an org's members, the
workspace's staff and users by name, email, or username; an org's projects by name or key."""

import pytest
from httpx import AsyncClient

from app.enums import OrgRole, WorkspaceRole
from tests.factories.org import MembershipFactory
from tests.factories.project import ProjectFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceMembershipFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]


@pytest.fixture
async def t(client: AsyncClient) -> Tenancy:
    t = await tenancy()
    await sign_in_as(client, await persona_user(t, "workspace_owner"))
    return t


async def people(t: Tenancy) -> None:
    """Bob by name, Cy by email, Di by username; each in the org and on the staff."""
    for name, email, username in [
        ("Bob Baker", "bob@acme.example", "bob"),
        ("Cy Cole", "cy@finance.example", "cy"),
        ("Di Diaz", "di@acme.example", "ledger-di"),
    ]:
        user = await UserFactory.create_async(name=name, email=email, username=username)
        await MembershipFactory.create_async(organization=t.org, user=user, role=OrgRole.MEMBER)
        await WorkspaceMembershipFactory.create_async(
            workspace=t.workspace, user=user, role=WorkspaceRole.MEMBER
        )


@pytest.mark.parametrize("list_", ["org_members", "staff", "users"])
@pytest.mark.parametrize(
    ("q", "found"), [("BAKER", ["Bob Baker"]), ("finance", ["Cy Cole"]), ("ledger", ["Di Diaz"])]
)
async def test_the_people_lists_search_name_email_and_username(
    client: AsyncClient, t: Tenancy, list_: str, q: str, found: list[str]
) -> None:
    """Bug: the list ignores `?q=` (422 before S3-C13), or searches one column only."""
    await people(t)
    url = {
        "org_members": f"/api/orgs/{t.org.id}/members",
        "staff": f"/api/workspaces/{t.workspace.id}/staff",
        "users": f"/api/workspaces/{t.workspace.id}/users",
    }[list_]

    response = await client.get(url, params={"q": q})

    assert response.status_code == 200, response.text
    assert [row["name"] for row in response.json()["items"]] == found
    assert response.json()["total"] == 1


@pytest.mark.parametrize(("q", "found"), [("ledg", ["Ledger"]), ("ops", ["Back office"])])
async def test_an_orgs_projects_search_name_and_key(
    client: AsyncClient, t: Tenancy, q: str, found: list[str]
) -> None:
    """TD-38: the project selector's search. Bug: only the name searched, so a key finds none."""
    await ProjectFactory.create_async(organization=t.org, key="LDG", name="Ledger")
    await ProjectFactory.create_async(organization=t.org, key="OPS", name="Back office")

    response = await client.get(f"/api/orgs/{t.org.id}/projects", params={"q": q})

    assert response.status_code == 200, response.text
    assert [p["name"] for p in response.json()["items"]] == found
