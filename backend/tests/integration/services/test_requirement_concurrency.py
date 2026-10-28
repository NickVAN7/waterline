"""Requirements between truly parallel transactions: two edits from the same version, or the
same restriction change twice, at once (backend/CLAUDE.md: a "nothing to change" check reads the
row under its lock; design-doc §3, §6.1). Sabotage-checked against the code without the lock."""

from collections.abc import Awaitable

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.authz.context import AuthzContext
from app.core.db import SessionMaker
from app.enums import ActivityField, RestrictionLevel
from app.models.audit import ActivityLog
from app.models.requirement import Requirement, RequirementRevision
from app.schemas.requirement import (
    RequirementCreate,
    RequirementRestrictionUpdate,
    RequirementUpdate,
)
from app.services.requirement import RequirementService
from tests.factories.org import OrganizationFactory
from tests.factories.project import ProjectFactory
from tests.factories.user import UserFactory
from tests.support.concurrency import committing_factories, run_in_parallel

pytestmark = pytest.mark.anyio

TABLES = (
    "activity_log",
    "requirement_revision",
    "requirement",
    "project_counter",
    "project",
    "organization",
    "workspace",
    "user",
)


async def outcome(work: Awaitable[object]) -> str:
    """ "ok", or the name of the error `work` raised: recorded, not asserted, inside the race's
    task group, so a regression can't stop the other transaction's commit (TD-30)."""
    try:
        await work
    except StaleDataError:
        return "stale"
    except Exception as error:
        return type(error).__name__
    return "ok"


async def a_requirement(concurrency: SessionMaker) -> tuple[AuthzContext, Requirement]:
    async with committing_factories(concurrency) as session:
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org, key="PMT")
        admin = await UserFactory.create_async(is_system_admin=True)
        ctx = AuthzContext(user_id=admin.id, is_system_admin=True)
        created = await RequirementService(session).create(
            ctx, project, RequirementCreate(title="Three-way match")
        )
    async with concurrency() as session:
        return ctx, await session.get_one(Requirement, created.id)


@pytest.mark.concurrency(*TABLES)
async def test_two_edits_from_the_same_version_at_once_are_one_save_and_one_409(
    concurrency: SessionMaker,
) -> None:
    """Without the lock both pass the version check and both take revision 2: the second hits
    the unique `(requirement_id, revision_number)` and is a 500, not a 409."""
    ctx, requirement = await a_requirement(concurrency)

    async def edit(session: AsyncSession, index: int) -> str:
        loaded = await session.get_one(Requirement, requirement.id)
        body = RequirementUpdate(version=1, title=f"Edit {index}")
        return await outcome(RequirementService(session).update(ctx, loaded, body))

    outcomes = await run_in_parallel(concurrency, 2, edit)

    async with concurrency() as check:
        revisions = await check.scalar(select(func.count()).select_from(RequirementRevision))
    assert (sorted(outcomes), revisions) == (["ok", "stale"], 2)


@pytest.mark.concurrency(*TABLES)
async def test_the_same_restriction_change_twice_at_once_logs_it_once(
    concurrency: SessionMaker,
) -> None:
    """The second compares against what the first committed, so the history's old values stay
    true and the change isn't logged twice."""
    ctx, requirement = await a_requirement(concurrency)

    async def restrict(session: AsyncSession, _index: int) -> str:
        loaded = await session.get_one(Requirement, requirement.id)
        body = RequirementRestrictionUpdate(level=RestrictionLevel.CONFIDENTIAL, categories=[])
        return await outcome(RequirementService(session).set_restriction(ctx, loaded, body))

    outcomes = await run_in_parallel(concurrency, 2, restrict)

    async with concurrency() as check:
        logged = await check.scalar(
            select(func.count())
            .select_from(ActivityLog)
            .where(ActivityLog.field_changed == ActivityField.RESTRICTION_LEVEL)
        )
    assert (outcomes, logged) == (["ok", "ok"], 1)
