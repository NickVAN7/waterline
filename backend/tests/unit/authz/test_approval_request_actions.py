"""S2-C10's approval-request actions, `approval_request.create` and `approval_request.cancel`
(design-doc §5, "The choke point", "Role capabilities", "Other targeted rules" → Approvals; §3.1
export-controlled projects; §6.2 "Who does what"; build plan S2-C10 and "Approvals (§6.2)";
S2-plan "Actions per row"):

- project admins, inherited included, create and cancel requests (§5 project roles table: admin
  is "Member + create and cancel approval requests"; §6.2); members, viewers, and who can't see
  the project may not;
- neither is a personal action: being the requester or a named approver grants nothing (§5:
  only `approval.decide` and editing one's own comment are personal);
- both are mutations: an archived project denies them to everyone (§5 step 1);
- both are content (approval requests inherit from what they approve, §3.1; S2-plan "Kind"):
  on an export-controlled project an inherited admin without an explicit membership is denied,
  a 404 from `ensure()`;
- `approval_request.create` is also asked on the project itself, to decide whether a requester
  still holds project admin (build plan, "Approvals (§6.2)": `authorize(requester,
  "approval_request.create", project)`), so it is decided at project level, entity or not.

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
from app.enums import AccessKind, ApprovalEntityType, ApprovalRequestStatus, ProjectRole
from app.models.approval import ApprovalRequest
from app.models.requirement import Requirement
from tests.support.authz import ORG, PERSONAS, PROJ, PROJ2, WS, rows

pytestmark = pytest.mark.security

CREATE = "approval_request.create"
CANCEL = "approval_request.cancel"
ACTIONS = [CREATE, CANCEL]

INHERITED_ADMINS = {"system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"}
PROJECT_ADMINS = INHERITED_ADMINS | {"project_admin"}
UNSEEN = [
    "org_member",
    "other_project_admin",
    "workspace_member",
    "other_org_owner",
    "other_workspace_owner",
    "nobody",
]

SOMEONE_ELSE = uuid.UUID(int=5000)
REQUIREMENT_ID = uuid.UUID(int=6000)
REVISION = uuid.UUID(int=6001)


def a_requirement() -> Requirement:
    return Requirement(id=REQUIREMENT_ID, reporter_id=SOMEONE_ELSE, current_revision_id=REVISION)


def a_request(requested_by: uuid.UUID = SOMEONE_ELSE) -> ApprovalRequest:
    """A pending request on the requirement, made by `requested_by`."""
    return ApprovalRequest(
        project_id=PROJ,
        entity_type=ApprovalEntityType.REQUIREMENT,
        entity_id=REQUIREMENT_ID,
        requirement_revision_id=REVISION,
        status=ApprovalRequestStatus.PENDING,
        requested_by=requested_by,
    )


def target(
    entity: object,
    *,
    project: uuid.UUID = PROJ,
    archived: bool = False,
    export_controlled: bool = False,
) -> Target:
    """`entity` inside `project` (in ORG), as `project_target(project, entity)` builds it."""
    return Target(
        workspace_id=WS,
        organization_id=ORG,
        project_id=project,
        archived=archived,
        export_controlled=export_controlled,
        entity=entity,
    )


# What each action is taken on: create on the requirement, cancel on the request.
ON = {CREATE: a_requirement, CANCEL: a_request}


def on(action: str, **kwargs: object) -> Target:
    return target(ON[action](), **kwargs)  # pyright: ignore[reportArgumentType]


def _with_viewer_membership(persona: str) -> AuthzContext:
    """The persona, plus an explicit viewer membership on PROJ."""
    return replace(PERSONAS[persona], projects={PROJ: ProjectAccess(ProjectRole.VIEWER, ORG, WS)})


# --- Registration --------------------------------------------------------------------------------


@pytest.mark.parametrize("action", ACTIONS)
def test_create_and_cancel_are_content(action: str) -> None:
    """§3.1: content is "approvals ... and anything else inside the project"; approval requests
    inherit from what they approve (S2-plan, "Kind": content)."""
    assert REGISTRY[action].access is AccessKind.CONTENT


@pytest.mark.parametrize("action", ACTIONS)
def test_create_and_cancel_are_at_project_level(action: str) -> None:
    assert REGISTRY[action].level is Level.PROJECT


@pytest.mark.parametrize("action", ACTIONS)
def test_create_and_cancel_are_not_personal_actions(action: str) -> None:
    """§5 "Personal actions": `approval.decide` and editing one's own comment, not these."""
    assert REGISTRY[action].relationship is None


