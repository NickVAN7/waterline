"""Account actions follow rank (design-doc §4, "Account management"): deactivate, reactivate,
reset password, sign out everywhere, and changing another user's email, name, or username.

Allowed only when the target holds at least one membership in the actor's scope, and every
membership the target holds is covered by an owner/admin role of the actor (the same workspace,
org, or project, or one above it) at an equal or higher rank. Ranks, highest first: system
admin > workspace owner > workspace admin > workspace member > org owner > org admin > org
member > project-only user. A user with no memberships left is managed by the workspace's
owners/admins and system admins. Members and project roles grant no account actions.
"""

import uuid

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from app.enums import OrgRole, WorkspaceRole
from app.rules.account_rank import (
    Account,
    Membership,
    OrgRoleHeld,
    ProjectRoleHeld,
    WorkspaceRoleHeld,
    can_manage_account,
)

# Account takeover is what this rule prevents (testing-strategy.md, Security).
pytestmark = pytest.mark.security

# One workspace with two client orgs, each with a project; and a second workspace.
WS = uuid.UUID(int=1)
OTHER_WS = uuid.UUID(int=2)
ORG = uuid.UUID(int=10)
OTHER_ORG = uuid.UUID(int=11)
FAR_ORG = uuid.UUID(int=12)  # in OTHER_WS
PROJECT = uuid.UUID(int=100)
OTHER_ORG_PROJECT = uuid.UUID(int=101)


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
PROJECT_ONLY = holding(project())
NO_MEMBERSHIPS = holding()


@pytest.mark.parametrize(
    ("actor", "target", "allowed"),
    [
        # System admin: the top rank, everywhere.
        (SYSTEM_ADMIN, WS_OWNER, True),
        (SYSTEM_ADMIN, holding(system_admin=True), True),  # equal rank
        (SYSTEM_ADMIN, holding(ws(WorkspaceRole.OWNER, OTHER_WS)), True),
        (SYSTEM_ADMIN, NO_MEMBERSHIPS, True),
        # Workspace owner.
        (WS_OWNER, WS_OWNER, True),  # equal rank
        (WS_OWNER, WS_ADMIN, True),
        (WS_OWNER, ORG_OWNER, True),
        (WS_OWNER, PROJECT_ONLY, True),
        (WS_OWNER, holding(system_admin=True), False),
        (WS_OWNER, holding(ws(WorkspaceRole.MEMBER), system_admin=True), False),
        (WS_OWNER, holding(ws(WorkspaceRole.MEMBER, OTHER_WS)), False),
        (WS_OWNER, NO_MEMBERSHIPS, True),
        # Workspace admin: can't manage the workspace owner or a system admin.
        (WS_ADMIN, WS_ADMIN, True),
        (WS_ADMIN, WS_MEMBER, True),
        (WS_ADMIN, ORG_OWNER, True),
        (WS_ADMIN, holding(org(OrgRole.MEMBER, FAR_ORG, OTHER_WS)), False),
        (WS_ADMIN, WS_OWNER, False),
        (WS_ADMIN, holding(system_admin=True), False),
        (WS_ADMIN, NO_MEMBERSHIPS, True),
        # Workspace member: no account actions.
        (WS_MEMBER, WS_MEMBER, False),
        (WS_MEMBER, PROJECT_ONLY, False),
        (WS_MEMBER, NO_MEMBERSHIPS, False),
        # Org owner.
        (ORG_OWNER, ORG_OWNER, True),
        (ORG_OWNER, ORG_ADMIN, True),
        (ORG_OWNER, ORG_MEMBER, True),
        (ORG_OWNER, WS_MEMBER, False),
        (ORG_OWNER, NO_MEMBERSHIPS, False),
        # Org admin: their own org's admins, members, and project-only users on its projects.
        (ORG_ADMIN, ORG_ADMIN, True),
        (ORG_ADMIN, ORG_MEMBER, True),
        (ORG_ADMIN, PROJECT_ONLY, True),
        (ORG_ADMIN, holding(org(OrgRole.MEMBER), project()), True),
        (ORG_ADMIN, ORG_OWNER, False),
        (ORG_ADMIN, WS_MEMBER, False),  # staff outrank org roles
        (ORG_ADMIN, holding(org(OrgRole.MEMBER, OTHER_ORG)), False),  # another org
        (ORG_ADMIN, holding(project(OTHER_ORG, OTHER_ORG_PROJECT)), False),  # its project
        # In the org, but also elsewhere: every membership must be covered.
        (ORG_ADMIN, holding(org(OrgRole.MEMBER), org(OrgRole.MEMBER, OTHER_ORG)), False),
        (ORG_ADMIN, holding(org(OrgRole.MEMBER), project(OTHER_ORG, OTHER_ORG_PROJECT)), False),
        (ORG_ADMIN, holding(org(OrgRole.MEMBER), ws(WorkspaceRole.MEMBER)), False),
        (ORG_ADMIN, holding(org(OrgRole.MEMBER), system_admin=True), False),
        (ORG_ADMIN, NO_MEMBERSHIPS, False),
        # Org member and project-only users: no account actions.
        (ORG_MEMBER, ORG_MEMBER, False),
        (ORG_MEMBER, PROJECT_ONLY, False),
        (PROJECT_ONLY, PROJECT_ONLY, False),
        (NO_MEMBERSHIPS, NO_MEMBERSHIPS, False),
        # Several roles: any admin role that covers each membership is enough.
        (
            holding(org(OrgRole.ADMIN), org(OrgRole.ADMIN, OTHER_ORG)),
            holding(org(OrgRole.MEMBER), org(OrgRole.MEMBER, OTHER_ORG)),
            True,
        ),
        (
            holding(org(OrgRole.ADMIN), org(OrgRole.MEMBER, OTHER_ORG)),
            holding(org(OrgRole.MEMBER), org(OrgRole.MEMBER, OTHER_ORG)),
            False,
        ),
        # Another workspace's roles don't reach this one.
        (holding(ws(WorkspaceRole.OWNER, OTHER_WS)), WS_MEMBER, False),
        (holding(org(OrgRole.OWNER, FAR_ORG, OTHER_WS)), PROJECT_ONLY, False),
    ],
)
def test_account_actions_follow_rank(actor: Account, target: Account, allowed: bool) -> None:
    assert can_manage_account(actor, target) is allowed


