"""Approval requests' rules beyond who may act (design-doc §6.2, §10; build plan, S2-C10;
DL-194, DL-195, DL-225 to DL-228, DL-231): bound to the current revision, one pending at a
time, eligible approvers only, 1 to 50 distinct; cancelling only a pending one; Cancel offered
only while pending; the list newest first, offset-paged; archiving cancels the project's pending
requests; each change logged. Authorization is the spec tests' (tests/api/authz/)."""

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    ActivityAction,
    ActivityEntityType,
    ActivityField,
    ApprovalDecision,
    ApprovalEntityType,
    ApprovalRequestStatus,
    ProjectRole,
    RequirementStatus,
)
from app.models.approval import Approval, ApprovalRequest
from app.models.audit import ActivityLog
from app.models.requirement import Requirement
from app.models.user import User
from tests.factories import BaseFactory
from tests.factories.approval import ApprovalFactory, ApprovalRequestFactory
from tests.factories.org import MembershipFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory, RequirementRevisionFactory
from tests.factories.user import UserFactory
from tests.support.authz import Tenancy, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

REQUESTS = "/api/projects/PMT/requirements/7/approval-requests"
NOTE = "Sign-off before the October release"


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


@pytest.fixture
async def admin(client: AsyncClient, t: Tenancy) -> User:
    """Ada Admin, an explicit project admin of PMT, signed in."""
    user = await UserFactory.create_async(name="Ada Admin", is_system_admin=False)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.ADMIN
    )
    await sign_in_as(client, user)
    return user


async def member(t: Tenancy, name: str, role: ProjectRole = ProjectRole.VIEWER) -> User:
    user = await UserFactory.create_async(name=name, is_system_admin=False, is_active=True)
    await ProjectMembershipFactory.create_async(project=t.project, user=user, role=role)
    return user


async def flush() -> None:
    # The app reads through its own session: flush what was set after a factory's flush.
    await cast(AsyncSession, BaseFactory.__async_session__).flush()


async def requirement(t: Tenancy, *, revisions: int = 1, number: int = 7) -> Requirement:
    """RQ-`number` in PMT, at revision `revisions` (each revision titled "Rev <n>")."""
    item = await RequirementFactory.create_async(project=t.project, number=number)
    for n in range(1, revisions + 1):
        revision = await RequirementRevisionFactory.create_async(
            requirement=item, revision_number=n, title=f"Rev {n}"
        )
    item.current_revision_id = revision.id  # pyright: ignore[reportPossiblyUnboundVariable]
    await flush()
    return item


async def request_on(
    t: Tenancy, item: Requirement, requester: User, **values: object
) -> ApprovalRequest:
    return await ApprovalRequestFactory.create_async(
        project=t.project,
        entity_type=ApprovalEntityType.REQUIREMENT,
        entity_id=item.id,
        requirement_revision_id=item.current_revision_id,
        requester=requester,
        **values,
    )


def ask(*approvers: User | uuid.UUID, note: str | None = NOTE) -> dict[str, object]:
    ids = [a if isinstance(a, uuid.UUID) else a.id for a in approvers]
    return {"approver_ids": [str(i) for i in ids], "note": note}


def field_error(response: Response) -> tuple[int, list[object], str]:
    (error,) = response.json()["details"]["fields"]
    return response.status_code, error["loc"], error["type"]


