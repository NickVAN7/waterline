"""Approver replacement on the paths outside the project (design-doc §6.2 "Causes"; build plan
S2-C13): an org or workspace removal, with or without their projects; an org or workspace role
change that took inherited admin away; `revoke-system-admin` (`changed_by` null); deactivation.
Each hands the approver's pending row to the requester, logged on the request as an
`approver_id` change by whoever took the access away; a path that leaves the access changes
nothing. The project paths are in test_approver_replacement.py."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.enums import ActivityEntityType, OrgRole, ProjectRole, WorkspaceRole
from app.models.user import User
from app.services.auth import AuthService
from tests.api.test_approval_decisions import logged, requirement
from tests.api.test_approver_replacement import (
    PENDING,
    REPLACED,
    ada,
    org_admin,
    request_by,
    rows,
    t,
)
from tests.factories.org import MembershipFactory
from tests.factories.project import ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceMembershipFactory
from tests.support.authz import Tenancy, sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

__all__ = ["ada", "t"]  # fixtures, used by name


@pytest.fixture
async def wren(client: AsyncClient, t: Tenancy) -> User:
    """Wren, the workspace owner, signed in: the one whose action takes the access away."""
    user = await UserFactory.create_async(name="Wren Owner", is_system_admin=False, is_active=True)
    await WorkspaceMembershipFactory.create_async(
        workspace=t.workspace, user=user, role=WorkspaceRole.OWNER
    )
    await sign_in_as(client, user)
    return user


async def org_viewer(t: Tenancy, name: str) -> User:
    """An org member who is a viewer of PMT: content access through the membership only."""
    user = await UserFactory.create_async(name=name, is_system_admin=False, is_active=True)
    await MembershipFactory.create_async(organization=t.org, user=user, role=OrgRole.MEMBER)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.VIEWER
    )
    return user


async def staff_admin(t: Tenancy, name: str) -> User:
    """A workspace admin with no project membership: inherited project admin (§5)."""
    user = await UserFactory.create_async(name=name, is_system_admin=False, is_active=True)
    await WorkspaceMembershipFactory.create_async(
        workspace=t.workspace, user=user, role=WorkspaceRole.ADMIN
    )
    return user


def org_member(t: Tenancy, user: User) -> str:
    return f"/api/orgs/{t.org.id}/members/{user.id}"


def staff(t: Tenancy, user: User) -> str:
    return f"/api/workspaces/{t.workspace.id}/staff/{user.id}"


# --- Org removals ---------------------------------------------------------------------------


async def test_an_org_removal_with_their_projects_replaces_the_approvers_row(
    client: AsyncClient, session: AsyncSession, t: Tenancy, ada: User, wren: User
) -> None:
    """§6.2 "Causes": their project membership removed with an org removal. Bug: the roster's
    removal never calls the replacement (the project handler deletes the membership only)."""
    item, (rev1,) = await requirement(t)
    vera = await org_viewer(t, "Vera Viewer")
    request = await request_by(t.project, ada, rev1, item, (vera, PENDING, None))

    response = await client.delete(org_member(t, vera))

    assert response.status_code == 204
    assert await rows(session, request) == {(vera.id, REPLACED), (ada.id, PENDING)}
    assert await logged(session, ActivityEntityType.APPROVAL_REQUEST, request.id) == {
        ("approver_id", str(vera.id), str(ada.id), wren.id)
    }


async def test_an_org_removal_without_their_projects_replaces_an_inherited_admin(
    client: AsyncClient, session: AsyncSession, t: Tenancy, ada: User, wren: User
) -> None:
    """§6.2 "Causes": the org membership that gave inherited admin removed. Ivy has no project
    membership, so keeping "their projects" leaves her nothing. Bug: only a removal with their
    projects replaces."""
    item, (rev1,) = await requirement(t)
    ivy = await org_admin(t, "Ivy Inherit")
    request = await request_by(t.project, ada, rev1, item, (ivy, PENDING, None))

    response = await client.delete(org_member(t, ivy), params={"with_projects": "false"})

    assert response.status_code == 204
    assert await rows(session, request) == {(ivy.id, REPLACED), (ada.id, PENDING)}


async def test_an_org_removal_that_keeps_their_project_membership_leaves_the_row_pending(
    client: AsyncClient, session: AsyncSession, t: Tenancy, ada: User, wren: User
) -> None:
    """§6.2: the rule is the loss of access. Vera keeps her PMT membership, so she can still
    decide. Bug: every org removal replaces."""
    item, (rev1,) = await requirement(t)
    vera = await org_viewer(t, "Vera Viewer")
    request = await request_by(t.project, ada, rev1, item, (vera, PENDING, None))

    response = await client.delete(org_member(t, vera), params={"with_projects": "false"})

    assert response.status_code == 204
    assert await rows(session, request) == {(vera.id, PENDING)}
    assert await logged(session, ActivityEntityType.APPROVAL_REQUEST, request.id) == set()


async def test_a_staff_removal_replaces_an_inherited_admin(
    client: AsyncClient, session: AsyncSession, t: Tenancy, ada: User, wren: User
) -> None:
    """§6.2 "Causes": the workspace membership that gave inherited admin removed. Bug: the
    staff roster isn't wired (it shares the roster with orgs, so only the scope differs)."""
    item, (rev1,) = await requirement(t)
    sam = await staff_admin(t, "Sam Staff")
    request = await request_by(t.project, ada, rev1, item, (sam, PENDING, None))

    response = await client.delete(staff(t, sam))

    assert response.status_code == 204
    assert await rows(session, request) == {(sam.id, REPLACED), (ada.id, PENDING)}
    assert await logged(session, ActivityEntityType.APPROVAL_REQUEST, request.id) == {
        ("approver_id", str(sam.id), str(ada.id), wren.id)
    }


