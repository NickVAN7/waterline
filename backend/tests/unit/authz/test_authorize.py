"""`authorize()` and its helpers (design-doc §5, "The choke point" and "Role capabilities"; §4,
"Visibility"; build plan, "Authorization (§5)", the test matrix; DL-44, DL-45).

The org- and project-level rules are proven with test-only actions (DL-44,
tests/support/authz.py). Personas sit relative to workspace WS, org ORG (in WS), and project
PROJ (in ORG); see `PERSONAS`.
"""

import uuid
from unittest.mock import patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.authz.actions import REGISTRY, Action, ActionSpec, Level
from app.authz.authorize import allowed_actions, authorize, can_see, ensure, module_enabled
from app.authz.context import AuthzContext, ProjectAccess
from app.authz.target import Target
from app.core.errors import ForbiddenError, NotFoundError
from app.enums import OrgRole, ProjectRole, WorkspaceRole
from tests.support.authz import (
    ARCHIVED_PROJECT_TARGET,
    EDIT_OWN_COMMENT,
    ORG,
    ORG2,
    ORG3,
    ORG_CREATE_PROJECT,
    ORG_MANAGE,
    ORG_OWNER_LEVEL,
    ORG_TARGET,
    PERSONAS,
    PROJ,
    PROJ2,
    PROJ3,
    PROJ4,
    PROJECT_EDIT,
    PROJECT_MANAGE,
    PROJECT_TARGET,
    PROJECT_UNARCHIVE,
    PROJECT_VIEW,
    SYSTEM_ONLY,
    UNREGISTERED,
    WORKSPACE_TARGET,
    WS,
    WS2,
    WS_MEMBER_LEVEL,
    Comment,
    register_test_actions,
    rows,
)

pytestmark = pytest.mark.security


@pytest.fixture(autouse=True)
def _test_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    register_test_actions(monkeypatch)


# --- The workspace-level actions (DL-45) --------------------------------------------------------

WORKSPACE_STAFF_ADMINS = {"system_admin", "workspace_owner", "workspace_admin"}


@pytest.mark.parametrize(("persona", "allowed"), rows(WORKSPACE_STAFF_ADMINS))
def test_workspace_view(persona: str, allowed: bool) -> None:
    assert authorize(PERSONAS[persona], Action.WORKSPACE_VIEW, WORKSPACE_TARGET) is allowed


@pytest.mark.parametrize(("persona", "allowed"), rows({"system_admin", "workspace_owner"}))
def test_workspace_update_is_for_workspace_owners_and_system_admins(
    persona: str, allowed: bool
) -> None:
    assert authorize(PERSONAS[persona], Action.WORKSPACE_UPDATE, WORKSPACE_TARGET) is allowed


@pytest.mark.parametrize(("persona", "allowed"), rows(WORKSPACE_STAFF_ADMINS))
def test_workspace_staff_manage(persona: str, allowed: bool) -> None:
    assert authorize(PERSONAS[persona], Action.WORKSPACE_STAFF_MANAGE, WORKSPACE_TARGET) is allowed


@pytest.mark.parametrize(("persona", "allowed"), rows(WORKSPACE_STAFF_ADMINS))
def test_org_create(persona: str, allowed: bool) -> None:
    assert authorize(PERSONAS[persona], Action.ORG_CREATE, WORKSPACE_TARGET) is allowed


@pytest.mark.parametrize(
    ("persona", "allowed"),
    rows({"system_admin", "workspace_owner", "workspace_admin", "workspace_member"}),
)
def test_a_member_level_workspace_action_reaches_every_staff_role(
    persona: str, allowed: bool
) -> None:
    """Roles include the roles below them (design-doc §5): member < admin < owner. Org and
    project roles in the workspace grant nothing at workspace level."""
    assert authorize(PERSONAS[persona], WS_MEMBER_LEVEL, WORKSPACE_TARGET) is allowed


def test_a_workspace_role_counts_only_in_its_own_workspace() -> None:
    owner_elsewhere = AuthzContext(user_id=uuid.uuid4(), workspace_roles={WS2: WorkspaceRole.OWNER})

    assert authorize(owner_elsewhere, Action.WORKSPACE_VIEW, Target(workspace_id=WS2)) is True
    assert authorize(owner_elsewhere, Action.WORKSPACE_VIEW, WORKSPACE_TARGET) is False


# --- Org level: inherited admin, and an org member's project.create (design-doc §5, "Org roles")


