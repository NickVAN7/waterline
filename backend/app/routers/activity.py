"""Item history and the project activity feed (design-doc §6.1 "History", §10; build plan,
S2-C3, S3-C12)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.authz.actions import Action
from app.core.db import SessionDep
from app.core.lists import Feed
from app.routers.deps import (
    ERRORS,
    AuthzContextDep,
    authorized,
    load_project,
    load_requirement,
    load_task,
)
from app.schemas.activity import ActivityEntry
from app.services.activity import ITEM_HISTORY, PROJECT_FEED, ActivityService
from app.services.project import ProjectEntity
from app.services.requirement import RequirementEntity
from app.services.task import TaskEntity

router = APIRouter(tags=["activity"])

RequirementViewed = Annotated[
    RequirementEntity, Depends(authorized(load_requirement, Action.REQUIREMENT_VIEW))
]
TaskViewed = Annotated[TaskEntity, Depends(authorized(load_task, Action.TASK_VIEW))]
ActivityViewed = Annotated[
    ProjectEntity, Depends(authorized(load_project, Action.PROJECT_VIEW_ACTIVITY))
]
FeedQuery = Annotated[PROJECT_FEED.query_model, Query()]  # pyright: ignore[reportInvalidTypeForm]
HistoryQuery = Annotated[ITEM_HISTORY.query_model, Query()]  # pyright: ignore[reportInvalidTypeForm]


@router.get("/projects/{key}/requirements/{number}/activity", responses=ERRORS)
async def requirement_activity(
    requirement: RequirementViewed, query: HistoryQuery, session: SessionDep
) -> Feed[ActivityEntry]:
    """The requirement's history, newest first (`?before=` the previous page's `next_cursor`)."""
    return await ActivityService(session).requirement_history(requirement, query)


@router.get("/projects/{key}/tasks/{number}/activity", responses=ERRORS)
async def task_activity(
    task: TaskViewed, query: HistoryQuery, session: SessionDep
) -> Feed[ActivityEntry]:
    """The task's history, newest first (`?before=` the previous page's `next_cursor`)."""
    return await ActivityService(session).task_history(task, query)


@router.get("/projects/{key}/activity", responses=ERRORS)
async def project_activity(
    project: ActivityViewed, query: FeedQuery, ctx: AuthzContextDep, session: SessionDep
) -> Feed[ActivityEntry]:
    """Every change logged in the project, newest first, filtered by item type, actor (`me`;
    `actor__is_null` for the system's), field, and the UTC day of the change."""
    return await ActivityService(session).project_feed(ctx, project, query)
