"""My work, the home page's data (design-doc §11; DL-76)."""

from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.core.db import SessionDep
from app.core.errors import ErrorBody
from app.core.lists import Page
from app.routers.deps import AuthzContextDep
from app.schemas.approval import ApprovalWorkItem
from app.schemas.project import MyProjectItem, MyWork
from app.services.my_work import APPROVALS, PROJECTS, MyWorkService

router = APIRouter(prefix="/me/work", tags=["my_work"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorBody}
    for code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_422_UNPROCESSABLE_CONTENT)
}
ProjectQuery = Annotated[PROJECTS.query_model, Query()]  # pyright: ignore[reportInvalidTypeForm]
ApprovalQuery = Annotated[APPROVALS.query_model, Query()]  # pyright: ignore[reportInvalidTypeForm]


@router.get("", responses=_ERRORS)
async def my_work(ctx: AuthzContextDep, session: SessionDep) -> MyWork:
    """Every section, each with its first items and total."""
    return await MyWorkService(session).work(ctx)


@router.get("/favorites", responses=_ERRORS)
async def my_favorites(
    ctx: AuthzContextDep, query: ProjectQuery, session: SessionDep
) -> Page[MyProjectItem]:
    """The projects the user starred and can open, archived left out, by name (DL-302)."""
    return await MyWorkService(session).favorites(ctx, query)


@router.get("/approvals", responses=_ERRORS)
async def my_approvals(
    ctx: AuthzContextDep, query: ApprovalQuery, session: SessionDep
) -> Page[ApprovalWorkItem]:
    """The caller's pending approvals, oldest request first (DL-236)."""
    return await MyWorkService(session).approvals(ctx, query)
