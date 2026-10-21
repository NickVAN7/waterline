"""S1-C9's three actions (DL-68; build plan, "Authorization (§5)", "The org members API"):

- `org_member.manage` (listing, adding, creating, changing roles of, and removing an org's
  members): org owners/admins, workspace owners/admins, system admins;
- `org_member.manage_admins` (granting, changing, or removing an org owner or admin role, on top
  of `org_member.manage`): org owners, workspace owners/admins, system admins;
- `user.check` (the user check, DL-66): a workspace-level action for workspace owners/admins and
  system admins, plus a targeted rule for owners/admins of an org in the workspace and explicit
  admins of its non-archived projects; 404 for anyone else (design-doc §4, "Visibility").

And the registry's `rule` field, through test-only actions: a targeted rule granting an action on
top of the roles, last in design-doc §5's order (so after the archived-project check).

The org-level personas are tests/support/authz.py's, relative to workspace WS and org ORG.
`user.check`'s rule reads each org role's workspace and each project's archived state, which those
personas don't carry, so its personas are built here.
"""

import uuid

import pytest

from app.authz.actions import REGISTRY, ActionSpec, Level
from app.authz.authorize import allowed_actions, authorize, ensure
from app.authz.context import AuthzContext, ProjectAccess
from app.authz.target import Target
from app.core.errors import ForbiddenError, NotFoundError
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

# --- org_member.manage and org_member.manage_admins (org level) ---------------------------------


@pytest.mark.parametrize(
    ("persona", "allowed"),
    rows({"system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"}),
)
def test_managing_members_is_for_org_owners_admins_and_the_admins_above(
    persona: str, allowed: bool
) -> None:
    """Denied to an org member, the org's project members and admins (no org role), staff with
    role member, another org's owner, another workspace's owner, and a user with no memberships."""
    assert authorize(PERSONAS[persona], "org_member.manage", ORG_TARGET) is allowed


@pytest.mark.parametrize(
    ("persona", "allowed"),
    rows({"system_admin", "workspace_owner", "workspace_admin", "org_owner"}),
)
def test_managing_owner_and_admin_roles_is_for_org_owners_and_the_admins_above(
    persona: str, allowed: bool
) -> None:
    """DL-68: unlike `workspace_staff.manage_admins`, workspace admins hold it too (their org
    owner capabilities in every org, §5); an org admin doesn't."""
    assert authorize(PERSONAS[persona], "org_member.manage_admins", ORG_TARGET) is allowed


@pytest.mark.parametrize("action", ["org_member.manage", "org_member.manage_admins"])
def test_an_org_role_manages_only_its_own_orgs_members(action: str) -> None:
    owner_of_org2 = PERSONAS["other_org_owner"]

    assert authorize(owner_of_org2, action, Target(workspace_id=WS, organization_id=ORG2)) is True
    assert authorize(owner_of_org2, action, ORG_TARGET) is False


@pytest.mark.parametrize("action", ["org_member.manage", "org_member.manage_admins"])
def test_a_workspace_admin_manages_members_only_in_their_own_workspace(action: str) -> None:
    admin_of_ws = PERSONAS["workspace_admin"]

    assert authorize(admin_of_ws, action, ORG_TARGET) is True
    assert authorize(admin_of_ws, action, Target(workspace_id=WS2, organization_id=ORG3)) is False


@pytest.mark.parametrize(
    ("persona", "action"),
    [
        ("org_member", "org_member.manage"),
        ("project_admin", "org_member.manage"),
        ("project_viewer", "org_member.manage"),
        ("other_project_admin", "org_member.manage"),
        ("org_admin", "org_member.manage_admins"),
        ("org_member", "org_member.manage_admins"),
    ],
)
def test_ensure_is_403_for_member_management_on_an_org_the_user_sees(
    persona: str, action: str
) -> None:
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS[persona], action, ORG_TARGET)


@pytest.mark.parametrize(
    "persona", ["workspace_member", "other_org_owner", "other_workspace_owner", "nobody"]
)
@pytest.mark.parametrize("action", ["org_member.manage", "org_member.manage_admins"])
def test_ensure_is_404_for_member_management_on_an_org_the_user_cannot_see(
    persona: str, action: str
) -> None:
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], action, ORG_TARGET)


@pytest.mark.parametrize(
    ("persona", "action"),
    [
        ("org_admin", "org_member.manage"),
        ("org_owner", "org_member.manage_admins"),
        ("workspace_admin", "org_member.manage_admins"),
    ],
)
def test_ensure_lets_member_managers_through(persona: str, action: str) -> None:
    assert ensure(PERSONAS[persona], action, ORG_TARGET) is None


