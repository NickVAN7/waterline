"""Tasks (design-doc §5, §6 "Task"; build plan, S3-C5)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.authz.actions import Action
from app.core.db import SessionDep
from app.routers.deps import ERRORS, AuthzContextDep, authorized, load_project, load_task
from app.schemas.task import TaskCreate, TaskList, TaskRead
from app.services.project import ProjectEntity
from app.services.task import TASKS, TaskEntity, TaskService

router = APIRouter(tags=["task"])

Creating = Annotated[ProjectEntity, Depends(authorized(load_project, Action.TASK_CREATE))]
Listed = Annotated[ProjectEntity, Depends(authorized(load_project, Action.TASK_VIEW))]
Viewed = Annotated[TaskEntity, Depends(authorized(load_task, Action.TASK_VIEW))]
TasksQuery = Annotated[TASKS.query_model, Query()]  # pyright: ignore[reportInvalidTypeForm]


@router.post("/projects/{key}/tasks", status_code=status.HTTP_201_CREATED, responses=ERRORS)
async def create_task(
    project: Creating, body: TaskCreate, ctx: AuthzContextDep, session: SessionDep
) -> TaskRead:
    """Create a task: the next `TA` number, `todo`, at the bottom of the project's order. 404
    for a requirement, phase, or workstream outside the project; 422 on `title` (`missing`),
    `type` (`not_offered`), `workstream_id` (`archived`), `restriction_level`
    (`below_project`), and `restriction_categories` (`project_only`)."""
    return await TaskService(session).create(ctx, project, body)


@router.get("/projects/{key}/tasks", responses=ERRORS)
async def list_tasks(
    project: Listed, query: TasksQuery, ctx: AuthzContextDep, session: SessionDep
) -> TaskList:
    """The project's tasks matching the filters, in rank order unless `sort` says otherwise:
    complete up to 2,000, with `truncated` above it (the backlog and the board)."""
    return await TaskService(session).list(ctx, project, query)


@router.get("/projects/{key}/tasks/{number}", responses=ERRORS)
async def get_task(task: Viewed, ctx: AuthzContextDep, session: SessionDep) -> TaskRead:
    """The task, with the actions and status moves the caller may make."""
    return await TaskService(session).read(ctx, task)
