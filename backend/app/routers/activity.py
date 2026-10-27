"""Item history (design-doc §6.1 "History"; build plan, S2-C3)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.authz.actions import Action
from app.core.db import SessionDep
from app.core.lists import Feed
from app.routers.deps import ERRORS, authorized, load_requirement
from app.schemas.activity import ActivityEntry
from app.services.activity import ITEM_HISTORY, ActivityService
from app.services.requirement import RequirementEntity

router = APIRouter(tags=["activity"])

RequirementViewed = Annotated[
    RequirementEntity, Depends(authorized(load_requirement, Action.REQUIREMENT_VIEW))
]
HistoryQuery = Annotated[ITEM_HISTORY.query_model, Query()]  # pyright: ignore[reportInvalidTypeForm]


@router.get("/projects/{key}/requirements/{number}/activity", responses=ERRORS)
async def requirement_activity(
    requirement: RequirementViewed, query: HistoryQuery, session: SessionDep
) -> Feed[ActivityEntry]:
    """The requirement's history, newest first (`?before=` the previous page's `next_cursor`)."""
    return await ActivityService(session).requirement_history(requirement, query)
