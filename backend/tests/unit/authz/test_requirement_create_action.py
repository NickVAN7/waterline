"""S2-C5's `requirement.create` (S2-plan, "Actions per row": project members and up, content;
design-doc §5, "Role capabilities": a member creates requirements, and "Project admin" always
includes inherited admin; "The choke point"; §3.1, export-controlled projects; §9: archived is
read-only):

- granted to the project's members and admins and to inherited admins (system admins,
  workspace owners/admins, owners/admins of the project's org), on the project and on a
  requirement inside it; denied to project viewers and to everyone who can't see the project;
- a mutation: an archived project denies it to everyone, system admins included (§5 step 1);
- content: on an export-controlled project, inherited admins without an explicit membership are
  denied (a 404 from `ensure()`), explicit members keep what their role grants (§3.1, §5 step 2);
- `ensure()`: 403 to who sees the project but may not create; 404 to who can't see it.

Personas are those of tests/support/authz.py, relative to workspace WS, org ORG, and project
PROJ (in ORG).
"""

from dataclasses import replace

import pytest

from app.authz.actions import REGISTRY, Action
from app.authz.authorize import authorize, ensure
from app.authz.context import ProjectAccess
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

CREATE = "requirement.create"

INHERITED_ADMINS = {"system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"}
CREATORS = INHERITED_ADMINS | {"project_admin", "project_member"}
SEES_THE_PROJECT = sorted(CREATORS | {"project_viewer"})
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


# --- Who may create ------------------------------------------------------------------------------


@pytest.mark.parametrize("target", LIVE, ids=TARGET_IDS)
@pytest.mark.parametrize(("persona", "allowed"), rows(CREATORS))
def test_requirement_create_is_for_project_members_and_up_and_inherited_admins(
    persona: str, allowed: bool, target: Target
) -> None:
    """§5 "Role capabilities": member = "create … requirements"; admin includes inherited admin;
    a viewer views only; an org membership alone shows the org, not its projects (§4)."""
    assert authorize(PERSONAS[persona], CREATE, target) is allowed


def test_a_project_role_grants_requirement_create_only_on_its_own_project() -> None:
    """The admin of PROJ2 (same org) creates in PROJ2, not in PROJ."""
    other = PERSONAS["other_project_admin"]

    assert authorize(other, CREATE, Target(WS, ORG, PROJ2)) is True
    assert authorize(other, CREATE, PROJECT_TARGET) is False


# --- A mutation: archived denies it --------------------------------------------------------------


@pytest.mark.parametrize("target", ARCHIVED, ids=TARGET_IDS)
@pytest.mark.parametrize(("persona", "allowed"), rows(set()))
def test_requirement_create_is_denied_to_everyone_in_an_archived_project(
    persona: str, allowed: bool, target: Target
) -> None:
    """§5 step 1: every mutation inside an archived project is denied, system admins included;
    §9: archived is read-only."""
    assert authorize(PERSONAS[persona], CREATE, target) is allowed


# --- Content: the export-control gate ------------------------------------------------------------


def test_requirement_create_is_marked_content() -> None:
    """S2-plan, "Actions per row": kind content (design-doc §3.1)."""
    assert REGISTRY[Action.REQUIREMENT_CREATE].access is AccessKind.CONTENT


@pytest.mark.parametrize("target", EC_TARGETS, ids=TARGET_IDS)
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
def test_requirement_create_on_an_export_controlled_project_needs_an_explicit_membership(
    persona: str, allowed: bool, target: Target
) -> None:
    """§3.1, §5 step 2: inherited admins lose content access; explicit members keep what their
    role grants (a viewer still can't create)."""
    assert authorize(PERSONAS[persona], CREATE, target) is allowed


@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_an_inherited_admin_with_an_explicit_viewer_membership_creates_on_an_ec_project(
    persona: str,
) -> None:
    """§3.1: "unless they hold an explicit `project_membership`"; past the gate their inherited
    admin applies (§5)."""
    ctx = replace(PERSONAS[persona], projects={PROJ: ProjectAccess(ProjectRole.VIEWER, ORG, WS)})

    assert authorize(ctx, CREATE, EC) is True


# --- ensure(): 403 to who sees the project, 404 to who doesn't -----------------------------------


@pytest.mark.parametrize("target", LIVE, ids=TARGET_IDS)
@pytest.mark.parametrize("persona", sorted(CREATORS))
def test_ensure_lets_creators_create(persona: str, target: Target) -> None:
    assert ensure(PERSONAS[persona], CREATE, target) is None


@pytest.mark.parametrize("target", LIVE, ids=TARGET_IDS)
def test_requirement_create_is_403_to_a_project_viewer(target: Target) -> None:
    """The viewer sees the project, so the denial is a 403 (§5: 404 only for the unseen)."""
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS["project_viewer"], CREATE, target)


@pytest.mark.parametrize("target", ARCHIVED, ids=TARGET_IDS)
@pytest.mark.parametrize("persona", SEES_THE_PROJECT)
def test_requirement_create_in_an_archived_project_is_403_to_who_sees_it(
    persona: str, target: Target
) -> None:
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS[persona], CREATE, target)


@pytest.mark.parametrize(
    "target", [*LIVE, *ARCHIVED], ids=[*TARGET_IDS, "archived", "archived-req"]
)
@pytest.mark.parametrize("persona", UNSEEN)
def test_requirement_create_is_404_to_who_cannot_see_the_project(
    persona: str, target: Target
) -> None:
    """§5: failures on entities the user can't see return 404, not 403."""
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], CREATE, target)


@pytest.mark.parametrize("target", EC_TARGETS, ids=TARGET_IDS)
@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_requirement_create_denied_by_the_gate_is_404(persona: str, target: Target) -> None:
    """§3.1: "Every content action denied to them, read or mutation, is a 404"."""
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], CREATE, target)


def test_requirement_create_on_an_ec_project_is_403_to_an_explicit_viewer() -> None:
    """The explicit viewer sees the content; only their role denies the create."""
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS["project_viewer"], CREATE, EC)
