"""Requirements (design-doc §6, §6.1; build plan, S2-C5)."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.authz.actions import Action
from app.core.db import SessionDep
from app.routers.deps import ERRORS, AuthzContextDep, authorized, load_project, load_requirement
from app.schemas.requirement import RequirementCreate, RequirementRead, RequirementTree
from app.services.project import ProjectEntity
from app.services.requirement import RequirementEntity, RequirementService

router = APIRouter(tags=["requirement"])

Creating = Annotated[ProjectEntity, Depends(authorized(load_project, Action.REQUIREMENT_CREATE))]
ProjectContentViewed = Annotated[
    ProjectEntity, Depends(authorized(load_project, Action.REQUIREMENT_VIEW))
]
Viewed = Annotated[
    RequirementEntity, Depends(authorized(load_requirement, Action.REQUIREMENT_VIEW))
]


@router.post("/projects/{key}/requirements", status_code=status.HTTP_201_CREATED, responses=ERRORS)
async def create_requirement(
    project: Creating, body: RequirementCreate, ctx: AuthzContextDep, session: SessionDep
) -> RequirementRead:
    """Create a requirement: the next `RQ` number, `draft`, revision 1, at the bottom of its
    siblings. 404 for a `parent_id` outside the project; 422 on `title` (`missing`) and on
    `restriction_categories` (`project_only`: `export_controlled` is set on the project)."""
    return await RequirementService(session).create(ctx, project, body)


@router.get("/projects/{key}/requirements", responses=ERRORS)
async def requirement_tree(project: ProjectContentViewed, session: SessionDep) -> RequirementTree:
    """The project's requirements for the tree, siblings in rank order: complete up to 2,000,
    with `truncated` above it (DL-159)."""
    return await RequirementService(session).tree(project)


@router.get("/projects/{key}/requirements/{number}", responses=ERRORS)
async def get_requirement(
    requirement: Viewed, ctx: AuthzContextDep, session: SessionDep
) -> RequirementRead:
    """The requirement, with the actions the caller may take on it."""
    return await RequirementService(session).read(ctx, requirement)
