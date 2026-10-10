"""`authorize()` (design-doc §5, "The choke point"): every check goes through it, and it fails
closed. Pure: it decides from the request's `AuthzContext` and the `Target`, never the database."""

from enum import StrEnum

from app.authz.actions import REGISTRY, Action, Level
from app.authz.context import AuthzContext
from app.authz.target import Target
from app.core.errors import ForbiddenError, NotFoundError
from app.enums import OrgRole, ProjectRole, WorkspaceRole

# Each level's roles, lowest first: a role grants what every role below it does.
_RANKS: dict[type[StrEnum], list[StrEnum]] = {
    WorkspaceRole: [WorkspaceRole.MEMBER, WorkspaceRole.ADMIN, WorkspaceRole.OWNER],
    OrgRole: [OrgRole.MEMBER, OrgRole.ADMIN, OrgRole.OWNER],
    ProjectRole: [ProjectRole.VIEWER, ProjectRole.MEMBER, ProjectRole.ADMIN],
}
_ADMINS = (WorkspaceRole.ADMIN, WorkspaceRole.OWNER, OrgRole.ADMIN, OrgRole.OWNER)


def _at_least[R: StrEnum](held: R | None, needed: R | None) -> bool:
    if held is None or needed is None:
        return False
    rank = _RANKS[type(needed)]
    return rank.index(held) >= rank.index(needed)


def _inherits_project_admin(ctx: AuthzContext, target: Target) -> bool:
    """System admins, the workspace's owners/admins, and the project's org's owners/admins
    (design-doc §4, "Tenancy")."""
    return (
        ctx.is_system_admin
        or ctx.workspace_roles.get(target.workspace_id) in _ADMINS
        or (
            target.organization_id is not None
            and ctx.org_roles.get(target.organization_id) in _ADMINS
        )
    )


def _project_access(ctx: AuthzContext, target: Target) -> bool:
    """Any project membership, or inherited project admin."""
    return target.project_id in ctx.projects or _inherits_project_admin(ctx, target)


def authorize(ctx: AuthzContext, action: str, target: Target) -> bool:
    """Whether the user may take `action` on `target`, in design-doc §5's order (the archived
    project; personal actions; system admin; workspace role; org role; project role). An action
    not in the registry is denied."""
    spec = REGISTRY.get(action)
    if spec is None:
        return False
    if target.archived and spec.mutation and not spec.archive_exempt:
        return False
    if spec.relationship is not None:
        # Only the relationship grants a personal action, and only with access to the project.
        return spec.relationship(ctx.user_id, target.entity) and _project_access(ctx, target)
    if spec.visible and can_see(ctx, target):
        return True
    # A None ID (a target above that level) finds nothing: no membership is keyed by None.
    project = ctx.projects.get(target.project_id)  # pyright: ignore[reportArgumentType] -- None finds nothing
    org_role = ctx.org_roles.get(target.organization_id)  # pyright: ignore[reportArgumentType] -- None finds nothing
    return (
        ctx.is_system_admin
        or _at_least(ctx.workspace_roles.get(target.workspace_id), spec.workspace_role)
        or _at_least(org_role, spec.org_role)
        or _at_least(project.role if project else None, spec.project_role)
    )


def can_see(ctx: AuthzContext, target: Target) -> bool:
    """Whether the target exists for this user (design-doc §4, "Visibility"); one they can't see
    is a 404, never a 403."""
    if target.project_id is not None:
        return _project_access(ctx, target)
    if target.organization_id is not None:
        return (
            _inherits_project_admin(ctx, target)
            or target.organization_id in ctx.org_roles
            or any(p.organization_id == target.organization_id for p in ctx.projects.values())
        )
    # The workspace pages: its owners/admins and system admins only.
    return _inherits_project_admin(ctx, target)


def ensure(ctx: AuthzContext, action: str, target: Target) -> None:
    """Raise unless `authorize()` allows it: `NotFoundError` (404) when the user can't see the
    target, `ForbiddenError` (403) when they can see it but may not do this."""
    if authorize(ctx, action, target):
        return
    if not can_see(ctx, target):
        raise NotFoundError
    raise ForbiddenError


def _level(target: Target) -> Level:
    if target.project_id is not None:
        return Level.PROJECT
    if target.organization_id is not None:
        return Level.ORGANIZATION
    return Level.WORKSPACE


def allowed_actions(ctx: AuthzContext, target: Target) -> list[Action]:
    """The real actions (`Action`) at the target's level that `authorize()` allows, sorted by
    name: the `allowed_actions` of a single-entity read (build plan, "API conventions")."""
    level = _level(target)
    return sorted(
        action
        for action in Action
        if REGISTRY[action].level is level and authorize(ctx, action, target)
    )


def module_enabled(target: Target, module: str) -> bool:
    """Whether the target's project has `module` enabled; a request to a disabled module is a
    404, before `authorize()` (design-doc §5, "Module gating")."""
    return module in target.enabled_modules
