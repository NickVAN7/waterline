"""My work's approvals section (design-doc §11; DL-236; build plan S2-C14): the caller's
pending approvals, oldest request first, each showing the revision under approval; rows and
requests not pending, deleted requirements, archived projects, and projects whose content the
caller can't see are left out. And a section whose query fails is unavailable while the others
still show (TD-40)."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import Select, text

from app.authz.scoping import Scope
from app.enums import (
    ApprovalDecision,
    ApprovalEntityType,
    ApprovalRequestStatus,
    ProjectRole,
    RestrictionCategory,
)
from app.models.approval import Approval, ApprovalRequest
from app.models.project import Project
from app.models.requirement import Requirement, RequirementRevision
from app.models.user import User
from app.repositories.approval import ApprovalRepository
from tests.api.test_approval_decisions import flush, viewer
from tests.api.test_approver_replacement import ada, org_admin, t
from tests.factories.approval import ApprovalFactory, ApprovalRequestFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory, RequirementRevisionFactory
from tests.factories.user import UserFactory
from tests.support.authz import Tenancy, sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

__all__ = ["ada", "t"]  # fixtures, used by name

WORK = "/api/me/work"
APPROVALS = "/api/me/work/approvals"
PENDING = ApprovalDecision.PENDING
MONDAY = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
TUESDAY = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)


async def requirement_at(
    project: Project, number: int, *, revision_title: str, current_title: str
) -> tuple[Requirement, RequirementRevision]:
    """A requirement at revision 2, whose revision 2 is titled `revision_title` and whose
    current title is `current_title` (an edit after the request)."""
    item = await RequirementFactory.create_async(
        project=project, number=number, title=current_title, approved_revision_id=None
    )
    await RequirementRevisionFactory.create_async(requirement=item, revision_number=1)
    revision = await RequirementRevisionFactory.create_async(
        requirement=item, revision_number=2, title=revision_title
    )
    item.current_revision_id = revision.id
    await flush()
    return item, revision


async def asked(
    project: Project,
    requester: User,
    item: Requirement,
    revision: RequirementRevision,
    approver: User,
    *,
    at: datetime = MONDAY,
    decision: ApprovalDecision = PENDING,
    status: ApprovalRequestStatus = ApprovalRequestStatus.PENDING,
    note: str | None = None,
) -> ApprovalRequest:
    """A request by `requester` on `item` at `revision`, made `at`, naming `approver`."""
    request = await ApprovalRequestFactory.create_async(
        project=project,
        entity_type=ApprovalEntityType.REQUIREMENT,
        entity_id=item.id,
        requirement_revision_id=revision.id,
        status=status,
        requester=requester,
        completed_at=None,
        note=note,
    )
    request.created_at = at
    await ApprovalFactory.create_async(
        approval_request=request, approver=approver, decision=decision, decided_at=None
    )
    await flush()
    return request


async def listed(client: AsyncClient) -> list[str]:
    """The listed requests' titles, in order."""
    response = await client.get(APPROVALS)
    assert response.status_code == 200
    return [item["title"] for item in response.json()["items"]]


# --- What an item shows ---------------------------------------------------------------------


async def test_an_item_shows_the_revision_under_approval_and_where_it_is(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """DL-236: the item's fields, with the revision's own title and number, not the
    requirement's current title. Bug: the title read from the requirement."""
    vera = await viewer(t, "Vera Viewer")
    item, revision = await requirement_at(
        t.project, 7, revision_title="Three-way match", current_title="Three-way match, edited"
    )
    request = await asked(t.project, ada, item, revision, vera, note="Before Friday, please")
    await sign_in_as(client, vera)

    response = await client.get(APPROVALS)

    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "request_id": str(request.id),
            "requested_at": "2026-10-05T09:00:00Z",
            "requested_by_id": str(ada.id),
            "requested_by_name": "Ada Admin",
            "note": "Before Friday, please",
            "entity_type": "requirement",
            "entity_number": 7,
            "title": "Three-way match",
            "revision_number": 2,
            "project_key": "PMT",
            "project_name": "Payments",
            "organization_slug": "bolt-foods",
        }
    ]


