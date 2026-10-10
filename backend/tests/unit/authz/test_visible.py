"""`ActionSpec.visible`: an action granted to anyone who can see the target (design-doc §4,
"Visibility"), on top of the roles it names (DL-56: `org.view`, for e.g. a project member with
no org role). Proven with test-only actions (DL-44), so no real action's spec is involved; the
archived-project check (design-doc §5, step 1) still comes first.

Personas and the layout are those of tests/support/authz.py.
"""

import uuid
from unittest.mock import patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.authz.actions import REGISTRY, ActionSpec, Level
from app.authz.authorize import allowed_actions, authorize
from app.authz.context import AuthzContext, ProjectAccess
from app.authz.target import Target
from app.enums import OrgRole, ProjectRole, WorkspaceRole
from tests.support.authz import (
    ARCHIVED_PROJECT_TARGET,
    ORG,
    ORG2,
    ORG3,
    ORG_TARGET,
    PERSONAS,
    PROJ,
    PROJ2,
    PROJ3,
    PROJ4,
    PROJECT_TARGET,
    WORKSPACE_TARGET,
    WS,
    WS2,
    rows,
)

pytestmark = pytest.mark.security

VISIBLE_WS_READ = "test_visible.workspace_read"
VISIBLE_ORG_READ = "test_visible.org_read"
VISIBLE_PROJECT_READ = "test_visible.project_read"
VISIBLE_PROJECT_EDIT = "test_visible.project_edit"
HIDDEN_ORG_READ = "test_visible.org_read_not_visible"

VISIBLE_ACTIONS = {
    VISIBLE_WS_READ: ActionSpec(Level.WORKSPACE, mutation=False, visible=True),
    VISIBLE_ORG_READ: ActionSpec(Level.ORGANIZATION, mutation=False, visible=True),
    VISIBLE_PROJECT_READ: ActionSpec(Level.PROJECT, mutation=False, visible=True),
    VISIBLE_PROJECT_EDIT: ActionSpec(Level.PROJECT, visible=True),
    # The same spec as VISIBLE_ORG_READ without `visible`: no role, so only system admins.
    HIDDEN_ORG_READ: ActionSpec(Level.ORGANIZATION, mutation=False),
}


@pytest.fixture(autouse=True)
def _visible_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, spec in VISIBLE_ACTIONS.items():
        monkeypatch.setitem(REGISTRY, name, spec)


SEES_THE_WORKSPACE = {"system_admin", "workspace_owner", "workspace_admin"}
SEES_THE_ORG = {
    "system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin", "org_member",
    "project_admin", "project_member", "project_viewer", "other_project_admin",
}  # fmt: skip
SEES_THE_PROJECT = {
    "system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin",
    "project_admin", "project_member", "project_viewer",
}  # fmt: skip


@pytest.mark.parametrize(("persona", "allowed"), rows(SEES_THE_ORG))
def test_a_visible_org_action_is_granted_to_whoever_sees_the_org(
    persona: str, allowed: bool
) -> None:
    """A project membership on one of the org's projects counts; staff membership alone, and
    roles in another org or workspace, don't."""
    assert authorize(PERSONAS[persona], VISIBLE_ORG_READ, ORG_TARGET) is allowed


@pytest.mark.parametrize(("persona", "allowed"), rows({"system_admin"}))
def test_without_visible_the_same_spec_is_granted_to_system_admins_only(
    persona: str, allowed: bool
) -> None:
    assert authorize(PERSONAS[persona], HIDDEN_ORG_READ, ORG_TARGET) is allowed


@pytest.mark.parametrize(("persona", "allowed"), rows(SEES_THE_PROJECT))
def test_a_visible_project_action_is_granted_to_whoever_sees_the_project(
    persona: str, allowed: bool
) -> None:
    """An org membership alone (role member) shows the org, not its projects (§4)."""
    assert authorize(PERSONAS[persona], VISIBLE_PROJECT_READ, PROJECT_TARGET) is allowed


