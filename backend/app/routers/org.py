"""Orgs: creating one in a workspace, and reading and updating it (build plan, "The workspace
and org API", DL-55)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.authz.actions import Action
from app.core.db import SessionDep
from app.core.lists import Page
from app.routers.deps import ERRORS, AuthzContextDep, authorized, load_org, load_workspace
from app.schemas.org import (
    MemberAdd,
    MemberCreate,
    MemberRead,
    MemberRoleUpdate,
    OrgCreate,
    OrgRead,
    OrgUpdate,
)
from app.schemas.workspace import SlugAvailability
from app.services.org import MEMBERS, OrgEntity, OrgService
from app.services.workspace import WorkspaceEntity

router = APIRouter(tags=["org"])

OrgCreatable = Annotated[WorkspaceEntity, Depends(authorized(load_workspace, Action.ORG_CREATE))]
Viewed = Annotated[OrgEntity, Depends(authorized(load_org, Action.ORG_VIEW))]
Updated = Annotated[OrgEntity, Depends(authorized(load_org, Action.ORG_UPDATE))]
MembersManaged = Annotated[OrgEntity, Depends(authorized(load_org, Action.ORG_MEMBER_MANAGE))]
MemberQuery = Annotated[MEMBERS.query_model, Query()]  # pyright: ignore[reportInvalidTypeForm]


@router.post(
    "/workspaces/{workspace_id}/orgs", status_code=status.HTTP_201_CREATED, responses=ERRORS
)
async def create_org(
    workspace: OrgCreatable, body: OrgCreate, ctx: AuthzContextDep, session: SessionDep
) -> OrgRead:
    """Create an org and its first owner: `owner_id` (an existing user; 404 if none, 422
    `account_inactive` if deactivated) or `new_owner` (a new account)."""
    return await OrgService(session).create(ctx, workspace, body)


@router.get("/workspaces/{workspace_id}/org-slug-availability", responses=ERRORS)
async def new_org_slug_availability(
    workspace: OrgCreatable, slug: str, session: SessionDep
) -> SlugAvailability:
    """Whether `slug` could be a new org's in the workspace."""
    return await OrgService(session).slug_availability(workspace.id, slug)


@router.get("/orgs/{org_id}", responses=ERRORS)
async def get_org(org: Viewed, ctx: AuthzContextDep, session: SessionDep) -> OrgRead:
    """The org, with the actions the caller may take on it."""
    return OrgService(session).read(ctx, org)


@router.patch("/orgs/{org_id}", responses=ERRORS)
async def update_org(
    org: Updated, body: OrgUpdate, ctx: AuthzContextDep, session: SessionDep
) -> OrgRead:
    """Rename the org or change its slug. 422 on `slug` when it's taken or invalid."""
    return await OrgService(session).update(ctx, org, body)


@router.get("/orgs/{org_id}/slug-availability", responses=ERRORS)
async def org_slug_availability(org: Updated, slug: str, session: SessionDep) -> SlugAvailability:
    """Whether `slug` could be this org's (its own counts as available)."""
    return await OrgService(session).slug_availability(org.workspace_id, slug, org=org)


@router.get("/orgs/{org_id}/members", responses=ERRORS)
async def list_members(
    org: MembersManaged, query: MemberQuery, ctx: AuthzContextDep, session: SessionDep
) -> Page[MemberRead]:
    """The org's members, each row with the actions the caller may take on it."""
    return await OrgService(session).list_members(ctx, org, query)


@router.post("/orgs/{org_id}/members", status_code=status.HTTP_201_CREATED, responses=ERRORS)
async def add_member(
    org: MembersManaged, body: MemberAdd, ctx: AuthzContextDep, session: SessionDep
) -> MemberRead:
    """Add an existing account by email. 422 on `email`: `already_member`, `no_account`, or
    `account_inactive`; 403 for an owner or admin role without `org_member.manage_admins`."""
    return await OrgService(session).add_member(ctx, org, body.email, body.role)


@router.post("/orgs/{org_id}/members/new", status_code=status.HTTP_201_CREATED, responses=ERRORS)
async def create_member(
    org: MembersManaged, body: MemberCreate, ctx: AuthzContextDep, session: SessionDep
) -> MemberRead:
    """Create the account and its membership in one step; the user must change the temporary
    password at their first sign-in."""
    return await OrgService(session).create_member(ctx, org, body)


@router.patch("/orgs/{org_id}/members/{user_id}", responses=ERRORS)
async def change_member_role(
    org: MembersManaged,
    user_id: uuid.UUID,
    body: MemberRoleUpdate,
    ctx: AuthzContextDep,
    session: SessionDep,
) -> MemberRead:
    """Change a member's role. 422 `last_owner` on `role` for the last owner, unless
    `new_owner_id` names a replacement; 422 on `new_owner_id`: `not_owner`, `same_user`,
    `not_member`, or `account_inactive`."""
    return await OrgService(session).change_member_role(ctx, org, user_id, body)


@router.delete(
    "/orgs/{org_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS
)
async def remove_member(
    org: MembersManaged,
    user_id: uuid.UUID,
    ctx: AuthzContextDep,
    session: SessionDep,
    with_projects: bool = True,
    new_owner_id: uuid.UUID | None = None,
) -> None:
    """Remove a member, by default with their project memberships in the org. 422 `last_owner`
    on `user_id` for the last owner, unless `new_owner_id` names a replacement (the same 422s on
    it as a role change)."""
    await OrgService(session).remove_member(
        ctx, org, user_id, with_projects=with_projects, new_owner_id=new_owner_id
    )
