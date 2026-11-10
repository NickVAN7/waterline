"""S2-C11's personal action, `approval.decide` (design-doc §5 "The choke point" → "Personal
actions", "Role capabilities" → System admin, "Other targeted rules" → Approvals; §3.1
export-controlled projects; §6.2 "Who does what"; schema-doc `approval`; build plan Slice 2
"Approvals (§6.2)"; testing-strategy "Security" → Personal actions; DL-234):

- only the request's named approver, while their own `approval` row is still pending (not
  approved, rejected, or `replaced`), and only with content access to the project (any
  `project_membership` or inherited project admin; on an export-controlled project an explicit
  membership);
- no admin level, system admin included, and no project role grants it on someone else's row;
- a mutation: an archived project denies it to everyone (§5 step 1);
- `authorize()` doesn't look at the request's own status: the 422 `not_pending` is for a named
  approver whose row is still pending on a request that isn't (DL-234);
- `ensure()`: a named approver who has decided is a 403 (DL-234); who can't see the project
  (an approver whose row was replaced and who lost access included) is a 404.

The target's entity is the `ApprovalRequest` with its `approvals` (the stub's loader).
"""

import uuid
from dataclasses import replace

import pytest

from app.authz.actions import REGISTRY, Level
from app.authz.authorize import allowed_actions, authorize, ensure
from app.authz.context import AuthzContext, ProjectAccess
from app.authz.target import Target
from app.core.errors import ForbiddenError, NotFoundError
from app.enums import (
    AccessKind,
    ApprovalDecision,
    ApprovalEntityType,
    ApprovalRequestStatus,
    ProjectRole,
)
from app.models.approval import Approval, ApprovalRequest
from app.models.requirement import Requirement
from tests.support.authz import ORG, PERSONAS, PROJ, PROJ2, WS, rows

pytestmark = pytest.mark.security

DECIDE = "approval.decide"

INHERITED_ADMINS = {"system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"}
EXPLICIT_MEMBERS = {"project_admin", "project_member", "project_viewer"}
CONTENT_ACCESS = INHERITED_ADMINS | EXPLICIT_MEMBERS
UNSEEN = [
    "org_member",
    "other_project_admin",
    "workspace_member",
    "other_org_owner",
    "other_workspace_owner",
    "nobody",
]

SOMEONE_ELSE = uuid.UUID(int=5000)
ANOTHER_APPROVER = uuid.UUID(int=5001)
REQUIREMENT_ID = uuid.UUID(int=6000)
REVISION = uuid.UUID(int=6001)


def a_request(
    *rows_: tuple[uuid.UUID, ApprovalDecision],
    status: ApprovalRequestStatus = ApprovalRequestStatus.PENDING,
) -> ApprovalRequest:
    """A request on the requirement, with one `approval` row per `(approver_id, decision)`."""
    return ApprovalRequest(
        project_id=PROJ,
        entity_type=ApprovalEntityType.REQUIREMENT,
        entity_id=REQUIREMENT_ID,
        requirement_revision_id=REVISION,
        status=status,
        requested_by=SOMEONE_ELSE,
        approvals=[Approval(approver_id=who, decision=decision) for who, decision in rows_],
    )


def target(
    entity: object,
    *,
    project: uuid.UUID = PROJ,
    archived: bool = False,
    export_controlled: bool = False,
) -> Target:
    return Target(
        workspace_id=WS,
        organization_id=ORG,
        project_id=project,
        archived=archived,
        export_controlled=export_controlled,
        entity=entity,
    )


def named(
    persona: str,
    decision: ApprovalDecision = ApprovalDecision.PENDING,
    *,
    status: ApprovalRequestStatus = ApprovalRequestStatus.PENDING,
    **kwargs: object,
) -> Target:
    """A request naming `persona` (their row at `decision`) and another approver still pending."""
    request = a_request(
        (PERSONAS[persona].user_id, decision),
        (ANOTHER_APPROVER, ApprovalDecision.PENDING),
        status=status,
    )
    return target(request, **kwargs)  # pyright: ignore[reportArgumentType]


def someone_elses() -> Target:
    """A request naming only another approver, still pending."""
    return target(a_request((ANOTHER_APPROVER, ApprovalDecision.PENDING)))


def _with_viewer_membership(persona: str) -> AuthzContext:
    return replace(PERSONAS[persona], projects={PROJ: ProjectAccess(ProjectRole.VIEWER, ORG, WS)})


DECIDED = [ApprovalDecision.APPROVED, ApprovalDecision.REJECTED, ApprovalDecision.REPLACED]


# --- Registration --------------------------------------------------------------------------------


