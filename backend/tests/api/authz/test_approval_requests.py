"""Authorization wiring of S2-C10's endpoints (build plan, Slice 2 row 10; design-doc §5 "Role
capabilities", "Other targeted rules" → Approvals; §3.1 export-controlled projects; §6.2;
S2-plan "Actions per row"; DL-227, DL-228):

- `POST /api/projects/{key}/requirements/{number}/approval-requests`
  (`approval_request.create`): 201 to project admins, inherited included; 403 to a member or
  viewer, and in an archived project; 404, naming nothing, to who can't see the project and to an
  inherited admin on an export-controlled project; nothing created when denied;
- `GET …/requirements/{number}/approval-requests` and `GET /api/approval-requests/{id}`
  (`requirement.view` on the approved requirement): viewers and up and inherited admins, an
  archived project included (reads); 404 to who can't see the project and behind the gate; a
  deleted requirement's requests are a 404 on each (DL-228);
- `POST /api/approval-requests/{id}/cancel` (`approval_request.cancel`): 200 to project admins,
  the request then `cancelled`; 403 to a member or viewer (the requester demoted to member
  included); 404 to who can't see the project, behind the gate, and for a deleted requirement's
  request (DL-228); the request stays pending when denied;
- the request read's `allowed_actions` carry `approval_request.cancel` exactly for project
  admins, and the requirement read's carry `approval_request.create` likewise.

Approver eligibility, `pending_exists`, `not_pending`, the activity log, archiving's
cancellations, and the create race are the main session's. Personas are relative to workspace
"Acme Consulting", org "Bolt Foods" (bolt-foods), and project "Payments" (PMT)
(tests/support/authz.py, `persona_user`).
"""

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ApprovalEntityType, ApprovalRequestStatus, ProjectRole, RequirementStatus
from app.models.approval import ApprovalRequest
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
TITLE = "Refunds above the card limit"
NOTE = "Sign-off before the October release"

REQUIREMENT = "/api/projects/PMT/requirements/7"
REQUESTS = "/api/projects/PMT/requirements/7/approval-requests"
MISSING_REQUESTS = "/api/projects/NOPE/requirements/7/approval-requests"
MISSING_REQUEST_ID = uuid.UUID("01900000-0000-7000-8000-000000000000")

CREATE = "approval_request.create"
CANCEL = "approval_request.cancel"


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


async def approver(t: Tenancy) -> User:
    """Ivy Moss, an explicit viewer of PMT: an eligible approver, export-controlled or not
    (§6.2, "Who can be an approver")."""
    ivy = await UserFactory.create_async(
        email="ivy@bolt.example", name="Ivy Moss", is_system_admin=False, is_active=True
    )
    await ProjectMembershipFactory.create_async(
        project=t.project, user=ivy, role=ProjectRole.VIEWER
    )
    return ivy


async def requirement(t: Tenancy, *, deleted_at: datetime | None = None) -> Requirement:
    """RQ-7 in PMT at revision 1, reported by its own member."""
    reporter = await UserFactory.create_async(is_system_admin=False)
    item = await RequirementFactory.create_async(
        project=t.project,
        number=7,
        title=TITLE,
        reporter=reporter,
        parent_requirement_id=None,
        rank="a7",
        status=RequirementStatus.DRAFT,
        deleted_at=deleted_at,
    )
    revision = await RequirementRevisionFactory.create_async(
        requirement=item, revision_number=1, title=TITLE
    )
    item.current_revision_id = revision.id
    # The app reads through its own session: flush what was set after the factory's flush.
    await cast(AsyncSession, BaseFactory.__async_session__).flush()
    return item


async def pending_request(
    t: Tenancy, item: Requirement, *, requested_by: User | None = None
) -> ApprovalRequest:
    """A pending request on `item`'s revision 1, naming Ivy Moss, made by `requested_by` (by
    default another explicit project admin)."""
    if requested_by is None:
        requested_by = await UserFactory.create_async(is_system_admin=False)
        await ProjectMembershipFactory.create_async(
            project=t.project, user=requested_by, role=ProjectRole.ADMIN
        )
    request = await ApprovalRequestFactory.create_async(
        project=t.project,
        entity_type=ApprovalEntityType.REQUIREMENT,
        entity_id=item.id,
        requirement_revision_id=item.current_revision_id,
        status=ApprovalRequestStatus.PENDING,
        note=NOTE,
        requester=requested_by,
        completed_at=None,
    )
    await ApprovalFactory.create_async(approval_request=request, approver=await approver(t))
    return request


