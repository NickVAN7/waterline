"""Requirements (design-doc §6, §6.1; build plan, S2-C5)."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.authz.actions import Action
from app.core.db import SessionDep
from app.routers.deps import ERRORS, AuthzContextDep, authorized, load_project, load_requirement
from app.schemas.requirement import (
    RequirementCreate,
    RequirementMove,
    RequirementRead,
    RequirementRestrictionUpdate,
    RequirementTree,
    RequirementUpdate,
)
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
Updated = Annotated[
    RequirementEntity, Depends(authorized(load_requirement, Action.REQUIREMENT_UPDATE))
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


@router.patch("/projects/{key}/requirements/{number}", responses=ERRORS)
async def update_requirement(
    requirement: Updated, body: RequirementUpdate, ctx: AuthzContextDep, session: SessionDep
) -> RequirementRead:
    """Change the fields sent. 409 on a stale `version`; a new revision only when the title or
    description changes. `status` `approved`: 403 without `requirement.approve_manually`, else
    422 `use_approve`; `reporter_id` needs `requirement.reassign_reporter`, 422
    `account_inactive` or `not_member`."""
    return await RequirementService(session).update(ctx, requirement, body)


@router.put("/projects/{key}/requirements/{number}/restriction", responses=ERRORS)
async def set_requirement_restriction(
    requirement: Viewed,
    body: RequirementRestrictionUpdate,
    ctx: AuthzContextDep,
    session: SessionDep,
) -> RequirementRead:
    """Set the requirement's restriction level and categories (no `version`, DL-162): raising
    needs `requirement.raise_restriction`, lowering `requirement.lower_restriction`. 422 on
    `level` (`below_project`) and on `categories` (`project_only`)."""
    return await RequirementService(session).set_restriction(ctx, requirement, body)


@router.post("/projects/{key}/requirements/{number}/move", responses=ERRORS)
async def move_requirement(
    requirement: Updated, body: RequirementMove, ctx: AuthzContextDep, session: SessionDep
) -> RequirementRead:
    """Move the requirement under `parent_id` (null: the top level), just after `after_id` or
    just before `before_id`, or to the bottom. 404 for a parent outside the project; 422 on
    `parent_id` (`cycle`), `after_id` or `before_id` (`not_sibling`), and `before_id` with both
    (`conflict`)."""
    return await RequirementService(session).move(ctx, requirement, body)
