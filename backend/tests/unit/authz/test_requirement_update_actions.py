"""S2-C6's requirement actions (S2-plan, "Actions per row"; design-doc §5, "The choke point",
"Role capabilities", "Requirement status" (DL-148), "Requirement approval by hand" (DL-161);
§3.1, "Who sets it" and export-controlled projects; DL-211, DL-212):

- `requirement.update` (title, description, status except `approved`, priority) and
  `requirement.raise_restriction`: project members and up, inherited admins included;
- `requirement.reassign_reporter`, `requirement.lower_restriction`, and
  `requirement.approve_manually`: project admins, inherited included ("Project admin" always
  includes inherited admin, §5);
- every one denied to project viewers (and members, for the admin ones) and to everyone who
  can't see the project; a project role grants them only on its own project;
- every one a mutation: an archived project denies it to everyone, system admins included (§5
  step 1; §9: archived is read-only);
- every one content: on an export-controlled project, inherited admins without an explicit
  membership are denied (a 404 from `ensure()`), explicit members keep what their role grants
  (§3.1, §5 step 2);
- each registered at project level, so a requirement's `allowed_actions` carries it (DL-212);
- `ensure()`: 403 to who sees the project but may not act; 404 to who can't see it.

Personas are those of tests/support/authz.py, relative to workspace WS, org ORG, and project
PROJ (in ORG).
"""

from dataclasses import replace

import pytest

from app.authz.actions import REGISTRY, Level
from app.authz.authorize import authorize, ensure
from app.authz.context import AuthzContext, ProjectAccess
from app.authz.target import Target
from app.core.errors import ForbiddenError, NotFoundError
from app.enums import AccessKind, ProjectRole
from tests.support.authz import (
    ARCHIVED_PROJECT_TARGET,
    ORG,
    PERSONAS,
    PROJ,
    PROJ2,
    PROJECT_TARGET,
    WS,
    rows,
)

pytestmark = pytest.mark.security

UPDATE = "requirement.update"
REASSIGN_REPORTER = "requirement.reassign_reporter"
RAISE = "requirement.raise_restriction"
LOWER = "requirement.lower_restriction"
APPROVE_MANUALLY = "requirement.approve_manually"

# Members and up: S2-plan rows `requirement.update` and `requirement.raise_restriction`.
MEMBER_ACTIONS = [UPDATE, RAISE]
# Project admins: `requirement.reassign_reporter`, `requirement.lower_restriction`,
# `requirement.approve_manually`.
ADMIN_ACTIONS = [REASSIGN_REPORTER, LOWER, APPROVE_MANUALLY]
ALL_ACTIONS = [*MEMBER_ACTIONS, *ADMIN_ACTIONS]

INHERITED_ADMINS = {"system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"}
PROJECT_ADMINS = INHERITED_ADMINS | {"project_admin"}
MEMBERS_AND_UP = PROJECT_ADMINS | {"project_member"}
SEES_THE_PROJECT = sorted(MEMBERS_AND_UP | {"project_viewer"})
UNSEEN = [
    "org_member",
    "other_project_admin",
    "workspace_member",
    "other_org_owner",
    "other_workspace_owner",
    "nobody",
]


class _Requirement:
    """A stand-in for a requirement inside PROJ (`project_target(project, requirement)`)."""


REQUIREMENT_TARGET = Target(
    workspace_id=WS, organization_id=ORG, project_id=PROJ, entity=_Requirement()
)
ARCHIVED_REQUIREMENT_TARGET = replace(REQUIREMENT_TARGET, archived=True)
LIVE = [PROJECT_TARGET, REQUIREMENT_TARGET]
ARCHIVED = [ARCHIVED_PROJECT_TARGET, ARCHIVED_REQUIREMENT_TARGET]
TARGET_IDS = ["project", "requirement"]

EC = replace(PROJECT_TARGET, export_controlled=True)
EC_REQUIREMENT = replace(REQUIREMENT_TARGET, export_controlled=True)
EC_TARGETS = [EC, EC_REQUIREMENT]


def _with_viewer_membership(persona: str) -> AuthzContext:
    """The persona, plus an explicit viewer membership on PROJ."""
    return replace(PERSONAS[persona], projects={PROJ: ProjectAccess(ProjectRole.VIEWER, ORG, WS)})


# --- Registration --------------------------------------------------------------------------------


