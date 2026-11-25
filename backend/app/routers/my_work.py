"""My work, the home page's data (design-doc §11; DL-76)."""

from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.core.db import SessionDep
from app.core.errors import ErrorBody
from app.core.lists import Page
from app.routers.deps import AuthzContextDep
from app.schemas.approval import ApprovalWorkItem
from app.schemas.project import MyWork
from app.schemas.task import TaskWorkItem
from app.services.my_work import APPROVALS, TASK_WORK, MyWorkService

router = APIRouter(prefix="/me/work", tags=["my_work"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorBody}
    for code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_422_UNPROCESSABLE_CONTENT)
}
ApprovalQuery = Annotated[APPROVALS.query_model, Query()]  # pyright: ignore[reportInvalidTypeForm]
TaskWorkQuery = Annotated[TASK_WORK.query_model, Query()]  # pyright: ignore[reportInvalidTypeForm]


@router.get("", responses=_ERRORS)
async def my_work(
    ctx: AuthzContextDep,
    session: SessionDep,
    today: Annotated[
        date | None,
        Query(
            description="The browser's date, for the due counts; default the server's UTC date",
            # The due window runs 7 days past it, which must still be a date.
            le=date.max - timedelta(days=7),  # pyright: ignore[reportArgumentType] -- pydantic compares dates; the stub types `le` as a number
        ),
    ] = None,
) -> MyWork:
    """Every section, each with its first items and total, and the summary's due counts."""
    return await MyWorkService(session).work(ctx, today)


@router.get("/approvals", responses=_ERRORS)
async def my_approvals(
    ctx: AuthzContextDep, query: ApprovalQuery, session: SessionDep
) -> Page[ApprovalWorkItem]:
    """The caller's pending approvals, oldest request first (DL-236)."""
    return await MyWorkService(session).approvals(ctx, query)


@router.get("/tasks", responses=_ERRORS)
async def my_tasks(
    ctx: AuthzContextDep, query: TaskWorkQuery, session: SessionDep
) -> Page[TaskWorkItem]:
    """The caller's open assigned tasks (any status but done or cancelled), priority first."""
    return await MyWorkService(session).tasks(ctx, query)


@router.get("/reviews", responses=_ERRORS)
async def my_reviews(
    ctx: AuthzContextDep, query: TaskWorkQuery, session: SessionDep
) -> Page[TaskWorkItem]:
    """The tasks in review with the caller as reviewer, priority first."""
    return await MyWorkService(session).reviews(ctx, query)
