"""Authorization of the workspace endpoints (build plan, "The workspace and org API", DL-55; the
actions, DL-45 and DL-56): 2xx for who holds the action, 403 for who sees the workspace without
it, 404 (the same as a missing workspace, naming nothing) for everyone else; and granting,
changing, or removing an owner or admin role also needs `workspace_staff.manage_admins`.

Only the workspace's owners/admins and system admins see it (design-doc §4, "Visibility"), so
the 404 personas are the rest: staff with role member, an org owner and a project admin inside
it, another workspace's owner, and a user with no memberships.
"""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import WorkspaceRole
from app.models.org import Organization
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceMembershipFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

ALL_FIVE = [
    "org.create",
    "workspace.update",
    "workspace.view",
    "workspace_staff.manage",
    "workspace_staff.manage_admins",
]
UNSEEN = ["workspace_member", "org_owner", "project_admin", "other_workspace_owner", "nobody"]
STAFF_MANAGERS = ["workspace_owner", "workspace_admin", "system_admin"]
ROLE_GRANTERS = ["workspace_owner", "system_admin"]


async def signed_in(client: AsyncClient, who: str) -> Tenancy:
    t = await tenancy()
    await sign_in_as(client, await persona_user(t, who))
    return t


async def staff(t: Tenancy, role: WorkspaceRole, email: str) -> User:
    user = await UserFactory.create_async(email=email, is_system_admin=False)
    await WorkspaceMembershipFactory.create_async(workspace=t.workspace, user=user, role=role)
    return user


async def stored_role(session: AsyncSession, t: Tenancy, user_id: uuid.UUID) -> str | None:
    return await session.scalar(
        select(WorkspaceMembership.role).where(
            WorkspaceMembership.workspace_id == t.workspace.id,
            WorkspaceMembership.user_id == user_id,
        )
    )


def assert_hidden(response: Response, missing: Response) -> None:
    """404 `not_found`, the same body as for a workspace that doesn't exist, naming nothing."""
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    assert "Acme Consulting" not in response.text
    assert "acme" not in response.text


def assert_forbidden(response: Response) -> None:
    assert (response.status_code, response.json()["code"]) == (403, "forbidden")


# --- GET /api/workspaces/{id} (workspace.view) --------------------------------------------------


@pytest.mark.parametrize(
    ("who", "expected"),
    [
        ("workspace_owner", ALL_FIVE),
        ("workspace_admin", ["org.create", "workspace.view", "workspace_staff.manage"]),
        ("system_admin", ALL_FIVE),
    ],
)
async def test_the_workspace_is_returned_with_the_callers_actions(
    client: AsyncClient, who: str, expected: list[str]
) -> None:
    t = await signed_in(client, who)

    response = await client.get(f"/api/workspaces/{t.workspace.id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(t.workspace.id),
        "name": "Acme Consulting",
        "slug": "acme",
        "allowed_actions": expected,
    }


@pytest.mark.parametrize("who", UNSEEN)
async def test_the_workspace_is_404_to_everyone_else(client: AsyncClient, who: str) -> None:
    t = await signed_in(client, who)

    response = await client.get(f"/api/workspaces/{t.workspace.id}")

    assert_hidden(response, await client.get(f"/api/workspaces/{uuid.uuid4()}"))


# --- PATCH /api/workspaces/{id} and its slug check (workspace.update) ---------------------------


async def stored_name(session: AsyncSession, t: Tenancy) -> str | None:
    return await session.scalar(select(Workspace.name).where(Workspace.id == t.workspace.id))


@pytest.mark.parametrize("who", ROLE_GRANTERS)
async def test_workspace_owners_and_system_admins_rename_the_workspace(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)

    response = await client.patch(
        f"/api/workspaces/{t.workspace.id}", json={"name": "Acme Advisory"}
    )

    assert (response.status_code, response.json()["name"]) == (200, "Acme Advisory")
    assert await stored_name(session, t) == "Acme Advisory"


async def test_a_workspace_admin_may_not_rename_the_workspace(
    client: AsyncClient, session: AsyncSession
) -> None:
    t = await signed_in(client, "workspace_admin")

    response = await client.patch(
        f"/api/workspaces/{t.workspace.id}", json={"name": "Acme Advisory"}
    )

    assert_forbidden(response)
    assert await stored_name(session, t) == "Acme Consulting"


