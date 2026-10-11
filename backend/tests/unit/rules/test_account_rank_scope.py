"""The rank rule's first half, and the orgs an account action's events go to (S1-C10).

- `in_scope(actor, target)`: the target holds at least one membership in the actor's scope
  (design-doc §4, "Account management"), which decides whether the actor sees the target at all:
  a 404 otherwise (build plan, "The account API", "Who sees whom"; DL-72). Rank plays no part
  here; it is the rule's second half (`can_manage_account`).
- `covering_orgs(actor, target)` (DL-75; build plan, "Audit scope"): when a system-admin or
  workspace role of the actor covers the target under the rank rule, no org (one event with no
  `organization_id`); otherwise each org whose owner/admin role of the actor covers one of the
  target's memberships.

Actors here hold only owner/admin roles (and the system-admin flag): whether a member role or a
project role makes a scope is left open (reported as a question).
"""

import uuid

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.enums import OrgRole, WorkspaceRole
from app.rules.account_rank import (
    Account,
    Membership,
    OrgRoleHeld,
    ProjectRoleHeld,
    WorkspaceRoleHeld,
    can_manage_account,
    covering_orgs,
    in_scope,
)

pytestmark = pytest.mark.security

# Workspace WS holds orgs ORG and ORG2, with projects PROJECT (in ORG) and ORG2_PROJECT; OTHER_WS
# holds FAR_ORG.
WS = uuid.UUID(int=1)
OTHER_WS = uuid.UUID(int=2)
ORG = uuid.UUID(int=10)
ORG2 = uuid.UUID(int=11)
FAR_ORG = uuid.UUID(int=12)
PROJECT = uuid.UUID(int=100)
ORG2_PROJECT = uuid.UUID(int=101)


def ws(role: WorkspaceRole, workspace: uuid.UUID = WS) -> WorkspaceRoleHeld:
    return WorkspaceRoleHeld(workspace_id=workspace, role=role)


def org(role: OrgRole, org_id: uuid.UUID = ORG, workspace: uuid.UUID = WS) -> OrgRoleHeld:
    return OrgRoleHeld(workspace_id=workspace, org_id=org_id, role=role)


def project(org_id: uuid.UUID = ORG, project_id: uuid.UUID = PROJECT) -> ProjectRoleHeld:
    return ProjectRoleHeld(workspace_id=WS, org_id=org_id, project_id=project_id)


def holding(*memberships: Membership, system_admin: bool = False) -> Account:
    return Account(is_system_admin=system_admin, memberships=memberships)


SYSTEM_ADMIN = holding(system_admin=True)
WS_OWNER = holding(ws(WorkspaceRole.OWNER))
WS_ADMIN = holding(ws(WorkspaceRole.ADMIN))
WS_MEMBER = holding(ws(WorkspaceRole.MEMBER))
ORG_OWNER = holding(org(OrgRole.OWNER))
ORG_ADMIN = holding(org(OrgRole.ADMIN))
ORG_MEMBER = holding(org(OrgRole.MEMBER))
ORG2_MEMBER = holding(org(OrgRole.MEMBER, ORG2))
ORG2_OWNER = holding(org(OrgRole.OWNER, ORG2))
PROJECT_ONLY = holding(project())
NO_MEMBERSHIPS = holding()

# --- in_scope: the rank rule's first half ------------------------------------------------------


@pytest.mark.parametrize(
    ("actor", "target"),
    [
        # An org admin's scope is their org: its members, admins, owners, and its projects' users.
        (ORG_ADMIN, ORG_MEMBER),
        (ORG_ADMIN, holding(org(OrgRole.ADMIN))),
        (ORG_ADMIN, ORG_OWNER),  # in scope, though above the actor's rank (a 403, not a 404)
        (ORG_ADMIN, PROJECT_ONLY),
        (ORG_OWNER, ORG_MEMBER),
        # One membership in scope is enough, whatever else the target holds.
        (ORG_ADMIN, holding(org(OrgRole.MEMBER), org(OrgRole.MEMBER, ORG2))),
        (ORG_ADMIN, holding(org(OrgRole.MEMBER), project(ORG2, ORG2_PROJECT))),
        (ORG_ADMIN, holding(ws(WorkspaceRole.MEMBER), org(OrgRole.MEMBER))),
        (ORG_ADMIN, holding(org(OrgRole.MEMBER), system_admin=True)),
        # A workspace admin's scope is the workspace: staff, its orgs, and their projects.
        (WS_ADMIN, WS_OWNER),
        (WS_ADMIN, WS_MEMBER),
        (WS_ADMIN, ORG_OWNER),
        (WS_ADMIN, PROJECT_ONLY),
        (WS_OWNER, ORG2_MEMBER),
        # A system admin's scope is everything.
        (SYSTEM_ADMIN, WS_OWNER),
        (SYSTEM_ADMIN, holding(org(OrgRole.MEMBER, FAR_ORG, OTHER_WS))),
        (SYSTEM_ADMIN, SYSTEM_ADMIN),
        # Roles in several orgs: a scope each.
        (holding(org(OrgRole.ADMIN), org(OrgRole.ADMIN, ORG2)), ORG2_MEMBER),
    ],
)
def test_a_target_with_a_membership_in_the_actors_scope_is_in_scope(
    actor: Account, target: Account
) -> None:
    assert in_scope(actor, target) is True


