"""Access scoping for lists (design-doc §5, "Reads are authorized too"; §4, "Visibility";
testing-strategy.md, "Security": list endpoints return only the user's accessible projects and
orgs)."""

import uuid
from collections.abc import Callable

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.authz.authorize import can_see
from app.authz.context import AuthzContext, ProjectAccess
from app.authz.scoping import Scope, org_scope, project_scope
from app.authz.target import Target
from app.enums import OrgRole, ProjectRole, WorkspaceRole

pytestmark = pytest.mark.security

WS = uuid.UUID(int=1)
WS2 = uuid.UUID(int=2)
WS3 = uuid.UUID(int=3)
ORG_A = uuid.UUID(int=10)
ORG_B = uuid.UUID(int=11)
ORG_C = uuid.UUID(int=12)
ORG_D = uuid.UUID(int=13)
ORG_E = uuid.UUID(int=14)
PROJ_1 = uuid.UUID(int=100)
PROJ_2 = uuid.UUID(int=101)

# Staff (admin) of WS, owner of WS2, plain staff of WS3; owner of ORG_A, admin of ORG_B, member of
# ORG_C; viewer of PROJ_1 (in ORG_D) and admin of PROJ_2 (in ORG_E).
MIXED = AuthzContext(
    user_id=uuid.UUID(int=1000),
    workspace_roles={WS: WorkspaceRole.ADMIN, WS2: WorkspaceRole.OWNER, WS3: WorkspaceRole.MEMBER},
    org_roles={ORG_A: OrgRole.OWNER, ORG_B: OrgRole.ADMIN, ORG_C: OrgRole.MEMBER},
    projects={
        PROJ_1: ProjectAccess(ProjectRole.VIEWER, ORG_D, WS3),
        PROJ_2: ProjectAccess(ProjectRole.ADMIN, ORG_E, WS3),
    },
)
SYSTEM_ADMIN = AuthzContext(user_id=uuid.UUID(int=1001), is_system_admin=True)
NOBODY = AuthzContext(user_id=uuid.UUID(int=1002))


def test_a_system_admin_sees_every_project() -> None:
    assert project_scope(SYSTEM_ADMIN).everything is True


def test_a_system_admin_sees_every_org() -> None:
    assert org_scope(SYSTEM_ADMIN).everything is True


def test_projects_are_scoped_to_memberships_and_inherited_admin() -> None:
    """Workspace and org owners/admins see every project under them; workspace and org members
    don't."""
    assert project_scope(MIXED) == Scope(
        ids=frozenset({PROJ_1, PROJ_2}),
        organization_ids=frozenset({ORG_A, ORG_B}),
        workspace_ids=frozenset({WS, WS2}),
    )


def test_orgs_are_scoped_to_memberships_projects_and_workspace_admin() -> None:
    """An org is seen through a membership in it (any role) or on one of its projects."""
    assert org_scope(MIXED) == Scope(
        ids=frozenset({ORG_A, ORG_B, ORG_C, ORG_D, ORG_E}),
        workspace_ids=frozenset({WS, WS2}),
    )


@pytest.mark.parametrize("scope", [project_scope, org_scope])
def test_a_user_with_no_membership_sees_nothing(scope: Callable[[AuthzContext], Scope]) -> None:
    assert scope(NOBODY) == Scope()


# --- The scope admits exactly the rows can_see() shows (Hypothesis, independent oracle) --------

# Two workspaces, three orgs, four projects.
_ORGS = {ORG_A: WS, ORG_B: WS, ORG_C: WS2}
_PROJECTS = {PROJ_1: ORG_A, PROJ_2: ORG_A, uuid.UUID(int=102): ORG_B, uuid.UUID(int=103): ORG_C}


def _access(held: dict[uuid.UUID, ProjectRole]) -> dict[uuid.UUID, ProjectAccess]:
    return {
        project: ProjectAccess(role, _PROJECTS[project], _ORGS[_PROJECTS[project]])
        for project, role in held.items()
    }


contexts = st.builds(
    AuthzContext,
    user_id=st.just(uuid.UUID(int=1)),
    is_system_admin=st.booleans(),
    workspace_roles=st.dictionaries(st.sampled_from([WS, WS2]), st.sampled_from(WorkspaceRole)),
    org_roles=st.dictionaries(st.sampled_from(list(_ORGS)), st.sampled_from(OrgRole)),
    projects=st.dictionaries(st.sampled_from(list(_PROJECTS)), st.sampled_from(ProjectRole)).map(
        _access
    ),
)

_ADMINS = {WorkspaceRole.OWNER, WorkspaceRole.ADMIN, OrgRole.OWNER, OrgRole.ADMIN}


def sees_project(ctx: AuthzContext, project: uuid.UUID) -> bool:
    """design-doc §4: a project membership, or inherited admin."""
    org = _PROJECTS[project]
    return (
        ctx.is_system_admin
        or project in ctx.projects
        or ctx.workspace_roles.get(_ORGS[org]) in _ADMINS
        or ctx.org_roles.get(org) in _ADMINS
    )


def sees_org(ctx: AuthzContext, org: uuid.UUID) -> bool:
    """design-doc §4: a membership in it, a project membership on one of its projects, or
    workspace owner/admin (and system admin)."""
    return (
        ctx.is_system_admin
        or org in ctx.org_roles
        or any(access.organization_id == org for access in ctx.projects.values())
        or ctx.workspace_roles.get(_ORGS[org]) in _ADMINS
    )


def admits(scope: Scope, row: uuid.UUID, org: uuid.UUID | None, workspace: uuid.UUID) -> bool:
    """`Scope`'s documented meaning, as a repository's WHERE would apply it."""
    return (
        scope.everything
        or row in scope.ids
        or (org is not None and org in scope.organization_ids)
        or workspace in scope.workspace_ids
    )


@given(ctx=contexts, project=st.sampled_from(list(_PROJECTS)))
def test_project_scope_and_can_see_agree_with_visibility(
    ctx: AuthzContext, project: uuid.UUID
) -> None:
    org = _PROJECTS[project]
    workspace = _ORGS[org]
    target = Target(workspace_id=workspace, organization_id=org, project_id=project)

    assert admits(project_scope(ctx), project, org, workspace) is sees_project(ctx, project)
    assert can_see(ctx, target) is sees_project(ctx, project)


@given(ctx=contexts, org=st.sampled_from(list(_ORGS)))
def test_org_scope_and_can_see_agree_with_visibility(ctx: AuthzContext, org: uuid.UUID) -> None:
    workspace = _ORGS[org]

    # `organization_ids` is unused for orgs: an org row is matched by its own ID.
    assert admits(org_scope(ctx), org, None, workspace) is sees_org(ctx, org)
    assert can_see(ctx, Target(workspace_id=workspace, organization_id=org)) is sees_org(ctx, org)
