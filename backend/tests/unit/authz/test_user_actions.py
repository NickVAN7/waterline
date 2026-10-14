"""S1-C10's two actions, on a user target (DL-73; build plan, "Users": "The account actions" and
"The account API"):

- a user is a target at its own level, `user`: its workspace, and the user's ID and memberships
  (an `Account`) for the rank rule;
- `user.manage` (every account action and the admin profile edit) is granted by no role, only by
  its targeted rule, the rank rule (design-doc §4, "Account management"); system admins hold it
  as for every action;
- `user.view_access` (the per-person access review, design-doc §5): workspace admins (and so
  owners) and system admins by role, and a targeted rule: the user themselves, or the rank rule;
- who sees whom (DL-72): a user target the actor can't see is a 404, one they see but may not act
  on a 403; the actor sees a user with at least one membership in the actor's scope, themselves,
  and, for workspace owners/admins and system admins, every user;
- a users-list row's `allowed_actions` are the `user`-level actions.

Actors are tests/support/authz.py's personas, relative to workspace WS, org ORG, and project
PROJ. System admins are left out of the matrices: `authorize()` already grants them every
non-personal action (test_authorize.py), so their rows couldn't fail here.
"""

import uuid

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.authz.authorize import allowed_actions, authorize, can_see, ensure
from app.authz.context import AuthzContext, ProjectAccess
from app.authz.target import Target, user_target
from app.core.errors import ForbiddenError, NotFoundError
from app.enums import OrgRole, ProjectRole, WorkspaceRole
from app.rules.account_rank import (
    Account,
    Membership,
    OrgRoleHeld,
    ProjectRoleHeld,
    WorkspaceRoleHeld,
    can_manage_account,
)
from tests.support.authz import ORG, ORG2, ORG3, PERSONAS, PROJ, PROJ2, PROJ3, PROJ4, WS, WS2

pytestmark = pytest.mark.security

MANAGE = "user.manage"
VIEW_ACCESS = "user.view_access"


def ws(role: WorkspaceRole, workspace: uuid.UUID = WS) -> WorkspaceRoleHeld:
    return WorkspaceRoleHeld(workspace_id=workspace, role=role)


def org(role: OrgRole, org_id: uuid.UUID = ORG) -> OrgRoleHeld:
    return OrgRoleHeld(workspace_id=WS, org_id=org_id, role=role)


def project(org_id: uuid.UUID = ORG, project_id: uuid.UUID = PROJ) -> ProjectRoleHeld:
    return ProjectRoleHeld(workspace_id=WS, org_id=org_id, project_id=project_id)


def user(
    n: int, *memberships: Membership, system_admin: bool = False, workspace: uuid.UUID = WS
) -> Target:
    """Another user (never one of the personas), in `workspace`, holding `memberships`."""
    account = Account(is_system_admin=system_admin, memberships=memberships)
    return user_target(workspace, uuid.UUID(int=5000 + n), account)


# The users acted on, relative to WS (orgs ORG and ORG2; PROJ in ORG, PROJ3 in ORG2) and WS2.
TARGETS: dict[str, Target] = {
    "workspace_owner": user(1, ws(WorkspaceRole.OWNER)),
    "workspace_admin": user(2, ws(WorkspaceRole.ADMIN)),
    "workspace_member": user(3, ws(WorkspaceRole.MEMBER)),
    "org_owner": user(4, org(OrgRole.OWNER)),
    "org_admin": user(5, org(OrgRole.ADMIN)),
    "org_member": user(6, org(OrgRole.MEMBER)),
    "project_only": user(7, project()),
    "org2_member": user(8, org(OrgRole.MEMBER, ORG2)),
    "org2_project_only": user(9, project(ORG2, PROJ3)),
    "member_of_org_and_org2": user(10, org(OrgRole.MEMBER), org(OrgRole.MEMBER, ORG2)),
    "org_member_on_an_org2_project": user(11, org(OrgRole.MEMBER), project(ORG2, PROJ3)),
    "staff_and_org_member": user(12, ws(WorkspaceRole.MEMBER), org(OrgRole.MEMBER)),
    "system_admin": user(13, system_admin=True),
    "system_admin_in_org": user(14, org(OrgRole.MEMBER), system_admin=True),
    "no_memberships": user(15),
    "other_workspace_owner": user(16, ws(WorkspaceRole.OWNER, WS2), workspace=WS2),
}

