"""The action registry (design-doc §5, "The choke point"; build plan, "Authorization (§5)").

Every action `authorize()` knows is registered here; anything else is denied. `Action` lists the
real actions (exported as an OpenAPI enum, so the generated client types them); tests register
test-only actions in `REGISTRY` directly.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from app.enums import OrgRole, ProjectRole, WorkspaceRole


class Level(StrEnum):
    """Where an action's target sits."""

    WORKSPACE = "workspace"
    ORGANIZATION = "organization"
    PROJECT = "project"


@dataclass(frozen=True)
class ActionSpec:
    """How an action is granted.

    - `level`: where its target sits.
    - `workspace_role`, `org_role`, `project_role`: the lowest role at that level that grants it,
      in the target's workspace, org, and project (roles above it grant it too: owner > admin >
      member; admin > member > viewer). None: no role at that level grants it. System admins are
      granted every action but a personal one.
    - `mutation`: it changes something (an archived project denies mutations on or inside it).
    - `archive_exempt`: a mutation still allowed inside an archived project (unarchive; removing
      a member with their projects).
    - `relationship`: set only for a personal action: `relationship(user_id, target.entity)`
      says whether the user has the relationship that grants it; no role does.
    """

    level: Level
    workspace_role: WorkspaceRole | None = None
    org_role: OrgRole | None = None
    project_role: ProjectRole | None = None
    mutation: bool = True
    archive_exempt: bool = False
    relationship: Callable[[uuid.UUID, object], bool] | None = None


class Action(StrEnum):
    """The real actions (DL-44, DL-45: the workspace-level ones; each area adds its own)."""

    WORKSPACE_VIEW = "workspace.view"
    WORKSPACE_UPDATE = "workspace.update"
    WORKSPACE_STAFF_MANAGE = "workspace_staff.manage"
    ORG_CREATE = "org.create"


# Workspace owners/admins, and system admins (DL-45).
_WORKSPACE_ADMINS = ActionSpec(Level.WORKSPACE, workspace_role=WorkspaceRole.ADMIN)

REGISTRY: dict[str, ActionSpec] = {
    Action.WORKSPACE_VIEW: ActionSpec(
        Level.WORKSPACE, workspace_role=WorkspaceRole.ADMIN, mutation=False
    ),
    Action.WORKSPACE_UPDATE: ActionSpec(Level.WORKSPACE, workspace_role=WorkspaceRole.OWNER),
    Action.WORKSPACE_STAFF_MANAGE: _WORKSPACE_ADMINS,
    Action.ORG_CREATE: _WORKSPACE_ADMINS,
}