# --- Role changes ---------------------------------------------------------------------------


async def test_an_org_role_change_that_takes_inherited_admin_away_replaces(
    client: AsyncClient, session: AsyncSession, t: Tenancy, ada: User, wren: User
) -> None:
    """§6.2 "Causes": the org role that gave inherited admin changed. Bug: a role change never
    calls the replacement."""
    item, (rev1,) = await requirement(t)
    ivy = await org_admin(t, "Ivy Inherit")
    request = await request_by(t.project, ada, rev1, item, (ivy, PENDING, None))

    response = await client.patch(org_member(t, ivy), json={"role": "member"})

    assert response.status_code == 200
    assert await rows(session, request) == {(ivy.id, REPLACED), (ada.id, PENDING)}
    assert await logged(session, ActivityEntityType.APPROVAL_REQUEST, request.id) == {
        ("approver_id", str(ivy.id), str(ada.id), wren.id)
    }


async def test_an_org_role_change_that_leaves_a_project_membership_leaves_the_row_pending(
    client: AsyncClient, session: AsyncSession, t: Tenancy, ada: User, wren: User
) -> None:
    """§6.2: an org admin who is also a PMT viewer keeps content access as a member. Bug: every
    role change replaces."""
    item, (rev1,) = await requirement(t)
    ivy = await org_admin(t, "Ivy Inherit")
    await ProjectMembershipFactory.create_async(
        project=t.project, user=ivy, role=ProjectRole.VIEWER
    )
    request = await request_by(t.project, ada, rev1, item, (ivy, PENDING, None))

    response = await client.patch(org_member(t, ivy), json={"role": "member"})

    assert response.status_code == 200
    assert await rows(session, request) == {(ivy.id, PENDING)}


async def test_a_staff_role_change_that_takes_inherited_admin_away_replaces(
    client: AsyncClient, session: AsyncSession, t: Tenancy, ada: User, wren: User
) -> None:
    """§6.2 "Causes": the workspace role that gave inherited admin changed."""
    item, (rev1,) = await requirement(t)
    sam = await staff_admin(t, "Sam Staff")
    request = await request_by(t.project, ada, rev1, item, (sam, PENDING, None))

    response = await client.patch(staff(t, sam), json={"role": "member"})

    assert response.status_code == 200
    assert await rows(session, request) == {(sam.id, REPLACED), (ada.id, PENDING)}


# --- Accounts -------------------------------------------------------------------------------


async def test_deactivating_an_approver_replaces_their_row(
    client: AsyncClient, session: AsyncSession, t: Tenancy, ada: User, wren: User
) -> None:
    """§6.2 "Causes": they are deactivated, keeping every membership. Bug: deactivation never
    calls the replacement (a deactivated account fails every check, so the row would stay
    pending with no one able to decide it)."""
    item, (rev1,) = await requirement(t)
    vera = await org_viewer(t, "Vera Viewer")
    request = await request_by(t.project, ada, rev1, item, (vera, PENDING, None))

    response = await client.post(f"/api/users/{vera.id}/deactivate")

    assert response.status_code == 204
    assert await rows(session, request) == {(vera.id, REPLACED), (ada.id, PENDING)}
    assert await logged(session, ActivityEntityType.APPROVAL_REQUEST, request.id) == {
        ("approver_id", str(vera.id), str(ada.id), wren.id)
    }


async def test_deactivating_the_requester_leaves_their_requests_rows_alone(
    client: AsyncClient, session: AsyncSession, t: Tenancy, ada: User, wren: User
) -> None:
    """§6.2: only approvers who lost access are replaced; the requester's own loss replaces
    no one (the request is flagged for a project admin instead). Bug: the replacement
    treats everyone on a request it scans as gone."""
    item, (rev1,) = await requirement(t)
    vera = await org_viewer(t, "Vera Viewer")
    request = await request_by(t.project, ada, rev1, item, (vera, PENDING, None))

    response = await client.post(f"/api/users/{ada.id}/deactivate")

    assert response.status_code == 204
    assert await rows(session, request) == {(vera.id, PENDING)}


async def test_revoking_system_admin_replaces_with_no_actor(
    session: AsyncSession, settings: Settings, t: Tenancy, ada: User
) -> None:
    """§6.2 "Causes" and "Logged": `revoke-system-admin` is an app CLI command, so
    `changed_by` is null. Called through the service the CLI calls (the CLI's own wiring is in
    tests/integration/test_cli.py). Bug: revocation never calls the replacement, or logs an
    actor."""
    item, (rev1,) = await requirement(t)
    sid = await UserFactory.create_async(name="Sid Sysadmin", is_system_admin=True, is_active=True)
    await UserFactory.create_async(is_system_admin=True, is_active=True)  # not the last one
    request = await request_by(t.project, ada, rev1, item, (sid, PENDING, None))

    assert await AuthService(session, settings).revoke_system_admin(sid.email) is True

    assert await rows(session, request) == {(sid.id, REPLACED), (ada.id, PENDING)}
    assert await logged(session, ActivityEntityType.APPROVAL_REQUEST, request.id) == {
        ("approver_id", str(sid.id), str(ada.id), None)
    }