# --- Properties over any accounts in one workspace -----------------------------------------------

_memberships = st.one_of(
    st.builds(ws, st.sampled_from(WorkspaceRole)),
    st.builds(org, st.sampled_from(OrgRole), st.sampled_from([ORG, OTHER_ORG])),
    st.builds(
        project,
        st.sampled_from([ORG, OTHER_ORG]),
        st.sampled_from([PROJECT, OTHER_ORG_PROJECT]),
    ),
)
_accounts = st.builds(
    Account,
    is_system_admin=st.booleans(),
    memberships=st.lists(_memberships, max_size=4).map(tuple),
)


@given(_accounts)
def test_a_system_admin_can_manage_anyone(target: Account) -> None:
    assert can_manage_account(SYSTEM_ADMIN, target)


_member_roles_only = st.builds(
    Account,
    is_system_admin=st.just(False),
    memberships=st.lists(
        st.one_of(
            st.just(ws(WorkspaceRole.MEMBER)),
            st.builds(org, st.just(OrgRole.MEMBER), st.sampled_from([ORG, OTHER_ORG])),
            st.builds(project, st.sampled_from([ORG, OTHER_ORG])),
        ),
        max_size=4,
    ).map(tuple),
)


@given(_member_roles_only, _accounts)
def test_member_and_project_roles_grant_no_account_actions(actor: Account, target: Account) -> None:
    assert not can_manage_account(actor, target)


@given(_accounts)
def test_only_a_system_admin_can_manage_a_system_admin(actor: Account) -> None:
    target = holding(system_admin=True)
    assert can_manage_account(actor, target) is actor.is_system_admin


@given(_accounts, _accounts, _memberships)
def test_another_membership_never_makes_a_target_easier_to_manage(
    actor: Account, target: Account, extra: Membership
) -> None:
    # Adding a membership can only add something the actor must cover.
    widened = Account(target.is_system_admin, (*target.memberships, extra))
    assume(target.memberships and can_manage_account(actor, widened))

    assert can_manage_account(actor, target)
