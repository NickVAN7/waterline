"""The approval policy wired into `POST /api/approval-requests/{id}/decision` (design-doc §6.2
"Policy (v1)", "Completing a requirement request", "Decisions are final", "Stale requests", "A
rejected request changes nothing"; §10; DL-148, DL-195; build plan S2-C11): the last approval
completes the request and approves the requirement at the request's revision, by the approver
whose decision completed it; `replaced` rows don't count; any rejection rejects the request and
changes nothing on the requirement, except a rejected re-open round, which moves it back to
`draft`. Authorization is in tests/api/authz/test_approval_decisions.py."""

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    ActivityAction,
    ActivityEntityType,
    ApprovalDecision,
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
from tests.factories.approval import ApprovalFactory, ApprovalRequestFactory
from tests.factories.project import ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory, RequirementRevisionFactory
from tests.factories.user import UserFactory
from tests.support.authz import Tenancy, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

PENDING = ApprovalDecision.PENDING
APPROVED = ApprovalDecision.APPROVED
REPLACED = ApprovalDecision.REPLACED
DECIDED_AT = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)
APPROVED_AT = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


async def flush() -> None:
    # The app reads through its own session: flush what was set after a factory's flush.
    await cast(AsyncSession, BaseFactory.__async_session__).flush()


async def viewer(t: Tenancy, name: str) -> User:
    user = await UserFactory.create_async(name=name, is_system_admin=False, is_active=True)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.VIEWER
    )
    return user


async def requirement(
    t: Tenancy, *, revisions: int = 1, status: RequirementStatus = RequirementStatus.DRAFT
) -> tuple[Requirement, list[RequirementRevision]]:
    """RQ-7 in PMT at revision `revisions`, never approved, in `status`."""
    item = await RequirementFactory.create_async(
        project=t.project,
        number=7,
        status=status,
        approved_revision_id=None,
        approved_by=None,
        approved_at=None,
    )
    made = [
        await RequirementRevisionFactory.create_async(requirement=item, revision_number=n)
        for n in range(1, revisions + 1)
    ]
    item.current_revision_id = made[-1].id
    await flush()
    return item, made


async def approved_at(item: Requirement, revision: RequirementRevision, by: User) -> None:
    """Mark `item` approved at `revision` by `by`, as an earlier sign-off left it."""
    item.status = RequirementStatus.APPROVED
    item.approved_revision_id = revision.id
    item.approved_by = by.id
    item.approved_at = APPROVED_AT
    await flush()


async def request_on(
    t: Tenancy,
    revision: RequirementRevision,
    item: Requirement,
    *rows: tuple[User, ApprovalDecision],
) -> ApprovalRequest:
    """A pending request bound to `revision`, made by an explicit project admin."""
    admin = await UserFactory.create_async(name="Ada Admin", is_system_admin=False)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=admin, role=ProjectRole.ADMIN
    )
    request = await ApprovalRequestFactory.create_async(
        project=t.project,
        entity_type=ApprovalEntityType.REQUIREMENT,
        entity_id=item.id,
        requirement_revision_id=revision.id,
        status=ApprovalRequestStatus.PENDING,
        requester=admin,
        completed_at=None,
    )
    for approver, decision in rows:
        await ApprovalFactory.create_async(
            approval_request=request,
            approver=approver,
            decision=decision,
            decided_at=DECIDED_AT if decision is APPROVED else None,
        )
    return request


async def decide(client: AsyncClient, request: ApprovalRequest, decision: str) -> int:
    response = await client.post(
        f"/api/approval-requests/{request.id}/decision", json={"decision": decision}
    )
    return response.status_code


async def request_state(session: AsyncSession, request: ApprovalRequest) -> tuple[object, bool]:
    """The request's `(status, completed_at is set)`, re-read."""
    row = (
        await session.execute(
            select(ApprovalRequest.status, ApprovalRequest.completed_at).where(
                ApprovalRequest.id == request.id
            )
        )
    ).one()
    return ApprovalRequestStatus(row[0]), row[1] is not None


