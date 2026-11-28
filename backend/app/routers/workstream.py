"""Workstreams (design-doc §6, "Workstream"; build plan, S3-C4)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.authz.actions import Action
from app.core.db import SessionDep
from app.routers.deps import ERRORS, AuthzContextDep, authorized, load_project, load_workstream
from app.schemas.move import ItemMove
from app.schemas.workstream import (
    WorkstreamCreate,
    WorkstreamList,
    WorkstreamListQuery,
    WorkstreamRead,
    WorkstreamUpdate,
)
from app.services.project import ProjectEntity
from app.services.workstream import WorkstreamEntity, WorkstreamService

router = APIRouter(tags=["workstream"])

Creating = Annotated[ProjectEntity, Depends(authorized(load_project, Action.WORKSTREAM_MANAGE))]
Listed = Annotated[ProjectEntity, Depends(authorized(load_project, Action.WORKSTREAM_VIEW))]
Viewed = Annotated[WorkstreamEntity, Depends(authorized(load_workstream, Action.WORKSTREAM_VIEW))]
Managed = Annotated[
    WorkstreamEntity, Depends(authorized(load_workstream, Action.WORKSTREAM_MANAGE))
]


@router.post("/projects/{key}/workstreams", status_code=status.HTTP_201_CREATED, responses=ERRORS)
async def create_workstream(
    project: Creating, body: WorkstreamCreate, ctx: AuthzContextDep, session: SessionDep
) -> WorkstreamRead:
    """Create a workstream at the bottom of the project's. 422 on `name` (`missing`, `taken`)
    and on `lead_id` (`not_member`, `account_inactive`)."""
    return await WorkstreamService(session).create(ctx, project, body)


@router.get("/projects/{key}/workstreams", responses=ERRORS)
async def list_workstreams(
    project: Listed, query: Annotated[WorkstreamListQuery, Query()], session: SessionDep
) -> WorkstreamList:
    """The project's workstreams in rank order, archived ones only with `include_archived`:
    complete up to 2,000, with `truncated` above it."""
    return await WorkstreamService(session).list(project, include_archived=query.include_archived)


@router.get("/projects/{key}/workstreams/{workstream_id}", responses=ERRORS)
async def get_workstream(
    workstream: Viewed, ctx: AuthzContextDep, session: SessionDep
) -> WorkstreamRead:
    """The workstream, archived or not, with the actions the caller may take on it."""
    return await WorkstreamService(session).read(ctx, workstream)


@router.patch("/projects/{key}/workstreams/{workstream_id}", responses=ERRORS)
async def update_workstream(
    workstream: Managed, body: WorkstreamUpdate, ctx: AuthzContextDep, session: SessionDep
) -> WorkstreamRead:
    """Change the fields sent; null clears the description or the lead. 422 on `name`
    (`missing`, `taken`) and on a newly named `lead_id` (`not_member`, `account_inactive`)."""
    return await WorkstreamService(session).update(ctx, workstream, body)


@router.post("/projects/{key}/workstreams/{workstream_id}/move", responses=ERRORS)
async def move_workstream(
    workstream: Managed, body: ItemMove, ctx: AuthzContextDep, session: SessionDep
) -> WorkstreamRead:
    """Put the workstream just after `after_id` or just before `before_id`, or at the bottom.
    422 on `after_id` or `before_id` (`not_found`) and on both (`conflict`)."""
    return await WorkstreamService(session).move(ctx, workstream, body)


@router.post("/projects/{key}/workstreams/{workstream_id}/archive", responses=ERRORS)
async def archive_workstream(
    workstream: Managed, ctx: AuthzContextDep, session: SessionDep
) -> WorkstreamRead:
    """Hide the workstream from pickers; items keep it. Archiving it again changes nothing."""
    return await WorkstreamService(session).archive(ctx, workstream)


@router.post("/projects/{key}/workstreams/{workstream_id}/unarchive", responses=ERRORS)
async def unarchive_workstream(
    workstream: Managed, ctx: AuthzContextDep, session: SessionDep
) -> WorkstreamRead:
    """Offer the workstream in pickers again."""
    return await WorkstreamService(session).unarchive(ctx, workstream)
