"""S2-C8's requirement actions, `requirement.delete` and `requirement.restore` (design-doc §5,
"The choke point", "Role capabilities", "Other targeted rules" → Deletion; §3.1 export-controlled
projects; §9 "Restore"; build plan S2-C8):

- Deletion table: a requirement may be deleted by its reporter, as a project member (member
  role or above; DL-219), while it has never been approved (`approved_revision_id IS NULL`);
  once approved, by a project admin only. "Project admin"
  always includes inherited admin (§5, "Role capabilities"), so project admins delete any;
- "whoever may delete an item may also restore it": `requirement.restore` follows the same rule;
- whether it was ever approved is `approved_revision_id`, not the current status (§5,
  "Requirement approval by hand": moving out of `approved` leaves it set, "so ... the delete
  rule above still work[s]");
- both are mutations: an archived project denies them to everyone (§5 step 1);
- both are content: on an export-controlled project an inherited admin without an explicit
  membership is denied, a 404 from `ensure()` (§3.1, §5 step 2), reporter or not;
- `ensure()`: 403 to who sees the project but may not; 404 to who can't see it, even as the
  requirement's reporter (§5: failures on entities the user can't see return 404).

Personas are those of tests/support/authz.py, relative to workspace WS, org ORG, and project
PROJ (in ORG).
"""

import uuid
from dataclasses import replace

import pytest

from app.authz.actions import REGISTRY, Level
from app.authz.authorize import authorize, ensure
from app.authz.context import AuthzContext, ProjectAccess
from app.authz.target import Target
from app.core.errors import ForbiddenError, NotFoundError
from app.enums import AccessKind, ProjectRole, RequirementStatus
from app.models.requirement import Requirement
from tests.support.authz import ORG, PERSONAS, PROJ, PROJ2, WS, rows

pytestmark = pytest.mark.security

DELETE = "requirement.delete"
RESTORE = "requirement.restore"
ACTIONS = [DELETE, RESTORE]

INHERITED_ADMINS = {"system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"}
PROJECT_ADMINS = INHERITED_ADMINS | {"project_admin"}
SEES_THE_PROJECT = sorted(PROJECT_ADMINS | {"project_member", "project_viewer"})
UNSEEN = [
    "org_member",
    "other_project_admin",
    "workspace_member",
    "other_org_owner",
    "other_workspace_owner",
    "nobody",
]

MEMBER = PERSONAS["project_member"].user_id
SOMEONE_ELSE = uuid.UUID(int=5000)
REVISION = uuid.UUID(int=6000)


def requirement(
    reporter: uuid.UUID,
    *,
    approved: bool,
    status: RequirementStatus = RequirementStatus.DRAFT,
) -> Requirement:
    """A requirement reported by `reporter`; once approved, `approved_revision_id` is set."""
    return Requirement(
        reporter_id=reporter,
        approved_revision_id=REVISION if approved else None,
        status=status,
    )


def target(
    entity: Requirement,
    *,
    project: uuid.UUID = PROJ,
    archived: bool = False,
    export_controlled: bool = False,
) -> Target:
    """`entity` inside `project` (in ORG), as `project_target(project, requirement)` builds it."""
    return Target(
        workspace_id=WS,
        organization_id=ORG,
        project_id=project,
        archived=archived,
        export_controlled=export_controlled,
        entity=entity,
    )


def own(persona: str, *, approved: bool) -> Target:
    """A requirement in PROJ reported by `persona` themself."""
    return target(requirement(PERSONAS[persona].user_id, approved=approved))


def _with_viewer_membership(persona: str) -> AuthzContext:
    """The persona, plus an explicit viewer membership on PROJ."""
    return replace(PERSONAS[persona], projects={PROJ: ProjectAccess(ProjectRole.VIEWER, ORG, WS)})


NEVER_APPROVED_BY_SOMEONE_ELSE = target(requirement(SOMEONE_ELSE, approved=False))
APPROVED_BY_SOMEONE_ELSE = target(requirement(SOMEONE_ELSE, approved=True))
NEVER_APPROVED_BY_MEMBER = target(requirement(MEMBER, approved=False))
APPROVED_BY_MEMBER = target(requirement(MEMBER, approved=True))


# --- Registration --------------------------------------------------------------------------------


@pytest.mark.parametrize("action", ACTIONS)
def test_delete_and_restore_are_content(action: str) -> None:
    """§3.1: content is requirements and "anything else inside the project"."""
    assert REGISTRY[action].access is AccessKind.CONTENT