async def approval_state(session: AsyncSession, item: Requirement) -> tuple[object, ...]:
    """The requirement's `(status, approved_revision_id, approved_by)`, re-read."""
    row = (
        await session.execute(
            select(
                Requirement.status, Requirement.approved_revision_id, Requirement.approved_by
            ).where(Requirement.id == item.id)
        )
    ).one()
    return RequirementStatus(row[0]), row[1], row[2]


async def logged(
    session: AsyncSession, entity_type: ActivityEntityType, entity_id: uuid.UUID
) -> set[tuple[object, ...]]:
    """The entity's `updated` entries as `(field_changed, old_value, new_value, changed_by)`."""
    rows = await session.scalars(
        select(ActivityLog).where(
            ActivityLog.entity_type == entity_type,
            ActivityLog.entity_id == entity_id,
            ActivityLog.action == ActivityAction.UPDATED,
        )
    )
    return {(r.field_changed, r.old_value, r.new_value, r.changed_by) for r in rows}


# --- Completion ---------------------------------------------------------------------------------


async def test_the_last_approval_completes_the_request_and_approves_a_draft(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """§6.2: every named approver approved completes the request; `approved_revision_id` the
    request's revision, `approved_by` the approver whose decision completed it; a draft moves to
    `approved`. Bug: the policy never called, or completion skipping the handler."""
    item, (rev1,) = await requirement(t)
    ivy, max_ = await viewer(t, "Ivy Moss"), await viewer(t, "Max Moore")
    request = await request_on(t, rev1, item, (ivy, APPROVED), (max_, PENDING))
    await sign_in_as(client, max_)

    assert await decide(client, request, "approved") == 200

    assert await request_state(session, request) == (ApprovalRequestStatus.APPROVED, True)
    assert await approval_state(session, item) == (RequirementStatus.APPROVED, rev1.id, max_.id)


async def test_completion_is_logged_on_the_request_and_the_requirement(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """§10: the request's `status` change; the requirement's `status` and
    `approved_revision_id`."""
    item, (rev1,) = await requirement(t)
    ivy = await viewer(t, "Ivy Moss")
    request = await request_on(t, rev1, item, (ivy, PENDING))
    await sign_in_as(client, ivy)

    assert await decide(client, request, "approved") == 200

    assert await logged(session, ActivityEntityType.APPROVAL_REQUEST, request.id) == {
        ("status", "pending", "approved", ivy.id)
    }
    assert await logged(session, ActivityEntityType.REQUIREMENT, item.id) == {
        ("status", "draft", "approved", ivy.id),
        ("approved_revision_id", None, str(rev1.id), ivy.id),
    }


async def test_an_approval_short_of_all_leaves_the_request_and_requirement_alone(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """Every named approver must approve. Bug: approved on the first approval."""
    item, (rev1,) = await requirement(t)
    ivy, max_ = await viewer(t, "Ivy Moss"), await viewer(t, "Max Moore")
    request = await request_on(t, rev1, item, (ivy, PENDING), (max_, PENDING))
    await sign_in_as(client, ivy)

    assert await decide(client, request, "approved") == 200

    assert await request_state(session, request) == (ApprovalRequestStatus.PENDING, False)
    assert await approval_state(session, item) == (RequirementStatus.DRAFT, None, None)


async def test_a_replaced_row_doesnt_hold_up_completion(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """§6.2: `replaced` rows don't count; approved when every other row is approved."""
    item, (rev1,) = await requirement(t)
    gone, ivy = await viewer(t, "Gus Gone"), await viewer(t, "Ivy Moss")
    request = await request_on(t, rev1, item, (gone, REPLACED), (ivy, PENDING))
    await sign_in_as(client, ivy)

    assert await decide(client, request, "approved") == 200

    assert await request_state(session, request) == (ApprovalRequestStatus.APPROVED, True)
    assert await approval_state(session, item) == (RequirementStatus.APPROVED, rev1.id, ivy.id)


async def test_a_stale_request_approves_exactly_the_revision_it_is_bound_to(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """§6.2 "Stale requests": approved after a newer revision was saved, it still records
    revision 1, so the requirement shows "Approved · modified"."""
    item, (rev1, _) = await requirement(t, revisions=2)
    ivy = await viewer(t, "Ivy Moss")
    request = await request_on(t, rev1, item, (ivy, PENDING))
    await sign_in_as(client, ivy)

    assert await decide(client, request, "approved") == 200

    assert await approval_state(session, item) == (RequirementStatus.APPROVED, rev1.id, ivy.id)


async def test_completion_moves_only_a_draft_to_approved(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """DL-148: "a completed request moves only a `draft` requirement to `approved`"; the
    approval itself is still recorded (§6.1)."""
    item, (rev1,) = await requirement(t, status=RequirementStatus.IN_PROGRESS)
    ivy = await viewer(t, "Ivy Moss")
    request = await request_on(t, rev1, item, (ivy, PENDING))
    await sign_in_as(client, ivy)

    assert await decide(client, request, "approved") == 200

    assert await approval_state(session, item) == (
        RequirementStatus.IN_PROGRESS,
        rev1.id,
        ivy.id,
    )


async def test_an_approved_reopen_round_updates_the_approval(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """DL-195: a re-open round approved, "the approval is updated as usual"."""
    item, (rev1,) = await requirement(t)
    earlier, ivy = await viewer(t, "Earl Early"), await viewer(t, "Ivy Moss")
    await approved_at(item, rev1, earlier)
    request = await request_on(t, rev1, item, (ivy, PENDING))
    await sign_in_as(client, ivy)

    assert await decide(client, request, "approved") == 200

    assert await approval_state(session, item) == (RequirementStatus.APPROVED, rev1.id, ivy.id)


# --- Rejection ----------------------------------------------------------------------------------


async def test_any_rejection_rejects_the_request_and_changes_nothing_on_a_draft(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """§6.2: any rejection rejects the whole request, others still pending; a rejected request
    changes nothing on the entity."""
    item, (rev1,) = await requirement(t)
    ivy, max_ = await viewer(t, "Ivy Moss"), await viewer(t, "Max Moore")
    request = await request_on(t, rev1, item, (ivy, PENDING), (max_, PENDING))
    await sign_in_as(client, ivy)

    assert await decide(client, request, "rejected") == 200

    assert await request_state(session, request) == (ApprovalRequestStatus.REJECTED, True)
    assert await logged(session, ActivityEntityType.APPROVAL_REQUEST, request.id) == {
        ("status", "pending", "rejected", ivy.id)
    }
    assert await approval_state(session, item) == (RequirementStatus.DRAFT, None, None)
    assert await logged(session, ActivityEntityType.REQUIREMENT, item.id) == set()


async def test_a_rejected_reopen_round_moves_the_requirement_back_to_draft_logged(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """DL-195: an approved requirement (not "Approved · modified") re-opened and rejected moves
    back to `draft`, logged like any status change; `approved_revision_id` stays set when the
    status moves out of `approved` (schema-doc `requirement`)."""
    item, (rev1,) = await requirement(t)
    earlier, ivy = await viewer(t, "Earl Early"), await viewer(t, "Ivy Moss")
    await approved_at(item, rev1, earlier)
    request = await request_on(t, rev1, item, (ivy, PENDING))
    await sign_in_as(client, ivy)

    assert await decide(client, request, "rejected") == 200

    assert await approval_state(session, item) == (RequirementStatus.DRAFT, rev1.id, earlier.id)
    assert await logged(session, ActivityEntityType.REQUIREMENT, item.id) == {
        ("status", "approved", "draft", ivy.id)
    }


async def test_a_rejected_reapproval_of_an_approved_modified_requirement_changes_nothing(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """DL-195: approved at revision 1, now at revision 2 ("Approved · modified"), the request on
    revision 2: not a re-open, so its rejection changes nothing."""
    item, (rev1, rev2) = await requirement(t, revisions=2)
    earlier, ivy = await viewer(t, "Earl Early"), await viewer(t, "Ivy Moss")
    await approved_at(item, rev1, earlier)
    request = await request_on(t, rev2, item, (ivy, PENDING))
    await sign_in_as(client, ivy)

    assert await decide(client, request, "rejected") == 200

    assert await request_state(session, request) == (ApprovalRequestStatus.REJECTED, True)
    assert await approval_state(session, item) == (
        RequirementStatus.APPROVED,
        rev1.id,
        earlier.id,
    )
    assert await logged(session, ActivityEntityType.REQUIREMENT, item.id) == set()
