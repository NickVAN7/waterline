"""Authorization wiring of S2-C11's endpoints (build plan, Slice 2 row 11 and "Approvals (§6.2)";
design-doc §5 "The choke point" → "Personal actions", "Requirement approval by hand", "Other
targeted rules" → Approvals; §3.1 export-controlled projects; §6.2; DL-161, DL-212, DL-230,
DL-233, DL-234):

- `POST /api/approval-requests/{id}/decision` (`approval.decide`, personal): 200 to the named
  approver whose own row is pending, with content access, whatever their role (viewers
  included); 403 to anyone else who sees the project (admins of every level included), to a
  named approver who has already decided (before any 422 `not_pending`) or whose row was
  replaced and who has access again, and in an archived project; 404, naming nothing, to who
  can't see the project (a replaced approver who lost access included), to a named inherited
  admin on an export-controlled project, and for a deleted requirement's request; a 422
  `not_pending` on `["path", "id"]` to a named approver whose row is pending on a request that
  isn't; nothing changes when refused;
- the request read's `allowed_actions` carry `approval.decide` only while the request is pending
  and the caller's own row is (DL-233);
- `POST /api/projects/{key}/requirements/{number}/approve` (`requirement.approve_manually`):
  200 to project admins, inherited included, the requirement then approved at its current
  revision by them; 403 to a member or viewer, and in an archived project; 404 to who can't see
  the project and to an inherited admin on an export-controlled project; nothing changes when
  refused.

Personas are relative to workspace "Acme Consulting", org "Bolt Foods" (bolt-foods), and project
"Payments" (PMT) (tests/support/authz.py, `persona_user`).
"""

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    ApprovalDecision,
    ApprovalEntityType,
    ApprovalRequestStatus,
    ProjectRole,
    RequirementStatus,
)
from app.models.approval import Approval, ApprovalRequest
from app.models.requirement import Requirement
from app.models.user import User
from tests.factories import BaseFactory
from tests.factories.approval import ApprovalFactory, ApprovalRequestFactory
from tests.factories.org import OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory, RequirementRevisionFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

INHERITED_ADMINS = ["system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"]
PROJECT_ADMINS = [*INHERITED_ADMINS, "project_admin"]
SEES_THE_PROJECT = [*PROJECT_ADMINS, "project_member", "project_viewer"]
PROJECT_UNSEEN = [
    "org_member",
    "other_project_admin",
    "workspace_member",
    "other_org_owner",
    "other_workspace_owner",
    "nobody",
]

ARCHIVED_AT = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)
DELETED_AT = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
DECIDED_AT = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)
TITLE = "Refunds above the card limit"
NOTE = "Sign-off before the October release"
EARLIER_COMMENT = "Looks right to me"

APPROVE = "/api/projects/PMT/requirements/7/approve"
MISSING_APPROVE = "/api/projects/NOPE/requirements/7/approve"
MISSING_REQUEST_ID = uuid.UUID("01900000-0000-7000-8000-000000000000")
MISSING_DECISION = f"/api/approval-requests/{MISSING_REQUEST_ID}/decision"

DECIDE = "approval.decide"
APPROVED = {"decision": "approved", "comment": "Matches the signed spec"}

PENDING = ApprovalDecision.PENDING


async def flush() -> None:
    # The app reads through its own session: flush what was set after a factory's flush.
    await cast(AsyncSession, BaseFactory.__async_session__).flush()


async def signed_in(
    client: AsyncClient, who: str, *, export_controlled: bool = False
) -> tuple[Tenancy, User]:
    """`who` signed in, relative to "Payments" (PMT)."""
    workspace = await WorkspaceFactory.create_async(name="Acme Consulting", slug="acme")
    org = await OrganizationFactory.create_async(
        workspace=workspace, name="Bolt Foods", slug="bolt-foods"
    )
    project = await ProjectFactory.create_async(
        organization=org,
        key="PMT",
        name="Payments",
        restriction_level=None,
        restriction_categories=["export_controlled"] if export_controlled else [],
    )
    t = Tenancy(workspace, org, project)
    user = await persona_user(t, who)
    await sign_in_as(client, user)
    return t, user