@pytest.mark.parametrize(("persona", "allowed"), rows(SEES_THE_WORKSPACE))
def test_a_visible_workspace_action_is_granted_to_whoever_sees_the_workspace(
    persona: str, allowed: bool
) -> None:
    """Only workspace owners/admins and system admins see the workspace pages (§4)."""
    assert authorize(PERSONAS[persona], VISIBLE_WS_READ, WORKSPACE_TARGET) is allowed


def test_visible_counts_only_for_the_org_the_user_sees() -> None:
    """A project in ORG2 shows ORG2, not ORG."""
    in_org2 = AuthzContext(
        user_id=uuid.uuid4(), projects={PROJ3: ProjectAccess(ProjectRole.VIEWER, ORG2, WS)}
    )

    assert (
        authorize(in_org2, VISIBLE_ORG_READ, Target(workspace_id=WS, organization_id=ORG2)) is True
    )
    assert authorize(in_org2, VISIBLE_ORG_READ, ORG_TARGET) is False


@pytest.mark.parametrize("persona", list(PERSONAS))
def test_a_visible_mutation_in_an_archived_project_is_denied_to_everyone(persona: str) -> None:
    """The archived check comes first (design-doc §5, step 1), whoever sees the project."""
    assert authorize(PERSONAS[persona], VISIBLE_PROJECT_EDIT, ARCHIVED_PROJECT_TARGET) is False


@pytest.mark.parametrize(("persona", "allowed"), rows(SEES_THE_PROJECT))
def test_a_visible_read_in_an_archived_project_is_still_granted(
    persona: str, allowed: bool
) -> None:
    assert authorize(PERSONAS[persona], VISIBLE_PROJECT_READ, ARCHIVED_PROJECT_TARGET) is allowed


@pytest.mark.parametrize(
    ("persona", "expected"),
    [
        ("org_member", ["org.view"]),
        ("project_viewer", ["org.view"]),
        ("workspace_member", []),
        ("nobody", []),
    ],
)
def test_allowed_actions_includes_a_real_action_granted_only_by_visible(
    persona: str, expected: list[str]
) -> None:
    """`org.view` is the real visible action (DL-56); these personas hold no role granting any
    other org-level action, and test-only actions are never listed."""
    assert allowed_actions(PERSONAS[persona], ORG_TARGET) == expected


# --- An independent oracle over many contexts (Hypothesis) -------------------------------------

_WS_RANK = {WorkspaceRole.MEMBER: 1, WorkspaceRole.ADMIN: 2, WorkspaceRole.OWNER: 3}
_ORG_RANK = {OrgRole.MEMBER: 1, OrgRole.ADMIN: 2, OrgRole.OWNER: 3}
_PROJECT_RANK = {ProjectRole.VIEWER: 1, ProjectRole.MEMBER: 2, ProjectRole.ADMIN: 3}
_PROJECTS = {PROJ: (ORG, WS), PROJ2: (ORG, WS), PROJ3: (ORG2, WS), PROJ4: (ORG3, WS2)}
_ORGS = {ORG: WS, ORG2: WS, ORG3: WS2}

contexts = st.builds(
    AuthzContext,
    user_id=st.just(uuid.UUID(int=1)),
    is_system_admin=st.booleans(),
    workspace_roles=st.dictionaries(st.sampled_from([WS, WS2]), st.sampled_from(WorkspaceRole)),
    org_roles=st.dictionaries(st.sampled_from(list(_ORGS)), st.sampled_from(OrgRole)),
    projects=st.dictionaries(st.sampled_from(list(_PROJECTS)), st.sampled_from(ProjectRole)).map(
        lambda held: {
            project: ProjectAccess(role, *_PROJECTS[project]) for project, role in held.items()
        }
    ),
)


def _project_target(project: uuid.UUID, archived: bool) -> Target:
    org, workspace = _PROJECTS[project]
    return Target(
        workspace_id=workspace, organization_id=org, project_id=project, archived=archived
    )