async def test_the_oldest_request_comes_first(client: AsyncClient, t: Tenancy, ada: User) -> None:
    """DL-236: oldest first, the longest wait on top. Bug: newest first, as the requirement's
    own request list (DL-227)."""
    vera = await viewer(t, "Vera Viewer")
    later, later_rev = await requirement_at(t.project, 8, revision_title="Later", current_title="x")
    first, first_rev = await requirement_at(t.project, 9, revision_title="First", current_title="y")
    await asked(t.project, ada, later, later_rev, vera, at=TUESDAY)
    await asked(t.project, ada, first, first_rev, vera, at=MONDAY)
    await sign_in_as(client, vera)

    assert await listed(client) == ["First", "Later"]


# --- What's left out ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "decision", [ApprovalDecision.APPROVED, ApprovalDecision.REJECTED, ApprovalDecision.REPLACED]
)
async def test_a_row_already_decided_or_replaced_is_left_out(
    client: AsyncClient, t: Tenancy, ada: User, decision: ApprovalDecision
) -> None:
    """DL-236: only rows pending the caller's decision. Bug: the `decision` filter dropped."""
    vera = await viewer(t, "Vera Viewer")
    item, revision = await requirement_at(t.project, 7, revision_title="Gone", current_title="x")
    await asked(t.project, ada, item, revision, vera, decision=decision)
    await sign_in_as(client, vera)

    assert await listed(client) == []


@pytest.mark.parametrize(
    "status",
    [
        ApprovalRequestStatus.APPROVED,
        ApprovalRequestStatus.REJECTED,
        ApprovalRequestStatus.CANCELLED,
    ],
)
async def test_a_request_no_longer_pending_is_left_out(
    client: AsyncClient, t: Tenancy, ada: User, status: ApprovalRequestStatus
) -> None:
    """DL-236: a cancelled request leaves its rows pending (§6.2), so the request's own status
    is checked too. Bug: only the row's decision is filtered."""
    vera = await viewer(t, "Vera Viewer")
    item, revision = await requirement_at(t.project, 7, revision_title="Gone", current_title="x")
    await asked(t.project, ada, item, revision, vera, status=status)
    await sign_in_as(client, vera)

    assert await listed(client) == []