@pytest.mark.parametrize("action", ALL_ACTIONS)
def test_each_s2_c6_action_is_marked_content(action: str) -> None:
    """S2-plan, "Actions per row": every S2-C6 row (and `requirement.approve_manually`,
    registered here, DL-212) is kind content (design-doc §3.1)."""
    assert REGISTRY[action].access is AccessKind.CONTENT


@pytest.mark.parametrize("action", ALL_ACTIONS)
def test_each_s2_c6_action_is_at_project_level(action: str) -> None:
    """DL-212: a requirement's `allowed_actions` lists `requirement.approve_manually`; a
    requirement is a project-level target, so every one of its actions is at project level."""
    assert REGISTRY[action].level is Level.PROJECT


# --- Who may: members and up ---------------------------------------------------------------------


@pytest.mark.parametrize("target", LIVE, ids=TARGET_IDS)
@pytest.mark.parametrize("action", MEMBER_ACTIONS)
@pytest.mark.parametrize(("persona", "allowed"), rows(MEMBERS_AND_UP))
def test_update_and_raise_are_for_project_members_and_up_and_inherited_admins(
    persona: str, allowed: bool, action: str, target: Target
) -> None:
    """§5 "Role capabilities": member = "create and edit requirements"; §3.1: "Members can raise
    an item's level and add categories"; admin includes inherited admin; a viewer views only;
    an org membership alone shows the org, not its projects (§4)."""
    assert authorize(PERSONAS[persona], action, target) is allowed


# --- Who may: project admins ---------------------------------------------------------------------


@pytest.mark.parametrize("target", LIVE, ids=TARGET_IDS)
@pytest.mark.parametrize("action", ADMIN_ACTIONS)
@pytest.mark.parametrize(("persona", "allowed"), rows(PROJECT_ADMINS))
def test_reassign_lower_and_approve_are_for_project_admins_inherited_included(
    persona: str, allowed: bool, action: str, target: Target
) -> None:
    """S2-plan: `requirement.reassign_reporter` project admins (DL-211); §3.1: "Lowering a level
    or removing a category is project-admin only"; §5: "only a project admin (including
    inherited) moves a requirement into `approved` by hand" (DL-148, DL-212)."""
    assert authorize(PERSONAS[persona], action, target) is allowed


@pytest.mark.parametrize("action", ALL_ACTIONS)
def test_a_project_role_grants_them_only_on_its_own_project(action: str) -> None:
    """The admin of PROJ2 (same org) may act in PROJ2, not in PROJ."""
    other = PERSONAS["other_project_admin"]

    assert authorize(other, action, Target(WS, ORG, PROJ2)) is True
    assert authorize(other, action, PROJECT_TARGET) is False


# --- Mutations: archived denies them -------------------------------------------------------------


@pytest.mark.parametrize("target", ARCHIVED, ids=TARGET_IDS)
@pytest.mark.parametrize("action", ALL_ACTIONS)
@pytest.mark.parametrize(("persona", "allowed"), rows(set()))
def test_they_are_denied_to_everyone_in_an_archived_project(
    persona: str, allowed: bool, action: str, target: Target
) -> None:
    """§5 step 1: every mutation inside an archived project is denied, system admins included;
    §9: archived is read-only."""
    assert authorize(PERSONAS[persona], action, target) is allowed


# --- Content: the export-control gate ------------------------------------------------------------


@pytest.mark.parametrize("target", EC_TARGETS, ids=TARGET_IDS)
@pytest.mark.parametrize("action", MEMBER_ACTIONS)
@pytest.mark.parametrize(
    ("persona", "allowed"),
    [
        ("system_admin", False),
        ("workspace_owner", False),
        ("workspace_admin", False),
        ("org_owner", False),
        ("org_admin", False),
        ("project_admin", True),
        ("project_member", True),
        ("project_viewer", False),
    ],
)
def test_update_and_raise_on_an_ec_project_need_an_explicit_membership(
    persona: str, allowed: bool, action: str, target: Target
) -> None:
    """§3.1, §5 step 2: inherited admins lose content access; explicit members keep what their
    role grants (a viewer still can't edit or raise)."""
    assert authorize(PERSONAS[persona], action, target) is allowed