async def stored(session: AsyncSession, request_id: object) -> ApprovalRequest:
    return (
        await session.execute(
            select(ApprovalRequest)
            .where(ApprovalRequest.id == request_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()


async def logged(session: AsyncSession, request_id: object) -> list[tuple[object, ...]]:
    rows = await session.scalars(
        select(ActivityLog)
        .where(
            ActivityLog.entity_type == ActivityEntityType.APPROVAL_REQUEST,
            ActivityLog.entity_id == request_id,
        )
        .order_by(ActivityLog.id)
    )
    return [(r.action, r.field_changed, r.old_value, r.new_value, r.changed_by) for r in rows]


# --- Create -------------------------------------------------------------------------------------


async def test_a_request_is_bound_to_the_current_revision_and_names_each_approver(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: bound to revision 1 rather than the current one, or an approver's row missing or not
    pending (§6.2: "each gets one `approval` row"; "bound to a specific revision")."""
    item = await requirement(t, revisions=2)
    vera, max_ = await member(t, "Vera Viewer"), await member(t, "Max Member", ProjectRole.MEMBER)

    response = await client.post(REQUESTS, json=ask(vera, max_))

    assert response.status_code == 201
    body = response.json()
    assert (body["status"], body["revision_number"], body["note"], body["requested_by_name"]) == (
        "pending",
        2,
        NOTE,
        "Ada Admin",
    )
    assert [(a["approver_name"], a["decision"]) for a in body["approvals"]] == [
        ("Vera Viewer", "pending"),
        ("Max Member", "pending"),
    ]
    request = await stored(session, body["id"])
    assert (request.requirement_revision_id, request.requested_by) == (
        item.current_revision_id,
        admin.id,
    )
    rows = await session.scalars(select(Approval).where(Approval.approval_request_id == request.id))
    assert sorted((r.approver_id, r.decision) for r in rows) == sorted(
        [(vera.id, ApprovalDecision.PENDING), (max_.id, ApprovalDecision.PENDING)]
    )


async def test_making_a_request_is_logged_as_created_by_the_requester(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: no `created` entry on the request (§10)."""
    await requirement(t)

    response = await client.post(REQUESTS, json=ask(await member(t, "Vera Viewer")))

    assert await logged(session, uuid.UUID(response.json()["id"])) == [
        (ActivityAction.CREATED, None, None, None, admin.id)
    ]


async def test_a_request_on_an_approved_requirement_reopens_it_without_moving_its_status(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """DL-195: a project admin re-opens an approved requirement with a new request; its status
    doesn't change while the request is pending. Bug: approved requirements refused."""
    item = await requirement(t)
    item.status = RequirementStatus.APPROVED
    item.approved_revision_id = item.current_revision_id
    await flush()

    response = await client.post(REQUESTS, json=ask(await member(t, "Vera Viewer")))

    assert (response.status_code, response.json()["revision_number"]) == (201, 1)
    await session.refresh(item)
    assert item.status is RequirementStatus.APPROVED


async def test_a_second_request_while_one_is_pending_is_a_422_and_creates_nothing(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """DL-225. Bug: no check, so the partial unique index turns it into a 500."""
    item = await requirement(t)
    await request_on(t, item, admin)

    response = await client.post(REQUESTS, json=ask(await member(t, "Vera Viewer")))

    assert field_error(response) == (422, ["body"], "pending_exists")
    count = await session.scalars(
        select(ApprovalRequest.id).where(ApprovalRequest.entity_id == item.id)
    )
    assert len(count.all()) == 1


@pytest.mark.parametrize(
    "status",
    [
        ApprovalRequestStatus.APPROVED,
        ApprovalRequestStatus.REJECTED,
        ApprovalRequestStatus.CANCELLED,
    ],
)
async def test_a_decided_or_cancelled_request_doesnt_block_a_new_one(
    client: AsyncClient, t: Tenancy, admin: User, status: ApprovalRequestStatus
) -> None:
    """Bug: the pending check counts every request, so no second round is ever possible (§6.2:
    "a further round is a new request")."""
    item = await requirement(t)
    await request_on(t, item, admin, status=status, completed_at=datetime.now(UTC))

    response = await client.post(REQUESTS, json=ask(await member(t, "Vera Viewer")))

    assert response.status_code == 201


async def test_another_requirements_pending_request_doesnt_block_this_one(
    client: AsyncClient, t: Tenancy, admin: User
) -> None:
    """Bug: the pending check isn't filtered by the entity."""
    await requirement(t)
    other = await requirement(t, number=8)
    await request_on(t, other, admin)

    response = await client.post(REQUESTS, json=ask(await member(t, "Vera Viewer")))

    assert response.status_code == 201


# --- Approvers (DL-226; §6.2, "Who can be an approver") ----------------------------------------


async def test_an_approver_without_access_to_the_project_is_a_404_and_creates_nothing(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: eligibility unchecked, or checked against the org rather than the project. An org
    member who isn't on the project can't see it (§4)."""
    await requirement(t)
    outsider = await UserFactory.create_async(name="Olive Outsider", is_system_admin=False)
    await MembershipFactory.create_async(organization=t.org, user=outsider)

    response = await client.post(REQUESTS, json=ask(await member(t, "Vera Viewer"), outsider))

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert "Olive Outsider" not in response.text
    assert (await session.scalars(select(ApprovalRequest.id))).all() == []


async def test_an_unknown_approver_is_a_404(client: AsyncClient, t: Tenancy, admin: User) -> None:
    await requirement(t)

    response = await client.post(REQUESTS, json=ask(uuid.uuid4()))

    assert (response.status_code, response.json()["code"]) == (404, "not_found")


async def test_on_an_ec_project_an_inherited_admin_isnt_an_eligible_approver(
    client: AsyncClient, t: Tenancy, admin: User
) -> None:
    """§3.1, §6.2: on an export-controlled project only an explicit membership counts. Bug:
    eligibility checked with a management action, which passes the gate."""
    t.project.restriction_categories = ["export_controlled"]
    await requirement(t)
    org_admin = await UserFactory.create_async(is_system_admin=False)
    await MembershipFactory.create_async(organization=t.org, user=org_admin, role="admin")

    response = await client.post(REQUESTS, json=ask(org_admin))

    assert (response.status_code, response.json()["code"]) == (404, "not_found")


async def test_on_an_ec_project_an_explicit_viewer_is_an_eligible_approver(
    client: AsyncClient, t: Tenancy, admin: User
) -> None:
    t.project.restriction_categories = ["export_controlled"]
    await requirement(t)

    response = await client.post(REQUESTS, json=ask(await member(t, "Vera Viewer")))

    assert response.status_code == 201


async def test_an_inherited_admin_is_an_eligible_approver_on_a_project_without_export_control(
    client: AsyncClient, t: Tenancy, admin: User
) -> None:
    """§6.2: "or inherited project admin". Bug: only explicit memberships counted."""
    await requirement(t)
    org_admin = await UserFactory.create_async(name="Otto Orgadmin", is_system_admin=False)
    await MembershipFactory.create_async(organization=t.org, user=org_admin, role="admin")

    response = await client.post(REQUESTS, json=ask(org_admin))

    assert response.status_code == 201


async def test_a_deactivated_approver_with_access_is_a_422(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """DL-226. Bug: the row would sit pending with nobody able to decide it."""
    await requirement(t)
    gone = await member(t, "Gil Gone")
    gone.is_active = False
    await flush()

    response = await client.post(REQUESTS, json=ask(gone))

    assert field_error(response) == (422, ["body", "approver_ids"], "account_inactive")
    assert (await session.scalars(select(ApprovalRequest.id))).all() == []


async def test_an_approver_named_twice_is_a_422(
    client: AsyncClient, t: Tenancy, admin: User
) -> None:
    await requirement(t)
    vera = await member(t, "Vera Viewer")

    response = await client.post(REQUESTS, json=ask(vera, vera))

    assert field_error(response) == (422, ["body", "approver_ids"], "duplicate")


@pytest.mark.parametrize(("count", "status"), [(0, 422), (51, 422), (50, 201)])
async def test_a_request_names_1_to_50_approvers(
    client: AsyncClient, t: Tenancy, admin: User, count: int, status: int
) -> None:
    """DL-226's bounds, both sides."""
    await requirement(t)
    approvers = [await member(t, f"Approver {n}") for n in range(count)]

    response = await client.post(REQUESTS, json=ask(*approvers))

    assert response.status_code == status


async def test_a_note_over_2000_characters_is_a_422(
    client: AsyncClient, t: Tenancy, admin: User
) -> None:
    """DL-143."""
    await requirement(t)
    vera = await member(t, "Vera Viewer")

    over = await client.post(REQUESTS, json=ask(vera, note="x" * 2001))
    at = await client.post(REQUESTS, json=ask(vera, note="x" * 2000))

    assert (field_error(over)[:2], at.status_code) == ((422, ["body", "note"]), 201)


# --- Cancel (DL-228, DL-231) --------------------------------------------------------------------


async def test_cancelling_sets_cancelled_and_completed_at_and_is_logged(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    item = await requirement(t)
    request = await request_on(t, item, admin)

    response = await client.post(f"/api/approval-requests/{request.id}/cancel")

    assert response.json()["status"] == "cancelled"
    row = await stored(session, request.id)
    assert (row.status, row.completed_at is not None) == (ApprovalRequestStatus.CANCELLED, True)
    assert await logged(session, request.id) == [
        (ActivityAction.UPDATED, ActivityField.STATUS, "pending", "cancelled", admin.id)
    ]


@pytest.mark.parametrize(
    "status",
    [
        ApprovalRequestStatus.APPROVED,
        ApprovalRequestStatus.REJECTED,
        ApprovalRequestStatus.CANCELLED,
    ],
)
async def test_cancelling_a_request_that_isnt_pending_is_a_422_and_changes_nothing(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    admin: User,
    status: ApprovalRequestStatus,
) -> None:
    item = await requirement(t)
    request = await request_on(t, item, admin, status=status, completed_at=datetime.now(UTC))

    response = await client.post(f"/api/approval-requests/{request.id}/cancel")

    assert field_error(response) == (422, ["path", "id"], "not_pending")
    assert ((await stored(session, request.id)).status, await logged(session, request.id)) == (
        status,
        [],
    )


@pytest.mark.parametrize(
    ("status", "offered"),
    [(ApprovalRequestStatus.PENDING, True), (ApprovalRequestStatus.CANCELLED, False)],
)
async def test_a_request_offers_cancel_only_while_it_is_pending(
    client: AsyncClient, t: Tenancy, admin: User, status: ApprovalRequestStatus, offered: bool
) -> None:
    """DL-231. Bug: `allowed_actions` from `authorize()` alone."""
    item = await requirement(t)
    request = await request_on(t, item, admin, status=status)

    response = await client.get(f"/api/approval-requests/{request.id}")

    assert ("approval_request.cancel" in response.json()["allowed_actions"]) is offered


# --- The list (DL-227) --------------------------------------------------------------------------


async def test_the_list_is_newest_first_offset_paged_and_only_this_requirements(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: oldest first, unpaged, or not filtered by requirement."""
    item = await requirement(t)
    other = await requirement(t, number=8)
    for n in range(3):
        await request_on(t, item, admin, note=f"Round {n}", status=ApprovalRequestStatus.CANCELLED)
    await request_on(t, other, admin, note="Theirs")
    # `created_at` is the transaction's start in a test: backdate each round in order.
    rows = (
        await session.scalars(
            select(ApprovalRequest)
            .where(ApprovalRequest.entity_id == item.id)
            .order_by(ApprovalRequest.id)
        )
    ).all()
    for n, row in enumerate(rows):
        row.created_at = datetime(2026, 10, 1 + n, tzinfo=UTC)
    await session.flush()

    first = (await client.get(REQUESTS, params={"limit": 2})).json()
    second = (await client.get(REQUESTS, params={"limit": 2, "offset": 2})).json()

    assert ([i["note"] for i in first["items"]], first["total"]) == (["Round 2", "Round 1"], 3)
    assert [i["note"] for i in second["items"]] == ["Round 0"]


# --- Archiving cancels pending requests (DL-194) -----------------------------------------------


async def test_archiving_cancels_the_projects_pending_requests_and_unarchiving_keeps_them_so(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: archive leaves them pending, or reaches another project's, or unarchiving reopens
    them (DL-194). Archiving needs an org admin (project.archive is management)."""
    pending = await request_on(t, await requirement(t), admin)
    approved = await request_on(
        t,
        await requirement(t, number=8),
        admin,
        status=ApprovalRequestStatus.APPROVED,
        completed_at=datetime.now(UTC),
    )
    elsewhere_project = await ProjectFactory.create_async(organization=t.org, key="OPS")
    elsewhere = await ApprovalRequestFactory.create_async(
        project=elsewhere_project, requester=admin
    )
    org_admin = await UserFactory.create_async(is_system_admin=False)
    await MembershipFactory.create_async(organization=t.org, user=org_admin, role="admin")
    await sign_in_as(client, org_admin)

    response = await client.post("/api/projects/PMT/archive")

    assert response.status_code == 204
    assert [(await stored(session, r.id)).status for r in (pending, approved, elsewhere)] == [
        ApprovalRequestStatus.CANCELLED,
        ApprovalRequestStatus.APPROVED,
        ApprovalRequestStatus.PENDING,
    ]
    assert await logged(session, pending.id) == [
        (ActivityAction.UPDATED, ActivityField.STATUS, "pending", "cancelled", org_admin.id)
    ]

    unarchived = await client.post("/api/projects/PMT/unarchive")

    # DL-194: unarchiving doesn't reopen them; a project admin re-requests.
    assert unarchived.status_code == 204
    assert ((await stored(session, pending.id)).status, len(await logged(session, pending.id))) == (
        ApprovalRequestStatus.CANCELLED,
        1,
    )


# --- The stale-revision warning (design-doc §6.2, "Stale requests") ----------------------------


async def stale_flags(client: AsyncClient, request: ApprovalRequest) -> tuple[bool, bool]:
    """`newer_revision_exists` on the request's read and on the list's row."""
    one = (await client.get(f"/api/approval-requests/{request.id}")).json()
    listed = (await client.get(REQUESTS)).json()["items"]
    return one["newer_revision_exists"], listed[0]["newer_revision_exists"]


async def test_a_request_on_the_current_revision_has_no_newer_one(
    client: AsyncClient, t: Tenancy, admin: User
) -> None:
    """Bug: the flag is always true, or compares the wrong revisions."""
    request = await request_on(t, await requirement(t), admin)

    assert await stale_flags(client, request) == (False, False)


async def test_a_request_says_when_a_newer_revision_was_saved_since(
    client: AsyncClient, t: Tenancy, admin: User
) -> None:
    """Bound to revision 1, the requirement now at revision 2. Bug: the flag is always false."""
    item = await requirement(t)
    request = await request_on(t, item, admin)
    newer = await RequirementRevisionFactory.create_async(requirement=item, revision_number=2)
    item.current_revision_id = newer.id
    await flush()

    assert await stale_flags(client, request) == (True, True)


# --- A decision's times (design-doc §6.2; schema-doc `approval`, `requirement`) ----------------


async def test_the_completing_decision_records_when_it_was_made_and_when_it_was_approved(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """`decided_at` on the row (the replacement's `approved_by` reads it, §6.2) and `approved_at`
    on the requirement, the instant the request completed. Bug: either left unset or old."""
    vera = await member(t, "Vera Viewer")
    item = await requirement(t)
    item.approved_at = datetime(2026, 9, 1, tzinfo=UTC)
    await flush()
    request = await request_on(t, item, admin)
    await ApprovalFactory.create_async(approval_request=request, approver=vera)
    await sign_in_as(client, vera)

    response = await client.post(
        f"/api/approval-requests/{request.id}/decision", json={"decision": "approved"}
    )

    assert response.status_code == 200
    row = cast(
        Approval,
        await session.scalar(select(Approval).where(Approval.approval_request_id == request.id)),
    )
    stored_request = await stored(session, request.id)
    await session.refresh(item)
    assert row.decided_at is not None
    assert stored_request.completed_at is not None
    assert item.approved_at == stored_request.completed_at


# --- The decision's body (DL-143; design-doc §6.2) ----------------------------------------------


@pytest.mark.parametrize(
    ("body", "loc"),
    [
        ({"decision": "approved", "comment": "x" * 2001}, ["body", "comment"]),
        ({"decision": "pending"}, ["body", "decision"]),
        ({"decision": "replaced"}, ["body", "decision"]),
    ],
)
async def test_a_decision_is_approved_or_rejected_with_a_comment_of_at_most_2000(
    client: AsyncClient, session: AsyncSession, t: Tenancy, body: dict[str, object], loc: list[str]
) -> None:
    """Bug: an approver sets their own row to `pending` again or to `replaced` (a system effect),
    or an unbounded comment."""
    vera = await member(t, "Vera Viewer")
    await sign_in_as(client, vera)
    item = await requirement(t)
    request = await request_on(t, item, vera)
    await ApprovalFactory.create_async(approval_request=request, approver=vera)

    response = await client.post(f"/api/approval-requests/{request.id}/decision", json=body)

    assert (response.status_code, response.json()["details"]["fields"][0]["loc"]) == (422, loc)
    row = await session.scalar(select(Approval).where(Approval.approval_request_id == request.id))
    assert cast(Approval, row).decision is ApprovalDecision.PENDING
