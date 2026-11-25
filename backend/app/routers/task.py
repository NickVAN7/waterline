"""Tasks (design-doc §5, §6 "Task"; build plan, S3-C5)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.authz.actions import Action
from app.core.db import SessionDep
from app.routers.deps import (
    ERRORS,
    AuthzContextDep,
    authorized,
    load_deleted_task,
    load_project,
    load_requirement,
    load_subtask,
    load_task,
)
from app.schemas.move import ItemMove
from app.schemas.subtask import SubtaskCreate, SubtaskItem, SubtaskList, SubtaskUpdate
from app.schemas.task import (
    TaskCreate,
    TaskList,
    TaskMove,
    TaskRead,
    TaskRestrictionUpdate,
    TaskUpdate,
)
from app.services.project import ProjectEntity
from app.services.requirement import RequirementEntity
from app.services.subtask import SubtaskEntity, SubtaskService
from app.services.task import TASKS, TaskEntity, TaskService

router = APIRouter(tags=["task"])

Creating = Annotated[ProjectEntity, Depends(authorized(load_project, Action.TASK_CREATE))]
Listed = Annotated[ProjectEntity, Depends(authorized(load_project, Action.TASK_VIEW))]
Viewed = Annotated[TaskEntity, Depends(authorized(load_task, Action.TASK_VIEW))]
Updated = Annotated[TaskEntity, Depends(authorized(load_task, Action.TASK_UPDATE))]
Deleted = Annotated[TaskEntity, Depends(authorized(load_task, Action.TASK_DELETE))]
Restored = Annotated[TaskEntity, Depends(authorized(load_deleted_task, Action.TASK_RESTORE))]
ChecklistManaged = Annotated[TaskEntity, Depends(authorized(load_task, Action.SUBTASK_MANAGE))]
SubtaskManaged = Annotated[SubtaskEntity, Depends(authorized(load_subtask, Action.SUBTASK_MANAGE))]
RequirementViewed = Annotated[
    RequirementEntity, Depends(authorized(load_requirement, Action.REQUIREMENT_VIEW))
]
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


@router.get("/projects/{key}/requirements/{number}/tasks", responses=ERRORS)
async def requirement_tasks(
    requirement: RequirementViewed, ctx: AuthzContextDep, session: SessionDep
) -> TaskList:
    """The requirement's tasks, as the backlog's rows and in its order: complete up to 2,000,
    with `truncated` above it."""
    return await TaskService(session).for_requirement(ctx, requirement)


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


@router.delete(
    "/projects/{key}/tasks/{number}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=ERRORS,
)
async def delete_task(task: Deleted, ctx: AuthzContextDep, session: SessionDep) -> None:
    """Move the task to the trash, its subtasks hidden with it."""
    await TaskService(session).delete(ctx, task)


@router.post("/projects/{key}/tasks/{number}/restore", responses=ERRORS)
async def restore_task(task: Restored, ctx: AuthzContextDep, session: SessionDep) -> TaskRead:
    """Bring the task back from the trash with its subtasks. 404 for one not in the trash."""
    return await TaskService(session).restore(ctx, task)


# --- Subtasks (design-doc §6, "Subtask"; S3-C8) ---------------------------------------------------


@router.get("/projects/{key}/tasks/{number}/subtasks", responses=ERRORS)
async def list_subtasks(task: Viewed, session: SessionDep) -> SubtaskList:
    """The task's subtasks in rank order: complete up to 2,000, with `truncated` above it."""
    return await SubtaskService(session).list(task)


@router.post(
    "/projects/{key}/tasks/{number}/subtasks",
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
async def create_subtask(
    task: ChecklistManaged, body: SubtaskCreate, session: SessionDep
) -> SubtaskItem:
    """Add a subtask at the bottom of the task's, numbered from the task's counter (never
    reused). 422 on `title` (`missing`)."""
    return await SubtaskService(session).create(task, body)


@router.patch("/projects/{key}/tasks/{number}/subtasks/{n}", responses=ERRORS)
async def update_subtask(
    subtask: SubtaskManaged, body: SubtaskUpdate, session: SessionDep
) -> SubtaskItem:
    """Change the fields sent (check it off with `is_done`). 422 on `title` (`missing`)."""
    return await SubtaskService(session).update(subtask, body)


@router.delete(
    "/projects/{key}/tasks/{number}/subtasks/{n}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=ERRORS,
)
async def delete_subtask(subtask: SubtaskManaged, session: SessionDep) -> None:
    """Delete the subtask for good; its number isn't reused."""
    await SubtaskService(session).delete(subtask)


@router.post("/projects/{key}/tasks/{number}/subtasks/{n}/move", responses=ERRORS)
async def move_subtask(subtask: SubtaskManaged, body: ItemMove, session: SessionDep) -> SubtaskItem:
    """Put the subtask just after `after_id` or just before `before_id` among its task's, or at
    the bottom. 422 on `after_id` or `before_id` (`not_found`) and on both (`conflict`)."""
    return await SubtaskService(session).move(subtask, body)