@pytest.mark.parametrize("action", ACTIONS)
def test_delete_and_restore_are_at_project_level(action: str) -> None:
    """A requirement is a project-level target; its read's `allowed_actions` and the trash's
    Restore (§9, "Trash": "Restore where `allowed_actions` allows it") carry them."""
    assert REGISTRY[action].level is Level.PROJECT


# --- Who may: the reporter of a never-approved requirement, and project admins -------------------


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize(("persona", "allowed"), rows(PROJECT_ADMINS))
def test_someone_elses_never_approved_requirement_is_for_project_admins(
    persona: str, allowed: bool, action: str
) -> None:
    """§5 Deletion: the reporter, or (project admins, inherited included, hold every targeted-rule
    override) a project admin; a member who isn't the reporter may not."""
    assert authorize(PERSONAS[persona], action, NEVER_APPROVED_BY_SOMEONE_ELSE) is allowed


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize(("persona", "allowed"), rows(PROJECT_ADMINS | {"project_member"}))
def test_the_reporter_may_as_a_project_member_while_it_has_never_been_approved(
    persona: str, allowed: bool, action: str
) -> None:
    """§5 Deletion: "reporter, as a project member (member role or above; DL-219), while it has
    never been approved": a reporter who is now a viewer may not, nor one who can no longer see
    the project (DL-219)."""
    assert authorize(PERSONAS[persona], action, own(persona, approved=False)) is allowed


@pytest.mark.parametrize("action", ACTIONS)
def test_a_reporter_who_is_now_a_viewer_gets_403(action: str) -> None:
    """DL-219: the viewer still sees the project, so the denial is a 403."""
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS["project_viewer"], action, own("project_viewer", approved=False))


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize(("persona", "allowed"), rows(PROJECT_ADMINS))
def test_once_approved_only_a_project_admin_may_even_as_its_reporter(
    persona: str, allowed: bool, action: str
) -> None:
    """§5 Deletion: "once approved, project admin only"."""
    assert authorize(PERSONAS[persona], action, own(persona, approved=True)) is allowed


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize(("persona", "allowed"), rows(PROJECT_ADMINS))
def test_someone_elses_approved_requirement_is_for_project_admins(
    persona: str, allowed: bool, action: str
) -> None:
    assert authorize(PERSONAS[persona], action, APPROVED_BY_SOMEONE_ELSE) is allowed


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize(
    "status",
    [
        RequirementStatus.IN_PROGRESS,
        RequirementStatus.DONE,
        RequirementStatus.DRAFT,
        RequirementStatus.REJECTED,
    ],
)
def test_a_requirement_moved_out_of_approved_still_needs_a_project_admin(
    status: RequirementStatus, action: str
) -> None:
    """§5: moving out of `approved` leaves `approved_revision_id` set, "so ... the delete rule
    above still work[s]": the reporter may no longer, a project admin still may."""
    moved_out = target(requirement(MEMBER, approved=True, status=status))

    assert authorize(PERSONAS["project_member"], action, moved_out) is False
    assert authorize(PERSONAS["project_admin"], action, moved_out) is True


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize(
    "status",
    [RequirementStatus.IN_PROGRESS, RequirementStatus.REJECTED, RequirementStatus.DEFERRED],
)
def test_never_approved_is_approved_revision_id_null_whatever_the_status(
    status: RequirementStatus, action: str
) -> None:
    """§5 Deletion: never approved means `approved_revision_id IS NULL`."""
    never_approved = target(requirement(MEMBER, approved=False, status=status))

    assert authorize(PERSONAS["project_member"], action, never_approved) is True


@pytest.mark.parametrize("action", ACTIONS)
def test_a_project_admin_role_grants_them_only_on_its_own_project(action: str) -> None:
    """The admin of PROJ2 (same org) may in PROJ2, not in PROJ."""
    other = PERSONAS["other_project_admin"]
    in_proj2 = target(requirement(SOMEONE_ELSE, approved=True), project=PROJ2)

    assert authorize(other, action, in_proj2) is True
    assert authorize(other, action, APPROVED_BY_SOMEONE_ELSE) is False


# --- Mutations: archived denies them -------------------------------------------------------------


