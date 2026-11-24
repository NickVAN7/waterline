"""Tasks (design-doc §5, §6 "Task"; build plan, S3-C5)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.authz.actions import Action
from app.core.db import SessionDep
from app.routers.deps import ERRORS, AuthzContextDep, authorized, load_project, load_task
from app.schemas.task import (
    TaskCreate,
    TaskList,
    TaskMove,
    TaskRead,
    TaskRestrictionUpdate,
    TaskUpdate,
)
from app.services.project import ProjectEntity
from app.services.task import TASKS, TaskEntity, TaskService

router = APIRouter(tags=["task"])

Creating = Annotated[ProjectEntity, Depends(authorized(load_project, Action.TASK_CREATE))]
Listed = Annotated[ProjectEntity, Depends(authorized(load_project, Action.TASK_VIEW))]
Viewed = Annotated[TaskEntity, Depends(authorized(load_task, Action.TASK_VIEW))]
Updated = Annotated[TaskEntity, Depends(authorized(load_task, Action.TASK_UPDATE))]
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


@router.patch("/projects/{key}/tasks/{number}", responses=ERRORS)
async def update_task(
    task: Updated, body: TaskUpdate, ctx: AuthzContextDep, session: SessionDep
) -> TaskRead:
    """Change the fields sent. 409 on a stale `version`; 403 for a status move design-doc §5's
    table denies, or a reporter change without `task.reassign_reporter`; 404 for a requirement,
    phase, or workstream outside the project; 422 on `title`, `type`, `assignee_id`,
    `reviewer_id`, `reporter_id`, and `workstream_id`."""
    return await TaskService(session).update(ctx, task, body)


@router.put("/projects/{key}/tasks/{number}/restriction", responses=ERRORS)
async def set_task_restriction(
    task: Viewed, body: TaskRestrictionUpdate, ctx: AuthzContextDep, session: SessionDep
) -> TaskRead:
    """Replace the task's restriction, without `version` (DL-162): a raise needs
    `task.raise_restriction`, a lower `task.lower_restriction` (403); 422 on `level`
    (`below_project`) and `categories` (`project_only`)."""
    return await TaskService(session).set_restriction(ctx, task, body)


@router.post("/projects/{key}/tasks/{number}/move", responses=ERRORS)
async def move_task(
    task: Updated, body: TaskMove, ctx: AuthzContextDep, session: SessionDep
) -> TaskRead:
    """Put the task just after `after_id` or just before `before_id` in the project's order, or
    at the bottom; with `status`, into that board column too, the transition checked first (403,
    nothing saved). 422 on `after_id` or `before_id` (`not_found`) and on both (`conflict`)."""
    return await TaskService(session).move(ctx, task, body)