@pytest.mark.parametrize("who", UNSEEN)
async def test_renaming_a_workspace_the_user_cannot_see_is_404_and_changes_nothing(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)

    response = await client.patch(
        f"/api/workspaces/{t.workspace.id}", json={"name": "Acme Advisory"}
    )

    missing = await client.patch(f"/api/workspaces/{uuid.uuid4()}", json={"name": "Acme Advisory"})
    assert_hidden(response, missing)
    assert await stored_name(session, t) == "Acme Consulting"


@pytest.mark.parametrize("who", ROLE_GRANTERS)
async def test_workspace_owners_and_system_admins_check_a_workspace_slug(
    client: AsyncClient, who: str
) -> None:
    """The workspace's own slug counts as available (DL-55)."""
    t = await signed_in(client, who)

    response = await client.get(f"/api/workspaces/{t.workspace.id}/slug-availability?slug=acme")

    assert response.status_code == 200
    assert response.json() == {"available": True, "problem": None}


async def test_a_workspace_admin_may_not_check_a_workspace_slug(client: AsyncClient) -> None:
    t = await signed_in(client, "workspace_admin")

    response = await client.get(f"/api/workspaces/{t.workspace.id}/slug-availability?slug=acme")

    assert_forbidden(response)


@pytest.mark.parametrize("who", UNSEEN)
async def test_a_workspace_slug_check_is_404_to_everyone_else(
    client: AsyncClient, who: str
) -> None:
    t = await signed_in(client, who)

    response = await client.get(f"/api/workspaces/{t.workspace.id}/slug-availability?slug=acme")

    missing = await client.get(f"/api/workspaces/{uuid.uuid4()}/slug-availability?slug=acme")
    assert_hidden(response, missing)


# --- GET staff and orgs (workspace.view) --------------------------------------------------------


@pytest.mark.parametrize("who", STAFF_MANAGERS)
async def test_the_staff_list_is_for_workspace_owners_admins_and_system_admins(
    client: AsyncClient, who: str
) -> None:
    t = await signed_in(client, who)
    keeper = await staff(t, WorkspaceRole.OWNER, "keeper@acme.example")

    response = await client.get(f"/api/workspaces/{t.workspace.id}/staff")

    assert response.status_code == 200
    rows = {row["user_id"]: row["role"] for row in response.json()["items"]}
    assert rows[str(keeper.id)] == "owner"


@pytest.mark.parametrize("who", UNSEEN)
async def test_the_staff_list_is_404_to_everyone_else(client: AsyncClient, who: str) -> None:
    t = await signed_in(client, who)
    await staff(t, WorkspaceRole.OWNER, "keeper@acme.example")

    response = await client.get(f"/api/workspaces/{t.workspace.id}/staff")

    assert_hidden(response, await client.get(f"/api/workspaces/{uuid.uuid4()}/staff"))
    assert "keeper@acme.example" not in response.text


@pytest.mark.parametrize("who", STAFF_MANAGERS)
async def test_the_org_list_is_for_workspace_owners_admins_and_system_admins(
    client: AsyncClient, who: str
) -> None:
    t = await signed_in(client, who)

    response = await client.get(f"/api/workspaces/{t.workspace.id}/orgs")

    assert response.status_code == 200
    assert response.json()["items"] == [
        {"id": str(t.org.id), "name": "Bolt Foods", "slug": "bolt-foods"}
    ]


@pytest.mark.parametrize("who", UNSEEN)
async def test_the_org_list_is_404_to_everyone_else(client: AsyncClient, who: str) -> None:
    t = await signed_in(client, who)

    response = await client.get(f"/api/workspaces/{t.workspace.id}/orgs")

    assert_hidden(response, await client.get(f"/api/workspaces/{uuid.uuid4()}/orgs"))
    assert "Bolt Foods" not in response.text


# --- POST staff: add an existing account (workspace_staff.manage; owner/admin roles also need
# workspace_staff.manage_admins, DL-56) ---------------------------------------------------------


