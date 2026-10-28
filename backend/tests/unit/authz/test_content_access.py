"""The export-control gate in `authorize()` (S2-C4; design-doc §5, "The choke point", step 2;
§3.1, "Export-controlled projects (who sees content)"; DL-58; testing-strategy.md, "Security"):

- on an export-controlled project, a content action, read or mutation, needs an explicit
  `project_membership`: inherited admins (system admins, workspace owners/admins, org
  owners/admins) without one are denied, and `ensure()` makes that a 404, as for an entity they
  can't see (§3.1: "Every content action denied to them, read or mutation, is a 404");
- management actions pass through the gate: inherited admins keep them (a denied management
  action stays a 403, since they see the project);
- with an explicit membership (any role), the gate is passed and the rest of the order decides,
  so an inherited admin who also holds one keeps their inherited admin on content;
- a visible action never takes an inherited admin past the gate (DL-58);
- personal actions need content access (§5, "Personal actions": on an export-controlled
  project, an explicit membership), however the action is marked;
- `allowed_actions` on an export-controlled project carries no content action for an inherited
  admin without an explicit membership, and keeps the management ones.

Test-only actions are registered in `REGISTRY` per test (DL-44); the real registry's
`requirement.view` (content) and `project.*` (management) are used too. Personas are those of
tests/support/authz.py, relative to workspace WS, org ORG, and project PROJ (in ORG).
"""

import uuid
from dataclasses import replace
from unittest.mock import patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.authz.actions import REGISTRY, ActionSpec, Level
from app.authz.authorize import allowed_actions, authorize, ensure
from app.authz.context import AuthzContext, ProjectAccess
from app.authz.target import Target
from app.core.errors import ForbiddenError, NotFoundError
from app.enums import AccessKind, OrgRole, ProjectRole, WorkspaceRole
from tests.support.authz import ORG, ORG2, PERSONAS, PROJ, PROJ2, WS, WS2, Comment, is_author

pytestmark = pytest.mark.security

_WS_ADMIN = WorkspaceRole.ADMIN
_ORG_ADMIN = OrgRole.ADMIN

READ = "test_ec.content_read"
EDIT = "test_ec.content_edit"
ADMIN_EDIT = "test_ec.content_admin_edit"
VISIBLE_READ = "test_ec.visible_content_read"
MANAGE = "test_ec.manage"
MANAGE_READ = "test_ec.manage_read"
EXPLICIT_ADMIN_MANAGE = "test_ec.explicit_admin_manage"
VISIBLE_MANAGE_READ = "test_ec.visible_manage_read"
OWN_CONTENT = "test_ec.own_content"
OWN_MANAGEMENT = "test_ec.own_management"

ACTIONS: dict[str, ActionSpec] = {
    READ: ActionSpec(
        Level.PROJECT,
        access=AccessKind.CONTENT,
        workspace_role=_WS_ADMIN,
        org_role=_ORG_ADMIN,
        project_role=ProjectRole.VIEWER,
        mutation=False,
    ),
    EDIT: ActionSpec(
        Level.PROJECT,
        access=AccessKind.CONTENT,
        workspace_role=_WS_ADMIN,
        org_role=_ORG_ADMIN,
        project_role=ProjectRole.MEMBER,
    ),
    ADMIN_EDIT: ActionSpec(
        Level.PROJECT,
        access=AccessKind.CONTENT,
        workspace_role=_WS_ADMIN,
        org_role=_ORG_ADMIN,
        project_role=ProjectRole.ADMIN,
    ),
    # Granted to anyone who sees the project (the step DL-58 keeps behind the gate).
    VISIBLE_READ: ActionSpec(
        Level.PROJECT, access=AccessKind.CONTENT, mutation=False, visible=True
    ),
    MANAGE: ActionSpec(
        Level.PROJECT,
        access=AccessKind.MANAGEMENT,
        workspace_role=_WS_ADMIN,
        org_role=_ORG_ADMIN,
        project_role=ProjectRole.ADMIN,
    ),
    MANAGE_READ: ActionSpec(
        Level.PROJECT,
        access=AccessKind.MANAGEMENT,
        workspace_role=_WS_ADMIN,
        org_role=_ORG_ADMIN,
        project_role=ProjectRole.VIEWER,
        mutation=False,
    ),
    # Management, but granted only by an explicit project admin role (and to system admins).
    EXPLICIT_ADMIN_MANAGE: ActionSpec(
        Level.PROJECT, access=AccessKind.MANAGEMENT, project_role=ProjectRole.ADMIN
    ),
    VISIBLE_MANAGE_READ: ActionSpec(
        Level.PROJECT, access=AccessKind.MANAGEMENT, mutation=False, visible=True
    ),
    # Personal actions, with a role at every level, to prove no role grants them.
    OWN_CONTENT: ActionSpec(
        Level.PROJECT,
        access=AccessKind.CONTENT,
        workspace_role=WorkspaceRole.MEMBER,
        org_role=OrgRole.MEMBER,
        project_role=ProjectRole.VIEWER,
        relationship=is_author,
    ),
    OWN_MANAGEMENT: ActionSpec(
        Level.PROJECT,
        access=AccessKind.MANAGEMENT,
        workspace_role=WorkspaceRole.MEMBER,
        org_role=OrgRole.MEMBER,
        project_role=ProjectRole.VIEWER,
        relationship=is_author,
    ),
}


