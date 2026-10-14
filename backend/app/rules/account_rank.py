"""The rank rule for account actions (design-doc §4, "Account management"): deactivate,
reactivate, reset password, sign out everywhere, and changing another user's email, name, or
username. Pure: the caller loads both users' memberships and passes them in.

Allowed only when the target holds at least one membership in the actor's scope, and every
membership the target holds is covered by an owner/admin role of the actor (the same workspace,
org, or project, or one above it) at an equal or higher rank. The system-admin flag counts as a
membership at the top rank. A user with no memberships left is managed by workspace
owners/admins and system admins. Members and project roles grant no account actions.
"""

import uuid
from dataclasses import dataclass, field
from enum import IntEnum

from app.enums import OrgRole, WorkspaceRole


@dataclass(frozen=True)
class WorkspaceRoleHeld:
    workspace_id: uuid.UUID
    role: WorkspaceRole


@dataclass(frozen=True)
class OrgRoleHeld:
    workspace_id: uuid.UUID
    org_id: uuid.UUID
    role: OrgRole


@dataclass(frozen=True)
class ProjectRoleHeld:
    """Any project role: on its own, the lowest rank ("project-only user")."""

    workspace_id: uuid.UUID
    org_id: uuid.UUID
    project_id: uuid.UUID


type Membership = WorkspaceRoleHeld | OrgRoleHeld | ProjectRoleHeld


@dataclass(frozen=True)
class Account:
    is_system_admin: bool = False
    memberships: tuple[Membership, ...] = field(default=())


class Rank(IntEnum):
    """Highest last, so a higher rank compares greater."""

    PROJECT_ONLY = 1
    ORG_MEMBER = 2
    ORG_ADMIN = 3
    ORG_OWNER = 4
    WORKSPACE_MEMBER = 5
    WORKSPACE_ADMIN = 6
    WORKSPACE_OWNER = 7
    SYSTEM_ADMIN = 8


_WORKSPACE_RANKS = {
    WorkspaceRole.MEMBER: Rank.WORKSPACE_MEMBER,
    WorkspaceRole.ADMIN: Rank.WORKSPACE_ADMIN,
    WorkspaceRole.OWNER: Rank.WORKSPACE_OWNER,
}
_ORG_RANKS = {
    OrgRole.MEMBER: Rank.ORG_MEMBER,
    OrgRole.ADMIN: Rank.ORG_ADMIN,
    OrgRole.OWNER: Rank.ORG_OWNER,
}


@dataclass(frozen=True)
class _SystemAdmin:
    """The system-admin flag, as a membership at the top rank, scoped to everything."""


type _Held = Membership | _SystemAdmin


def _rank(held: _Held) -> Rank:
    # The cases cover every type in `_Held` (pyright checks), so the last can't fail to match.
    match held:
        case _SystemAdmin():
            return Rank.SYSTEM_ADMIN
        case WorkspaceRoleHeld(role=role):
            return _WORKSPACE_RANKS[role]
        case OrgRoleHeld(role=role):
            return _ORG_RANKS[role]
        case ProjectRoleHeld():  # pragma: no branch
            return Rank.PROJECT_ONLY


# The roles that grant account actions: a project role never does, so it can't be a scope.
type _AdminRole = _SystemAdmin | WorkspaceRoleHeld | OrgRoleHeld


def _contains(scope: _AdminRole, held: _Held) -> bool:
    """Whether `held` is inside the actor role `scope`'s workspace, org, or everything."""
    # The cases cover every type in `_AdminRole` (pyright checks): the last can't fail to match.
    match scope:
        case _SystemAdmin():
            return True
        case WorkspaceRoleHeld(workspace_id=workspace_id):
            return not isinstance(held, _SystemAdmin) and held.workspace_id == workspace_id
        case OrgRoleHeld(org_id=org_id):  # pragma: no branch
            return isinstance(held, OrgRoleHeld | ProjectRoleHeld) and held.org_id == org_id


def _held(account: Account) -> list[_Held]:
    flag: list[_Held] = [_SystemAdmin()] if account.is_system_admin else []
    return [*flag, *account.memberships]


def _admin_roles(account: Account) -> list[_AdminRole]:
    """The account's owner and admin roles (and the system-admin flag)."""
    return [
        held
        for held in _held(account)
        if not isinstance(held, ProjectRoleHeld)
        and _rank(held)
        in {
            Rank.SYSTEM_ADMIN,
            Rank.WORKSPACE_OWNER,
            Rank.WORKSPACE_ADMIN,
            Rank.ORG_OWNER,
            Rank.ORG_ADMIN,
        }
    ]


def can_manage_account(actor: Account, target: Account) -> bool:
    """Whether `actor` may take an account action on `target` under the rank rule. It doesn't
    exclude `actor == target`: actions on oneself (and the last-owner and last-system-admin
    guards) are the caller's to refuse."""
    admin_roles = _admin_roles(actor)
    target_held = _held(target)
    if not target_held:
        # No memberships left: workspace owners/admins and system admins manage the user. Such
        # a user belongs to no workspace, so any workspace's owners/admins qualify: fine with
        # v1's one workspace; a second workspace would need a rule (design-doc §4, "One
        # workspace").
        return any(_rank(role) >= Rank.WORKSPACE_ADMIN for role in admin_roles)
    return all(
        any(_contains(role, held) and _rank(role) >= _rank(held) for role in admin_roles)
        for held in target_held
    )


def in_scope(actor: Account, target: Account) -> bool:
    """Whether `target` holds at least one membership in `actor`'s scope: the rank rule's first
    half, which decides whether the actor sees the target at all (a 404 otherwise, DL-72). The
    target's system-admin flag is in a system admin's scope only."""
    return any(_contains(role, held) for role in _admin_roles(actor) for held in _held(target))


def covering_orgs(actor: Account, target: Account) -> frozenset[uuid.UUID]:
    """The orgs an account action's audit events go to (DL-75): empty when a system-admin or
    workspace role of `actor` covers `target`; otherwise each org whose owner/admin role of
    `actor` covers one of `target`'s memberships."""
    above_orgs = Account(
        is_system_admin=actor.is_system_admin,
        memberships=tuple(m for m in actor.memberships if isinstance(m, WorkspaceRoleHeld)),
    )
    if can_manage_account(above_orgs, target):
        return frozenset()
    return frozenset(
        role.org_id
        for role in _admin_roles(actor)
        if isinstance(role, OrgRoleHeld) and any(_contains(role, held) for held in _held(target))
    )
