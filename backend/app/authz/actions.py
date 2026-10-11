"""The action registry (design-doc §5, "The choke point"; build plan, "Authorization (§5)").

Every action `authorize()` knows is registered here; anything else is denied. `Action` lists the
real actions (exported as an OpenAPI enum, so the generated client types them); tests register
test-only actions in `REGISTRY` directly.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from app.authz.context import AuthzContext, rank_account
from app.authz.target import Target
from app.enums import OrgRole, ProjectRole, WorkspaceRole
from app.rules.account_rank import Account, can_manage_account


class Level(StrEnum):
    """Where an action's target sits."""

    WORKSPACE = "workspace"
    ORGANIZATION = "organization"
    PROJECT = "project"
    USER = "user"


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
    - `visible`: granted to anyone who can see the target (design-doc §4, "Visibility"), on top
      of the roles above: e.g. `org.view`, for a project member who has no org role.
    - `rule`: a targeted rule granting it on top of the roles above, from the whole context
      (e.g. `user.check`: an admin role anywhere in the target's workspace, DL-68).
    """

    level: Level
    workspace_role: WorkspaceRole | None = None
    org_role: OrgRole | None = None
    project_role: ProjectRole | None = None
    mutation: bool = True
    archive_exempt: bool = False
    relationship: Callable[[uuid.UUID, object], bool] | None = None
    visible: bool = False
    rule: Callable[[AuthzContext, Target], bool] | None = None


class Action(StrEnum):
    """The real actions (DL-44, DL-45, DL-56; each area adds its own)."""

    WORKSPACE_VIEW = "workspace.view"
    WORKSPACE_UPDATE = "workspace.update"
    WORKSPACE_STAFF_MANAGE = "workspace_staff.manage"
    WORKSPACE_STAFF_MANAGE_ADMINS = "workspace_staff.manage_admins"
    ORG_CREATE = "org.create"
    ORG_VIEW = "org.view"
    ORG_UPDATE = "org.update"
    ORG_MEMBER_MANAGE = "org_member.manage"
    ORG_MEMBER_MANAGE_ADMINS = "org_member.manage_admins"
    USER_CHECK = "user.check"
    USER_MANAGE = "user.manage"
    USER_VIEW_ACCESS = "user.view_access"
    PROJECT_CREATE = "project.create"
    PROJECT_ASSIGN_FIRST_ADMIN = "project.assign_first_admin"
    PROJECT_VIEW = "project.view"
    PROJECT_UPDATE = "project.update"
    PROJECT_ARCHIVE = "project.archive"
    PROJECT_UNARCHIVE = "project.unarchive"


# Workspace owners/admins, and system admins (DL-45).
_WORKSPACE_ADMINS = ActionSpec(Level.WORKSPACE, workspace_role=WorkspaceRole.ADMIN)


def _adds_people_in_workspace(ctx: AuthzContext, target: Target) -> bool:
    """`user.check`'s targeted rule (DL-68): an org owner/admin of an org in the target's
    workspace, or an explicit admin of one of its projects that isn't archived."""
    return any(
        role in (OrgRole.ADMIN, OrgRole.OWNER)
        and ctx.org_workspaces.get(org_id) == target.workspace_id
        for org_id, role in ctx.org_roles.items()
    ) or any(
        access.role is ProjectRole.ADMIN
        and access.workspace_id == target.workspace_id
        and not access.archived
        for access in ctx.projects.values()
    )


def _outranks(ctx: AuthzContext, target: Target) -> bool:
    """The rank rule (design-doc §4, "Account management"; DL-73) on a user target."""
    return isinstance(target.entity, Account) and can_manage_account(
        rank_account(ctx), target.entity
    )


def _self_or_outranks(ctx: AuthzContext, target: Target) -> bool:
    """The access review's targeted rule: the user themselves, or the rank rule (DL-73)."""
    return target.user_id == ctx.user_id or _outranks(ctx, target)


REGISTRY: dict[str, ActionSpec] = {
    Action.WORKSPACE_VIEW: ActionSpec(
        Level.WORKSPACE, workspace_role=WorkspaceRole.ADMIN, mutation=False
    ),
    Action.WORKSPACE_UPDATE: ActionSpec(Level.WORKSPACE, workspace_role=WorkspaceRole.OWNER),
    Action.WORKSPACE_STAFF_MANAGE: _WORKSPACE_ADMINS,
    Action.ORG_CREATE: _WORKSPACE_ADMINS,
    # Granting, changing, or removing an owner or admin role: workspace owners (DL-56).
    Action.WORKSPACE_STAFF_MANAGE_ADMINS: ActionSpec(
        Level.WORKSPACE, workspace_role=WorkspaceRole.OWNER
    ),
    # Anyone who sees the org, a project member with no org role included (DL-56).
    Action.ORG_VIEW: ActionSpec(Level.ORGANIZATION, mutation=False, visible=True),
    # Org owners, and workspace admins' "org owner capabilities in every org" (§5).
    Action.ORG_UPDATE: ActionSpec(
        Level.ORGANIZATION, workspace_role=WorkspaceRole.ADMIN, org_role=OrgRole.OWNER
    ),
    # Org owners/admins, and workspace admins as org owners in every org (§5; DL-68).
    Action.ORG_MEMBER_MANAGE: ActionSpec(
        Level.ORGANIZATION, workspace_role=WorkspaceRole.ADMIN, org_role=OrgRole.ADMIN
    ),
    # Granting, changing, or removing an org owner or admin role: org owners (DL-68).
    Action.ORG_MEMBER_MANAGE_ADMINS: ActionSpec(
        Level.ORGANIZATION, workspace_role=WorkspaceRole.ADMIN, org_role=OrgRole.OWNER
    ),
    # Whoever may add or create a person in the workspace (DL-66, DL-68).
    Action.USER_CHECK: ActionSpec(
        Level.WORKSPACE,
        workspace_role=WorkspaceRole.ADMIN,
        mutation=False,
        rule=_adds_people_in_workspace,
    ),
    # Every account action and the admin profile edit: the rank rule only (DL-73).
    Action.USER_MANAGE: ActionSpec(Level.USER, rule=_outranks),
    # The per-person access review: workspace admins, and the user or the rank rule (DL-73).
    Action.USER_VIEW_ACCESS: ActionSpec(
        Level.USER, workspace_role=WorkspaceRole.ADMIN, mutation=False, rule=_self_or_outranks
    ),
    # Any org member, and the admins above (§5 Org roles; DL-77).
    Action.PROJECT_CREATE: ActionSpec(
        Level.ORGANIZATION, workspace_role=WorkspaceRole.ADMIN, org_role=OrgRole.MEMBER
    ),
    # Naming someone else as a new project's first admin: org owners/admins and above (DL-77).
    Action.PROJECT_ASSIGN_FIRST_ADMIN: ActionSpec(
        Level.ORGANIZATION, workspace_role=WorkspaceRole.ADMIN, org_role=OrgRole.ADMIN
    ),
    # Project roles, and inherited project admin (§5; DL-77).
    Action.PROJECT_VIEW: ActionSpec(
        Level.PROJECT,
        workspace_role=WorkspaceRole.ADMIN,
        org_role=OrgRole.ADMIN,
        project_role=ProjectRole.VIEWER,
        mutation=False,
    ),
    Action.PROJECT_UPDATE: ActionSpec(
        Level.PROJECT,
        workspace_role=WorkspaceRole.ADMIN,
        org_role=OrgRole.ADMIN,
        project_role=ProjectRole.ADMIN,
    ),
    # The org's owners/admins and above, not a project admin by role alone (§5 Org roles).
    Action.PROJECT_ARCHIVE: ActionSpec(
        Level.PROJECT, workspace_role=WorkspaceRole.ADMIN, org_role=OrgRole.ADMIN
    ),
    Action.PROJECT_UNARCHIVE: ActionSpec(
        Level.PROJECT,
        workspace_role=WorkspaceRole.ADMIN,
        org_role=OrgRole.ADMIN,
        archive_exempt=True,
    ),
}