@pytest.fixture(autouse=True)
def _actions(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, spec in ACTIONS.items():
        monkeypatch.setitem(REGISTRY, name, spec)


EC = Target(workspace_id=WS, organization_id=ORG, project_id=PROJ, export_controlled=True)
ARCHIVED_EC = replace(EC, archived=True)

INHERITED_ADMINS = {"system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"}
EXPLICIT_MEMBERS = {"project_admin", "project_member", "project_viewer"}
# The personas the gate decides for: who sees the project (§4). Everyone else is denied before
# and after the gate alike (tests/unit/authz/test_requirement_actions.py and test_authorize.py).
SEES_THE_PROJECT = sorted(INHERITED_ADMINS | EXPLICIT_MEMBERS)


def gate_rows(allowed: set[str]) -> list[tuple[str, bool]]:
    """One `(persona, expected)` row per persona who sees the project."""
    return [(persona, persona in allowed) for persona in SEES_THE_PROJECT]


def _with_viewer_membership(persona: str) -> AuthzContext:
    """An inherited admin who also holds an explicit viewer membership on PROJ."""
    ctx = PERSONAS[persona]
    return replace(ctx, projects={PROJ: ProjectAccess(ProjectRole.VIEWER, ORG, WS)})


def authored_by(persona: str, target: Target = EC) -> Target:
    return replace(target, entity=Comment(author_id=PERSONAS[persona].user_id))


# --- The gate: content actions need an explicit membership ------------------------------------


@pytest.mark.parametrize(
    ("action", "explicit_allowed"),
    [
        (READ, EXPLICIT_MEMBERS),
        (EDIT, {"project_admin", "project_member"}),
        (ADMIN_EDIT, {"project_admin"}),
        ("requirement.view", EXPLICIT_MEMBERS),
    ],
)
@pytest.mark.parametrize("persona", SEES_THE_PROJECT)
def test_a_content_action_on_an_export_controlled_project_needs_an_explicit_membership(
    action: str, explicit_allowed: set[str], persona: str
) -> None:
    """§5 step 2, §3.1: inherited admins, system admins included, lose content access; explicit
    members keep what their role grants."""
    assert authorize(PERSONAS[persona], action, EC) is (persona in explicit_allowed)


@pytest.mark.parametrize(("persona", "allowed"), gate_rows(EXPLICIT_MEMBERS))
def test_a_content_read_on_an_archived_export_controlled_project_needs_an_explicit_membership(
    persona: str, allowed: bool
) -> None:
    """Archived denies mutations only (§5 step 1); the gate still applies to reads (step 2)."""
    assert authorize(PERSONAS[persona], READ, ARCHIVED_EC) is allowed


@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
@pytest.mark.parametrize("action", [READ, EDIT, ADMIN_EDIT, "requirement.view"])
def test_an_inherited_admin_with_an_explicit_membership_keeps_content_access(
    persona: str, action: str
) -> None:
    """§3.1: they lose content access "unless they hold an explicit `project_membership`"; past
    the gate, the rest of the order decides, so their inherited admin applies (§5)."""
    assert authorize(_with_viewer_membership(persona), action, EC) is True


def test_an_explicit_membership_on_another_project_does_not_pass_the_gate() -> None:
    """An org admin who is an explicit admin of PROJ2, not PROJ."""
    ctx = replace(
        PERSONAS["org_admin"], projects={PROJ2: ProjectAccess(ProjectRole.ADMIN, ORG, WS)}
    )

    assert authorize(ctx, READ, EC) is False


@pytest.mark.parametrize(("persona", "allowed"), gate_rows(EXPLICIT_MEMBERS))
def test_a_visible_content_action_never_takes_an_inherited_admin_past_the_gate(
    persona: str, allowed: bool
) -> None:
    """DL-58: the visible step comes after the gate."""
    assert authorize(PERSONAS[persona], VISIBLE_READ, EC) is allowed


# --- Management actions pass through -----------------------------------------------------------


@pytest.mark.parametrize(
    "action",
    [
        MANAGE,
        MANAGE_READ,
        VISIBLE_MANAGE_READ,
        "project.view",
        "project.update",
        "project_member.manage",
        "project.view_access",
        "project.archive",
        "project.raise_restriction",
    ],
)
@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_management_actions_pass_the_gate_for_inherited_admins(persona: str, action: str) -> None:
    """§3.1: inherited admins keep management access (the project in lists, its settings,
    members, archive and unarchive, raising its restriction; §5 "Access review")."""
    assert authorize(PERSONAS[persona], action, EC) is True


def test_unarchive_passes_the_gate_for_an_inherited_admin() -> None:
    assert authorize(PERSONAS["org_admin"], "project.unarchive", ARCHIVED_EC) is True


# --- Personal actions need content access ------------------------------------------------------


@pytest.mark.parametrize(("persona", "allowed"), gate_rows(EXPLICIT_MEMBERS))
def test_a_personal_action_on_an_export_controlled_project_needs_an_explicit_membership(
    persona: str, allowed: bool
) -> None:
    """§5, "Personal actions": the relationship holds for every persona here; content access on
    an export-controlled project is an explicit membership."""
    assert authorize(PERSONAS[persona], OWN_CONTENT, authored_by(persona)) is allowed


@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_a_personal_action_marked_management_still_needs_content_access(persona: str) -> None:
    """§5: a personal action is allowed only for a user with content access, whatever its
    marking, so the gate alone isn't what denies it."""
    assert authorize(PERSONAS[persona], OWN_MANAGEMENT, authored_by(persona)) is False


@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_an_inherited_admin_with_an_explicit_membership_may_take_their_personal_action(
    persona: str,
) -> None:
    target = replace(EC, entity=Comment(author_id=PERSONAS[persona].user_id))

    assert authorize(_with_viewer_membership(persona), OWN_CONTENT, target) is True


@pytest.mark.parametrize("persona", sorted(EXPLICIT_MEMBERS | INHERITED_ADMINS))
def test_content_access_without_the_relationship_never_grants_a_personal_action(
    persona: str,
) -> None:
    someone_elses = replace(EC, entity=Comment(author_id=uuid.UUID(int=9999)))

    assert authorize(PERSONAS[persona], OWN_CONTENT, someone_elses) is False


# --- ensure(): 404 for content an inherited admin can't see; 403 otherwise -------------------


@pytest.mark.parametrize("target", [EC, ARCHIVED_EC], ids=["live", "archived"])
@pytest.mark.parametrize("action", [READ, EDIT, "requirement.view"])
@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_a_content_action_denied_by_the_gate_is_404(
    persona: str, action: str, target: Target
) -> None:
    """§3.1: "Every content action denied to them, read or mutation, is a 404"."""
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], action, target)