# --- user.check (workspace level, with a targeted rule) -----------------------------------------


def _user(n: int) -> uuid.UUID:
    return uuid.UUID(int=2000 + n)


def _org_role(n: int, org: uuid.UUID, workspace: uuid.UUID, role: OrgRole) -> AuthzContext:
    return AuthzContext(user_id=_user(n), org_roles={org: role}, org_workspaces={org: workspace})


def _projects(n: int, **held: ProjectAccess) -> AuthzContext:
    ids = {"proj": PROJ, "proj2": PROJ2, "proj3": PROJ3, "proj4": PROJ4}
    return AuthzContext(
        user_id=_user(n), projects={ids[key]: access for key, access in held.items()}
    )


# Relative to workspace WS (orgs ORG and ORG2; projects PROJ and PROJ2 in ORG, PROJ3 in ORG2) and
# WS2 (org ORG3, project PROJ4).
CHECKERS: dict[str, AuthzContext] = {
    "system_admin": AuthzContext(user_id=_user(1), is_system_admin=True),
    "workspace_owner": AuthzContext(user_id=_user(2), workspace_roles={WS: WorkspaceRole.OWNER}),
    "workspace_admin": AuthzContext(user_id=_user(3), workspace_roles={WS: WorkspaceRole.ADMIN}),
    "org_owner": _org_role(4, ORG, WS, OrgRole.OWNER),
    "org_admin": _org_role(5, ORG, WS, OrgRole.ADMIN),
    # Another org in the same workspace counts the same.
    "org2_admin": _org_role(6, ORG2, WS, OrgRole.ADMIN),
    "project_admin": _projects(7, proj=ProjectAccess(ProjectRole.ADMIN, ORG, WS)),
    "org2_project_admin": _projects(8, proj3=ProjectAccess(ProjectRole.ADMIN, ORG2, WS)),
    # One archived project doesn't cancel a live one.
    "admin_of_an_archived_and_a_live_project": _projects(
        9,
        proj=ProjectAccess(ProjectRole.ADMIN, ORG, WS, archived=True),
        proj2=ProjectAccess(ProjectRole.ADMIN, ORG, WS),
    ),
    # Staff with role member who are also an explicit project admin there.
    "staff_member_and_project_admin": AuthzContext(
        user_id=_user(10),
        workspace_roles={WS: WorkspaceRole.MEMBER},
        projects={PROJ: ProjectAccess(ProjectRole.ADMIN, ORG, WS)},
    ),
}
NOT_CHECKERS: dict[str, AuthzContext] = {
    "workspace_member": AuthzContext(user_id=_user(20), workspace_roles={WS: WorkspaceRole.MEMBER}),
    "org_member": _org_role(21, ORG, WS, OrgRole.MEMBER),
    "project_member": _projects(22, proj=ProjectAccess(ProjectRole.MEMBER, ORG, WS)),
    "project_viewer": _projects(23, proj=ProjectAccess(ProjectRole.VIEWER, ORG, WS)),
    # An archived project's admin can't add anyone to it, so isn't in the audience.
    "archived_project_admin": _projects(
        24, proj=ProjectAccess(ProjectRole.ADMIN, ORG, WS, archived=True)
    ),
    "member_and_viewer_of_live_projects": _projects(
        25,
        proj=ProjectAccess(ProjectRole.MEMBER, ORG, WS),
        proj2=ProjectAccess(ProjectRole.VIEWER, ORG, WS),
    ),
    # Roles in another workspace.
    "other_workspace_owner": AuthzContext(
        user_id=_user(26), workspace_roles={WS2: WorkspaceRole.OWNER}
    ),
    "other_workspace_org_owner": _org_role(27, ORG3, WS2, OrgRole.OWNER),
    "other_workspace_project_admin": _projects(
        28, proj4=ProjectAccess(ProjectRole.ADMIN, ORG3, WS2)
    ),
    "nobody": AuthzContext(user_id=_user(29)),
}
# Those granted only by the targeted rule (no role in the workspace's own pages).
RULE_CHECKERS = [
    "org_owner",
    "org_admin",
    "org2_admin",
    "project_admin",
    "org2_project_admin",
    "admin_of_an_archived_and_a_live_project",
    "staff_member_and_project_admin",
]


