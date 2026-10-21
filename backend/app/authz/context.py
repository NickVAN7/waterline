"""The authorization context (build plan, "Authorization (§5)"): who the user is to every
workspace, org, and project, loaded once per request and reused by every check, by
`allowed_actions`, and by list scoping."""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.enums import OrgRole, ProjectRole, WorkspaceRole
from app.rules.account_rank import (
    Account,
    Membership,
    OrgRoleHeld,
    ProjectRoleHeld,
    WorkspaceRoleHeld,
)


@dataclass(frozen=True)
class ProjectAccess:
    """A project membership, with the project's own org and workspace (from the project row,
    never assumed from the user's other memberships)."""

    role: ProjectRole
    organization_id: uuid.UUID
    workspace_id: uuid.UUID
    archived: bool = False


@dataclass(frozen=True)
class AuthzContext:
    user_id: uuid.UUID
    is_system_admin: bool = False
    workspace_roles: Mapping[uuid.UUID, WorkspaceRole] = field(
        default_factory=dict[uuid.UUID, WorkspaceRole]
    )
    org_roles: Mapping[uuid.UUID, OrgRole] = field(default_factory=dict[uuid.UUID, OrgRole])
    # Each org in `org_roles`, with its workspace (DL-68: `user.check`'s targeted rule).
    org_workspaces: Mapping[uuid.UUID, uuid.UUID] = field(
        default_factory=dict[uuid.UUID, uuid.UUID]
    )
    projects: Mapping[uuid.UUID, ProjectAccess] = field(
        default_factory=dict[uuid.UUID, ProjectAccess]
    )


def rank_account(ctx: AuthzContext) -> Account:
    """The user's memberships as the rank rule sees them (DL-73). An org whose workspace isn't
    loaded can't be placed, so it's left out (the loader always fills `org_workspaces`)."""
    memberships: list[Membership] = [
        *(WorkspaceRoleHeld(ws_id, role) for ws_id, role in ctx.workspace_roles.items()),
        *(
            OrgRoleHeld(ctx.org_workspaces[org_id], org_id, role)
            for org_id, role in ctx.org_roles.items()
            if org_id in ctx.org_workspaces
        ),
        *(
            ProjectRoleHeld(access.workspace_id, access.organization_id, project_id)
            for project_id, access in ctx.projects.items()
        ),
    ]
    return Account(is_system_admin=ctx.is_system_admin, memberships=tuple(memberships))
