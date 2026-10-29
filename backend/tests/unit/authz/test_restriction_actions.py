"""S1-C13's two restriction actions (DL-82, renamed by DL-134; build plan, "Classification &
export control", "The classification actions"; design-doc §3.1, "Who sets it"; §5, "The choke
point" and "Role capabilities"):

- `project.raise_restriction`: project admins, inherited included (system admins, workspace
  owners/admins, owners/admins of the project's org), on an export-controlled project too;
- `project.lower_restriction`: the same, but on an export-controlled project an explicit
  project admin only (a `project_membership` with role admin), which also covers removing
  `export_controlled`: inherited admins, system admins included, are denied it there unless they
  also hold that explicit membership;
- both are project-level mutations, so an archived project denies them to everyone;
- a project's `allowed_actions` carry them exactly where `authorize()` allows them;
- `project_target(project)` sets `Target.export_controlled` from the project's categories;
- the registry marks every action `access` (content or management), and every action so far is
  management (DL-82; design-doc §5).

Personas are those of tests/support/authz.py, relative to workspace WS, org ORG, and project PROJ
(in ORG).
"""

import uuid

import pytest

from app.authz.actions import REGISTRY, Action
from app.authz.authorize import allowed_actions, authorize, ensure
from app.authz.context import AuthzContext, ProjectAccess
from app.authz.target import Target, project_target
from app.core.errors import ForbiddenError, NotFoundError
from app.enums import AccessKind, OrgRole, ProjectRole, ProjectType, WorkspaceRole
from app.models.project import Project
from tests.support.authz import (
    ARCHIVED_PROJECT_TARGET,
    ORG,
    PERSONAS,
    PROJ,
    PROJECT_TARGET,
    WS,
    rows,
)

pytestmark = pytest.mark.security

RAISE = "project.raise_restriction"
LOWER = "project.lower_restriction"
BOTH = [RAISE, LOWER]

PROJECT_ADMINS = {
    "system_admin",
    "workspace_owner",
    "workspace_admin",
    "org_owner",
    "org_admin",
    "project_admin",
}
INHERITED_ADMINS = ["system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"]
UNSEEN = [
    "org_member",
    "other_project_admin",
    "workspace_member",
    "other_org_owner",
    "other_workspace_owner",
    "nobody",
]

EXPORT_CONTROLLED_TARGET = Target(
    workspace_id=WS, organization_id=ORG, project_id=PROJ, export_controlled=True
)
ARCHIVED_EXPORT_CONTROLLED_TARGET = Target(
    workspace_id=WS, organization_id=ORG, project_id=PROJ, archived=True, export_controlled=True
)


def _user(n: int) -> uuid.UUID:
    return uuid.UUID(int=2000 + n)


# Inherited admins who also hold an explicit membership on PROJ.
EXPLICIT_ADMIN_TOO: dict[str, AuthzContext] = {
    "system_admin": AuthzContext(
        user_id=_user(1),
        is_system_admin=True,
        projects={PROJ: ProjectAccess(ProjectRole.ADMIN, ORG, WS)},
    ),
    "workspace_admin": AuthzContext(
        user_id=_user(2),
        workspace_roles={WS: WorkspaceRole.ADMIN},
        projects={PROJ: ProjectAccess(ProjectRole.ADMIN, ORG, WS)},
    ),
    "org_owner": AuthzContext(
        user_id=_user(3),
        org_roles={ORG: OrgRole.OWNER},
        org_workspaces={ORG: WS},
        projects={PROJ: ProjectAccess(ProjectRole.ADMIN, ORG, WS)},
    ),
}
EXPLICIT_MEMBER_ONLY: dict[str, AuthzContext] = {
    "org_admin_as_member": AuthzContext(
        user_id=_user(4),
        org_roles={ORG: OrgRole.ADMIN},
        org_workspaces={ORG: WS},
        projects={PROJ: ProjectAccess(ProjectRole.MEMBER, ORG, WS)},
    ),
    "workspace_owner_as_viewer": AuthzContext(
        user_id=_user(5),
        workspace_roles={WS: WorkspaceRole.OWNER},
        projects={PROJ: ProjectAccess(ProjectRole.VIEWER, ORG, WS)},
    ),
}


# --- A live project, not export-controlled ------------------------------------------------------


@pytest.mark.parametrize(("persona", "allowed"), rows(PROJECT_ADMINS))
@pytest.mark.parametrize("action", BOTH)
def test_both_are_for_project_admins_inherited_included(
    action: str, persona: str, allowed: bool
) -> None:
    """§3.1: "Project admins (including inherited) set and raise them"; "Lowering a level or
    removing a category is project-admin only" (DL-82)."""
    assert authorize(PERSONAS[persona], action, PROJECT_TARGET) is allowed


# --- An export-controlled project (§3.1; DL-82) -------------------------------------------------