async def newcomer() -> User:
    return await UserFactory.create_async(email="dana@bolt.example", is_system_admin=False)


@pytest.mark.parametrize(
    ("who", "role"),
    [
        ("workspace_admin", WorkspaceRole.MEMBER),
        ("workspace_owner", WorkspaceRole.MEMBER),
        ("workspace_owner", WorkspaceRole.ADMIN),
        ("workspace_owner", WorkspaceRole.OWNER),
        ("system_admin", WorkspaceRole.ADMIN),
        ("system_admin", WorkspaceRole.OWNER),
    ],
)
async def test_adding_staff_with_a_role_the_caller_may_grant(
    client: AsyncClient, session: AsyncSession, who: str, role: WorkspaceRole
) -> None:
    t = await signed_in(client, who)
    dana = await newcomer()

    response = await client.post(
        f"/api/workspaces/{t.workspace.id}/staff",
        json={"email": "dana@bolt.example", "role": role.value},
    )

    assert response.status_code == 201
    assert (response.json()["user_id"], response.json()["role"]) == (str(dana.id), role.value)
    assert await stored_role(session, t, dana.id) == role.value


@pytest.mark.parametrize("role", [WorkspaceRole.ADMIN, WorkspaceRole.OWNER])
async def test_a_workspace_admin_may_not_add_staff_as_owner_or_admin(
    client: AsyncClient, session: AsyncSession, role: WorkspaceRole
) -> None:
    t = await signed_in(client, "workspace_admin")
    dana = await newcomer()

    response = await client.post(
        f"/api/workspaces/{t.workspace.id}/staff",
        json={"email": "dana@bolt.example", "role": role.value},
    )

    assert_forbidden(response)
    assert await stored_role(session, t, dana.id) is None


@pytest.mark.parametrize("who", UNSEEN)
async def test_adding_staff_is_404_to_everyone_else(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)
    dana = await newcomer()
    body = {"email": "dana@bolt.example", "role": "member"}

    response = await client.post(f"/api/workspaces/{t.workspace.id}/staff", json=body)

    assert_hidden(response, await client.post(f"/api/workspaces/{uuid.uuid4()}/staff", json=body))
    assert await stored_role(session, t, dana.id) is None


# --- POST staff/new: create the account and membership (as above) ------------------------------


def new_account(role: WorkspaceRole) -> dict[str, Any]:
    return {
        "email": "erin@acme.example",
        "username": "erin-new",
        "name": "Erin New",
        "password": "plum-harbor-lantern-quietly",
        "role": role.value,
    }


async def stored_user_id(session: AsyncSession) -> uuid.UUID | None:
    return await session.scalar(select(User.id).where(User.email == "erin@acme.example"))


@pytest.mark.parametrize(
    ("who", "role"),
    [
        ("workspace_admin", WorkspaceRole.MEMBER),
        ("workspace_owner", WorkspaceRole.ADMIN),
        ("workspace_owner", WorkspaceRole.OWNER),
        ("system_admin", WorkspaceRole.OWNER),
    ],
)
async def test_creating_staff_with_a_role_the_caller_may_grant(
    client: AsyncClient, session: AsyncSession, who: str, role: WorkspaceRole
) -> None:
    t = await signed_in(client, who)

    response = await client.post(
        f"/api/workspaces/{t.workspace.id}/staff/new", json=new_account(role)
    )

    assert response.status_code == 201
    erin = await stored_user_id(session)
    assert erin is not None
    assert (response.json()["user_id"], response.json()["role"]) == (str(erin), role.value)
    assert await stored_role(session, t, erin) == role.value


@pytest.mark.parametrize("role", [WorkspaceRole.ADMIN, WorkspaceRole.OWNER])
async def test_a_workspace_admin_may_not_create_staff_as_owner_or_admin(
    client: AsyncClient, session: AsyncSession, role: WorkspaceRole
) -> None:
    """Nothing is created: no account, no membership."""
    t = await signed_in(client, "workspace_admin")

    response = await client.post(
        f"/api/workspaces/{t.workspace.id}/staff/new", json=new_account(role)
    )

    assert_forbidden(response)
    assert await stored_user_id(session) is None


