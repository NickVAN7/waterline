"""The authorization context (build plan, "Authorization (§5)"): who the user is to every
workspace, org, and project, loaded once per request and reused by every check, by
`allowed_actions`, and by list scoping."""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.enums import OrgRole, ProjectRole, WorkspaceRole


@dataclass(frozen=True)
class ProjectAccess:
    """A project membership, with the project's own org and workspace (from the project row,
    never assumed from the user's other memberships)."""

    role: ProjectRole
    organization_id: uuid.UUID
    workspace_id: uuid.UUID


@dataclass(frozen=True)
class AuthzContext:
    user_id: uuid.UUID
    is_system_admin: bool = False
    workspace_roles: Mapping[uuid.UUID, WorkspaceRole] = field(
        default_factory=dict[uuid.UUID, WorkspaceRole]
    )
    org_roles: Mapping[uuid.UUID, OrgRole] = field(default_factory=dict[uuid.UUID, OrgRole])
    projects: Mapping[uuid.UUID, ProjectAccess] = field(
        default_factory=dict[uuid.UUID, ProjectAccess]
    )