WS_ADMINS = {"workspace_owner", "workspace_admin"}
ORG_ADMINS_ABOVE = WS_ADMINS | {"org_owner", "org_admin"}

# Who may take account actions on each target under the rank rule (design-doc §4: "for every
# membership the target holds, the actor has a role covering it ... at an equal or higher
# rank"; members and project roles have no account actions).
MANAGERS: dict[str, set[str]] = {
    "workspace_owner": {"workspace_owner"},  # a workspace admin can't manage the owner
    "workspace_admin": WS_ADMINS,
    "workspace_member": WS_ADMINS,  # staff are above every org role
    "org_owner": WS_ADMINS | {"org_owner"},  # an org admin can't manage an owner
    "org_admin": ORG_ADMINS_ABOVE,
    "org_member": ORG_ADMINS_ABOVE,
    "project_only": ORG_ADMINS_ABOVE,  # not the project's own admin
    "org2_member": WS_ADMINS | {"other_org_owner"},
    "org2_project_only": WS_ADMINS | {"other_org_owner"},
    # A membership another org's admin can't cover keeps every org admin out.
    "member_of_org_and_org2": WS_ADMINS,
    "org_member_on_an_org2_project": WS_ADMINS,
    "staff_and_org_member": WS_ADMINS,
    # The flag is the top rank: only system admins.
    "system_admin": set(),
    "system_admin_in_org": set(),
    # No memberships: the workspace's owners/admins (DL-69).
    "no_memberships": WS_ADMINS,
    "other_workspace_owner": {"other_workspace_owner"},
}

# Users in more than one workspace are undecided (design-doc §4, "One workspace"): whether another
# workspace's owner manages, or sees, a user with no memberships in the only workspace.
UNDECIDED = {("no_memberships", "other_workspace_owner")}
ACTORS = [persona for persona in PERSONAS if persona != "system_admin"]


def matrix(allowed: dict[str, set[str]]) -> list[tuple[str, str, bool]]:
    return [
        (target, persona, persona in allowed[target])
        for target in allowed
        for persona in ACTORS
        if (target, persona) not in UNDECIDED
    ]


# The per-person view: workspace owners/admins for anyone in their workspace, and the rank rule.
VIEWERS: dict[str, set[str]] = {
    target: MANAGERS[target] | (WS_ADMINS if TARGETS[target].workspace_id == WS else set())
    for target in TARGETS
}


# --- user.manage: the rank rule only ------------------------------------------------------------


@pytest.mark.parametrize(("target", "persona", "allowed"), matrix(MANAGERS))
def test_user_manage_follows_the_rank_rule(target: str, persona: str, allowed: bool) -> None:
    assert authorize(PERSONAS[persona], MANAGE, TARGETS[target]) is allowed


@pytest.mark.parametrize("target", ["system_admin", "system_admin_in_org"])
def test_a_system_admin_is_managed_by_system_admins_only(target: str) -> None:
    """Not even the workspace owner."""
    assert authorize(PERSONAS["system_admin"], MANAGE, TARGETS[target]) is True
    assert authorize(PERSONAS["workspace_owner"], MANAGE, TARGETS[target]) is False


# Own account (design-doc §4: admins act on their own account through the admin path, under the
# same rule; the own-email and own-password-reset exceptions are the services', DL-73).
SELF_ACCOUNTS: dict[str, Account] = {
    "workspace_owner": Account(memberships=(ws(WorkspaceRole.OWNER),)),
    "workspace_admin": Account(memberships=(ws(WorkspaceRole.ADMIN),)),
    "workspace_member": Account(memberships=(ws(WorkspaceRole.MEMBER),)),
    "org_owner": Account(memberships=(org(OrgRole.OWNER),)),
    "org_admin": Account(memberships=(org(OrgRole.ADMIN),)),
    "org_member": Account(memberships=(org(OrgRole.MEMBER),)),
    "project_admin": Account(memberships=(project(),)),
    "project_member": Account(memberships=(project(),)),
    "project_viewer": Account(memberships=(project(),)),
    "other_project_admin": Account(memberships=(project(ORG, PROJ2),)),
    "other_org_owner": Account(memberships=(org(OrgRole.OWNER, ORG2),)),
    "other_workspace_owner": Account(memberships=(ws(WorkspaceRole.OWNER, WS2),)),
    "nobody": Account(),
}
SELF_WORKSPACE = {"other_workspace_owner": WS2}