def test_decide_is_a_project_level_content_mutation() -> None:
    """§3.1: approvals are content; approval requests inherit from what they approve. §5: a
    personal action inside an archived project is denied like any other mutation."""
    spec = REGISTRY[DECIDE]
    assert (spec.level, spec.access, spec.mutation, spec.archive_exempt) == (
        Level.PROJECT,
        AccessKind.CONTENT,
        True,
        False,
    )


def test_decide_is_a_personal_action() -> None:
    """§5: "The action registry ... marks the personal actions"; `approval.decide` is one."""
    assert REGISTRY[DECIDE].relationship is not None


# --- The named approver, own row pending, with content access ------------------------------------


@pytest.mark.parametrize(("persona", "allowed"), rows(CONTENT_ACCESS))
def test_the_named_approver_with_a_pending_row_and_content_access_may_decide(
    persona: str, allowed: bool
) -> None:
    """§5: allowed when the relationship holds and the user has content access (any project
    membership or inherited project admin); named personas with no access to PROJ are denied."""
    assert authorize(PERSONAS[persona], DECIDE, named(persona)) is allowed


@pytest.mark.parametrize("persona", list(PERSONAS))
def test_nobody_decides_on_another_approvers_row(persona: str) -> None:
    """§5: "nobody, including project, org, or workspace admins, or system admins, decides on
    another approver's behalf"."""
    assert authorize(PERSONAS[persona], DECIDE, someone_elses()) is False


@pytest.mark.parametrize("decision", DECIDED)
@pytest.mark.parametrize("persona", sorted(CONTENT_ACCESS))
def test_a_named_approver_whose_own_row_is_decided_or_replaced_may_not_decide(
    persona: str, decision: ApprovalDecision
) -> None:
    """DL-234: the relationship is "the named approver whose own `approval` row is still
    pending"; decisions are final (DL-195). Another approver still pending changes nothing."""
    assert authorize(PERSONAS[persona], DECIDE, named(persona, decision)) is False


def test_only_the_callers_own_row_counts() -> None:
    """Another approver's pending row doesn't make a decided approver's relationship hold."""
    viewer = PERSONAS["project_viewer"].user_id
    request = a_request(
        (ANOTHER_APPROVER, ApprovalDecision.PENDING),
        (viewer, ApprovalDecision.APPROVED),
        (SOMEONE_ELSE, ApprovalDecision.PENDING),
    )

    assert authorize(PERSONAS["project_viewer"], DECIDE, target(request)) is False


def test_the_named_approver_among_several_rows_may_decide() -> None:
    """The caller's row is found among others, whatever its place."""
    viewer = PERSONAS["project_viewer"].user_id
    request = a_request(
        (ANOTHER_APPROVER, ApprovalDecision.APPROVED),
        (SOMEONE_ELSE, ApprovalDecision.REPLACED),
        (viewer, ApprovalDecision.PENDING),
    )

    assert authorize(PERSONAS["project_viewer"], DECIDE, target(request)) is True


@pytest.mark.parametrize(
    "status",
    [
        ApprovalRequestStatus.PENDING,
        ApprovalRequestStatus.REJECTED,
        ApprovalRequestStatus.CANCELLED,
    ],
)
def test_authorize_lets_a_named_approver_with_a_pending_row_through_whatever_the_requests_status(
    status: ApprovalRequestStatus,
) -> None:
    """DL-234: `authorize()` runs first; the 422 `not_pending` (DL-230) is for a named approver
    whose own row is still pending on a request that isn't."""
    ctx = PERSONAS["project_viewer"]

    assert authorize(ctx, DECIDE, named("project_viewer", status=status)) is True


@pytest.mark.parametrize("entity", [None, Requirement(id=REQUIREMENT_ID, reporter_id=SOMEONE_ELSE)])
@pytest.mark.parametrize("persona", sorted(CONTENT_ACCESS))
def test_decide_on_anything_but_an_approval_request_is_denied(persona: str, entity: object) -> None:
    """The relationship is about an approval row: a bare project or a requirement has none."""
    assert authorize(PERSONAS[persona], DECIDE, target(entity)) is False


def test_a_named_approver_of_another_projects_request_may_not_decide_it_here() -> None:
    """The admin of PROJ2 is named, but the target is in PROJ, which they can't see."""
    other = PERSONAS["other_project_admin"]

    assert authorize(other, DECIDE, named("other_project_admin", project=PROJ2)) is True
    assert authorize(other, DECIDE, named("other_project_admin")) is False


# --- Archived and export-controlled projects -----------------------------------------------------