@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_a_personal_action_denied_for_want_of_content_access_is_404(persona: str) -> None:
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], OWN_CONTENT, authored_by(persona))


@pytest.mark.parametrize(
    ("persona", "action", "target"),
    [
        ("project_viewer", EDIT, EC),
        ("project_member", ADMIN_EDIT, EC),
        ("project_viewer", OWN_CONTENT, replace(EC, entity=Comment(uuid.UUID(int=9999)))),
        # Archived (step 1) denies an explicit member's content mutation; they see it.
        ("project_member", EDIT, ARCHIVED_EC),
        # Management denied to an inherited admin: they see the project (§3.1).
        ("org_admin", EXPLICIT_ADMIN_MANAGE, EC),
        ("workspace_admin", EXPLICIT_ADMIN_MANAGE, EC),
        ("project_viewer", MANAGE, EC),
    ],
)
def test_a_denial_to_who_sees_the_content_or_a_management_denial_stays_403(
    persona: str, action: str, target: Target
) -> None:
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS[persona], action, target)


@pytest.mark.parametrize(
    ("persona", "action"),
    [
        ("org_admin", MANAGE),
        ("workspace_owner", MANAGE_READ),
        ("system_admin", "project.view"),
        ("project_viewer", READ),
        ("project_member", EDIT),
        ("project_viewer", "requirement.view"),
    ],
)
def test_ensure_lets_through_what_the_gate_allows(persona: str, action: str) -> None:
    assert ensure(PERSONAS[persona], action, EC) is None


