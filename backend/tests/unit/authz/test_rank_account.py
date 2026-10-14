"""The actor's side of the rank rule (build plan, "Users": "The account actions", DL-73: "the rank
rule (`can_manage_account`, the actor's roles from the context)"; DL-75: `covering_orgs` decides
an account action's audit orgs from it). `rank_account(ctx)` is the user's memberships as the rank
rule sees them: the system-admin flag, each workspace role, each org role in its own workspace
(`org_workspaces`), and each project membership in its project's org and workspace (the
`ProjectAccess`, from the project row), and nothing else. The order of the memberships carries no
meaning, so they're compared as a set.
"""

import uuid

import pytest

from app.authz.context import AuthzContext, ProjectAccess, rank_account
from app.enums import OrgRole, ProjectRole, WorkspaceRole
from app.rules.account_rank import Account, OrgRoleHeld, ProjectRoleHeld, WorkspaceRoleHeld

pytestmark = pytest.mark.security

USER = uuid.UUID(int=1)
WS = uuid.UUID(int=10)
WS2 = uuid.UUID(int=11)
ORG = uuid.UUID(int=20)
ORG2 = uuid.UUID(int=21)
PROJ = uuid.UUID(int=30)
PROJ2 = uuid.UUID(int=31)


def memberships(account: Account) -> set[object]:
    return set(account.memberships)


@pytest.mark.parametrize("flag", [True, False])
def test_the_system_admin_flag_is_carried(flag: bool) -> None:
    account = rank_account(AuthzContext(user_id=USER, is_system_admin=flag))

    assert account.is_system_admin is flag
    assert account.memberships == ()


@pytest.mark.parametrize("role", list(WorkspaceRole))
def test_each_workspace_role_is_held_in_its_workspace(role: WorkspaceRole) -> None:
    account = rank_account(AuthzContext(user_id=USER, workspace_roles={WS: role}))

    assert account == Account(
        is_system_admin=False, memberships=(WorkspaceRoleHeld(workspace_id=WS, role=role),)
    )


@pytest.mark.parametrize("role", list(OrgRole))
def test_each_org_role_is_held_in_its_org_and_the_orgs_workspace(role: OrgRole) -> None:
    ctx = AuthzContext(user_id=USER, org_roles={ORG: role}, org_workspaces={ORG: WS})

    assert rank_account(ctx) == Account(
        is_system_admin=False,
        memberships=(OrgRoleHeld(workspace_id=WS, org_id=ORG, role=role),),
    )


@pytest.mark.parametrize("role", list(ProjectRole))
def test_each_project_membership_is_held_in_its_projects_org_and_workspace(
    role: ProjectRole,
) -> None:
    """The org and workspace come from the `ProjectAccess` (the project row), never from the
    user's other roles: here the user's org role is in another org and workspace."""
    ctx = AuthzContext(
        user_id=USER,
        org_roles={ORG: OrgRole.ADMIN},
        org_workspaces={ORG: WS},
        projects={PROJ: ProjectAccess(role, ORG2, WS2)},
    )

    assert memberships(rank_account(ctx)) == {
        OrgRoleHeld(workspace_id=WS, org_id=ORG, role=OrgRole.ADMIN),
        ProjectRoleHeld(workspace_id=WS2, org_id=ORG2, project_id=PROJ),
    }


def test_every_role_of_the_context_is_held_and_nothing_else() -> None:
    ctx = AuthzContext(
        user_id=USER,
        is_system_admin=True,
        workspace_roles={WS: WorkspaceRole.MEMBER, WS2: WorkspaceRole.OWNER},
        org_roles={ORG: OrgRole.OWNER, ORG2: OrgRole.MEMBER},
        org_workspaces={ORG: WS, ORG2: WS2},
        projects={
            PROJ: ProjectAccess(ProjectRole.VIEWER, ORG, WS),
            PROJ2: ProjectAccess(ProjectRole.ADMIN, ORG2, WS2, archived=True),
        },
    )

    account = rank_account(ctx)

    assert account.is_system_admin is True
    assert memberships(account) == {
        WorkspaceRoleHeld(workspace_id=WS, role=WorkspaceRole.MEMBER),
        WorkspaceRoleHeld(workspace_id=WS2, role=WorkspaceRole.OWNER),
        OrgRoleHeld(workspace_id=WS, org_id=ORG, role=OrgRole.OWNER),
        OrgRoleHeld(workspace_id=WS2, org_id=ORG2, role=OrgRole.MEMBER),
        ProjectRoleHeld(workspace_id=WS, org_id=ORG, project_id=PROJ),
        ProjectRoleHeld(workspace_id=WS2, org_id=ORG2, project_id=PROJ2),
    }
    assert len(account.memberships) == 6


def test_a_context_with_no_roles_holds_nothing() -> None:
    assert rank_account(AuthzContext(user_id=USER)) == Account(
        is_system_admin=False, memberships=()
    )