# --- Who may: project admins, inherited included -------------------------------------------------


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize(("persona", "allowed"), rows(PROJECT_ADMINS))
def test_project_admins_create_and_cancel_approval_requests(
    persona: str, allowed: bool, action: str
) -> None:
    """§5 project roles: admin is "Member + create and cancel approval requests"; "Project admin"
    includes inherited (system admins, workspace owners/admins, the org's owners/admins).
    Members, viewers, and who can't see the project may not."""
    assert authorize(PERSONAS[persona], action, on(action)) is allowed


@pytest.mark.parametrize(("persona", "allowed"), rows(PROJECT_ADMINS))
def test_create_on_the_project_itself_is_project_admin(persona: str, allowed: bool) -> None:
    """Build plan "Approvals (§6.2)": the approval service asks
    `authorize(requester, "approval_request.create", project)` to decide whether the requester
    still holds project admin."""
    assert authorize(PERSONAS[persona], CREATE, target(None)) is allowed


@pytest.mark.parametrize("action", ACTIONS)
def test_a_project_admin_role_grants_them_only_on_its_own_project(action: str) -> None:
    """The admin of PROJ2 (same org) may in PROJ2, not in PROJ."""
    other = PERSONAS["other_project_admin"]

    assert authorize(other, action, on(action, project=PROJ2)) is True
    assert authorize(other, action, on(action)) is False


@pytest.mark.parametrize("persona", ["project_member", "project_viewer"])
def test_the_requester_who_is_no_longer_a_project_admin_may_not_cancel(persona: str) -> None:
    """§6.2: project admins cancel; having made the request grants nothing (not personal)."""
    own_request = target(a_request(requested_by=PERSONAS[persona].user_id))

    assert authorize(PERSONAS[persona], CANCEL, own_request) is False


# --- Mutations: archived denies them -------------------------------------------------------------


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize(("persona", "allowed"), rows(set()))
def test_they_are_denied_to_everyone_in_an_archived_project(
    persona: str, allowed: bool, action: str
) -> None:
    """§5 step 1: every mutation inside an archived project is denied, system admins included."""
    assert authorize(PERSONAS[persona], action, on(action, archived=True)) is allowed


def test_create_on_an_archived_project_itself_is_denied_to_a_project_admin() -> None:
    """§5 step 1; the requester check never needs to pass it (build plan "Approvals (§6.2)":
    archiving cancels pending requests, so it "needn't get past the archived step")."""
    assert authorize(PERSONAS["project_admin"], CREATE, target(None, archived=True)) is False


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
        ("project_member", False),
        ("project_viewer", False),
    ],
)
def test_on_an_ec_project_they_need_an_explicit_project_admin(
    persona: str, allowed: bool, action: str
) -> None:
    """§3.1: inherited admins without an explicit membership lose content access; §6.2: the
    requester holds project admin "on an export-controlled project, explicit only"."""
    assert authorize(PERSONAS[persona], action, on(action, export_controlled=True)) is allowed


@pytest.mark.parametrize(("persona", "allowed"), [("org_admin", False), ("project_admin", True)])
def test_create_on_an_ec_project_itself_needs_an_explicit_project_admin(
    persona: str, allowed: bool
) -> None:
    """§6.2 replacement: the requester must still hold project admin, "on an export-controlled
    project, explicit only"."""
    ec_project = target(None, export_controlled=True)

    assert authorize(PERSONAS[persona], CREATE, ec_project) is allowed


@pytest.mark.parametrize("action", ACTIONS)
def test_an_inherited_admin_with_an_explicit_viewer_membership_passes_the_gate(
    action: str,
) -> None:
    """§3.1: the gate needs "an explicit `project_membership`" of any role; past it, the org
    admin role is inherited project admin again (§5 step 7)."""
    ctx = _with_viewer_membership("org_admin")

    assert authorize(ctx, action, on(action, export_controlled=True)) is True


# --- ensure(): 403 to who sees the project, 404 to who doesn't -----------------------------------


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("persona", sorted(PROJECT_ADMINS))
def test_ensure_lets_project_admins_through(persona: str, action: str) -> None:
    ensure(PERSONAS[persona], action, on(action))


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("persona", ["project_member", "project_viewer"])
def test_they_are_403_to_who_sees_the_project_but_is_not_a_project_admin(
    persona: str, action: str
) -> None:
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS[persona], action, on(action))


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("persona", UNSEEN)
def test_they_are_404_to_who_cannot_see_the_project(persona: str, action: str) -> None:
    """§5: failures on entities the user can't see return 404, not 403."""
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], action, on(action))


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_they_are_404_to_an_inherited_admin_on_an_ec_project(persona: str, action: str) -> None:
    """§3.1: "Every content action denied to them, read or mutation, is a 404"."""
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], action, on(action, export_controlled=True))


@pytest.mark.parametrize("action", ACTIONS)
def test_they_are_403_to_a_project_admin_in_an_archived_project(action: str) -> None:
    """They still see the archived project, so the denial is a 403."""
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS["project_admin"], action, on(action, archived=True))