_ADMIN_OR_ABOVE_WS = st.sampled_from([None, WorkspaceRole.ADMIN, WorkspaceRole.OWNER])
_ADMIN_OR_ABOVE_ORG = st.sampled_from([None, OrgRole.ADMIN, OrgRole.OWNER])
specs_and_targets = st.one_of(
    st.tuples(
        st.builds(
            ActionSpec,
            level=st.just(Level.WORKSPACE),
            workspace_role=st.sampled_from([None, *WorkspaceRole]),
            mutation=st.booleans(),
            visible=st.booleans(),
        ),
        st.sampled_from([Target(workspace_id=WS), Target(workspace_id=WS2)]),
    ),
    st.tuples(
        st.builds(
            ActionSpec,
            level=st.just(Level.ORGANIZATION),
            workspace_role=_ADMIN_OR_ABOVE_WS,
            org_role=st.sampled_from([None, *OrgRole]),
            mutation=st.booleans(),
            visible=st.booleans(),
        ),
        st.sampled_from(
            [Target(workspace_id=ws, organization_id=org) for org, ws in _ORGS.items()]
        ),
    ),
    st.tuples(
        st.builds(
            ActionSpec,
            level=st.just(Level.PROJECT),
            workspace_role=_ADMIN_OR_ABOVE_WS,
            org_role=_ADMIN_OR_ABOVE_ORG,
            project_role=st.sampled_from([None, *ProjectRole]),
            mutation=st.booleans(),
            archive_exempt=st.booleans(),
            visible=st.booleans(),
        ),
        st.builds(_project_target, st.sampled_from(list(_PROJECTS)), st.booleans()),
    ),
)


def _admin_of_workspace(ctx: AuthzContext, workspace: uuid.UUID) -> bool:
    return ctx.workspace_roles.get(workspace) in (WorkspaceRole.ADMIN, WorkspaceRole.OWNER)


def sees(ctx: AuthzContext, target: Target) -> bool:
    """design-doc §4, "Visibility", written independently of the code."""
    if ctx.is_system_admin or _admin_of_workspace(ctx, target.workspace_id):
        return True
    if target.project_id is not None:
        return target.project_id in ctx.projects or ctx.org_roles.get(
            target.organization_id  # pyright: ignore[reportArgumentType] -- set for a project
        ) in (OrgRole.ADMIN, OrgRole.OWNER)
    if target.organization_id is not None:
        return target.organization_id in ctx.org_roles or any(
            _PROJECTS[p][0] == target.organization_id for p in ctx.projects
        )
    return False


def _at_least[R](held: R | None, needed: R | None, rank: dict[R, int]) -> bool:
    return held is not None and needed is not None and rank[held] >= rank[needed]


def oracle(ctx: AuthzContext, spec: ActionSpec, target: Target) -> bool:
    """design-doc §5's order for a non-personal action, with `visible` on top of the roles."""
    if target.archived and spec.mutation and not spec.archive_exempt:
        return False
    project = ctx.projects.get(target.project_id) if target.project_id else None
    org_role = ctx.org_roles.get(target.organization_id) if target.organization_id else None
    return (
        ctx.is_system_admin
        or _at_least(ctx.workspace_roles.get(target.workspace_id), spec.workspace_role, _WS_RANK)
        or _at_least(org_role, spec.org_role, _ORG_RANK)
        or _at_least(project.role if project else None, spec.project_role, _PROJECT_RANK)
        or (spec.visible and sees(ctx, target))
    )


@given(ctx=contexts, spec_and_target=specs_and_targets)
def test_authorize_with_visible_agrees_with_the_documented_rules(
    ctx: AuthzContext, spec_and_target: tuple[ActionSpec, Target]
) -> None:
    spec, target = spec_and_target
    with patch.dict(REGISTRY, {"test_generated.visible": spec}):
        assert authorize(ctx, "test_generated.visible", target) is oracle(ctx, spec, target)