@pytest.mark.parametrize("target", EC_TARGETS, ids=TARGET_IDS)
@pytest.mark.parametrize("action", ADMIN_ACTIONS)
@pytest.mark.parametrize(
    ("persona", "allowed"),
    [
        ("system_admin", False),
        ("workspace_owner", False),
        ("workspace_admin", False),
        ("org_owner", False),
        ("org_admin", False),
        ("project_admin", True),
        ("project_member", False),
        ("project_viewer", False),
    ],
)
def test_reassign_lower_and_approve_on_an_ec_project_need_an_explicit_admin(
    persona: str, allowed: bool, action: str, target: Target
) -> None:
    """§3.1, §5 step 2: inherited admins lose content access; an explicit project admin keeps
    it; explicit members and viewers still lack the admin role."""
    assert authorize(PERSONAS[persona], action, target) is allowed


@pytest.mark.parametrize("action", [UPDATE, RAISE, REASSIGN_REPORTER, APPROVE_MANUALLY])
@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_an_inherited_admin_with_an_explicit_viewer_membership_passes_the_gate(
    persona: str, action: str
) -> None:
    """§3.1: inherited admins lose content access "unless they hold an explicit
    `project_membership`"; past the gate their inherited admin applies (§5)."""
    assert authorize(_with_viewer_membership(persona), action, EC) is True


# --- ensure(): 403 to who sees the project, 404 to who doesn't -----------------------------------


@pytest.mark.parametrize("target", LIVE, ids=TARGET_IDS)
@pytest.mark.parametrize("action", MEMBER_ACTIONS)
@pytest.mark.parametrize("persona", sorted(MEMBERS_AND_UP))
def test_ensure_lets_members_and_up_update_and_raise(
    persona: str, action: str, target: Target
) -> None:
    assert ensure(PERSONAS[persona], action, target) is None


@pytest.mark.parametrize("target", LIVE, ids=TARGET_IDS)
@pytest.mark.parametrize("action", ADMIN_ACTIONS)
@pytest.mark.parametrize("persona", sorted(PROJECT_ADMINS))
def test_ensure_lets_project_admins_reassign_lower_and_approve(
    persona: str, action: str, target: Target
) -> None:
    assert ensure(PERSONAS[persona], action, target) is None


@pytest.mark.parametrize("target", LIVE, ids=TARGET_IDS)
@pytest.mark.parametrize("action", ALL_ACTIONS)
def test_they_are_403_to_a_project_viewer(action: str, target: Target) -> None:
    """The viewer sees the project, so the denial is a 403 (§5: 404 only for the unseen)."""
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS["project_viewer"], action, target)


@pytest.mark.parametrize("target", LIVE, ids=TARGET_IDS)
@pytest.mark.parametrize("action", ADMIN_ACTIONS)
def test_the_admin_actions_are_403_to_a_project_member(action: str, target: Target) -> None:
    """DL-161: "members get 403" for approving; the same for reassigning and lowering."""
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS["project_member"], action, target)


@pytest.mark.parametrize("target", ARCHIVED, ids=TARGET_IDS)
@pytest.mark.parametrize("action", ALL_ACTIONS)
@pytest.mark.parametrize("persona", SEES_THE_PROJECT)
def test_they_are_403_in_an_archived_project_to_who_sees_it(
    persona: str, action: str, target: Target
) -> None:
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS[persona], action, target)


@pytest.mark.parametrize(
    "target", [*LIVE, *ARCHIVED], ids=[*TARGET_IDS, "archived", "archived-req"]
)
@pytest.mark.parametrize("action", ALL_ACTIONS)
@pytest.mark.parametrize("persona", UNSEEN)
def test_they_are_404_to_who_cannot_see_the_project(
    persona: str, action: str, target: Target
) -> None:
    """§5: failures on entities the user can't see return 404, not 403."""
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], action, target)


@pytest.mark.parametrize("target", EC_TARGETS, ids=TARGET_IDS)
@pytest.mark.parametrize("action", ALL_ACTIONS)
@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_a_denial_by_the_gate_is_404(persona: str, action: str, target: Target) -> None:
    """§3.1: "Every content action denied to them, read or mutation, is a 404"."""
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], action, target)


@pytest.mark.parametrize("action", ALL_ACTIONS)
def test_they_are_403_on_an_ec_project_to_an_explicit_viewer(action: str) -> None:
    """The explicit viewer sees the content; only their role denies the action."""
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS["project_viewer"], action, EC)


@pytest.mark.parametrize("action", ADMIN_ACTIONS)
def test_the_admin_actions_are_403_on_an_ec_project_to_an_explicit_member(action: str) -> None:
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS["project_member"], action, EC)