@pytest.mark.parametrize(("persona", "allowed"), rows(PROJECT_ADMINS))
def test_raising_an_export_controlled_project_stays_open_to_inherited_admins(
    persona: str, allowed: bool
) -> None:
    """§3.1: inherited admins keep management access, including "raising its restriction"; on
    an export-controlled project they "may only raise"."""
    assert authorize(PERSONAS[persona], RAISE, EXPORT_CONTROLLED_TARGET) is allowed


@pytest.mark.parametrize(("persona", "allowed"), rows({"project_admin"}))
def test_lowering_an_export_controlled_project_needs_an_explicit_project_admin(
    persona: str, allowed: bool
) -> None:
    """§3.1: "lowering the level or removing any category needs an explicit project admin";
    removing `export_controlled` too. System admins without an explicit admin membership are
    denied it like every other inherited admin."""
    assert authorize(PERSONAS[persona], LOWER, EXPORT_CONTROLLED_TARGET) is allowed


@pytest.mark.parametrize("persona", list(EXPLICIT_ADMIN_TOO))
@pytest.mark.parametrize("action", BOTH)
def test_an_inherited_admin_with_an_explicit_admin_membership_may_both_raise_and_lower(
    action: str, persona: str
) -> None:
    """§3.1: the explicit `project_membership` with role admin is what counts, whatever else the
    user holds."""
    assert authorize(EXPLICIT_ADMIN_TOO[persona], action, EXPORT_CONTROLLED_TARGET) is True


@pytest.mark.parametrize("persona", list(EXPLICIT_MEMBER_ONLY))
def test_an_explicit_membership_below_admin_does_not_let_an_inherited_admin_lower(
    persona: str,
) -> None:
    """§3.1: "an explicit project admin (a `project_membership` with role admin)"; a member or
    viewer row is not one."""
    assert authorize(EXPLICIT_MEMBER_ONLY[persona], LOWER, EXPORT_CONTROLLED_TARGET) is False


@pytest.mark.parametrize("persona", list(EXPLICIT_MEMBER_ONLY))
def test_an_inherited_admin_with_a_lesser_explicit_role_still_raises(persona: str) -> None:
    """Inherited project admin still grants the raise (§5, "Role capabilities")."""
    assert authorize(EXPLICIT_MEMBER_ONLY[persona], RAISE, EXPORT_CONTROLLED_TARGET) is True


# --- An archived project (§5, step 1) -----------------------------------------------------------


@pytest.mark.parametrize(
    "target", [ARCHIVED_PROJECT_TARGET, ARCHIVED_EXPORT_CONTROLLED_TARGET], ids=["plain", "ec"]
)
@pytest.mark.parametrize("persona", list(PERSONAS))
@pytest.mark.parametrize("action", BOTH)
def test_an_archived_project_denies_both_to_everyone(
    action: str, persona: str, target: Target
) -> None:
    """DL-82: both are project-level mutations, so an archived project denies them, system admins
    included."""
    assert authorize(PERSONAS[persona], action, target) is False


@pytest.mark.parametrize("action", BOTH)
def test_an_archived_project_denies_both_to_an_explicit_admin_who_also_inherits(
    action: str,
) -> None:
    assert (
        authorize(EXPLICIT_ADMIN_TOO["system_admin"], action, ARCHIVED_EXPORT_CONTROLLED_TARGET)
        is False
    )


# --- ensure(): 403 for who sees the project, 404 for who doesn't --------------------------------


@pytest.mark.parametrize(
    ("persona", "action", "target"),
    [
        ("project_member", RAISE, PROJECT_TARGET),
        ("project_member", LOWER, PROJECT_TARGET),
        ("project_viewer", RAISE, PROJECT_TARGET),
        ("project_viewer", LOWER, PROJECT_TARGET),
        ("project_viewer", RAISE, EXPORT_CONTROLLED_TARGET),
        ("project_admin", RAISE, ARCHIVED_PROJECT_TARGET),
        ("project_admin", LOWER, ARCHIVED_PROJECT_TARGET),
        ("org_admin", RAISE, ARCHIVED_PROJECT_TARGET),
        ("system_admin", LOWER, ARCHIVED_PROJECT_TARGET),
        ("system_admin", LOWER, EXPORT_CONTROLLED_TARGET),
        ("workspace_owner", LOWER, EXPORT_CONTROLLED_TARGET),
        ("workspace_admin", LOWER, EXPORT_CONTROLLED_TARGET),
        ("org_owner", LOWER, EXPORT_CONTROLLED_TARGET),
        ("org_admin", LOWER, EXPORT_CONTROLLED_TARGET),
    ],
)
def test_a_denied_change_is_403_to_who_sees_the_project(
    persona: str, action: str, target: Target
) -> None:
    """Build plan, "The classification API": "A change the caller lacks the action for is a 403";
    an inherited admin sees an export-controlled project (management, §3.1)."""
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS[persona], action, target)