async def archive(session: AsyncSession, t: Tenancy) -> None:
    t.project.archived_at = ARCHIVED_AT
    await session.flush()


async def request_count(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(ApprovalRequest))).scalar_one()


async def stored_status(session: AsyncSession, request: ApprovalRequest) -> ApprovalRequestStatus:
    """The request's status, re-read from the database."""
    statement = select(ApprovalRequest.status).where(ApprovalRequest.id == request.id)
    return ApprovalRequestStatus((await session.execute(statement)).scalar_one())


def one(request: ApprovalRequest) -> str:
    return f"/api/approval-requests/{request.id}"


def cancel(request: ApprovalRequest) -> str:
    return f"/api/approval-requests/{request.id}/cancel"


MISSING_ONE = f"/api/approval-requests/{MISSING_REQUEST_ID}"
MISSING_CANCEL = f"/api/approval-requests/{MISSING_REQUEST_ID}/cancel"


def assert_hidden(response: Response, missing: Response) -> None:
    """404 `not_found`, the same body as for something that doesn't exist, naming nothing."""
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    for name in ("Bolt Foods", "bolt-foods", "Payments", "PMT", TITLE, NOTE, "Ivy Moss"):
        assert name not in response.text


def assert_forbidden(response: Response) -> None:
    assert (response.status_code, response.json()["code"]) == (403, "forbidden")


