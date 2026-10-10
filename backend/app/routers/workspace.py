"""The workspace and its staff (build plan, "The workspace and org API", DL-55)."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app.authz.actions import Action
from app.core.db import SessionDep
from app.core.errors import ErrorBody
from app.core.lists import Page
from app.routers.deps import AuthzContextDep, authorized, load_workspace
from app.schemas.org import OrgListItem
from app.schemas.workspace import (
    SlugAvailability,
    StaffAdd,
    StaffCreate,
    StaffRead,
    StaffRoleUpdate,
    WorkspaceRead,
    WorkspaceUpdate,
)
from app.services.workspace import ORGS, STAFF, WorkspaceEntity, WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["workspace"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorBody}
    for code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    )
}

Viewed = Annotated[WorkspaceEntity, Depends(authorized(load_workspace, Action.WORKSPACE_VIEW))]
Updated = Annotated[WorkspaceEntity, Depends(authorized(load_workspace, Action.WORKSPACE_UPDATE))]
StaffManaged = Annotated[
    WorkspaceEntity, Depends(authorized(load_workspace, Action.WORKSPACE_STAFF_MANAGE))
]
StaffQuery = Annotated[STAFF.query_model, Query()]  # pyright: ignore[reportInvalidTypeForm]
OrgQuery = Annotated[ORGS.query_model, Query()]  # pyright: ignore[reportInvalidTypeForm]


@router.get("/{workspace_id}", responses=_ERRORS)
async def get_workspace(
    workspace: Viewed, ctx: AuthzContextDep, session: SessionDep
) -> WorkspaceRead:
    """The workspace, with the actions the caller may take on it."""
    return WorkspaceService(session).read(ctx, workspace)


@router.patch("/{workspace_id}", responses=_ERRORS)
async def update_workspace(
    workspace: Updated, body: WorkspaceUpdate, ctx: AuthzContextDep, session: SessionDep
) -> WorkspaceRead:
    """Rename the workspace or change its slug. 422 on `slug` when it's taken or invalid."""
    return await WorkspaceService(session).update(ctx, workspace, body)


@router.get("/{workspace_id}/slug-availability", responses=_ERRORS)
async def workspace_slug_availability(
    workspace: Updated, slug: str, session: SessionDep
) -> SlugAvailability:
    """Whether `slug` could be the workspace's (its own counts as available)."""
    return await WorkspaceService(session).slug_availability(workspace, slug)


@router.get("/{workspace_id}/staff", responses=_ERRORS)
async def list_staff(
    workspace: Viewed, query: StaffQuery, ctx: AuthzContextDep, session: SessionDep
) -> Page[StaffRead]:
    """The workspace's staff, each row with the actions the caller may take on it."""
    return await WorkspaceService(session).list_staff(ctx, workspace, query)


@router.post("/{workspace_id}/staff", status_code=status.HTTP_201_CREATED, responses=_ERRORS)
async def add_staff(
    workspace: StaffManaged, body: StaffAdd, ctx: AuthzContextDep, session: SessionDep
) -> StaffRead:
    """Add an existing account by email. 422 on `email`: `already_member`, `no_account`, or
    `account_inactive`; 403 for an owner or admin role without `workspace_staff.manage_admins`."""
    return await WorkspaceService(session).add_staff(ctx, workspace, body.email, body.role)


@router.post("/{workspace_id}/staff/new", status_code=status.HTTP_201_CREATED, responses=_ERRORS)
async def create_staff(
    workspace: StaffManaged, body: StaffCreate, ctx: AuthzContextDep, session: SessionDep
) -> StaffRead:
    """Create the account and its staff membership in one step; the user must change the
    temporary password at their first sign-in."""
    return await WorkspaceService(session).create_staff(ctx, workspace, body)


@router.patch("/{workspace_id}/staff/{user_id}", responses=_ERRORS)
async def change_staff_role(
    workspace: StaffManaged,
    user_id: uuid.UUID,
    body: StaffRoleUpdate,
    ctx: AuthzContextDep,
    session: SessionDep,
) -> StaffRead:
    """Change a staff member's role. 422 `last_owner` on `role` for the last owner, unless
    `new_owner_id` names a replacement; 422 on `new_owner_id`: `not_owner`, `same_user`,
    `not_member`, or `account_inactive`."""
    return await WorkspaceService(session).change_staff_role(
        ctx, workspace, user_id, body.role, new_owner_id=body.new_owner_id
    )


@router.delete(
    "/{workspace_id}/staff/{user_id}", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS
)
async def remove_staff(
    workspace: StaffManaged,
    user_id: uuid.UUID,
    ctx: AuthzContextDep,
    session: SessionDep,
    with_projects: bool = True,
    new_owner_id: uuid.UUID | None = None,
) -> None:
    """Remove a staff member, by default with their project memberships in the workspace.
    422 `last_owner` on `user_id` for the last owner, unless `new_owner_id` names a
    replacement (the same 422s on it as a role change)."""
    await WorkspaceService(session).remove_staff(
        ctx, workspace, user_id, with_projects=with_projects, new_owner_id=new_owner_id
    )


@router.get("/{workspace_id}/orgs", responses=_ERRORS)
async def list_orgs(workspace: Viewed, query: OrgQuery, session: SessionDep) -> Page[OrgListItem]:
    """The workspace's orgs."""
    return await WorkspaceService(session).list_orgs(workspace, query)