@pytest.mark.parametrize("who", UNSEEN)
async def test_creating_staff_is_404_to_everyone_else(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)
    body = new_account(WorkspaceRole.MEMBER)

    response = await client.post(f"/api/workspaces/{t.workspace.id}/staff/new", json=body)

    missing = await client.post(f"/api/workspaces/{uuid.uuid4()}/staff/new", json=body)
    assert_hidden(response, missing)
    assert await stored_user_id(session) is None


# --- PATCH staff/{user_id}: change a role (as above) --------------------------------------------
# Every role change touches an owner or admin role but member to member, so a workspace admin
# changes no role; an extra owner keeps the last-owner guard out of the way.


@pytest.mark.parametrize(
    ("who", "old", "new"),
    [
        ("workspace_owner", WorkspaceRole.MEMBER, WorkspaceRole.ADMIN),
        ("workspace_owner", WorkspaceRole.ADMIN, WorkspaceRole.MEMBER),
        ("workspace_owner", WorkspaceRole.OWNER, WorkspaceRole.ADMIN),
        ("system_admin", WorkspaceRole.MEMBER, WorkspaceRole.OWNER),
        ("system_admin", WorkspaceRole.OWNER, WorkspaceRole.MEMBER),
    ],
)
async def test_owners_and_system_admins_change_owner_and_admin_roles(
    client: AsyncClient,
    session: AsyncSession,
    who: str,
    old: WorkspaceRole,
    new: WorkspaceRole,
) -> None:
    t = await signed_in(client, who)
    await staff(t, WorkspaceRole.OWNER, "keeper@acme.example")
    target = await staff(t, old, "frank@acme.example")

    response = await client.patch(
        f"/api/workspaces/{t.workspace.id}/staff/{target.id}", json={"role": new.value}
    )

    assert (response.status_code, response.json()["role"]) == (200, new.value)
    assert await stored_role(session, t, target.id) == new.value


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (WorkspaceRole.MEMBER, WorkspaceRole.ADMIN),
        (WorkspaceRole.MEMBER, WorkspaceRole.OWNER),
        (WorkspaceRole.ADMIN, WorkspaceRole.MEMBER),
        (WorkspaceRole.ADMIN, WorkspaceRole.OWNER),
        (WorkspaceRole.OWNER, WorkspaceRole.ADMIN),
        (WorkspaceRole.OWNER, WorkspaceRole.MEMBER),
    ],
)
async def test_a_workspace_admin_may_not_grant_change_or_remove_owner_or_admin_roles(
    client: AsyncClient, session: AsyncSession, old: WorkspaceRole, new: WorkspaceRole
) -> None:
    t = await signed_in(client, "workspace_admin")
    await staff(t, WorkspaceRole.OWNER, "keeper@acme.example")
    target = await staff(t, old, "frank@acme.example")

    response = await client.patch(
        f"/api/workspaces/{t.workspace.id}/staff/{target.id}", json={"role": new.value}
    )

    assert_forbidden(response)
    assert await stored_role(session, t, target.id) == old.value


@pytest.mark.parametrize("who", UNSEEN)
async def test_changing_a_staff_role_is_404_to_everyone_else(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)
    target = await staff(t, WorkspaceRole.MEMBER, "frank@acme.example")

    response = await client.patch(
        f"/api/workspaces/{t.workspace.id}/staff/{target.id}", json={"role": "admin"}
    )

    missing = await client.patch(
        f"/api/workspaces/{uuid.uuid4()}/staff/{target.id}", json={"role": "admin"}
    )
    assert_hidden(response, missing)
    assert "frank@acme.example" not in response.text
    assert await stored_role(session, t, target.id) == "member"


# --- DELETE staff/{user_id}: remove (as above) --------------------------------------------------