@pytest.mark.parametrize(("persona", "allowed"), rows(set()))
def test_deciding_in_an_archived_project_is_denied_to_everyone(persona: str, allowed: bool) -> None:
    """§5: "a personal action inside an archived project is denied like any other mutation"."""
    assert authorize(PERSONAS[persona], DECIDE, named(persona, archived=True)) is allowed


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
        ("project_viewer", True),
    ],
)
def test_on_an_ec_project_the_named_approver_needs_an_explicit_membership(
    persona: str, allowed: bool
) -> None:
    """§3.1, §5: content access on an export-controlled project is an explicit membership; the
    relationship without it is denied (testing-strategy, personal actions)."""
    assert authorize(PERSONAS[persona], DECIDE, named(persona, export_controlled=True)) is allowed


@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_an_inherited_admin_named_with_an_explicit_viewer_membership_decides_on_an_ec_project(
    persona: str,
) -> None:
    ctx = _with_viewer_membership(persona)

    assert authorize(ctx, DECIDE, named(persona, export_controlled=True)) is True


@pytest.mark.parametrize("persona", sorted(CONTENT_ACCESS))
def test_on_an_ec_project_nobody_decides_on_another_approvers_row(persona: str) -> None:
    ec = replace(someone_elses(), export_controlled=True)

    assert authorize(PERSONAS[persona], DECIDE, ec) is False


# --- ensure(): 403 or 404 ------------------------------------------------------------------------


@pytest.mark.parametrize("persona", sorted(CONTENT_ACCESS))
def test_ensure_lets_the_named_approver_with_a_pending_row_through(persona: str) -> None:
    assert ensure(PERSONAS[persona], DECIDE, named(persona)) is None


@pytest.mark.parametrize("decision", [ApprovalDecision.APPROVED, ApprovalDecision.REJECTED])
@pytest.mark.parametrize("persona", ["project_viewer", "project_admin", "org_admin"])
def test_deciding_again_after_ones_own_row_is_decided_is_403(
    persona: str, decision: ApprovalDecision
) -> None:
    """DL-234: a named approver who has already decided is refused by `authorize()`: a 403."""
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS[persona], DECIDE, named(persona, decision))


def test_a_replaced_approver_who_has_access_again_is_403() -> None:
    """DL-234: "a 403 only once they have access again"."""
    with pytest.raises(ForbiddenError):
        ensure(
            PERSONAS["project_viewer"],
            DECIDE,
            named("project_viewer", ApprovalDecision.REPLACED),
        )


@pytest.mark.parametrize("persona", sorted(CONTENT_ACCESS))
def test_deciding_another_approvers_row_is_403_to_who_sees_the_project(persona: str) -> None:
    """§5: they see the request, so the denial is a 403, system admins included."""
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS[persona], DECIDE, someone_elses())


@pytest.mark.parametrize("decision", [ApprovalDecision.PENDING, ApprovalDecision.REPLACED])
@pytest.mark.parametrize("persona", UNSEEN)
def test_deciding_is_404_to_a_named_approver_who_cannot_see_the_project(
    persona: str, decision: ApprovalDecision
) -> None:
    """§5: failures on entities the user can't see are 404; DL-234: an approver whose row was
    replaced has lost content access, so a 404."""
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], DECIDE, named(persona, decision))


@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_deciding_on_an_ec_project_is_404_to_a_named_inherited_admin(persona: str) -> None:
    """§3.1: every content action denied to them is a 404."""
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], DECIDE, named(persona, export_controlled=True))


def test_deciding_in_an_archived_project_is_403_to_the_named_approver() -> None:
    """They still see the archived project."""
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS["project_viewer"], DECIDE, named("project_viewer", archived=True))


# --- allowed_actions -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("decision", "offered"),
    [
        (ApprovalDecision.PENDING, True),
        (ApprovalDecision.APPROVED, False),
        (ApprovalDecision.REJECTED, False),
        (ApprovalDecision.REPLACED, False),
    ],
)
def test_allowed_actions_carry_decide_only_for_the_approvers_own_pending_row(
    decision: ApprovalDecision, offered: bool
) -> None:
    """§5: `allowed_actions` evaluated through `authorize()`; DL-233."""
    actions = allowed_actions(PERSONAS["project_viewer"], named("project_viewer", decision))

    assert (DECIDE in actions) is offered


@pytest.mark.parametrize("persona", ["system_admin", "org_admin", "project_admin"])
def test_an_admins_allowed_actions_on_another_approvers_request_leave_out_decide(
    persona: str,
) -> None:
    assert DECIDE not in allowed_actions(PERSONAS[persona], someone_elses())
