"""`/me`'s workspace entries (build plan, "Authentication (§4)", `/me`; DL-45: each entry's
workspace-level `allowed_actions`; DL-46: a system admin sees every workspace, with a null role
where they aren't staff)."""

from typing import Any

import pytest
from httpx import AsyncClient

from app.enums import OrgRole, WorkspaceRole
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory
from tests.support.authz import sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

ALL_FOUR = ["org.create", "workspace.update", "workspace.view", "workspace_staff.manage"]


async def my_workspaces(client: AsyncClient) -> list[dict[str, Any]]:
    response = await client.get("/api/auth/me")
    assert response.status_code == 200, response.text
    return sorted(response.json()["workspaces"], key=lambda entry: entry["slug"])


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (WorkspaceRole.OWNER, ALL_FOUR),
        (WorkspaceRole.ADMIN, ["org.create", "workspace.view", "workspace_staff.manage"]),
        (WorkspaceRole.MEMBER, []),
    ],
)
async def test_each_staff_role_gets_its_workspace_actions(
    client: AsyncClient, role: WorkspaceRole, expected: list[str]
) -> None:
    workspace = await WorkspaceFactory.create_async(name="Acme Consulting", slug="acme")
    user = await UserFactory.create_async(is_system_admin=False)
    await WorkspaceMembershipFactory.create_async(workspace=workspace, user=user, role=role)
    await sign_in_as(client, user)

    assert await my_workspaces(client) == [
        {
            "id": str(workspace.id),
            "name": "Acme Consulting",
            "slug": "acme",
            "role": role.value,
            "allowed_actions": expected,
        }
    ]


async def test_a_system_admin_sees_every_workspace_with_a_null_role_and_every_action(
    client: AsyncClient,
) -> None:
    acme = await WorkspaceFactory.create_async(name="Acme Consulting", slug="acme")
    bolt = await WorkspaceFactory.create_async(name="Bolt Partners", slug="bolt")
    admin = await UserFactory.create_async(is_system_admin=True)
    await sign_in_as(client, admin)

    assert await my_workspaces(client) == [
        {
            "id": str(acme.id),
            "name": "Acme Consulting",
            "slug": "acme",
            "role": None,
            "allowed_actions": ALL_FOUR,
        },
        {
            "id": str(bolt.id),
            "name": "Bolt Partners",
            "slug": "bolt",
            "role": None,
            "allowed_actions": ALL_FOUR,
        },
    ]


async def test_a_system_admin_who_is_staff_keeps_their_role_there(client: AsyncClient) -> None:
    acme = await WorkspaceFactory.create_async(name="Acme Consulting", slug="acme")
    bolt = await WorkspaceFactory.create_async(name="Bolt Partners", slug="bolt")
    admin = await UserFactory.create_async(is_system_admin=True)
    await WorkspaceMembershipFactory.create_async(
        workspace=acme, user=admin, role=WorkspaceRole.MEMBER
    )
    await sign_in_as(client, admin)

    assert [(w["id"], w["role"], w["allowed_actions"]) for w in await my_workspaces(client)] == [
        (str(acme.id), "member", ALL_FOUR),
        (str(bolt.id), None, ALL_FOUR),
    ]


async def test_other_users_see_only_the_workspaces_they_are_staff_of(
    client: AsyncClient,
) -> None:
    """An org role in a workspace (even owner) neither lists it nor grants its actions."""
    acme = await WorkspaceFactory.create_async(name="Acme Consulting", slug="acme")
    bolt = await WorkspaceFactory.create_async(name="Bolt Partners", slug="bolt")
    user = await UserFactory.create_async(is_system_admin=False)
    await WorkspaceMembershipFactory.create_async(
        workspace=acme, user=user, role=WorkspaceRole.MEMBER
    )
    org = await OrganizationFactory.create_async(workspace=bolt)
    await MembershipFactory.create_async(organization=org, user=user, role=OrgRole.OWNER)
    await sign_in_as(client, user)

    assert [(w["id"], w["role"], w["allowed_actions"]) for w in await my_workspaces(client)] == [
        (str(acme.id), "member", [])
    ]