async def test_a_deleted_requirements_request_is_left_out(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """DL-236 (its requests are a 404, DL-228). Bug: the requirement joined without the
    soft-delete filter."""
    vera = await viewer(t, "Vera Viewer")
    item, revision = await requirement_at(t.project, 7, revision_title="Gone", current_title="x")
    await asked(t.project, ada, item, revision, vera)
    item.deleted_at = TUESDAY
    await flush()
    await sign_in_as(client, vera)

    assert await listed(client) == []


async def test_an_archived_projects_request_is_left_out(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """§11, DL-236: archived projects and every item in them. Archiving cancels pending
    requests (DL-194), so the row is set up as if one slipped through. Bug: no archived
    filter."""
    vera = await viewer(t, "Vera Viewer")
    item, revision = await requirement_at(t.project, 7, revision_title="Gone", current_title="x")
    await asked(t.project, ada, item, revision, vera)
    t.project.archived_at = TUESDAY
    await flush()
    await sign_in_as(client, vera)

    assert await listed(client) == []


async def test_a_project_the_caller_can_no_longer_open_is_left_out(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """DL-236: a row left pending after its approver lost access (the requester without admin,
    §6.2) is the admin's to handle, not the approver's to see. Bug: rows listed without the
    content scope."""
    vera = await UserFactory.create_async(name="Vera Gone", is_system_admin=False, is_active=True)
    item, revision = await requirement_at(t.project, 7, revision_title="Gone", current_title="x")
    await asked(t.project, ada, item, revision, vera)
    await sign_in_as(client, vera)

    assert await listed(client) == []


async def test_an_export_controlled_project_is_left_out_for_an_inherited_admin(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """§3.1, DL-236: an org admin sees PMT, but not its content once it's export-controlled,
    without an explicit membership. Bug: the project scope used, not the content scope."""
    ivy = await org_admin(t, "Ivy Inherit")
    item, revision = await requirement_at(t.project, 7, revision_title="Hidden", current_title="x")
    await asked(t.project, ada, item, revision, ivy)
    t.project.restriction_categories = [RestrictionCategory.EXPORT_CONTROLLED.value]
    await flush()
    await sign_in_as(client, ivy)

    assert await listed(client) == []


async def test_an_export_controlled_project_is_listed_for_an_explicit_member(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """§3.1: an explicit membership gives the content. Bug: export-controlled projects left out
    for everyone."""
    vera = await viewer(t, "Vera Viewer")
    item, revision = await requirement_at(t.project, 7, revision_title="Shown", current_title="x")
    await asked(t.project, ada, item, revision, vera)
    t.project.restriction_categories = [RestrictionCategory.EXPORT_CONTROLLED.value]
    await flush()
    await sign_in_as(client, vera)

    assert await listed(client) == ["Shown"]


async def test_an_export_controlled_project_is_left_out_for_a_system_admin(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """§3.1, DL-236: a system admin's reach, too, stops at export-controlled content without an
    explicit membership. Bug: the content scope's export-control check skipped for everyone
    with the whole workspace."""
    sam = await UserFactory.create_async(name="Sam System", is_system_admin=True, is_active=True)
    item, revision = await requirement_at(t.project, 7, revision_title="Hidden", current_title="x")
    await asked(t.project, ada, item, revision, sam)
    t.project.restriction_categories = [RestrictionCategory.EXPORT_CONTROLLED.value]
    await flush()
    await sign_in_as(client, sam)

    assert await listed(client) == []


async def test_someone_elses_pending_row_is_left_out(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """DL-236: the caller's own rows only, even where they could decide nothing and see
    everything (an org admin). Bug: the approver filter dropped."""
    vera = await viewer(t, "Vera Viewer")
    otto = await org_admin(t, "Otto Org")
    item, revision = await requirement_at(t.project, 7, revision_title="Vera's", current_title="x")
    await asked(t.project, ada, item, revision, vera)
    await sign_in_as(client, otto)

    assert await listed(client) == []


async def test_another_projects_request_is_listed_with_its_own_project(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """§11: My work is across projects. Bug: the item's project read from the wrong join."""
    vera = await viewer(t, "Vera Viewer")
    other = await ProjectFactory.create_async(organization=t.org, key="OPS", name="Operations")
    await ProjectMembershipFactory.create_async(project=other, user=vera, role=ProjectRole.VIEWER)
    item, revision = await requirement_at(other, 3, revision_title="Ops item", current_title="x")
    await asked(other, ada, item, revision, vera)
    await sign_in_as(client, vera)

    response = await client.get(APPROVALS)

    assert [(i["project_key"], i["entity_number"]) for i in response.json()["items"]] == [
        ("OPS", 3)
    ]


# --- In GET /api/me/work --------------------------------------------------------------------


async def test_my_work_shows_the_first_ten_approvals_and_the_total(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """§11: each section's first 10 items and its total (DL-76). Bug: the section left out of
    the home page's one request, or not limited."""
    vera = await viewer(t, "Vera Viewer")
    for number in range(1, 12):  # setup only
        item, revision = await requirement_at(
            t.project, number, revision_title=f"Item {number:02}", current_title="x"
        )
        await asked(t.project, ada, item, revision, vera)
    await sign_in_as(client, vera)

    approvals = (await client.get(WORK)).json()["sections"]["approvals"]

    assert (approvals["available"], len(approvals["items"]), approvals["total"]) == (True, 10, 11)


async def test_an_approvals_section_whose_query_fails_leaves_the_projects_section(
    client: AsyncClient, t: Tenancy, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TD-40: each section in its own savepoint, so a failed one is unavailable and the rest
    still show. Bug: one savepoint around every section."""
    vera = await viewer(t, "Vera Viewer")
    await sign_in_as(client, vera)
    real = ApprovalRepository.pending_for

    def failing(self: ApprovalRepository, approver_id: object, scope: Scope) -> Select[Approval]:
        # A query Postgres rejects (no such column), so the savepoint really rolls back.
        return real(self, approver_id, scope).where(text("no_such_column = 1"))  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(ApprovalRepository, "pending_for", failing)

    sections = (await client.get(WORK)).json()["sections"]

    assert (sections["approvals"], [p["key"] for p in sections["projects"]["items"]]) == (
        {"available": False, "items": [], "total": 0},
        ["PMT"],
    )