async def ivy(t: Tenancy) -> User:
    """Ivy Moss, an explicit viewer of PMT: another named approver."""
    user = await UserFactory.create_async(
        email="ivy@bolt.example", name="Ivy Moss", is_system_admin=False, is_active=True
    )
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.VIEWER
    )
    return user


async def requirement(t: Tenancy, *, deleted_at: datetime | None = None) -> Requirement:
    """RQ-7 in PMT, a draft at revision 1, never approved, reported by its own member."""
    reporter = await UserFactory.create_async(is_system_admin=False)
    item = await RequirementFactory.create_async(
        project=t.project,
        number=7,
        title=TITLE,
        reporter=reporter,
        parent_requirement_id=None,
        rank="a7",
        status=RequirementStatus.DRAFT,
        approved_revision_id=None,
        approved_by=None,
        approved_at=None,
        deleted_at=deleted_at,
    )
    revision = await RequirementRevisionFactory.create_async(
        requirement=item, revision_number=1, title=TITLE
    )
    item.current_revision_id = revision.id
    await flush()
    return item


async def request_naming(
    t: Tenancy,
    item: Requirement,
    *rows: tuple[User, ApprovalDecision],
    status: ApprovalRequestStatus = ApprovalRequestStatus.PENDING,
) -> ApprovalRequest:
    """A request on `item`'s revision 1, made by another explicit project admin, with one row per
    `(approver, decision)`; a decided row has a comment and `decided_at`."""
    requester = await UserFactory.create_async(is_system_admin=False)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=requester, role=ProjectRole.ADMIN
    )
    request = await ApprovalRequestFactory.create_async(
        project=t.project,
        entity_type=ApprovalEntityType.REQUIREMENT,
        entity_id=item.id,
        requirement_revision_id=item.current_revision_id,
        status=status,
        note=NOTE,
        requester=requester,
        completed_at=None if status is ApprovalRequestStatus.PENDING else DECIDED_AT,
    )
    for approver, decision in rows:
        decided = decision in (ApprovalDecision.APPROVED, ApprovalDecision.REJECTED)
        await ApprovalFactory.create_async(
            approval_request=request,
            approver=approver,
            decision=decision,
            comment=EARLIER_COMMENT if decided else None,
            decided_at=DECIDED_AT if decided else None,
        )
    return request


async def archive(session: AsyncSession, t: Tenancy) -> None:
    t.project.archived_at = ARCHIVED_AT
    await session.flush()


def decision_url(request: ApprovalRequest) -> str:
    return f"/api/approval-requests/{request.id}/decision"


async def decisions(session: AsyncSession, request: ApprovalRequest) -> dict[uuid.UUID, object]:
    """Each row's `(decision, comment)` by approver, re-read from the database."""
    result = await session.execute(
        select(Approval.approver_id, Approval.decision, Approval.comment)
        .where(Approval.approval_request_id == request.id)
        .execution_options(populate_existing=True)
    )
    return {who: (ApprovalDecision(d), comment) for who, d, comment in result.all()}


async def stored_status(session: AsyncSession, request: ApprovalRequest) -> ApprovalRequestStatus:
    statement = select(ApprovalRequest.status).where(ApprovalRequest.id == request.id)
    return ApprovalRequestStatus((await session.execute(statement)).scalar_one())


async def approval_state(session: AsyncSession, item: Requirement) -> tuple[object, ...]:
    """The requirement's `(status, approved_revision_id, approved_by)`, re-read."""
    row = (
        await session.execute(
            select(
                Requirement.status, Requirement.approved_revision_id, Requirement.approved_by
            ).where(Requirement.id == item.id)
        )
    ).one()
    return (RequirementStatus(row[0]), row[1], row[2])


def assert_hidden(response: Response, missing: Response) -> None:
    """404 `not_found`, the same body as for something that doesn't exist, naming nothing."""
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    for name in ("Bolt Foods", "bolt-foods", "Payments", "PMT", TITLE, NOTE, "Ivy Moss"):
        assert name not in response.text


def assert_forbidden(response: Response) -> None:
    assert (response.status_code, response.json()["code"]) == (403, "forbidden")


