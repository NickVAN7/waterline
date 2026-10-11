"""`/me`'s workspace entries (build plan, "Authentication (§4)", `/me`; DL-45: each entry's
workspace-level `allowed_actions`, with DL-56's `workspace_staff.manage_admins`; DL-46: a system
admin sees every workspace, with a null role where they aren't staff). Each org entry carries
that org's `allowed_actions` (DL-76, DL-77: `project.create` and `project.assign_first_admin`
among them, for the create-project dialog)."""

from typing import Any

import pytest
from httpx import AsyncClient

from app.enums import OrgRole, WorkspaceRole
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory
from tests.support.authz import persona_user, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

ALL_SIX = [
    "org.create",
    "user.check",
    "workspace.update",
    "workspace.view",
    "workspace_staff.manage",
    "workspace_staff.manage_admins",
]


async def my_workspaces(client: AsyncClient) -> list[dict[str, Any]]:
    response = await client.get("/api/auth/me")
    assert response.status_code == 200, response.text
    return sorted(response.json()["workspaces"], key=lambda entry: entry["slug"])


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (WorkspaceRole.OWNER, ALL_SIX),
        (
            WorkspaceRole.ADMIN,
            ["org.create", "user.check", "workspace.view", "workspace_staff.manage"],
        ),
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
            "allowed_actions": ALL_SIX,
        },
        {
            "id": str(bolt.id),
            "name": "Bolt Partners",
            "slug": "bolt",
            "role": None,
            "allowed_actions": ALL_SIX,
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
        (str(acme.id), "member", ALL_SIX),
        (str(bolt.id), None, ALL_SIX),
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


# --- Each org entry's allowed_actions (DL-76, DL-77) ---------------------------------------------

ALL_ORG_LEVEL = [
    "org.update",
    "org.view",
    "org_member.manage",
    "org_member.manage_admins",
    "project.assign_first_admin",
    "project.create",
]


@pytest.mark.parametrize(
    ("who", "role", "expected"),
    [
        ("system_admin", None, ALL_ORG_LEVEL),
        ("workspace_owner", None, ALL_ORG_LEVEL),
        ("workspace_admin", None, ALL_ORG_LEVEL),
        ("org_owner", "owner", ALL_ORG_LEVEL),
        (
            "org_admin",
            "admin",
            ["org.view", "org_member.manage", "project.assign_first_admin", "project.create"],
        ),
        ("org_member", "member", ["org.view", "project.create"]),
        # A project-only link shows the org but grants no project creation in it.
        ("project_admin", None, ["org.view"]),
        ("project_viewer", None, ["org.view"]),
    ],
)
async def test_each_org_entry_carries_that_orgs_actions(
    client: AsyncClient, who: str, role: str | None, expected: list[str]
) -> None:
    t = await tenancy()
    await sign_in_as(client, await persona_user(t, who))

    response = await client.get("/api/auth/me")

    assert response.status_code == 200, response.text
    assert [o for o in response.json()["orgs"] if o["slug"] == "bolt-foods"] == [
        {
            "id": str(t.org.id),
            "name": "Bolt Foods",
            "slug": "bolt-foods",
            "role": role,
            "allowed_actions": expected,
        }
    ]