def self_target(persona: str) -> Target:
    return user_target(
        SELF_WORKSPACE.get(persona, WS), PERSONAS[persona].user_id, SELF_ACCOUNTS[persona]
    )


SELF_MANAGERS = {
    "workspace_owner", "workspace_admin", "org_owner", "org_admin", "other_org_owner",
    "other_workspace_owner",
}  # fmt: skip


@pytest.mark.parametrize(
    ("persona", "allowed"), [(persona, persona in SELF_MANAGERS) for persona in ACTORS]
)
def test_user_manage_on_ones_own_account_follows_the_same_rank_rule(
    persona: str, allowed: bool
) -> None:
    """An admin covers their own role at equal rank; a member or project-only user has no
    account actions, on themselves either."""
    assert authorize(PERSONAS[persona], MANAGE, self_target(persona)) is allowed


# --- user.view_access: workspace admins by role, the user themselves, or the rank rule ---------


@pytest.mark.parametrize(("target", "persona", "allowed"), matrix(VIEWERS))
def test_the_access_review_is_for_workspace_admins_and_whoever_has_the_person_in_rank(
    target: str, persona: str, allowed: bool
) -> None:
    """design-doc §5, "Access review": workspace owners/admins for anyone (the workspace owner and
    system admins included), org owners/admins only for a person every membership of whom their
    roles cover; never an org member, a project admin, or staff with role member."""
    assert authorize(PERSONAS[persona], VIEW_ACCESS, TARGETS[target]) is allowed


@pytest.mark.parametrize("persona", ACTORS)
def test_everyone_may_open_their_own_access_review(persona: str) -> None:
    assert authorize(PERSONAS[persona], VIEW_ACCESS, self_target(persona)) is True


def test_a_workspace_role_opens_access_reviews_only_in_its_own_workspace() -> None:
    assert authorize(PERSONAS["workspace_admin"], VIEW_ACCESS, TARGETS["org2_member"]) is True
    assert (
        authorize(PERSONAS["workspace_admin"], VIEW_ACCESS, TARGETS["other_workspace_owner"])
        is False
    )


# --- Who sees whom: can_see, and ensure()'s 404 and 403 ----------------------------------------

NOT_WORKSPACE_ADMINS = [
    "workspace_member", "org_owner", "org_admin", "org_member", "project_admin",
    "project_member", "project_viewer", "other_project_admin", "other_org_owner", "nobody",
]  # fmt: skip


@pytest.mark.parametrize("persona", NOT_WORKSPACE_ADMINS)
def test_everyone_sees_themselves(persona: str) -> None:
    assert can_see(PERSONAS[persona], self_target(persona)) is True


@pytest.mark.parametrize(
    ("persona", "target"),
    [
        ("org_admin", "org_member"),
        ("org_admin", "org_owner"),
        ("org_admin", "project_only"),
        ("org_admin", "member_of_org_and_org2"),
        ("org_admin", "org_member_on_an_org2_project"),
        ("org_admin", "staff_and_org_member"),
        ("org_admin", "system_admin_in_org"),
        ("org_owner", "org_admin"),
        ("other_org_owner", "org2_project_only"),
        ("other_org_owner", "member_of_org_and_org2"),
    ],
)
def test_an_org_admin_sees_a_user_with_a_membership_in_their_org(persona: str, target: str) -> None:
    assert can_see(PERSONAS[persona], TARGETS[target]) is True


@pytest.mark.parametrize(
    ("persona", "target"),
    [
        ("org_admin", "org_owner"),
        ("org_admin", "member_of_org_and_org2"),
        ("org_admin", "org_member_on_an_org2_project"),
        ("org_admin", "staff_and_org_member"),
        ("org_admin", "system_admin_in_org"),
        ("other_org_owner", "member_of_org_and_org2"),
        ("workspace_admin", "workspace_owner"),
        ("workspace_admin", "system_admin"),
        ("workspace_owner", "system_admin_in_org"),
    ],
)
def test_ensure_is_403_for_a_user_the_actor_sees_but_may_not_manage(
    persona: str, target: str
) -> None:
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS[persona], MANAGE, TARGETS[target])


