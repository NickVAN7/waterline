"""Content scoping for lists (S2-C4; design-doc §5, "Reads are authorized too": lists are scoped
at the query level; §3.1, "Export-controlled projects (who sees content)"; S2-plan, threat model:
"Export-controlled content leaking through a list…": content scoping in every list query).

`content_scope(ctx)` says which projects' content the user can see: the projects they see
(`project_scope`), except that an export-controlled project needs an explicit membership.
`Scope.content` (its docstring): only `ids` reach an export-controlled project; a row reached
through `everything`, an org, or a workspace (inherited admin) must not be in one.
"""

import uuid

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.authz.context import AuthzContext, ProjectAccess
from app.authz.scoping import Scope, content_scope
from app.enums import OrgRole, ProjectRole, WorkspaceRole

pytestmark = pytest.mark.security

WS = uuid.UUID(int=1)
WS2 = uuid.UUID(int=2)
ORG_A = uuid.UUID(int=10)
ORG_B = uuid.UUID(int=11)
ORG_C = uuid.UUID(int=12)
# Two projects in ORG_A (WS), one in ORG_B (WS), one in ORG_C (WS2).
PROJ_A1 = uuid.UUID(int=100)
PROJ_A2 = uuid.UUID(int=101)
PROJ_B1 = uuid.UUID(int=102)
PROJ_C1 = uuid.UUID(int=103)
_PROJECTS = {PROJ_A1: ORG_A, PROJ_A2: ORG_A, PROJ_B1: ORG_B, PROJ_C1: ORG_C}
_ORGS = {ORG_A: WS, ORG_B: WS, ORG_C: WS2}


def admits(scope: Scope, project: uuid.UUID, export_controlled: bool) -> bool:
    """`Scope`'s documented meaning, as a repository's WHERE applies it to a project row."""
    org = _PROJECTS[project]
    by_id = project in scope.ids
    inherited = (
        scope.everything or org in scope.organization_ids or _ORGS[org] in scope.workspace_ids
    )
    if scope.content and export_controlled:
        return by_id
    return by_id or inherited


def _ctx(**kwargs: object) -> AuthzContext:
    return AuthzContext(user_id=uuid.UUID(int=1000), **kwargs)  # pyright: ignore[reportArgumentType]


def _explicit(
    project: uuid.UUID, role: ProjectRole = ProjectRole.VIEWER
) -> dict[uuid.UUID, ProjectAccess]:
    org = _PROJECTS[project]
    return {project: ProjectAccess(role, org, _ORGS[org])}


SYSTEM_ADMIN = _ctx(is_system_admin=True)
WORKSPACE_ADMIN = _ctx(workspace_roles={WS: WorkspaceRole.ADMIN})
WORKSPACE_OWNER = _ctx(workspace_roles={WS: WorkspaceRole.OWNER})
ORG_ADMIN = _ctx(org_roles={ORG_A: OrgRole.ADMIN}, org_workspaces={ORG_A: WS})
ORG_OWNER = _ctx(org_roles={ORG_A: OrgRole.OWNER}, org_workspaces={ORG_A: WS})
INHERITED = [SYSTEM_ADMIN, WORKSPACE_ADMIN, WORKSPACE_OWNER, ORG_ADMIN, ORG_OWNER]
INHERITED_IDS = ["system_admin", "workspace_admin", "workspace_owner", "org_admin", "org_owner"]


@pytest.mark.parametrize("ctx", INHERITED, ids=INHERITED_IDS)
def test_an_inherited_admin_sees_the_content_of_a_project_that_is_not_export_controlled(
    ctx: AuthzContext,
) -> None:
    assert admits(content_scope(ctx), PROJ_A1, export_controlled=False) is True


@pytest.mark.parametrize("ctx", INHERITED, ids=INHERITED_IDS)
def test_an_inherited_admin_does_not_see_the_content_of_an_export_controlled_project(
    ctx: AuthzContext,
) -> None:
    """§3.1: they lose content access unless they hold an explicit membership."""
    assert admits(content_scope(ctx), PROJ_A1, export_controlled=True) is False


@pytest.mark.parametrize("ctx", INHERITED, ids=INHERITED_IDS)
def test_an_inherited_admin_with_an_explicit_membership_sees_its_export_controlled_content(
    ctx: AuthzContext,
) -> None:
    with_membership = AuthzContext(
        user_id=ctx.user_id,
        is_system_admin=ctx.is_system_admin,
        workspace_roles=ctx.workspace_roles,
        org_roles=ctx.org_roles,
        org_workspaces=ctx.org_workspaces,
        projects=_explicit(PROJ_A1),
    )
    scope = content_scope(with_membership)

    assert admits(scope, PROJ_A1, export_controlled=True) is True
    # Their other export-controlled project in the same org stays out.
    assert admits(scope, PROJ_A2, export_controlled=True) is False


@pytest.mark.parametrize("role", list(ProjectRole))
@pytest.mark.parametrize("export_controlled", [False, True])
def test_an_explicit_member_sees_their_projects_content(
    role: ProjectRole, export_controlled: bool
) -> None:
    scope = content_scope(_ctx(projects=_explicit(PROJ_B1, role)))

    assert admits(scope, PROJ_B1, export_controlled) is True
    assert admits(scope, PROJ_A1, export_controlled=False) is False


def test_a_system_admin_sees_content_in_every_workspace_but_not_export_controlled() -> None:
    scope = content_scope(SYSTEM_ADMIN)

    assert admits(scope, PROJ_C1, export_controlled=False) is True
    assert admits(scope, PROJ_C1, export_controlled=True) is False


# --- Agrees with §3.1 over many contexts (Hypothesis, independent oracle) ----------------------

contexts = st.builds(
    AuthzContext,
    user_id=st.just(uuid.UUID(int=1)),
    is_system_admin=st.booleans(),
    workspace_roles=st.dictionaries(st.sampled_from([WS, WS2]), st.sampled_from(WorkspaceRole)),
    org_roles=st.dictionaries(st.sampled_from(list(_ORGS)), st.sampled_from(OrgRole)),
    projects=st.dictionaries(st.sampled_from(list(_PROJECTS)), st.sampled_from(ProjectRole)).map(
        lambda held: {
            p: ProjectAccess(role, _PROJECTS[p], _ORGS[_PROJECTS[p]]) for p, role in held.items()
        }
    ),
)

_ADMINS = {WorkspaceRole.OWNER, WorkspaceRole.ADMIN, OrgRole.OWNER, OrgRole.ADMIN}


def sees_content(ctx: AuthzContext, project: uuid.UUID, export_controlled: bool) -> bool:
    """§4 "Visibility" and §3.1: an explicit membership; otherwise inherited admin, and only on a
    project that isn't export-controlled."""
    org = _PROJECTS[project]
    inherited = (
        ctx.is_system_admin
        or ctx.workspace_roles.get(_ORGS[org]) in _ADMINS
        or ctx.org_roles.get(org) in _ADMINS
    )
    return project in ctx.projects or (inherited and not export_controlled)


@given(ctx=contexts, project=st.sampled_from(list(_PROJECTS)), export_controlled=st.booleans())
def test_content_scope_agrees_with_who_sees_content(
    ctx: AuthzContext, project: uuid.UUID, export_controlled: bool
) -> None:
    assert admits(content_scope(ctx), project, export_controlled) is sees_content(
        ctx, project, export_controlled
    )