@pytest.mark.parametrize(
    ("who", "role"),
    [
        ("workspace_admin", WorkspaceRole.MEMBER),
        ("workspace_owner", WorkspaceRole.MEMBER),
        ("workspace_owner", WorkspaceRole.ADMIN),
        ("workspace_owner", WorkspaceRole.OWNER),
        ("system_admin", WorkspaceRole.ADMIN),
        ("system_admin", WorkspaceRole.OWNER),
    ],
)
async def test_removing_staff_whose_role_the_caller_may_remove(
    client: AsyncClient, session: AsyncSession, who: str, role: WorkspaceRole
) -> None:
    t = await signed_in(client, who)
    await staff(t, WorkspaceRole.OWNER, "keeper@acme.example")
    target = await staff(t, role, "frank@acme.example")

    response = await client.delete(f"/api/workspaces/{t.workspace.id}/staff/{target.id}")

    assert response.status_code == 204
    assert await stored_role(session, t, target.id) is None


@pytest.mark.parametrize("role", [WorkspaceRole.ADMIN, WorkspaceRole.OWNER])
async def test_a_workspace_admin_may_not_remove_an_owner_or_admin(
    client: AsyncClient, session: AsyncSession, role: WorkspaceRole
) -> None:
    t = await signed_in(client, "workspace_admin")
    await staff(t, WorkspaceRole.OWNER, "keeper@acme.example")
    target = await staff(t, role, "frank@acme.example")

    response = await client.delete(f"/api/workspaces/{t.workspace.id}/staff/{target.id}")

    assert_forbidden(response)
    assert await stored_role(session, t, target.id) == role.value


@pytest.mark.parametrize("who", UNSEEN)
async def test_removing_staff_is_404_to_everyone_else(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)
    target = await staff(t, WorkspaceRole.MEMBER, "frank@acme.example")

    response = await client.delete(f"/api/workspaces/{t.workspace.id}/staff/{target.id}")

    missing = await client.delete(f"/api/workspaces/{uuid.uuid4()}/staff/{target.id}")
    assert_hidden(response, missing)
    assert await stored_role(session, t, target.id) == "member"


# --- POST orgs and the new-org slug check (org.create) ------------------------------------------


async def stored_org_name(session: AsyncSession, t: Tenancy) -> str | None:
    return await session.scalar(
        select(Organization.name).where(
            Organization.workspace_id == t.workspace.id, Organization.slug == "cove-retail"
        )
    )


@pytest.mark.parametrize("who", STAFF_MANAGERS)
async def test_workspace_owners_admins_and_system_admins_create_an_org(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)
    owner = await UserFactory.create_async(is_system_admin=False)

    response = await client.post(
        f"/api/workspaces/{t.workspace.id}/orgs",
        json={"name": "Cove Retail", "slug": "cove-retail", "owner_id": str(owner.id)},
    )

    assert response.status_code == 201
    assert (response.json()["name"], response.json()["slug"]) == ("Cove Retail", "cove-retail")
    assert await stored_org_name(session, t) == "Cove Retail"


@pytest.mark.parametrize("who", UNSEEN)
async def test_creating_an_org_is_404_to_everyone_else(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)
    owner = await UserFactory.create_async(is_system_admin=False)
    body = {"name": "Cove Retail", "slug": "cove-retail", "owner_id": str(owner.id)}

    response = await client.post(f"/api/workspaces/{t.workspace.id}/orgs", json=body)

    assert_hidden(response, await client.post(f"/api/workspaces/{uuid.uuid4()}/orgs", json=body))
    assert await stored_org_name(session, t) is None


@pytest.mark.parametrize("who", STAFF_MANAGERS)
async def test_workspace_owners_admins_and_system_admins_check_a_new_org_slug(
    client: AsyncClient, who: str
) -> None:
    t = await signed_in(client, who)

    response = await client.get(
        f"/api/workspaces/{t.workspace.id}/org-slug-availability?slug=cove-retail"
    )

    assert response.status_code == 200
    assert response.json() == {"available": True, "problem": None}


@pytest.mark.parametrize("who", UNSEEN)
async def test_a_new_org_slug_check_is_404_to_everyone_else(client: AsyncClient, who: str) -> None:
    t = await signed_in(client, who)

    response = await client.get(
        f"/api/workspaces/{t.workspace.id}/org-slug-availability?slug=cove-retail"
    )

    missing = await client.get(
        f"/api/workspaces/{uuid.uuid4()}/org-slug-availability?slug=cove-retail"
    )
    assert_hidden(response, missing)