# --- POST …/approval-requests: project admins ----------------------------------------------------


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_a_project_admin_requests_approval(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5 project roles: admin creates approval requests ("Project admin" includes inherited);
    §6.2: bound to the current revision, a pending row per approver."""
    t, user = await signed_in(client, who)
    item = await requirement(t)
    ivy = await approver(t)

    response = await client.post(REQUESTS, json={"approver_ids": [str(ivy.id)]})

    assert response.status_code == 201
    body = response.json()
    assert (body["status"], body["requested_by_id"]) == ("pending", str(user.id))
    assert [(a["approver_id"], a["decision"]) for a in body["approvals"]] == [
        (str(ivy.id), "pending")
    ]
    stored = (await session.execute(select(ApprovalRequest))).scalars().all()
    assert [(r.entity_id, r.requirement_revision_id, r.requested_by) for r in stored] == [
        (item.id, item.current_revision_id, user.id)
    ]


@pytest.mark.parametrize("who", ["project_member", "project_viewer"])
async def test_a_member_or_viewer_may_not_request_approval(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5: creating requests is admin-only; they see the project, so a 403."""
    t, _ = await signed_in(client, who)
    await requirement(t)
    ivy = await approver(t)

    assert_forbidden(await client.post(REQUESTS, json={"approver_ids": [str(ivy.id)]}))
    assert await request_count(session) == 0


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_requesting_approval_is_404_to_who_cannot_see_the_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5: failures on entities the user can't see return 404, not 403."""
    t, _ = await signed_in(client, who)
    await requirement(t)
    body = {"approver_ids": [str((await approver(t)).id)]}

    response = await client.post(REQUESTS, json=body)

    assert_hidden(response, await client.post(MISSING_REQUESTS, json=body))
    assert await request_count(session) == 0


@pytest.mark.parametrize("who", ["project_admin", "org_admin"])
async def test_requesting_approval_in_an_archived_project_is_403(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5 step 1: every mutation inside an archived project is denied."""
    t, _ = await signed_in(client, who)
    await requirement(t)
    ivy = await approver(t)
    await archive(session, t)

    assert_forbidden(await client.post(REQUESTS, json={"approver_ids": [str(ivy.id)]}))
    assert await request_count(session) == 0


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_requesting_approval_on_an_ec_project_is_404_to_an_inherited_admin(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§3.1: "Every content action denied to them, read or mutation, is a 404"."""
    t, _ = await signed_in(client, who, export_controlled=True)
    await requirement(t)
    body = {"approver_ids": [str((await approver(t)).id)]}

    response = await client.post(REQUESTS, json=body)

    assert_hidden(response, await client.post(MISSING_REQUESTS, json=body))
    assert await request_count(session) == 0


async def test_an_explicit_project_admin_requests_approval_on_an_ec_project(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§3.1: content needs an explicit membership, which they hold."""
    t, user = await signed_in(client, "project_admin", export_controlled=True)
    await requirement(t)
    ivy = await approver(t)

    response = await client.post(REQUESTS, json={"approver_ids": [str(ivy.id)]})

    assert response.status_code == 201
    stored = (await session.execute(select(ApprovalRequest.requested_by))).scalars().all()
    assert stored == [user.id]


# --- GET …/approval-requests (the requirement's list) --------------------------------------------


@pytest.mark.parametrize("who", SEES_THE_PROJECT)
async def test_viewers_and_up_and_inherited_admins_list_a_requirements_requests(
    client: AsyncClient, who: str
) -> None:
    """S2-plan: `requirement.view` on the approved entity (approval requests inherit, §3.1)."""
    t, _ = await signed_in(client, who)
    request = await pending_request(t, await requirement(t))

    response = await client.get(REQUESTS)

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [str(request.id)]


async def test_a_requirements_requests_stay_listed_in_an_archived_project(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Archiving denies mutations (§5 step 1), not reads."""
    t, _ = await signed_in(client, "project_viewer")
    request = await pending_request(t, await requirement(t))
    await archive(session, t)

    response = await client.get(REQUESTS)

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [str(request.id)]


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_a_requirements_requests_are_404_to_who_cannot_see_the_project(
    client: AsyncClient, who: str
) -> None:
    t, _ = await signed_in(client, who)
    await pending_request(t, await requirement(t))

    assert_hidden(await client.get(REQUESTS), await client.get(MISSING_REQUESTS))


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_a_requirements_requests_on_an_ec_project_are_404_to_an_inherited_admin(
    client: AsyncClient, who: str
) -> None:
    t, _ = await signed_in(client, who, export_controlled=True)
    await pending_request(t, await requirement(t))

    assert_hidden(await client.get(REQUESTS), await client.get(MISSING_REQUESTS))


async def test_an_explicit_viewer_lists_a_requirements_requests_on_an_ec_project(
    client: AsyncClient,
) -> None:
    t, _ = await signed_in(client, "project_viewer", export_controlled=True)
    request = await pending_request(t, await requirement(t))

    response = await client.get(REQUESTS)

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [str(request.id)]


async def test_a_deleted_requirements_requests_list_is_404(client: AsyncClient) -> None:
    """DL-228: a deleted requirement's approval requests are a 404, as its history is."""
    t, _ = await signed_in(client, "project_admin")
    await pending_request(t, await requirement(t, deleted_at=DELETED_AT))

    assert_hidden(await client.get(REQUESTS), await client.get(MISSING_REQUESTS))


# --- GET /api/approval-requests/{id} -------------------------------------------------------------


@pytest.mark.parametrize("who", SEES_THE_PROJECT)
async def test_viewers_and_up_and_inherited_admins_read_a_request(
    client: AsyncClient, who: str
) -> None:
    t, _ = await signed_in(client, who)
    request = await pending_request(t, await requirement(t))

    response = await client.get(one(request))

    assert response.status_code == 200
    assert (response.json()["id"], response.json()["note"]) == (str(request.id), NOTE)


async def test_a_request_stays_readable_in_an_archived_project(
    client: AsyncClient, session: AsyncSession
) -> None:
    t, _ = await signed_in(client, "project_viewer")
    request = await pending_request(t, await requirement(t))
    await archive(session, t)

    response = await client.get(one(request))

    assert response.status_code == 200
    assert response.json()["id"] == str(request.id)


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_a_request_is_404_to_who_cannot_see_the_project(
    client: AsyncClient, who: str
) -> None:
    t, _ = await signed_in(client, who)
    request = await pending_request(t, await requirement(t))

    assert_hidden(await client.get(one(request)), await client.get(MISSING_ONE))


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_a_request_on_an_ec_project_is_404_to_an_inherited_admin(
    client: AsyncClient, who: str
) -> None:
    t, _ = await signed_in(client, who, export_controlled=True)
    request = await pending_request(t, await requirement(t))

    assert_hidden(await client.get(one(request)), await client.get(MISSING_ONE))


async def test_an_explicit_viewer_reads_a_request_on_an_ec_project(client: AsyncClient) -> None:
    t, _ = await signed_in(client, "project_viewer", export_controlled=True)
    request = await pending_request(t, await requirement(t))

    response = await client.get(one(request))

    assert response.status_code == 200
    assert response.json()["id"] == str(request.id)


async def test_a_deleted_requirements_request_is_404(client: AsyncClient) -> None:
    """DL-228: a 404 on every request URL, a request's read included."""
    t, _ = await signed_in(client, "project_admin")
    request = await pending_request(t, await requirement(t, deleted_at=DELETED_AT))

    assert_hidden(await client.get(one(request)), await client.get(MISSING_ONE))


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_a_project_admins_request_actions_include_cancel(
    client: AsyncClient, who: str
) -> None:
    """API conventions: single-entity reads return `allowed_actions` through `authorize()`."""
    t, _ = await signed_in(client, who)
    request = await pending_request(t, await requirement(t))

    response = await client.get(one(request))

    assert response.status_code == 200
    assert CANCEL in response.json()["allowed_actions"]


@pytest.mark.parametrize("who", ["project_member", "project_viewer"])
async def test_a_member_or_viewers_request_actions_leave_out_cancel(
    client: AsyncClient, who: str
) -> None:
    t, _ = await signed_in(client, who)
    request = await pending_request(t, await requirement(t))

    response = await client.get(one(request))

    assert response.status_code == 200
    assert CANCEL not in response.json()["allowed_actions"]


# --- POST /api/approval-requests/{id}/cancel -----------------------------------------------------


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_a_project_admin_cancels_a_pending_request(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5, §6.2: project admins cancel requests (inherited included)."""
    t, _ = await signed_in(client, who)
    request = await pending_request(t, await requirement(t))

    response = await client.post(cancel(request))

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert await stored_status(session, request) is ApprovalRequestStatus.CANCELLED


@pytest.mark.parametrize("who", ["project_member", "project_viewer"])
async def test_a_member_or_viewer_may_not_cancel_a_request(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """They see the project, so a 403; the request stays pending."""
    t, _ = await signed_in(client, who)
    request = await pending_request(t, await requirement(t))

    assert_forbidden(await client.post(cancel(request)))
    assert await stored_status(session, request) is ApprovalRequestStatus.PENDING


async def test_the_requester_demoted_to_member_may_not_cancel_their_request(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Cancelling is a project-admin action, not the requester's (not a personal action)."""
    t, user = await signed_in(client, "project_member")
    request = await pending_request(t, await requirement(t), requested_by=user)

    assert_forbidden(await client.post(cancel(request)))
    assert await stored_status(session, request) is ApprovalRequestStatus.PENDING


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_cancelling_is_404_to_who_cannot_see_the_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    request = await pending_request(t, await requirement(t))

    assert_hidden(await client.post(cancel(request)), await client.post(MISSING_CANCEL))
    assert await stored_status(session, request) is ApprovalRequestStatus.PENDING


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_cancelling_on_an_ec_project_is_404_to_an_inherited_admin(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who, export_controlled=True)
    request = await pending_request(t, await requirement(t))

    assert_hidden(await client.post(cancel(request)), await client.post(MISSING_CANCEL))
    assert await stored_status(session, request) is ApprovalRequestStatus.PENDING


async def test_an_explicit_project_admin_cancels_on_an_ec_project(
    client: AsyncClient, session: AsyncSession
) -> None:
    t, _ = await signed_in(client, "project_admin", export_controlled=True)
    request = await pending_request(t, await requirement(t))

    assert (await client.post(cancel(request))).status_code == 200
    assert await stored_status(session, request) is ApprovalRequestStatus.CANCELLED


async def test_cancelling_a_deleted_requirements_request_is_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-228: a 404 on every request URL, cancel included."""
    t, _ = await signed_in(client, "project_admin")
    request = await pending_request(t, await requirement(t, deleted_at=DELETED_AT))

    assert_hidden(await client.post(cancel(request)), await client.post(MISSING_CANCEL))
    assert await stored_status(session, request) is ApprovalRequestStatus.PENDING


@pytest.mark.parametrize("who", ["project_admin", "org_admin"])
async def test_cancelling_in_an_archived_project_is_403(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5 step 1: every mutation inside an archived project is denied. (Archiving cancels
    pending requests, DL-194; the row is set up pending only to prove the check comes first.)"""
    t, _ = await signed_in(client, who)
    request = await pending_request(t, await requirement(t))
    await archive(session, t)

    assert_forbidden(await client.post(cancel(request)))
    assert await stored_status(session, request) is ApprovalRequestStatus.PENDING


# --- The requirement read offers Request approval only to project admins -------------------------


@pytest.mark.parametrize(
    ("who", "offered"),
    [
        ("project_admin", True),
        ("org_admin", True),
        ("project_member", False),
        ("project_viewer", False),
    ],
)
async def test_the_requirement_read_offers_create_exactly_to_project_admins(
    client: AsyncClient, who: str, offered: bool
) -> None:
    """API conventions: `allowed_actions` evaluated through `authorize()`, so the UI hides what
    the user can't do."""
    t, _ = await signed_in(client, who)
    await requirement(t)

    response = await client.get(REQUIREMENT)

    assert response.status_code == 200
    assert (CREATE in response.json()["allowed_actions"]) is offered