@pytest.mark.parametrize(
    "persona", ["workspace_member", "org_member", "project_viewer", "other_project_admin", "nobody"]
)
def test_ensure_is_403_on_ones_own_account_without_the_rank(persona: str) -> None:
    """They see themselves, so it's a 403, never a 404."""
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS[persona], MANAGE, self_target(persona))


@pytest.mark.parametrize(
    ("persona", "target"),
    [
        ("org_admin", "org2_member"),
        ("org_admin", "org2_project_only"),
        ("org_admin", "workspace_member"),
        ("org_admin", "no_memberships"),
        ("org_admin", "system_admin"),
        ("org_owner", "workspace_admin"),
        ("other_org_owner", "org_member"),
        ("other_org_owner", "project_only"),
        ("nobody", "org_member"),
    ],
)
def test_ensure_is_404_for_a_user_outside_the_actors_scope(persona: str, target: str) -> None:
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], MANAGE, TARGETS[target])


@pytest.mark.parametrize(
    ("persona", "target"),
    [
        ("org_admin", "org_member"),
        ("org_owner", "org_admin"),
        ("workspace_admin", "no_memberships"),
        ("workspace_admin", "staff_and_org_member"),
    ],
)
def test_ensure_lets_a_manager_through(persona: str, target: str) -> None:
    assert ensure(PERSONAS[persona], MANAGE, TARGETS[target]) is None


# --- allowed_actions on a user target: the user-level actions ---------------------------------

BOTH = ["user.manage", "user.view_access"]


@pytest.mark.parametrize(
    ("persona", "target", "expected"),
    [
        ("system_admin", "org_member", BOTH),
        ("system_admin", "system_admin", BOTH),
        ("workspace_admin", "org_member", BOTH),
        ("workspace_admin", "workspace_owner", ["user.view_access"]),
        ("workspace_owner", "system_admin", ["user.view_access"]),
        ("org_admin", "org_member", BOTH),
        ("org_admin", "org_owner", []),
        ("org_admin", "member_of_org_and_org2", []),
        ("org_admin", "org2_member", []),
        ("project_admin", "project_only", []),
    ],
)
def test_allowed_actions_on_a_user_are_the_user_level_actions_allowed(
    persona: str, target: str, expected: list[str]
) -> None:
    """No workspace-level action (e.g. `user.check`, `workspace.view`) is listed on a user."""
    assert allowed_actions(PERSONAS[persona], TARGETS[target]) == expected


@pytest.mark.parametrize(
    ("persona", "expected"),
    [
        ("org_admin", BOTH),
        ("workspace_owner", BOTH),
        ("org_member", ["user.view_access"]),
        ("nobody", ["user.view_access"]),
    ],
)
def test_allowed_actions_on_ones_own_row(persona: str, expected: list[str]) -> None:
    assert allowed_actions(PERSONAS[persona], self_target(persona)) == expected


# --- Over many contexts: independent oracles (Hypothesis) --------------------------------------

_PROJECTS = {PROJ: (ORG, WS), PROJ2: (ORG, WS), PROJ3: (ORG2, WS), PROJ4: (ORG3, WS2)}
_ORGS = {ORG: WS, ORG2: WS, ORG3: WS2}
ACTOR_ID = uuid.UUID(int=1)


def _context(
    flag: bool,
    workspace_roles: dict[uuid.UUID, WorkspaceRole],
    org_roles: dict[uuid.UUID, OrgRole],
    projects: dict[uuid.UUID, ProjectRole],
) -> AuthzContext:
    return AuthzContext(
        user_id=ACTOR_ID,
        is_system_admin=flag,
        workspace_roles=workspace_roles,
        org_roles=org_roles,
        org_workspaces={org_id: _ORGS[org_id] for org_id in org_roles},
        projects={p: ProjectAccess(role, *_PROJECTS[p]) for p, role in projects.items()},
    )


