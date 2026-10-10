"""Orgs: creating one in a workspace, and reading and updating it (build plan, "The workspace
and org API", DL-55)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.authz.actions import Action
from app.core.db import SessionDep
from app.core.errors import ErrorBody
from app.routers.deps import AuthzContextDep, authorized, load_org, load_workspace
from app.schemas.org import OrgCreate, OrgRead, OrgUpdate
from app.schemas.workspace import SlugAvailability
from app.services.org import OrgEntity, OrgService
from app.services.workspace import WorkspaceEntity

router = APIRouter(tags=["org"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorBody}
    for code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    )
}

OrgCreatable = Annotated[WorkspaceEntity, Depends(authorized(load_workspace, Action.ORG_CREATE))]
Viewed = Annotated[OrgEntity, Depends(authorized(load_org, Action.ORG_VIEW))]
Updated = Annotated[OrgEntity, Depends(authorized(load_org, Action.ORG_UPDATE))]


@router.post(
    "/workspaces/{workspace_id}/orgs", status_code=status.HTTP_201_CREATED, responses=_ERRORS
)
async def create_org(
    workspace: OrgCreatable, body: OrgCreate, ctx: AuthzContextDep, session: SessionDep
) -> OrgRead:
    """Create an org and its first owner: `owner_id` (an existing user; 404 if none, 422
    `account_inactive` if deactivated) or `new_owner` (a new account)."""
    return await OrgService(session).create(ctx, workspace, body)


@router.get("/workspaces/{workspace_id}/org-slug-availability", responses=_ERRORS)
async def new_org_slug_availability(
    workspace: OrgCreatable, slug: str, session: SessionDep
) -> SlugAvailability:
    """Whether `slug` could be a new org's in the workspace."""
    return await OrgService(session).slug_availability(workspace.id, slug)


@router.get("/orgs/{org_id}", responses=_ERRORS)
async def get_org(org: Viewed, ctx: AuthzContextDep, session: SessionDep) -> OrgRead:
    """The org, with the actions the caller may take on it."""
    return OrgService(session).read(ctx, org)


@router.patch("/orgs/{org_id}", responses=_ERRORS)
async def update_org(
    org: Updated, body: OrgUpdate, ctx: AuthzContextDep, session: SessionDep
) -> OrgRead:
    """Rename the org or change its slug. 422 on `slug` when it's taken or invalid."""
    return await OrgService(session).update(ctx, org, body)


@router.get("/orgs/{org_id}/slug-availability", responses=_ERRORS)
async def org_slug_availability(org: Updated, slug: str, session: SessionDep) -> SlugAvailability:
    """Whether `slug` could be this org's (its own counts as available)."""
    return await OrgService(session).slug_availability(org.workspace_id, slug, org=org)