@pytest.mark.parametrize(
    ("actor", "target"),
    [
        # Another org of the same workspace is outside an org admin's scope.
        (ORG_ADMIN, ORG2_MEMBER),
        (ORG_ADMIN, holding(project(ORG2, ORG2_PROJECT))),
        (ORG2_OWNER, ORG_MEMBER),
        # Staff sit above any org: outside an org admin's or owner's scope.
        (ORG_ADMIN, WS_MEMBER),
        (ORG_OWNER, WS_ADMIN),
        # The system-admin flag alone sits above every scope but a system admin's.
        (ORG_ADMIN, SYSTEM_ADMIN),
        (WS_OWNER, SYSTEM_ADMIN),
        # No memberships at all: nothing in an org admin's scope (DL-69: until they add them).
        (ORG_ADMIN, NO_MEMBERSHIPS),
        (ORG_OWNER, NO_MEMBERSHIPS),
        # Another workspace.
        (WS_OWNER, holding(ws(WorkspaceRole.MEMBER, OTHER_WS))),
        (WS_ADMIN, holding(org(OrgRole.MEMBER, FAR_ORG, OTHER_WS))),
        (holding(ws(WorkspaceRole.OWNER, OTHER_WS)), ORG_MEMBER),
    ],
)
def test_a_target_with_no_membership_in_the_actors_scope_is_out_of_scope(
    actor: Account, target: Account
) -> None:
    assert in_scope(actor, target) is False


def test_an_org_admins_scope_is_their_own_org_only() -> None:
    """The same target shape, inside and outside the scope."""
    assert in_scope(ORG_ADMIN, ORG_MEMBER) is True
    assert in_scope(holding(org(OrgRole.ADMIN, ORG2)), ORG_MEMBER) is False


# --- in_scope over many accounts: an independent oracle (Hypothesis) ---------------------------

_ORGS = {ORG: WS, ORG2: WS, FAR_ORG: OTHER_WS}
_PROJECTS = {PROJECT: ORG, ORG2_PROJECT: ORG2}

_admin_roles = st.lists(
    st.one_of(
        st.builds(
            WorkspaceRoleHeld,
            workspace_id=st.sampled_from([WS, OTHER_WS]),
            role=st.sampled_from([WorkspaceRole.ADMIN, WorkspaceRole.OWNER]),
        ),
        st.sampled_from(list(_ORGS)).flatmap(
            lambda org_id: st.builds(
                OrgRoleHeld,
                workspace_id=st.just(_ORGS[org_id]),
                org_id=st.just(org_id),
                role=st.sampled_from([OrgRole.ADMIN, OrgRole.OWNER]),
            )
        ),
    ),
    max_size=3,
)
_any_membership: st.SearchStrategy[Membership] = st.one_of(
    st.builds(
        WorkspaceRoleHeld,
        workspace_id=st.sampled_from([WS, OTHER_WS]),
        role=st.sampled_from(WorkspaceRole),
    ),
    st.sampled_from(list(_ORGS)).flatmap(
        lambda org_id: st.builds(
            OrgRoleHeld,
            workspace_id=st.just(_ORGS[org_id]),
            org_id=st.just(org_id),
            role=st.sampled_from(OrgRole),
        )
    ),
    st.sampled_from(list(_PROJECTS)).map(
        lambda project_id: ProjectRoleHeld(
            workspace_id=WS, org_id=_PROJECTS[project_id], project_id=project_id
        )
    ),
)


def _account(flag: bool, held: list[Membership]) -> Account:
    return Account(is_system_admin=flag, memberships=tuple(held))