def test_ensure_lets_an_inherited_admin_with_an_explicit_membership_read_content() -> None:
    assert ensure(_with_viewer_membership("org_admin"), "requirement.view", EC) is None


# --- allowed_actions on an export-controlled project (the project read) ------------------------

INHERITED_ON_AN_EC_PROJECT = [
    "project.archive",
    "project.raise_restriction",
    "project.unarchive",
    "project.update",
    "project.view",
    "project.view_access",
    "project_member.manage",
]


@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_an_inherited_admins_allowed_actions_on_an_ec_project_are_management_only(
    persona: str,
) -> None:
    """§3.1: management kept; `requirement.view` (content) gone; `project.lower_restriction`
    needs an explicit project admin there (DL-82)."""
    assert allowed_actions(PERSONAS[persona], EC) == INHERITED_ON_AN_EC_PROJECT


@pytest.mark.parametrize(
    ("persona", "expected"),
    [
        (
            "project_admin",
            [
                "project.lower_restriction",
                "project.raise_restriction",
                "project.update",
                "project.view",
                "project.view_access",
                "project_member.manage",
                "requirement.create",
                "requirement.view",
            ],
        ),
        ("project_member", ["project.view", "requirement.create", "requirement.view"]),
        ("project_viewer", ["project.view", "requirement.view"]),
    ],
)
def test_an_explicit_members_allowed_actions_on_an_ec_project_keep_content(
    persona: str, expected: list[str]
) -> None:
    assert allowed_actions(PERSONAS[persona], EC) == expected


@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_an_inherited_admin_with_a_viewer_membership_keeps_content_in_allowed_actions(
    persona: str,
) -> None:
    """Content back with the membership; lowering still needs an explicit admin (DL-82)."""
    assert allowed_actions(_with_viewer_membership(persona), EC) == [
        "project.archive",
        "project.raise_restriction",
        "project.unarchive",
        "project.update",
        "project.view",
        "project.view_access",
        "project_member.manage",
        "requirement.create",
        "requirement.view",
    ]


@pytest.mark.parametrize("persona", ["system_admin", "workspace_admin", "org_admin"])
def test_an_archived_ec_projects_allowed_actions_for_an_inherited_admin_carry_no_content(
    persona: str,
) -> None:
    assert allowed_actions(PERSONAS[persona], ARCHIVED_EC) == [
        "project.unarchive",
        "project.view",
        "project.view_access",
    ]


# --- An independent oracle over many contexts and specs (Hypothesis) ---------------------------

