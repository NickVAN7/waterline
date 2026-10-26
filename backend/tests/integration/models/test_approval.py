"""`approval_request` and `approval` constraints (schema-doc "Approvals"; design-doc §6.2)."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ApprovalEntityType, ApprovalRequestStatus
from tests.factories.approval import ApprovalFactory, ApprovalRequestFactory
from tests.factories.requirement import RequirementRevisionFactory
from tests.factories.user import UserFactory

pytestmark = pytest.mark.anyio


# --- The revision a requirement's request approves -------------------------------------------


async def test_requirement_request_needs_the_revision_it_approves(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="ck_approval_request_requirement_revision"):
        await ApprovalRequestFactory.create_async(
            entity_type=ApprovalEntityType.REQUIREMENT, requirement_revision_id=None
        )


async def test_requirement_request_with_its_revision_is_stored(session: AsyncSession) -> None:
    revision = await RequirementRevisionFactory.create_async()

    await ApprovalRequestFactory.create_async(
        entity_type=ApprovalEntityType.REQUIREMENT,
        entity_id=revision.requirement_id,
        requirement_revision_id=revision.id,
    )

    assert await session.scalar(text("SELECT count(*) FROM approval_request")) == 1


async def test_milestone_request_needs_no_revision(session: AsyncSession) -> None:
    await ApprovalRequestFactory.create_async(
        entity_type=ApprovalEntityType.MILESTONE, requirement_revision_id=None
    )

    assert await session.scalar(text("SELECT count(*) FROM approval_request")) == 1


# --- One pending request per entity ----------------------------------------------------------


async def test_an_entity_has_one_pending_request_at_most(session: AsyncSession) -> None:
    entity_id = uuid.uuid7()
    await ApprovalRequestFactory.create_async(entity_id=entity_id)

    with pytest.raises(IntegrityError, match="ix_approval_request_entity_type_entity_id"):
        await ApprovalRequestFactory.create_async(entity_id=entity_id)


@pytest.mark.parametrize(
    "closed",
    [
        ApprovalRequestStatus.APPROVED,
        ApprovalRequestStatus.REJECTED,
        ApprovalRequestStatus.CANCELLED,
    ],
)
async def test_a_closed_request_leaves_room_for_a_new_pending_one(
    session: AsyncSession, closed: ApprovalRequestStatus
) -> None:
    entity_id = uuid.uuid7()
    await ApprovalRequestFactory.create_async(entity_id=entity_id, status=closed)

    await ApprovalRequestFactory.create_async(entity_id=entity_id)

    assert await session.scalar(text("SELECT count(*) FROM approval_request")) == 2


async def test_the_same_id_under_another_entity_type_is_another_entity(
    session: AsyncSession,
) -> None:
    entity_id = uuid.uuid7()
    await ApprovalRequestFactory.create_async(
        entity_type=ApprovalEntityType.MILESTONE, entity_id=entity_id
    )

    await ApprovalRequestFactory.create_async(
        entity_type=ApprovalEntityType.TEST_RUN, entity_id=entity_id
    )

    assert await session.scalar(text("SELECT count(*) FROM approval_request")) == 2


# --- Approvers -------------------------------------------------------------------------------


async def test_an_approver_is_named_once_per_request(session: AsyncSession) -> None:
    request = await ApprovalRequestFactory.create_async()
    approver = await UserFactory.create_async()
    await ApprovalFactory.create_async(approval_request=request, approver=approver)

    with pytest.raises(IntegrityError, match="uq_approval_approval_request_id_approver_id"):
        await ApprovalFactory.create_async(approval_request=request, approver=approver)


# --- Enums -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("update", "constraint"),
    [
        (
            "UPDATE approval_request SET entity_type = 'task' WHERE id = :request",
            "ck_approval_request_entity_type",
        ),
        (
            "UPDATE approval_request SET status = 'flagged' WHERE id = :request",
            "ck_approval_request_status",
        ),
        ("UPDATE approval SET decision = 'abstained' WHERE id = :approval", "ck_approval_decision"),
    ],
)
async def test_approval_enum_value_outside_the_enum_is_rejected(
    session: AsyncSession, update: str, constraint: str
) -> None:
    approval = await ApprovalFactory.create_async()

    with pytest.raises(IntegrityError, match=constraint):
        await session.execute(
            text(update), {"request": approval.approval_request_id, "approval": approval.id}
        )