# --- POST …/decision: the named approver, own row pending ----------------------------------------


@pytest.mark.parametrize("who", SEES_THE_PROJECT)
async def test_the_named_approver_decides_their_own_row(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§6.2: approvers may hold any role, viewers included; each decides only their own row. Ivy
    is still pending, so the request stays pending (every approver must approve)."""
    t, user = await signed_in(client, who)
    other = await ivy(t)
    request = await request_naming(t, await requirement(t), (user, PENDING), (other, PENDING))

    response = await client.post(decision_url(request), json=APPROVED)

    assert response.status_code == 200
    assert await decisions(session, request) == {
        user.id: (ApprovalDecision.APPROVED, "Matches the signed spec"),
        other.id: (PENDING, None),
    }
    assert await stored_status(session, request) is ApprovalRequestStatus.PENDING


@pytest.mark.parametrize("who", SEES_THE_PROJECT)
async def test_nobody_decides_on_another_approvers_row(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5: "nobody, including project, org, or workspace admins, or system admins, decides on
    another approver's behalf"; they see the request, so a 403."""
    t, _ = await signed_in(client, who)
    other = await ivy(t)
    request = await request_naming(t, await requirement(t), (other, PENDING))

    assert_forbidden(await client.post(decision_url(request), json=APPROVED))
    assert await decisions(session, request) == {other.id: (PENDING, None)}
    assert await stored_status(session, request) is ApprovalRequestStatus.PENDING


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_deciding_is_404_to_a_named_approver_who_cannot_see_the_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5: a personal action needs content access; failures on what the user can't see are 404."""
    t, user = await signed_in(client, who)
    other = await ivy(t)
    request = await request_naming(t, await requirement(t), (user, PENDING), (other, PENDING))

    response = await client.post(decision_url(request), json=APPROVED)

    assert_hidden(response, await client.post(MISSING_DECISION, json=APPROVED))
    assert await decisions(session, request) == {
        user.id: (PENDING, None),
        other.id: (PENDING, None),
    }


async def test_a_replaced_approver_who_lost_access_gets_a_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-234: an approver whose row was replaced has lost content access, so a 404."""
    t, user = await signed_in(client, "nobody")
    other = await ivy(t)
    request = await request_naming(
        t, await requirement(t), (user, ApprovalDecision.REPLACED), (other, PENDING)
    )

    response = await client.post(decision_url(request), json=APPROVED)

    assert_hidden(response, await client.post(MISSING_DECISION, json=APPROVED))
    assert (await decisions(session, request))[user.id] == (ApprovalDecision.REPLACED, None)


async def test_a_replaced_approver_with_access_again_gets_a_403(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-234: "a 403 only once they have access again"."""
    t, user = await signed_in(client, "project_viewer")
    other = await ivy(t)
    request = await request_naming(
        t, await requirement(t), (user, ApprovalDecision.REPLACED), (other, PENDING)
    )

    assert_forbidden(await client.post(decision_url(request), json=APPROVED))
    assert (await decisions(session, request))[user.id] == (ApprovalDecision.REPLACED, None)


@pytest.mark.parametrize(
    ("earlier", "status"),
    [
        # Ivy is still pending, so the request is too.
        (ApprovalDecision.APPROVED, ApprovalRequestStatus.PENDING),
        # The caller's own rejection rejected the request.
        (ApprovalDecision.REJECTED, ApprovalRequestStatus.REJECTED),
    ],
)
async def test_deciding_again_after_ones_own_row_is_decided_is_403(
    client: AsyncClient,
    session: AsyncSession,
    earlier: ApprovalDecision,
    status: ApprovalRequestStatus,
) -> None:
    """DL-234, DL-195: decisions are final: a 403, the row unchanged."""
    t, user = await signed_in(client, "project_viewer")
    other = await ivy(t)
    request = await request_naming(
        t, await requirement(t), (user, earlier), (other, PENDING), status=status
    )

    response = await client.post(decision_url(request), json={"decision": "rejected"})

    assert_forbidden(response)
    assert (await decisions(session, request))[user.id] == (earlier, EARLIER_COMMENT)
    assert await stored_status(session, request) is status


async def test_a_decided_approver_on_a_request_that_isnt_pending_gets_403_not_422(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-234: `authorize()` runs first, so the 403 comes before any 422 `not_pending`. The
    caller approved; Ivy rejected, which rejected the request."""
    t, user = await signed_in(client, "project_member")
    other = await ivy(t)
    request = await request_naming(
        t,
        await requirement(t),
        (user, ApprovalDecision.APPROVED),
        (other, ApprovalDecision.REJECTED),
        status=ApprovalRequestStatus.REJECTED,
    )

    assert_forbidden(await client.post(decision_url(request), json=APPROVED))
    assert await stored_status(session, request) is ApprovalRequestStatus.REJECTED


@pytest.mark.parametrize(
    ("status", "others"),
    [
        # Ivy rejected, which rejected the request.
        (ApprovalRequestStatus.REJECTED, ApprovalDecision.REJECTED),
        # A project admin cancelled it.
        (ApprovalRequestStatus.CANCELLED, PENDING),
    ],
)
async def test_a_pending_row_on_a_request_that_isnt_pending_is_a_422_not_pending(
    client: AsyncClient,
    session: AsyncSession,
    status: ApprovalRequestStatus,
    others: ApprovalDecision,
) -> None:
    """DL-230, DL-234: the 422 `not_pending` on `["path", "id"]` is for a named approver whose
    own row is still pending on a request that isn't."""
    t, user = await signed_in(client, "project_viewer")
    other = await ivy(t)
    request = await request_naming(
        t, await requirement(t), (user, PENDING), (other, others), status=status
    )

    response = await client.post(decision_url(request), json=APPROVED)

    assert (response.status_code, response.json()["code"]) == (422, "validation_error")
    (error,) = response.json()["details"]["fields"]
    assert (error["loc"], error["type"]) == (["path", "id"], "not_pending")
    assert (await decisions(session, request))[user.id] == (PENDING, None)
    assert await stored_status(session, request) is status


@pytest.mark.parametrize("who", ["project_viewer", "project_admin", "org_admin"])
async def test_deciding_in_an_archived_project_is_403(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5: a personal action inside an archived project is denied like any other mutation.
    (Archiving cancels pending requests, DL-194; the rows are set up pending only to prove the
    check comes first.)"""
    t, user = await signed_in(client, who)
    other = await ivy(t)
    request = await request_naming(t, await requirement(t), (user, PENDING), (other, PENDING))
    await archive(session, t)

    assert_forbidden(await client.post(decision_url(request), json=APPROVED))
    assert (await decisions(session, request))[user.id] == (PENDING, None)


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_deciding_on_an_ec_project_is_404_to_a_named_inherited_admin(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§3.1, §5: content access there is an explicit membership; without it, a 404."""
    t, user = await signed_in(client, who, export_controlled=True)
    other = await ivy(t)
    request = await request_naming(t, await requirement(t), (user, PENDING), (other, PENDING))

    response = await client.post(decision_url(request), json=APPROVED)

    assert_hidden(response, await client.post(MISSING_DECISION, json=APPROVED))
    assert (await decisions(session, request))[user.id] == (PENDING, None)


async def test_a_named_explicit_viewer_decides_on_an_ec_project(
    client: AsyncClient, session: AsyncSession
) -> None:
    t, user = await signed_in(client, "project_viewer", export_controlled=True)
    other = await ivy(t)
    request = await request_naming(t, await requirement(t), (user, PENDING), (other, PENDING))

    response = await client.post(decision_url(request), json={"decision": "rejected"})

    assert response.status_code == 200
    assert (await decisions(session, request))[user.id] == (ApprovalDecision.REJECTED, None)


async def test_deciding_a_deleted_requirements_request_is_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-230: a deleted requirement's request is a 404, as for cancel (DL-228)."""
    t, user = await signed_in(client, "project_viewer")
    other = await ivy(t)
    item = await requirement(t, deleted_at=DELETED_AT)
    request = await request_naming(t, item, (user, PENDING), (other, PENDING))

    response = await client.post(decision_url(request), json=APPROVED)

    assert_hidden(response, await client.post(MISSING_DECISION, json=APPROVED))
    assert (await decisions(session, request))[user.id] == (PENDING, None)


# --- The request read offers Decide only for the caller's own pending row (DL-233) --------------


@pytest.mark.parametrize(
    ("own", "status", "offered"),
    [
        (PENDING, ApprovalRequestStatus.PENDING, True),
        (ApprovalDecision.APPROVED, ApprovalRequestStatus.PENDING, False),
        (ApprovalDecision.REPLACED, ApprovalRequestStatus.PENDING, False),
        # Their row still pending, but the request isn't: ruled out for good (DL-232).
        (PENDING, ApprovalRequestStatus.CANCELLED, False),
    ],
)
async def test_the_request_read_offers_decide_only_while_the_callers_own_row_is_pending(
    client: AsyncClient, own: ApprovalDecision, status: ApprovalRequestStatus, offered: bool
) -> None:
    t, user = await signed_in(client, "project_viewer")
    other = await ivy(t)
    request = await request_naming(
        t, await requirement(t), (user, own), (other, PENDING), status=status
    )

    response = await client.get(f"/api/approval-requests/{request.id}")

    assert response.status_code == 200
    assert (DECIDE in response.json()["allowed_actions"]) is offered


@pytest.mark.parametrize("who", ["system_admin", "org_admin", "project_admin"])
async def test_an_admins_request_read_leaves_out_decide_on_someone_elses_rows(
    client: AsyncClient, who: str
) -> None:
    t, _ = await signed_in(client, who)
    request = await request_naming(t, await requirement(t), (await ivy(t), PENDING))

    response = await client.get(f"/api/approval-requests/{request.id}")

    assert response.status_code == 200
    assert DECIDE not in response.json()["allowed_actions"]


# --- POST …/approve: project admins, inherited included ------------------------------------------


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_a_project_admin_approves_a_requirement_by_hand(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5 "Requirement approval by hand": `approved_revision_id` the current revision,
    `approved_by` that admin."""
    t, user = await signed_in(client, who)
    item = await requirement(t)

    response = await client.post(APPROVE, json={"version": item.version})

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert await approval_state(session, item) == (
        RequirementStatus.APPROVED,
        item.current_revision_id,
        user.id,
    )


@pytest.mark.parametrize("who", ["project_member", "project_viewer"])
async def test_a_member_or_viewer_may_not_approve_by_hand(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5: "members get 403 for that transition"."""
    t, _ = await signed_in(client, who)
    item = await requirement(t)

    assert_forbidden(await client.post(APPROVE, json={"version": item.version}))
    assert await approval_state(session, item) == (RequirementStatus.DRAFT, None, None)


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_approving_by_hand_is_404_to_who_cannot_see_the_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    item = await requirement(t)
    body = {"version": item.version}

    response = await client.post(APPROVE, json=body)

    assert_hidden(response, await client.post(MISSING_APPROVE, json=body))
    assert await approval_state(session, item) == (RequirementStatus.DRAFT, None, None)


@pytest.mark.parametrize("who", ["project_admin", "org_admin"])
async def test_approving_by_hand_in_an_archived_project_is_403(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    item = await requirement(t)
    await archive(session, t)

    assert_forbidden(await client.post(APPROVE, json={"version": item.version}))
    assert await approval_state(session, item) == (RequirementStatus.DRAFT, None, None)


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_approving_by_hand_on_an_ec_project_is_404_to_an_inherited_admin(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who, export_controlled=True)
    item = await requirement(t)
    body = {"version": item.version}

    response = await client.post(APPROVE, json=body)

    assert_hidden(response, await client.post(MISSING_APPROVE, json=body))
    assert await approval_state(session, item) == (RequirementStatus.DRAFT, None, None)


async def test_an_explicit_project_admin_approves_by_hand_on_an_ec_project(
    client: AsyncClient, session: AsyncSession
) -> None:
    t, user = await signed_in(client, "project_admin", export_controlled=True)
    item = await requirement(t)

    response = await client.post(APPROVE, json={"version": item.version})

    assert response.status_code == 200
    assert await approval_state(session, item) == (
        RequirementStatus.APPROVED,
        item.current_revision_id,
        user.id,
    )