_WS_RANK = {WorkspaceRole.MEMBER: 1, WorkspaceRole.ADMIN: 2, WorkspaceRole.OWNER: 3}
_ORG_RANK = {OrgRole.MEMBER: 1, OrgRole.ADMIN: 2, OrgRole.OWNER: 3}
_PROJECT_RANK = {ProjectRole.VIEWER: 1, ProjectRole.MEMBER: 2, ProjectRole.ADMIN: 3}
_PROJECTS = {PROJ: (ORG, WS), PROJ2: (ORG2, WS), uuid.UUID(int=103): (uuid.UUID(int=12), WS2)}

contexts = st.builds(
    AuthzContext,
    user_id=st.just(uuid.UUID(int=1)),
    is_system_admin=st.booleans(),
    workspace_roles=st.dictionaries(st.sampled_from([WS, WS2]), st.sampled_from(WorkspaceRole)),
    org_roles=st.dictionaries(
        st.sampled_from([ORG, ORG2, uuid.UUID(int=12)]), st.sampled_from(OrgRole)
    ),
    projects=st.dictionaries(st.sampled_from(list(_PROJECTS)), st.sampled_from(ProjectRole)).map(
        lambda held: {p: ProjectAccess(role, *_PROJECTS[p]) for p, role in held.items()}
    ),
)

specs = st.builds(
    ActionSpec,
    level=st.just(Level.PROJECT),
    workspace_role=st.sampled_from([None, WorkspaceRole.ADMIN, WorkspaceRole.OWNER]),
    org_role=st.sampled_from([None, OrgRole.ADMIN, OrgRole.OWNER]),
    project_role=st.sampled_from([None, *ProjectRole]),
    mutation=st.booleans(),
    archive_exempt=st.booleans(),
    visible=st.booleans(),
    access=st.sampled_from(AccessKind),
)


def _target(project: uuid.UUID, archived: bool) -> Target:
    org, workspace = _PROJECTS[project]
    return Target(
        workspace_id=workspace,
        organization_id=org,
        project_id=project,
        archived=archived,
        export_controlled=True,
    )


targets = st.builds(_target, st.sampled_from(list(_PROJECTS)), st.booleans())

_ADMINS = (WorkspaceRole.ADMIN, WorkspaceRole.OWNER, OrgRole.ADMIN, OrgRole.OWNER)


def _at_least[R](held: R | None, needed: R | None, rank: dict[R, int]) -> bool:
    return held is not None and needed is not None and rank[held] >= rank[needed]


def oracle(ctx: AuthzContext, spec: ActionSpec, target: Target) -> bool:
    """design-doc §5's order for a non-personal action on an export-controlled project, written
    independently of the code: archived, then the gate, then visible and the roles."""
    if target.archived and spec.mutation and not spec.archive_exempt:
        return False
    explicit = ctx.projects.get(target.project_id)  # pyright: ignore[reportArgumentType]
    if spec.access is AccessKind.CONTENT and explicit is None:
        return False
    org_role = ctx.org_roles.get(target.organization_id)  # pyright: ignore[reportArgumentType]
    sees = (
        ctx.is_system_admin
        or explicit is not None
        or ctx.workspace_roles.get(target.workspace_id) in _ADMINS
        or org_role in _ADMINS
    )
    return (
        ctx.is_system_admin
        or _at_least(ctx.workspace_roles.get(target.workspace_id), spec.workspace_role, _WS_RANK)
        or _at_least(org_role, spec.org_role, _ORG_RANK)
        or _at_least(explicit.role if explicit else None, spec.project_role, _PROJECT_RANK)
        or (spec.visible and sees)
    )


@given(ctx=contexts, spec=specs, target=targets)
def test_authorize_on_an_export_controlled_project_agrees_with_the_documented_order(
    ctx: AuthzContext, spec: ActionSpec, target: Target
) -> None:
    with patch.dict(REGISTRY, {"test_generated.ec": spec}):
        assert authorize(ctx, "test_generated.ec", target) is oracle(ctx, spec, target)
