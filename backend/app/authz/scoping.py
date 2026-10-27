"""Access scoping for lists (design-doc §5, "Reads are authorized too"; §4, "Visibility"): a list
can't check row by row, so its query is limited to what the user can see. Pure: these say which
rows, by ID; the repository turns that into its `WHERE`."""

import uuid
from dataclasses import dataclass, field, replace

from app.authz.context import AuthzContext
from app.enums import OrgRole, WorkspaceRole

_WORKSPACE_ADMINS = (WorkspaceRole.ADMIN, WorkspaceRole.OWNER)
_ORG_ADMINS = (OrgRole.ADMIN, OrgRole.OWNER)


@dataclass(frozen=True)
class Scope:
    """Rows the user can see: every row (`everything`), or those whose own ID is in `ids`, or
    whose org is in `organization_ids`, or whose workspace is in `workspace_ids`.

    `content` (a content scope, design-doc §3.1): only `ids` reach an export-controlled project;
    a row reached through `everything`, an org, or a workspace (inherited admin) must not be in
    one."""

    everything: bool = False
    ids: frozenset[uuid.UUID] = field(default_factory=frozenset[uuid.UUID])
    organization_ids: frozenset[uuid.UUID] = field(default_factory=frozenset[uuid.UUID])
    workspace_ids: frozenset[uuid.UUID] = field(default_factory=frozenset[uuid.UUID])
    content: bool = False


def _admin_workspaces(ctx: AuthzContext) -> frozenset[uuid.UUID]:
    return frozenset(ws for ws, role in ctx.workspace_roles.items() if role in _WORKSPACE_ADMINS)


def project_scope(ctx: AuthzContext) -> Scope:
    """The projects the user can see (`ids` are project IDs): their project memberships, and every
    project of an org or workspace they own or administer (inherited project admin)."""
    if ctx.is_system_admin:
        return Scope(everything=True)
    return Scope(
        ids=frozenset(ctx.projects),
        organization_ids=frozenset(
            org for org, role in ctx.org_roles.items() if role in _ORG_ADMINS
        ),
        workspace_ids=_admin_workspaces(ctx),
    )


def content_scope(ctx: AuthzContext) -> Scope:
    """The projects whose content the user can see (`ids` are project IDs): `project_scope`, as a
    content scope, so an export-controlled project needs an explicit membership (design-doc §3.1;
    the export-control gate for lists)."""
    return replace(project_scope(ctx), ids=frozenset(ctx.projects), content=True)


def org_scope(ctx: AuthzContext) -> Scope:
    """The orgs the user can see (`ids` are org IDs; `organization_ids` is unused): their org
    memberships, the orgs of their projects, and every org of a workspace they own or
    administer."""
    if ctx.is_system_admin:
        return Scope(everything=True)
    return Scope(
        ids=frozenset(ctx.org_roles) | {p.organization_id for p in ctx.projects.values()},
        workspace_ids=_admin_workspaces(ctx),
    )