@pytest.mark.parametrize("approved", [False, True], ids=["never-approved", "approved"])
@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize(("persona", "allowed"), rows(set()))
def test_they_are_denied_to_everyone_in_an_archived_project_reporter_included(
    persona: str, allowed: bool, action: str, approved: bool
) -> None:
    """§5 step 1: every mutation inside an archived project is denied, system admins included;
    the reporter of a never-approved requirement too."""
    archived = target(requirement(PERSONAS[persona].user_id, approved=approved), archived=True)

    assert authorize(PERSONAS[persona], action, archived) is allowed


# --- Content: the export-control gate ------------------------------------------------------------


@pytest.mark.parametrize("action", ACTIONS)
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
    ],
)
def test_on_an_ec_project_a_never_approved_one_needs_an_explicit_membership(
    persona: str, allowed: bool, action: str
) -> None:
    """§3.1, §5 step 2: inherited admins lose content access, even as the reporter; the
    explicit admin keeps it, and so does the reporter with an explicit membership."""
    ec = target(requirement(PERSONAS[persona].user_id, approved=False), export_controlled=True)

    assert authorize(PERSONAS[persona], action, ec) is allowed


@pytest.mark.parametrize("action", ACTIONS)
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
def test_on_an_ec_project_an_approved_one_needs_an_explicit_project_admin(
    persona: str, allowed: bool, action: str
) -> None:
    ec = target(requirement(PERSONAS[persona].user_id, approved=True), export_controlled=True)

    assert authorize(PERSONAS[persona], action, ec) is allowed


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_an_inherited_admin_with_an_explicit_viewer_membership_passes_the_gate(
    persona: str, action: str
) -> None:
    """§3.1: content access "unless they hold an explicit `project_membership`"; past the gate
    their inherited admin applies (§5)."""
    ec = target(requirement(SOMEONE_ELSE, approved=True), export_controlled=True)

    assert authorize(_with_viewer_membership(persona), action, ec) is True


# --- ensure(): 403 to who sees the project, 404 to who doesn't -----------------------------------


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("persona", sorted(PROJECT_ADMINS))
def test_ensure_lets_project_admins_delete_and_restore_an_approved_one(
    persona: str, action: str
) -> None:
    assert ensure(PERSONAS[persona], action, APPROVED_BY_SOMEONE_ELSE) is None


@pytest.mark.parametrize("action", ACTIONS)
def test_ensure_lets_the_reporter_delete_and_restore_a_never_approved_one(action: str) -> None:
    assert ensure(PERSONAS["project_member"], action, NEVER_APPROVED_BY_MEMBER) is None


@pytest.mark.parametrize("entity", [NEVER_APPROVED_BY_SOMEONE_ELSE, APPROVED_BY_MEMBER])
@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("persona", ["project_member", "project_viewer"])
def test_they_are_403_to_a_member_or_viewer_who_may_not(
    persona: str, action: str, entity: Target
) -> None:
    """They see the project, so the denial is a 403 (§5: 404 only for the unseen)."""
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS[persona], action, entity)


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("persona", SEES_THE_PROJECT)
def test_they_are_403_in_an_archived_project_to_who_sees_it(persona: str, action: str) -> None:
    archived = target(requirement(PERSONAS[persona].user_id, approved=False), archived=True)

    with pytest.raises(ForbiddenError):
        ensure(PERSONAS[persona], action, archived)


@pytest.mark.parametrize("archived", [False, True], ids=["live", "archived"])
@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("persona", UNSEEN)
def test_they_are_404_to_who_cannot_see_the_project_even_as_its_reporter(
    persona: str, action: str, archived: bool
) -> None:
    """§5: failures on entities the user can't see return 404, not 403."""
    theirs = target(requirement(PERSONAS[persona].user_id, approved=False), archived=archived)

    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], action, theirs)


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_a_denial_by_the_gate_is_404_even_to_the_reporter(persona: str, action: str) -> None:
    """§3.1: "Every content action denied to them, read or mutation, is a 404"."""
    ec = target(requirement(PERSONAS[persona].user_id, approved=False), export_controlled=True)

    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], action, ec)


@pytest.mark.parametrize("action", ACTIONS)
def test_they_are_403_on_an_ec_project_to_an_explicit_member_who_may_not(action: str) -> None:
    """The explicit member sees the content; only the rule denies an approved one."""
    ec = target(requirement(MEMBER, approved=True), export_controlled=True)

    with pytest.raises(ForbiddenError):
        ensure(PERSONAS["project_member"], action, ec)
