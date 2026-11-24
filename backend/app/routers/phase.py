"""Phases (design-doc §6, "Phase"; build plan, S3-C3)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.authz.actions import Action
from app.core.db import SessionDep
from app.routers.deps import ERRORS, AuthzContextDep, authorized, load_phase, load_project
from app.schemas.move import ItemMove
from app.schemas.phase import PhaseCreate, PhaseList, PhaseRead, PhaseUpdate
from app.services.phase import PhaseEntity, PhaseService
from app.services.project import ProjectEntity

router = APIRouter(tags=["phase"])

Creating = Annotated[ProjectEntity, Depends(authorized(load_project, Action.PHASE_MANAGE))]
Listed = Annotated[ProjectEntity, Depends(authorized(load_project, Action.PHASE_VIEW))]
Viewed = Annotated[PhaseEntity, Depends(authorized(load_phase, Action.PHASE_VIEW))]
Managed = Annotated[PhaseEntity, Depends(authorized(load_phase, Action.PHASE_MANAGE))]


@router.post("/projects/{key}/phases", status_code=status.HTTP_201_CREATED, responses=ERRORS)
async def create_phase(
    project: Creating, body: PhaseCreate, ctx: AuthzContextDep, session: SessionDep
) -> PhaseRead:
    """Create a phase at the bottom of the project's phases. 422 on `name` (`missing`, `taken`)
    and on `end_date` (`before_start`)."""
    return await PhaseService(session).create(ctx, project, body)


@router.get("/projects/{key}/phases", responses=ERRORS)
async def list_phases(project: Listed, session: SessionDep) -> PhaseList:
    """The project's phases in rank order: complete up to 2,000, with `truncated` above it."""
    return await PhaseService(session).list(project)


@router.get("/projects/{key}/phases/{phase_id}", responses=ERRORS)
async def get_phase(phase: Viewed, ctx: AuthzContextDep, session: SessionDep) -> PhaseRead:
    """The phase, with the actions the caller may take on it."""
    return await PhaseService(session).read(ctx, phase)


@router.patch("/projects/{key}/phases/{phase_id}", responses=ERRORS)
async def update_phase(
    phase: Managed, body: PhaseUpdate, ctx: AuthzContextDep, session: SessionDep
) -> PhaseRead:
    """Change the fields sent; null clears the description or a date. Status, dates, and
    baselines are logged. 422 on `name` (`missing`, `taken`) and on `end_date` (`before_start`)."""
    return await PhaseService(session).update(ctx, phase, body)


@router.delete(
    "/projects/{key}/phases/{phase_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=ERRORS,
)
async def delete_phase(phase: Managed, ctx: AuthzContextDep, session: SessionDep) -> None:
    """Delete the phase for good: a 422 `in_use` while any task, one in the trash too, is in it."""
    await PhaseService(session).delete(ctx, phase)


@router.post("/projects/{key}/phases/{phase_id}/move", responses=ERRORS)
async def move_phase(
    phase: Managed, body: ItemMove, ctx: AuthzContextDep, session: SessionDep
) -> PhaseRead:
    """Put the phase just after `after_id` or just before `before_id`, or at the bottom. 422
    on `after_id` or `before_id` (`not_found`) and on both (`conflict`)."""
    return await PhaseService(session).move(ctx, phase, body)