actors = st.builds(_account, st.booleans(), _admin_roles)
# At least one thing held (the flag or a membership): an empty target's scope is left open for
# workspace admins and system admins (reported as a question).
targets = st.builds(_account, st.booleans(), st.lists(_any_membership, max_size=3)).filter(
    lambda account: account.is_system_admin or bool(account.memberships)
)


def _contains(scope: Membership, held: Membership) -> bool:
    """Whether an actor role's workspace or org holds the membership `held` (design-doc §4: "the
    same workspace, org, or project, or one above it"); written independently of the code."""
    if isinstance(scope, WorkspaceRoleHeld):
        return held.workspace_id == scope.workspace_id
    return isinstance(held, OrgRoleHeld | ProjectRoleHeld) and held.org_id == scope.org_id


def scope_oracle(actor: Account, target: Account) -> bool:
    """A system admin's scope is everything; the target's own system-admin flag is instance-level
    (design-doc §10.1: no workspace), so only a system admin's scope holds it."""
    if actor.is_system_admin:
        return True
    return any(_contains(scope, held) for scope in actor.memberships for held in target.memberships)


@given(actor=actors, target=targets)
def test_in_scope_agrees_with_the_documented_scope(actor: Account, target: Account) -> None:
    assert in_scope(actor, target) is scope_oracle(actor, target)


@given(actor=actors, target=targets)
def test_whoever_may_manage_a_target_with_memberships_has_it_in_scope(
    actor: Account, target: Account
) -> None:
    """The first half is part of the full rule: it never hides a target the actor may manage."""
    assert not can_manage_account(actor, target) or in_scope(actor, target)


# --- covering_orgs: the orgs an account action's events go to (DL-75) --------------------------

NO_ORG: frozenset[uuid.UUID] = frozenset()


@pytest.mark.parametrize(
    ("actor", "target"),
    [
        (SYSTEM_ADMIN, ORG_MEMBER),
        (SYSTEM_ADMIN, WS_OWNER),
        (SYSTEM_ADMIN, NO_MEMBERSHIPS),
        (WS_ADMIN, ORG_MEMBER),
        (WS_ADMIN, PROJECT_ONLY),
        (WS_ADMIN, NO_MEMBERSHIPS),
        (WS_OWNER, WS_ADMIN),
        (WS_OWNER, holding(org(OrgRole.MEMBER), org(OrgRole.MEMBER, ORG2))),
        # A workspace role that covers the target wins over the actor's org roles.
        (holding(ws(WorkspaceRole.ADMIN), org(OrgRole.ADMIN)), ORG_MEMBER),
        (holding(org(OrgRole.OWNER), system_admin=True), ORG_MEMBER),
    ],
)
def test_an_action_through_a_system_admin_or_workspace_role_goes_to_no_org(
    actor: Account, target: Account
) -> None:
    assert covering_orgs(actor, target) == NO_ORG


@pytest.mark.parametrize(
    ("actor", "target", "orgs"),
    [
        (ORG_ADMIN, ORG_MEMBER, {ORG}),
        (ORG_OWNER, holding(org(OrgRole.ADMIN)), {ORG}),
        (ORG_ADMIN, PROJECT_ONLY, {ORG}),
        (ORG2_OWNER, ORG2_MEMBER, {ORG2}),
        # Through the roles of several orgs: one event per covering org.
        (
            holding(org(OrgRole.ADMIN), org(OrgRole.ADMIN, ORG2)),
            holding(org(OrgRole.MEMBER), org(OrgRole.MEMBER, ORG2)),
            {ORG, ORG2},
        ),
        (
            holding(org(OrgRole.ADMIN), org(OrgRole.OWNER, ORG2)),
            holding(org(OrgRole.MEMBER), project(ORG2, ORG2_PROJECT)),
            {ORG, ORG2},
        ),
        # An org role that covers none of the target's memberships adds no event.
        (holding(org(OrgRole.ADMIN), org(OrgRole.ADMIN, ORG2)), ORG_MEMBER, {ORG}),
        # Staff with role member who are an org's admin (design-doc §4): the workspace role
        # grants no account actions, so it covers nothing; the org role does.
        (holding(ws(WorkspaceRole.MEMBER), org(OrgRole.ADMIN)), ORG_MEMBER, {ORG}),
    ],
)
def test_an_action_through_org_roles_goes_to_each_covering_org(
    actor: Account, target: Account, orgs: set[uuid.UUID]
) -> None:
    assert covering_orgs(actor, target) == frozenset(orgs)