@pytest.mark.parametrize(
    ("persona", "allowed"),
    rows({"system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin",
          "org_member"}),
)  # fmt: skip
def test_creating_a_project_is_for_org_members_and_the_admins_above(
    persona: str, allowed: bool
) -> None:
    """Denied to users whose only link to the org is a project membership, to workspace members
    with no role in the org, and to users of another org or workspace (testing-strategy.md,
    "Security")."""
    assert authorize(PERSONAS[persona], ORG_CREATE_PROJECT, ORG_TARGET) is allowed


@pytest.mark.parametrize(
    ("persona", "allowed"),
    rows({"system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"}),
)
def test_an_org_admin_action_is_denied_to_a_plain_org_member(persona: str, allowed: bool) -> None:
    assert authorize(PERSONAS[persona], ORG_MANAGE, ORG_TARGET) is allowed


@pytest.mark.parametrize(
    ("persona", "allowed"),
    rows({"system_admin", "workspace_owner", "workspace_admin", "org_owner"}),
)
def test_an_org_owner_action_is_denied_to_an_org_admin(persona: str, allowed: bool) -> None:
    """Workspace admins hold org owner capabilities in every org of the workspace."""
    assert authorize(PERSONAS[persona], ORG_OWNER_LEVEL, ORG_TARGET) is allowed


def test_an_org_role_counts_only_in_its_own_org() -> None:
    admin_of_o2 = AuthzContext(user_id=uuid.uuid4(), org_roles={ORG2: OrgRole.ADMIN})

    assert authorize(admin_of_o2, ORG_MANAGE, Target(workspace_id=WS, organization_id=ORG2)) is True
    assert authorize(admin_of_o2, ORG_MANAGE, ORG_TARGET) is False


# --- Project level: project roles and inherited project admin ----------------------------------

INHERITED_ADMINS = {"system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"}


@pytest.mark.parametrize(
    ("persona", "allowed"),
    rows(INHERITED_ADMINS | {"project_admin", "project_member", "project_viewer"}),
)
def test_a_viewer_level_action(persona: str, allowed: bool) -> None:
    """Workspace and org members get no inherited access; another project's admin and admins of
    another org or workspace get none here."""
    assert authorize(PERSONAS[persona], PROJECT_VIEW, PROJECT_TARGET) is allowed


@pytest.mark.parametrize(
    ("persona", "allowed"), rows(INHERITED_ADMINS | {"project_admin", "project_member"})
)
def test_a_member_level_action_is_denied_to_a_viewer(persona: str, allowed: bool) -> None:
    assert authorize(PERSONAS[persona], PROJECT_EDIT, PROJECT_TARGET) is allowed


@pytest.mark.parametrize(("persona", "allowed"), rows(INHERITED_ADMINS | {"project_admin"}))
def test_an_admin_level_action_is_for_project_admins_including_inherited(
    persona: str, allowed: bool
) -> None:
    assert authorize(PERSONAS[persona], PROJECT_MANAGE, PROJECT_TARGET) is allowed


@pytest.mark.parametrize(("persona", "allowed"), rows({"system_admin"}))
def test_an_action_no_role_grants_is_for_system_admins_only(persona: str, allowed: bool) -> None:
    assert authorize(PERSONAS[persona], SYSTEM_ONLY, PROJECT_TARGET) is allowed


def test_a_system_admin_is_granted_in_a_workspace_they_hold_no_role_in() -> None:
    far_project = Target(workspace_id=WS2, organization_id=ORG3, project_id=PROJ4)

    assert authorize(PERSONAS["system_admin"], PROJECT_MANAGE, far_project) is True


def test_a_project_role_counts_only_on_its_own_project() -> None:
    """The role comes from the membership on the target project, not from any project in the
    same org."""
    admin_of_p2 = PERSONAS["other_project_admin"]
    p2 = Target(workspace_id=WS, organization_id=ORG, project_id=PROJ2)

    assert authorize(admin_of_p2, PROJECT_MANAGE, p2) is True
    assert authorize(admin_of_p2, PROJECT_VIEW, PROJECT_TARGET) is False


def test_an_inherited_admin_counts_in_the_projects_own_org_only() -> None:
    owner_of_o2 = PERSONAS["other_org_owner"]
    p3 = Target(workspace_id=WS, organization_id=ORG2, project_id=PROJ3)

    assert authorize(owner_of_o2, PROJECT_MANAGE, p3) is True
    assert authorize(owner_of_o2, PROJECT_VIEW, PROJECT_TARGET) is False


# --- The archived project (design-doc §5, step 1) ----------------------------------------------