@pytest.mark.parametrize("persona", list(CHECKERS))
def test_the_user_check_is_for_those_who_may_add_a_person_in_the_workspace(persona: str) -> None:
    assert authorize(CHECKERS[persona], "user.check", WORKSPACE_TARGET) is True


@pytest.mark.parametrize("persona", list(NOT_CHECKERS))
def test_the_user_check_is_denied_to_everyone_else(persona: str) -> None:
    assert authorize(NOT_CHECKERS[persona], "user.check", WORKSPACE_TARGET) is False


@pytest.mark.parametrize("persona", RULE_CHECKERS)
def test_an_org_or_project_admin_role_counts_only_in_its_own_workspace(persona: str) -> None:
    assert authorize(CHECKERS[persona], "user.check", Target(workspace_id=WS2)) is False


@pytest.mark.parametrize("persona", list(CHECKERS))
def test_ensure_lets_the_user_checks_audience_through(persona: str) -> None:
    """Including the org and project admins, who don't see the workspace pages."""
    assert ensure(CHECKERS[persona], "user.check", WORKSPACE_TARGET) is None


@pytest.mark.parametrize("persona", list(NOT_CHECKERS))
def test_ensure_is_404_for_everyone_else_on_the_user_check(persona: str) -> None:
    """404, never 403: the same as for the workspace pages (DL-68)."""
    with pytest.raises(NotFoundError):
        ensure(NOT_CHECKERS[persona], "user.check", WORKSPACE_TARGET)


@pytest.mark.parametrize(
    ("persona", "expected"),
    [
        ("org_admin", ["user.check"]),
        ("project_admin", ["user.check"]),
        ("staff_member_and_project_admin", ["user.check"]),
    ],
)
def test_allowed_actions_on_the_workspace_carry_the_user_check_from_the_rule(
    persona: str, expected: list[str]
) -> None:
    assert allowed_actions(CHECKERS[persona], WORKSPACE_TARGET) == expected


@pytest.mark.parametrize("persona", ["org_member", "archived_project_admin", "nobody"])
def test_allowed_actions_on_the_workspace_are_empty_for_everyone_else(persona: str) -> None:
    assert allowed_actions(NOT_CHECKERS[persona], WORKSPACE_TARGET) == []


# --- The `rule` field, through test-only actions ------------------------------------------------

FAVOURED = uuid.UUID(int=3000)
RULE_ACTION = "test_rule.edit"


def favoured_on_proj(ctx: AuthzContext, target: Target) -> bool:
    """A rule reading both the context and the target."""
    return ctx.user_id == FAVOURED and target.project_id == PROJ


def never(ctx: AuthzContext, target: Target) -> bool:
    return False


def test_a_targeted_rule_grants_an_action_no_role_does(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(REGISTRY, RULE_ACTION, ActionSpec(Level.PROJECT, rule=favoured_on_proj))

    assert authorize(AuthzContext(user_id=FAVOURED), RULE_ACTION, PROJECT_TARGET) is True


@pytest.mark.parametrize(
    ("user_id", "target"),
    [
        (_user(99), PROJECT_TARGET),
        (FAVOURED, Target(workspace_id=WS, organization_id=ORG, project_id=PROJ2)),
    ],
)
def test_a_targeted_rule_that_doesnt_hold_grants_nothing(
    monkeypatch: pytest.MonkeyPatch, user_id: uuid.UUID, target: Target
) -> None:
    monkeypatch.setitem(REGISTRY, RULE_ACTION, ActionSpec(Level.PROJECT, rule=favoured_on_proj))

    assert authorize(AuthzContext(user_id=user_id), RULE_ACTION, target) is False


def test_a_targeted_rule_comes_after_the_archived_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """design-doc §5: targeted rules are last; a mutation in an archived project is denied."""
    monkeypatch.setitem(REGISTRY, RULE_ACTION, ActionSpec(Level.PROJECT, rule=favoured_on_proj))

    assert authorize(AuthzContext(user_id=FAVOURED), RULE_ACTION, ARCHIVED_PROJECT_TARGET) is False


def test_a_role_still_grants_when_the_targeted_rule_doesnt(monkeypatch: pytest.MonkeyPatch) -> None:
    """The rule grants on top of the roles; it never takes away what a role grants."""
    spec = ActionSpec(Level.PROJECT, project_role=ProjectRole.VIEWER, rule=never)
    monkeypatch.setitem(REGISTRY, RULE_ACTION, spec)

    assert authorize(PERSONAS["project_viewer"], RULE_ACTION, PROJECT_TARGET) is True
