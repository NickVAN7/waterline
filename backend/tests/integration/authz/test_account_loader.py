"""A user as an account action's target (DL-73; build plan, "Users": "The account actions"): its
workspace, and the user's ID and memberships for the rank rule, loaded from real joins. The rule
trusts the memberships it's given, so a project membership's org and workspace come from the
project row (`project.organization_id`, `project.workspace_id`), never from the user's other
memberships (S1-C3 security review); a user with no memberships is in the only workspace
(design-doc §4, "One workspace")."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.target import Target
from app.enums import OrgRole, ProjectRole, WorkspaceRole
from app.models.user import User
from app.rules.account_rank import Account, OrgRoleHeld, ProjectRoleHeld, WorkspaceRoleHeld
from app.services.user import AccountSubject, UserService
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory

pytestmark = [pytest.mark.anyio, pytest.mark.security]


async def loaded(session: AsyncSession, user: User) -> tuple[AccountSubject, Target]:
    result = await UserService(session).load(user.id)
    assert result is not None
    return result


def held(target: Target) -> set[object]:
    assert isinstance(target.entity, Account)
    return set(target.entity.memberships)


async def test_the_target_carries_every_membership_of_the_user(session: AsyncSession) -> None:
    workspace = await WorkspaceFactory.create_async()
    bolt = await OrganizationFactory.create_async(workspace=workspace)
    cove = await OrganizationFactory.create_async(workspace=workspace)
    payments = await ProjectFactory.create_async(organization=bolt)
    user = await UserFactory.create_async(is_system_admin=False)
    await WorkspaceMembershipFactory.create_async(
        workspace=workspace, user=user, role=WorkspaceRole.MEMBER
    )
    await MembershipFactory.create_async(organization=cove, user=user, role=OrgRole.ADMIN)
    await ProjectMembershipFactory.create_async(
        project=payments, user=user, role=ProjectRole.VIEWER
    )

    _, target = await loaded(session, user)

    assert held(target) == {
        WorkspaceRoleHeld(workspace_id=workspace.id, role=WorkspaceRole.MEMBER),
        OrgRoleHeld(workspace_id=workspace.id, org_id=cove.id, role=OrgRole.ADMIN),
        ProjectRoleHeld(workspace_id=workspace.id, org_id=bolt.id, project_id=payments.id),
    }
    assert (target.workspace_id, target.user_id) == (workspace.id, user.id)


async def test_a_project_only_user_in_another_org_gets_that_projects_org(
    session: AsyncSession,
) -> None:
    """The project's org comes from the project row: the user has no role in it, only one in
    another org, which an admin of that other org must not be able to treat as covering them."""
    workspace = await WorkspaceFactory.create_async()
    their_org = await OrganizationFactory.create_async(workspace=workspace)
    project_org = await OrganizationFactory.create_async(workspace=workspace)
    ledger = await ProjectFactory.create_async(organization=project_org)
    user = await UserFactory.create_async(is_system_admin=False)
    await MembershipFactory.create_async(organization=their_org, user=user, role=OrgRole.MEMBER)
    await ProjectMembershipFactory.create_async(project=ledger, user=user, role=ProjectRole.MEMBER)

    _, target = await loaded(session, user)

    assert held(target) == {
        OrgRoleHeld(workspace_id=workspace.id, org_id=their_org.id, role=OrgRole.MEMBER),
        ProjectRoleHeld(workspace_id=workspace.id, org_id=project_org.id, project_id=ledger.id),
    }


async def test_only_the_users_own_memberships_are_loaded(session: AsyncSession) -> None:
    workspace = await WorkspaceFactory.create_async()
    bolt = await OrganizationFactory.create_async(workspace=workspace)
    user = await UserFactory.create_async(is_system_admin=False)
    await MembershipFactory.create_async(organization=bolt, user=user, role=OrgRole.MEMBER)
    someone_else = await UserFactory.create_async()
    await WorkspaceMembershipFactory.create_async(
        workspace=workspace, user=someone_else, role=WorkspaceRole.OWNER
    )
    await MembershipFactory.create_async(organization=bolt, user=someone_else, role=OrgRole.OWNER)

    _, target = await loaded(session, user)

    assert held(target) == {
        OrgRoleHeld(workspace_id=workspace.id, org_id=bolt.id, role=OrgRole.MEMBER)
    }


async def test_the_system_admin_flag_is_carried(session: AsyncSession) -> None:
    workspace = await WorkspaceFactory.create_async()
    user = await UserFactory.create_async(is_system_admin=True)
    await WorkspaceMembershipFactory.create_async(
        workspace=workspace, user=user, role=WorkspaceRole.OWNER
    )

    subject, target = await loaded(session, user)

    assert target.entity == Account(
        is_system_admin=True,
        memberships=(WorkspaceRoleHeld(workspace_id=workspace.id, role=WorkspaceRole.OWNER),),
    )
    assert subject.account == target.entity


async def test_a_user_with_no_memberships_is_in_the_only_workspace_holding_nothing(
    session: AsyncSession,
) -> None:
    workspace = await WorkspaceFactory.create_async()
    user = await UserFactory.create_async(is_system_admin=False)

    subject, target = await loaded(session, user)

    assert target.entity == Account(is_system_admin=False, memberships=())
    assert (target.workspace_id, target.user_id) == (workspace.id, user.id)
    assert subject.account == target.entity
    assert subject.user.id == user.id


async def test_the_subject_and_the_target_carry_the_same_memberships(
    session: AsyncSession,
) -> None:
    """The service acts on what `authorize()` decided on."""
    workspace = await WorkspaceFactory.create_async()
    bolt = await OrganizationFactory.create_async(workspace=workspace)
    user = await UserFactory.create_async(is_system_admin=False)
    await MembershipFactory.create_async(organization=bolt, user=user, role=OrgRole.OWNER)

    subject, target = await loaded(session, user)

    assert subject.account == Account(
        memberships=(OrgRoleHeld(workspace_id=workspace.id, org_id=bolt.id, role=OrgRole.OWNER),)
    )
    assert target.entity == subject.account