@pytest.mark.parametrize("action", [PROJECT_EDIT, PROJECT_MANAGE, SYSTEM_ONLY])
@pytest.mark.parametrize("persona", list(PERSONAS))
def test_every_mutation_in_an_archived_project_is_denied_to_every_role(
    persona: str, action: str
) -> None:
    assert authorize(PERSONAS[persona], action, ARCHIVED_PROJECT_TARGET) is False


@pytest.mark.parametrize(
    ("persona", "allowed"),
    rows(INHERITED_ADMINS | {"project_admin", "project_member", "project_viewer"}),
)
def test_reads_in_an_archived_project_are_still_allowed(persona: str, allowed: bool) -> None:
    assert authorize(PERSONAS[persona], PROJECT_VIEW, ARCHIVED_PROJECT_TARGET) is allowed


@pytest.mark.parametrize(("persona", "allowed"), rows(INHERITED_ADMINS | {"project_admin"}))
def test_an_archive_exempt_mutation_is_allowed_in_an_archived_project(
    persona: str, allowed: bool
) -> None:
    """Unarchive, and removing a member with their projects: still role-checked."""
    assert authorize(PERSONAS[persona], PROJECT_UNARCHIVE, ARCHIVED_PROJECT_TARGET) is allowed


# --- Personal actions (design-doc §5, step 3) ---------------------------------------------------

CONTENT_ACCESS = INHERITED_ADMINS | {"project_admin", "project_member", "project_viewer"}


def authored_by(persona: str, target: Target = PROJECT_TARGET) -> Target:
    return Target(
        workspace_id=target.workspace_id,
        organization_id=target.organization_id,
        project_id=target.project_id,
        archived=target.archived,
        entity=Comment(author_id=PERSONAS[persona].user_id),
    )


@pytest.mark.parametrize(("persona", "allowed"), rows(CONTENT_ACCESS))
def test_a_personal_action_is_allowed_by_its_relationship_with_project_access(
    persona: str, allowed: bool
) -> None:
    """With the relationship: allowed for any project membership or inherited admin; denied
    to workspace and org members, another project's admin, and outsiders (no project
    access)."""
    assert authorize(PERSONAS[persona], EDIT_OWN_COMMENT, authored_by(persona)) is allowed


@pytest.mark.parametrize("persona", list(PERSONAS))
def test_no_role_grants_a_personal_action_without_its_relationship(persona: str) -> None:
    """Every admin level, system admin included, and every project role is denied, although
    the test action names a role at every level."""
    someone_elses = Target(
        workspace_id=WS,
        organization_id=ORG,
        project_id=PROJ,
        entity=Comment(author_id=uuid.UUID(int=9999)),
    )

    assert authorize(PERSONAS[persona], EDIT_OWN_COMMENT, someone_elses) is False


@pytest.mark.parametrize("persona", list(PERSONAS))
def test_a_personal_action_in_an_archived_project_is_denied(persona: str) -> None:
    target = authored_by(persona, ARCHIVED_PROJECT_TARGET)

    assert authorize(PERSONAS[persona], EDIT_OWN_COMMENT, target) is False


def test_a_personal_action_with_no_entity_is_denied() -> None:
    assert authorize(PERSONAS["project_admin"], EDIT_OWN_COMMENT, PROJECT_TARGET) is False


# --- Fail closed --------------------------------------------------------------------------------


@pytest.mark.parametrize("target", [WORKSPACE_TARGET, ORG_TARGET, PROJECT_TARGET])
@pytest.mark.parametrize("persona", list(PERSONAS))
def test_an_unregistered_action_is_denied_to_everyone(persona: str, target: Target) -> None:
    assert authorize(PERSONAS[persona], UNREGISTERED, target) is False


@pytest.mark.parametrize("action", ["Workspace.View", "workspace.view ", "workspace", ""])
def test_a_near_miss_of_a_real_action_is_denied_to_a_system_admin(action: str) -> None:
    assert authorize(PERSONAS["system_admin"], action, WORKSPACE_TARGET) is False


# --- An independent oracle over many contexts (Hypothesis) -------------------------------------

_WS_RANK = {WorkspaceRole.MEMBER: 1, WorkspaceRole.ADMIN: 2, WorkspaceRole.OWNER: 3}
_ORG_RANK = {OrgRole.MEMBER: 1, OrgRole.ADMIN: 2, OrgRole.OWNER: 3}
_PROJECT_RANK = {ProjectRole.VIEWER: 1, ProjectRole.MEMBER: 2, ProjectRole.ADMIN: 3}
_PROJECTS = {PROJ: (ORG, WS), PROJ2: (ORG, WS), PROJ3: (ORG2, WS), PROJ4: (ORG3, WS2)}