@pytest.mark.parametrize(
    "target",
    [PROJECT_TARGET, ARCHIVED_PROJECT_TARGET, EXPORT_CONTROLLED_TARGET],
    ids=["live", "archived", "ec"],
)
@pytest.mark.parametrize("persona", UNSEEN)
@pytest.mark.parametrize("action", BOTH)
def test_both_are_404_to_who_cannot_see_the_project(
    action: str, persona: str, target: Target
) -> None:
    """§5: failures on entities the user can't see return 404, not 403."""
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], action, target)


# --- allowed_actions on a project (the project read) --------------------------------------------


@pytest.mark.parametrize(("persona", "listed"), rows(PROJECT_ADMINS))
@pytest.mark.parametrize("action", BOTH)
def test_a_projects_allowed_actions_carry_them_exactly_where_allowed(
    action: str, persona: str, listed: bool
) -> None:
    """Build plan, "The classification actions": the project read's `allowed_actions` carries
    them."""
    assert (action in allowed_actions(PERSONAS[persona], PROJECT_TARGET)) is listed


@pytest.mark.parametrize(("persona", "listed"), rows(PROJECT_ADMINS))
def test_an_export_controlled_projects_allowed_actions_carry_raise_for_every_admin(
    persona: str, listed: bool
) -> None:
    assert (RAISE in allowed_actions(PERSONAS[persona], EXPORT_CONTROLLED_TARGET)) is listed


@pytest.mark.parametrize(("persona", "listed"), rows({"project_admin"}))
def test_an_export_controlled_projects_allowed_actions_carry_lower_only_for_explicit_admins(
    persona: str, listed: bool
) -> None:
    assert (LOWER in allowed_actions(PERSONAS[persona], EXPORT_CONTROLLED_TARGET)) is listed


@pytest.mark.parametrize("persona", list(PERSONAS))
@pytest.mark.parametrize("action", BOTH)
def test_an_archived_projects_allowed_actions_never_carry_them(action: str, persona: str) -> None:
    assert action not in allowed_actions(PERSONAS[persona], ARCHIVED_PROJECT_TARGET)


# --- project_target sets export_controlled ------------------------------------------------------


def _project(categories: list[str]) -> Project:
    return Project(
        organization_id=ORG,
        workspace_id=WS,
        key="PMT",
        name="Payments",
        type=ProjectType.SOFTWARE,
        enabled_modules=[],
        archived_at=None,
        restriction_level=None,
        restriction_categories=categories,
    )


@pytest.mark.parametrize(
    ("categories", "expected"),
    [
        (["export_controlled"], True),
        (["pii", "export_controlled", "financial"], True),
        ([], False),
        (["pii", "financial", "proprietary"], False),
    ],
)
def test_a_project_target_is_export_controlled_exactly_when_the_project_has_the_category(
    categories: list[str], expected: bool
) -> None:
    """§3.1: "When a project has `export_controlled`"; the target carries it (Target docstring)."""
    assert project_target(_project(categories)).export_controlled is expected


def test_a_project_target_carries_export_controlled_beside_its_other_facts() -> None:
    project = _project(["export_controlled"])

    assert project_target(project) == Target(
        workspace_id=WS,
        organization_id=ORG,
        project_id=project.id,
        archived=False,
        enabled_modules=frozenset(),
        export_controlled=True,
    )


# --- The registry's content/management marking (DL-82; §5) --------------------------------------


def test_every_action_so_far_is_marked_management_but_the_requirement_actions() -> None:
    """DL-82: "The registry marks every action content or management; every action so far is
    management"; S2-C3 adds the first content action, `requirement.view`, S2-C5
    `requirement.create`, S2-C6 the update, reporter, restriction, and approve-by-hand
    actions (S2-plan, "Actions per row"; DL-212), and S2-C8 delete and restore."""
    assert {
        action: REGISTRY[action].access
        for action in Action
        if REGISTRY[action].access is not AccessKind.MANAGEMENT
    } == {
        Action.REQUIREMENT_VIEW: AccessKind.CONTENT,
        Action.REQUIREMENT_CREATE: AccessKind.CONTENT,
        Action.REQUIREMENT_UPDATE: AccessKind.CONTENT,
        Action.REQUIREMENT_REASSIGN_REPORTER: AccessKind.CONTENT,
        Action.REQUIREMENT_RAISE_RESTRICTION: AccessKind.CONTENT,
        Action.REQUIREMENT_LOWER_RESTRICTION: AccessKind.CONTENT,
        Action.REQUIREMENT_APPROVE_MANUALLY: AccessKind.CONTENT,
        Action.REQUIREMENT_DELETE: AccessKind.CONTENT,
        Action.REQUIREMENT_RESTORE: AccessKind.CONTENT,
    }