contexts = st.builds(
    _context,
    st.booleans(),
    st.dictionaries(st.sampled_from([WS, WS2]), st.sampled_from(WorkspaceRole)),
    st.dictionaries(st.sampled_from(list(_ORGS)), st.sampled_from(OrgRole)),
    st.dictionaries(st.sampled_from(list(_PROJECTS)), st.sampled_from(ProjectRole)),
)
_WS_ADMIN_ROLES = st.sampled_from([WorkspaceRole.ADMIN, WorkspaceRole.OWNER])
_ORG_ADMIN_ROLES = st.sampled_from([OrgRole.ADMIN, OrgRole.OWNER])
# Only owner/admin roles: whether a member role makes a scope is left open.
admin_contexts = st.builds(
    _context,
    st.booleans(),
    st.dictionaries(st.just(WS), _WS_ADMIN_ROLES),
    st.dictionaries(st.sampled_from([ORG, ORG2]), _ORG_ADMIN_ROLES),
    st.just({}),
)

_target_memberships: st.SearchStrategy[Membership] = st.one_of(
    st.builds(ws, st.sampled_from(WorkspaceRole)),
    st.builds(org, st.sampled_from(OrgRole), st.sampled_from([ORG, ORG2])),
    st.sampled_from([PROJ, PROJ2, PROJ3]).map(lambda p: project(_PROJECTS[p][0], p)),
)


# Another user in WS, holding at least the flag or a membership (an empty one is undecided for
# another workspace's admins, above).
def _other_user(flag: bool, held: list[Membership]) -> Target:
    return user_target(WS, uuid.UUID(int=2), Account(is_system_admin=flag, memberships=tuple(held)))


targets = st.builds(
    _other_user,
    st.booleans(),
    st.lists(_target_memberships, max_size=3).filter(bool) | st.just([]),
).filter(lambda t: t != _other_user(False, []))


def account_of(ctx: AuthzContext) -> Account:
    """The actor's memberships as the rank rule sees them, from the context."""
    return Account(
        is_system_admin=ctx.is_system_admin,
        memberships=(
            *(WorkspaceRoleHeld(w, role) for w, role in ctx.workspace_roles.items()),
            *(OrgRoleHeld(ctx.org_workspaces[o], o, role) for o, role in ctx.org_roles.items()),
            *(
                ProjectRoleHeld(a.workspace_id, a.organization_id, p)
                for p, a in ctx.projects.items()
            ),
        ),
    )


def _entity(target: Target) -> Account:
    assert isinstance(target.entity, Account)
    return target.entity


@given(ctx=contexts, target=targets)
def test_user_manage_is_the_rank_rule_over_the_context(ctx: AuthzContext, target: Target) -> None:
    expected = ctx.is_system_admin or can_manage_account(account_of(ctx), _entity(target))

    assert authorize(ctx, MANAGE, target) is expected


@given(ctx=contexts, target=targets)
def test_user_view_access_is_a_workspace_admin_role_or_the_rank_rule(
    ctx: AuthzContext, target: Target
) -> None:
    expected = (
        ctx.is_system_admin
        or ctx.workspace_roles.get(WS) in (WorkspaceRole.ADMIN, WorkspaceRole.OWNER)
        or can_manage_account(account_of(ctx), _entity(target))
    )

    assert authorize(ctx, VIEW_ACCESS, target) is expected


def _in_reach(ctx: AuthzContext, held: Membership) -> bool:
    """An owner/admin role of the actor whose workspace or org holds `held`."""
    in_org = isinstance(held, OrgRoleHeld | ProjectRoleHeld) and held.org_id in ctx.org_roles
    return ctx.workspace_roles.get(held.workspace_id) is not None or in_org


def sees(ctx: AuthzContext, target: Target) -> bool:
    """DL-72's "who sees whom", for owner/admin actors, written independently of the code."""
    return (
        ctx.is_system_admin
        or WS in ctx.workspace_roles
        or any(_in_reach(ctx, held) for held in _entity(target).memberships)
    )


@given(ctx=admin_contexts, target=targets)
def test_can_see_a_user_agrees_with_who_sees_whom(ctx: AuthzContext, target: Target) -> None:
    assert can_see(ctx, target) is sees(ctx, target)