contexts = st.builds(
    AuthzContext,
    user_id=st.just(uuid.UUID(int=1)),
    is_system_admin=st.booleans(),
    workspace_roles=st.dictionaries(st.sampled_from([WS, WS2]), st.sampled_from(WorkspaceRole)),
    org_roles=st.dictionaries(st.sampled_from([ORG, ORG2, ORG3]), st.sampled_from(OrgRole)),
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
        ),
        st.sampled_from([WORKSPACE_TARGET, Target(workspace_id=WS2)]),
    ),
    st.tuples(
        st.builds(
            ActionSpec,
            level=st.just(Level.ORGANIZATION),
            workspace_role=_ADMIN_OR_ABOVE_WS,
            org_role=st.sampled_from([None, *OrgRole]),
            mutation=st.booleans(),
        ),
        st.sampled_from(
            [
                Target(workspace_id=_PROJECTS[p][1], organization_id=_PROJECTS[p][0])
                for p in _PROJECTS
            ]
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
        ),
        st.builds(_project_target, st.sampled_from(list(_PROJECTS)), st.booleans()),
    ),
)


def _at_least[R](held: R | None, needed: R | None, rank: dict[R, int]) -> bool:
    return held is not None and needed is not None and rank[held] >= rank[needed]


def oracle(ctx: AuthzContext, spec: ActionSpec, target: Target) -> bool:
    """design-doc §5's order for a non-personal action, written independently of the code."""
    if target.archived and spec.mutation and not spec.archive_exempt:
        return False
    project = ctx.projects.get(target.project_id) if target.project_id else None
    org_role = ctx.org_roles.get(target.organization_id) if target.organization_id else None
    return (
        ctx.is_system_admin
        or _at_least(ctx.workspace_roles.get(target.workspace_id), spec.workspace_role, _WS_RANK)
        or _at_least(org_role, spec.org_role, _ORG_RANK)
        or _at_least(project.role if project else None, spec.project_role, _PROJECT_RANK)
    )


@given(ctx=contexts, spec_and_target=specs_and_targets)
def test_authorize_agrees_with_the_documented_order(
    ctx: AuthzContext, spec_and_target: tuple[ActionSpec, Target]
) -> None:
    spec, target = spec_and_target
    with patch.dict(REGISTRY, {"test_generated.action": spec}):
        assert authorize(ctx, "test_generated.action", target) is oracle(ctx, spec, target)


# --- Visibility (design-doc §4): what exists for the user --------------------------------------


@pytest.mark.parametrize(("persona", "visible"), rows(WORKSPACE_STAFF_ADMINS))
def test_only_workspace_owners_admins_and_system_admins_see_the_workspace(
    persona: str, visible: bool
) -> None:
    """The workspace pages are theirs alone (testing-strategy.md: 404 to everyone else)."""
    assert can_see(PERSONAS[persona], WORKSPACE_TARGET) is visible


@pytest.mark.parametrize(
    ("persona", "visible"),
    rows(INHERITED_ADMINS | {"org_member", "project_admin", "project_member", "project_viewer",
                             "other_project_admin"}),
)  # fmt: skip
def test_an_org_is_seen_through_a_membership_in_it_or_on_one_of_its_projects(
    persona: str, visible: bool
) -> None:
    assert can_see(PERSONAS[persona], ORG_TARGET) is visible


def test_a_project_membership_shows_the_projects_own_org_only() -> None:
    """The org comes from the membership's `ProjectAccess` (the project row)."""
    in_o2 = AuthzContext(
        user_id=uuid.uuid4(), projects={PROJ3: ProjectAccess(ProjectRole.VIEWER, ORG2, WS)}
    )

    assert can_see(in_o2, Target(workspace_id=WS, organization_id=ORG2)) is True
    assert can_see(in_o2, ORG_TARGET) is False


@pytest.mark.parametrize(("persona", "visible"), rows(CONTENT_ACCESS))
def test_a_project_is_seen_through_its_membership_or_inherited_admin(
    persona: str, visible: bool
) -> None:
    """An org membership alone (role member) shows the org, not its projects."""
    assert can_see(PERSONAS[persona], PROJECT_TARGET) is visible


def test_an_archived_project_is_still_seen() -> None:
    assert can_see(PERSONAS["project_viewer"], ARCHIVED_PROJECT_TARGET) is True


# --- ensure(): 404 for what the user can't see, 403 for what they can -------------------------


