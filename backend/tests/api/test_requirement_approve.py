"""Approving a requirement by hand (design-doc §5, "Requirement approval by hand"; §6.2; §10;
DL-161, DL-169): the current revision, by the caller, now; a stale `version` a 409; a pending
request cancelled and logged; `status` and `approved_revision_id` logged when they change.
Who may approve is the spec tests' (tests/api/authz/test_approval_decisions.py)."""

from datetime import UTC, datetime
from typing import cast

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import IdMixin
from app.enums import (
    ActivityAction,
    ActivityField,
    ApprovalEntityType,
    ApprovalRequestStatus,
    ProjectRole,
    RequirementStatus,
)
from app.models.approval import ApprovalRequest
from app.models.audit import ActivityLog
from app.models.requirement import Requirement, RequirementRevision
from app.models.user import User
from tests.factories import BaseFactory
from tests.factories.approval import ApprovalRequestFactory
from tests.factories.project import ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory, RequirementRevisionFactory
from tests.factories.user import UserFactory
from tests.support.authz import Tenancy, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

APPROVE = "/api/projects/PMT/requirements/7/approve"
EARLIER = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


@pytest.fixture
async def admin(client: AsyncClient, t: Tenancy) -> User:
    user = await UserFactory.create_async(name="Ada Admin", is_system_admin=False)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.ADMIN
    )
    await sign_in_as(client, user)
    return user


async def requirement(t: Tenancy, *, revisions: int = 1) -> Requirement:
    """RQ-7 in PMT, a draft at revision `revisions`."""
    item = await RequirementFactory.create_async(
        project=t.project, number=7, status=RequirementStatus.DRAFT
    )
    for n in range(1, revisions + 1):
        revision = await RequirementRevisionFactory.create_async(
            requirement=item, revision_number=n
        )
    item.current_revision_id = revision.id  # pyright: ignore[reportPossiblyUnboundVariable]
    await cast(AsyncSession, BaseFactory.__async_session__).flush()
    return item


async def logged(session: AsyncSession, entity_id: object) -> list[tuple[object, ...]]:
    rows = await session.scalars(
        select(ActivityLog).where(ActivityLog.entity_id == entity_id).order_by(ActivityLog.id)
    )
    return [(r.action, r.field_changed, r.old_value, r.new_value, r.changed_by) for r in rows]


async def stored[M: IdMixin](session: AsyncSession, model: type[M], entity_id: object) -> M:
    return (
        await session.execute(
            select(model).where(model.id == entity_id).execution_options(populate_existing=True)
        )
    ).scalar_one()


async def test_approving_by_hand_logs_the_status_and_the_revision_as_the_admin(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """§10: `status` and `approved_revision_id` logged. Bug: either change unlogged."""
    item = await requirement(t)

    response = await client.post(APPROVE, json={"version": item.version})

    assert response.status_code == 200
    assert await logged(session, item.id) == [
        (ActivityAction.UPDATED, ActivityField.STATUS, "draft", "approved", admin.id),
        (
            ActivityAction.UPDATED,
            ActivityField.APPROVED_REVISION_ID,
            None,
            str(item.current_revision_id),
            admin.id,
        ),
    ]


async def test_a_stale_version_is_a_409_and_approves_nothing(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """DL-169: the revision approved is the one on screen. Bug: no version check."""
    item = await requirement(t)

    response = await client.post(APPROVE, json={"version": item.version - 1})

    assert response.status_code == 409
    row = await stored(session, Requirement, item.id)
    assert (row.status, row.approved_revision_id) == (RequirementStatus.DRAFT, None)


async def test_approving_by_hand_cancels_the_pending_request_logged_as_the_admin(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """§6.2: the request is moot. Bug: left pending."""
    item = await requirement(t)
    request = await ApprovalRequestFactory.create_async(
        project=t.project,
        entity_type=ApprovalEntityType.REQUIREMENT,
        entity_id=item.id,
        requirement_revision_id=item.current_revision_id,
        requester=admin,
    )

    await client.post(APPROVE, json={"version": item.version})

    row = await stored(session, ApprovalRequest, request.id)
    assert row.status is ApprovalRequestStatus.CANCELLED
    assert await logged(session, request.id) == [
        (ActivityAction.UPDATED, ActivityField.STATUS, "pending", "cancelled", admin.id)
    ]


async def test_approving_an_approved_modified_requirement_approves_its_current_revision(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """§6.1: approved at revision 1, edited to revision 2, re-approved by hand at revision 2.
    Bug: the old approved revision kept, or the unchanged status logged again."""
    item = await requirement(t, revisions=2)
    revision_1 = await session.scalar(
        select(RequirementRevision.id).where(
            RequirementRevision.requirement_id == item.id, RequirementRevision.revision_number == 1
        )
    )
    item.status = RequirementStatus.APPROVED
    item.approved_revision_id = revision_1
    item.approved_at = EARLIER
    await session.flush()

    response = await client.post(APPROVE, json={"version": item.version})

    assert response.status_code == 200
    row = await stored(session, Requirement, item.id)
    assert (row.approved_revision_id, row.approved_by) == (item.current_revision_id, admin.id)
    # Approved now, not left at the earlier approval's time.
    assert row.approved_at != EARLIER
    assert await logged(session, item.id) == [
        (
            ActivityAction.UPDATED,
            ActivityField.APPROVED_REVISION_ID,
            str(revision_1),
            str(item.current_revision_id),
            admin.id,
        )
    ]