@pytest.mark.parametrize(
    ("persona", "action", "target"),
    [
        ("project_member", PROJECT_EDIT, PROJECT_TARGET),
        ("org_admin", PROJECT_MANAGE, PROJECT_TARGET),
        ("org_member", ORG_CREATE_PROJECT, ORG_TARGET),
        ("workspace_owner", Action.WORKSPACE_UPDATE, WORKSPACE_TARGET),
        ("system_admin", Action.ORG_CREATE, WORKSPACE_TARGET),
    ],
)
def test_ensure_returns_quietly_when_allowed(persona: str, action: str, target: Target) -> None:
    assert ensure(PERSONAS[persona], action, target) is None


@pytest.mark.parametrize(
    ("persona", "action", "target"),
    [
        ("org_member", PROJECT_VIEW, PROJECT_TARGET),
        ("workspace_member", PROJECT_VIEW, PROJECT_TARGET),
        ("other_project_admin", PROJECT_VIEW, PROJECT_TARGET),
        ("nobody", PROJECT_EDIT, PROJECT_TARGET),
        ("other_org_owner", ORG_CREATE_PROJECT, ORG_TARGET),
        ("other_workspace_owner", ORG_MANAGE, ORG_TARGET),
        ("workspace_member", Action.WORKSPACE_VIEW, WORKSPACE_TARGET),
        ("org_owner", Action.WORKSPACE_VIEW, WORKSPACE_TARGET),
        ("other_workspace_owner", Action.WORKSPACE_VIEW, WORKSPACE_TARGET),
    ],
)
def test_ensure_is_404_for_what_the_user_cannot_see(
    persona: str, action: str, target: Target
) -> None:
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], action, target)


@pytest.mark.parametrize(
    ("persona", "action", "target"),
    [
        ("project_viewer", PROJECT_EDIT, PROJECT_TARGET),
        ("project_member", PROJECT_MANAGE, PROJECT_TARGET),
        ("project_admin", PROJECT_EDIT, ARCHIVED_PROJECT_TARGET),
        ("system_admin", PROJECT_EDIT, ARCHIVED_PROJECT_TARGET),
        ("system_admin", UNREGISTERED, PROJECT_TARGET),
        ("system_admin", EDIT_OWN_COMMENT, PROJECT_TARGET),
        ("org_member", ORG_MANAGE, ORG_TARGET),
        ("project_admin", ORG_CREATE_PROJECT, ORG_TARGET),
        ("workspace_admin", Action.WORKSPACE_UPDATE, WORKSPACE_TARGET),
    ],
)
def test_ensure_is_403_for_what_the_user_sees_but_may_not_do(
    persona: str, action: str, target: Target
) -> None:
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS[persona], action, target)


# --- allowed_actions (build plan, "API conventions"; DL-45, DL-56) -------------------------------

ALL_FIVE = [
    "org.create",
    "workspace.update",
    "workspace.view",
    "workspace_staff.manage",
    "workspace_staff.manage_admins",
]


@pytest.mark.parametrize(
    ("persona", "expected"),
    [
        ("system_admin", ALL_FIVE),
        ("workspace_owner", ALL_FIVE),
        ("workspace_admin", ["org.create", "workspace.view", "workspace_staff.manage"]),
        # A test-only member-level workspace action is registered too: never listed.
        ("workspace_member", []),
        ("org_owner", []),
        ("project_admin", []),
        ("other_workspace_owner", []),
        ("nobody", []),
    ],
)
def test_allowed_actions_on_a_workspace_are_the_real_ones_allowed_sorted_by_name(
    persona: str, expected: list[str]
) -> None:
    assert allowed_actions(PERSONAS[persona], WORKSPACE_TARGET) == expected


@pytest.mark.parametrize(
    ("target", "expected"),
    [(ORG_TARGET, ["org.update", "org.view"]), (PROJECT_TARGET, [])],
)
def test_allowed_actions_lists_only_actions_at_the_targets_level(
    target: Target, expected: list[str]
) -> None:
    """The real org-level actions are DL-56's two; no real project-level action exists yet
    (DL-44), and test-only ones are never listed."""
    assert allowed_actions(PERSONAS["system_admin"], target) == expected


# --- Module gating (design-doc §5, "Module gating") ---------------------------------------------


@pytest.mark.parametrize(
    ("enabled", "module", "expected"),
    [
        (frozenset({"sprints", "github"}), "sprints", True),
        (frozenset({"sprints"}), "sprints", True),
        (frozenset({"sprints"}), "github", False),
        (frozenset({"github"}), "sprints", False),
        (frozenset[str](), "sprints", False),
    ],
)
def test_a_module_is_enabled_only_when_the_project_lists_it(
    enabled: frozenset[str], module: str, expected: bool
) -> None:
    target = Target(workspace_id=WS, organization_id=ORG, project_id=PROJ, enabled_modules=enabled)

    assert module_enabled(target, module) is expected
