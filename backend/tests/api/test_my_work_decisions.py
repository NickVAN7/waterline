"""My work's past decisions (design-doc §11; DL-286; build plan S2-C20b): the rows the caller
approved or rejected, newest decision first, each showing the decided revision and the request's
status now; pending and replaced rows, deleted requirements, archived projects, and projects
whose content the caller can't see are left out. And a section whose query fails is
unavailable while the others still show (TD-40)."""

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
from tests.api.test_my_work_approvals import requirement_at
from tests.factories.approval import ApprovalFactory, ApprovalRequestFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.support.authz import Tenancy, sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

__all__ = ["ada", "t"]  # fixtures, used by name

WORK = "/api/me/work"
DECISIONS = "/api/me/work/decisions"
APPROVED = ApprovalDecision.APPROVED
MONDAY = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
TUESDAY = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)


async def decided(
    project: Project,
    requester: User,
    item: Requirement,
    revision: RequirementRevision,
    approver: User,
    *,
    at: datetime = MONDAY,
    decision: ApprovalDecision = APPROVED,
    status: ApprovalRequestStatus = ApprovalRequestStatus.APPROVED,
    comment: str | None = None,
) -> ApprovalRequest:
    """A request by `requester` on `item` at `revision`, in `status`, where `approver` made
    `decision` `at`."""
    request = await ApprovalRequestFactory.create_async(
        project=project,
        entity_type=ApprovalEntityType.REQUIREMENT,
        entity_id=item.id,
        requirement_revision_id=revision.id,
        status=status,
        requester=requester,
        completed_at=None,
        note=None,
    )
    await ApprovalFactory.create_async(
        approval_request=request,
        approver=approver,
        decision=decision,
        decided_at=at,
        comment=comment,
    )
    await flush()
    return request


async def listed(client: AsyncClient) -> list[str]:
    """The listed decisions' titles, in order."""
    response = await client.get(DECISIONS)
    assert response.status_code == 200
    return [item["title"] for item in response.json()["items"]]


# --- What an item shows ---------------------------------------------------------------------


async def test_an_item_shows_the_decision_the_decided_revision_and_the_request_now(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """DL-286: the item's fields, with the decided revision's own title and number, and the
    request's status now (cancelled after the caller approved). Bug: the title read from the
    requirement, or the status from the caller's row."""
    vera = await viewer(t, "Vera Viewer")
    item, revision = await requirement_at(
        t.project, 7, revision_title="Three-way match", current_title="Three-way match, edited"
    )
    request = await decided(
        t.project,
        ada,
        item,
        revision,
        vera,
        status=ApprovalRequestStatus.CANCELLED,
        comment="Fine by me",
    )
    await sign_in_as(client, vera)

    response = await client.get(DECISIONS)

    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "request_id": str(request.id),
            "decision": "approved",
            "decided_at": "2026-10-05T09:00:00Z",
            "comment": "Fine by me",
            "request_status": "cancelled",
            "entity_type": "requirement",
            "entity_number": 7,
            "title": "Three-way match",
            "revision_number": 2,
            "project_key": "PMT",
            "project_name": "Payments",
            "organization_slug": "bolt-foods",
        }
    ]


async def test_the_newest_decision_comes_first(client: AsyncClient, t: Tenancy, ada: User) -> None:
    """DL-286: newest first. Bug: oldest first, as the approvals section (DL-236)."""
    vera = await viewer(t, "Vera Viewer")
    older, older_rev = await requirement_at(t.project, 8, revision_title="Older", current_title="x")
    newer, newer_rev = await requirement_at(t.project, 9, revision_title="Newer", current_title="y")
    await decided(t.project, ada, newer, newer_rev, vera, at=TUESDAY)
    await decided(t.project, ada, older, older_rev, vera, at=MONDAY)
    await sign_in_as(client, vera)

    assert await listed(client) == ["Newer", "Older"]


async def test_a_rejection_is_listed_with_its_comment(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """DL-286: approved or rejected. Bug: only approvals listed."""
    vera = await viewer(t, "Vera Viewer")
    item, revision = await requirement_at(t.project, 7, revision_title="No", current_title="x")
    await decided(
        t.project,
        ada,
        item,
        revision,
        vera,
        decision=ApprovalDecision.REJECTED,
        status=ApprovalRequestStatus.REJECTED,
        comment="Missing the VAT case",
    )
    await sign_in_as(client, vera)

    response = await client.get(DECISIONS)

    assert [
        (i["decision"], i["comment"], i["request_status"]) for i in response.json()["items"]
    ] == [("rejected", "Missing the VAT case", "rejected")]


# --- What's left out ------------------------------------------------------------------------


@pytest.mark.parametrize("decision", [ApprovalDecision.PENDING, ApprovalDecision.REPLACED])
async def test_a_row_not_decided_by_the_caller_is_left_out(
    client: AsyncClient, t: Tenancy, ada: User, decision: ApprovalDecision
) -> None:
    """DL-286: pending and replaced rows aren't decisions. Bug: the `decision` filter dropped,
    or `replaced` counted as decided."""
    vera = await viewer(t, "Vera Viewer")
    item, revision = await requirement_at(t.project, 7, revision_title="Gone", current_title="x")
    await decided(
        t.project,
        ada,
        item,
        revision,
        vera,
        decision=decision,
        status=ApprovalRequestStatus.PENDING,
    )
    await sign_in_as(client, vera)

    assert await listed(client) == []


async def test_a_deleted_requirements_decision_is_left_out(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """DL-286, as DL-236. Bug: the requirement joined without the soft-delete filter."""
    vera = await viewer(t, "Vera Viewer")
    item, revision = await requirement_at(t.project, 7, revision_title="Gone", current_title="x")
    await decided(t.project, ada, item, revision, vera)
    item.deleted_at = TUESDAY
    await flush()
    await sign_in_as(client, vera)

    assert await listed(client) == []


async def test_an_archived_projects_decision_is_left_out(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """§11, DL-286: archived projects and every item in them. Bug: no archived filter."""
    vera = await viewer(t, "Vera Viewer")
    item, revision = await requirement_at(t.project, 7, revision_title="Gone", current_title="x")
    await decided(t.project, ada, item, revision, vera)
    t.project.archived_at = TUESDAY
    await flush()
    await sign_in_as(client, vera)

    assert await listed(client) == []


async def test_a_project_the_caller_can_no_longer_open_is_left_out(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """DL-286: an approver who left the project no longer sees what they decided there. Bug:
    rows listed without the content scope."""
    vera = await UserFactory.create_async(name="Vera Gone", is_system_admin=False, is_active=True)
    item, revision = await requirement_at(t.project, 7, revision_title="Gone", current_title="x")
    await decided(t.project, ada, item, revision, vera)
    await sign_in_as(client, vera)

    assert await listed(client) == []


async def test_an_export_controlled_project_is_left_out_for_an_inherited_admin(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """§3.1, DL-286: an org admin sees PMT, but not its content once it's export-controlled,
    without an explicit membership. Bug: the project scope used, not the content scope."""
    ivy = await org_admin(t, "Ivy Inherit")
    item, revision = await requirement_at(t.project, 7, revision_title="Hidden", current_title="x")
    await decided(t.project, ada, item, revision, ivy)
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
    await decided(t.project, ada, item, revision, vera)
    t.project.restriction_categories = [RestrictionCategory.EXPORT_CONTROLLED.value]
    await flush()
    await sign_in_as(client, vera)

    assert await listed(client) == ["Shown"]


async def test_an_export_controlled_project_is_left_out_for_a_system_admin(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """§3.1, DL-286: a system admin's reach stops at export-controlled content without an
    explicit membership. Bug: the export-control check skipped for the whole workspace."""
    sam = await UserFactory.create_async(name="Sam System", is_system_admin=True, is_active=True)
    item, revision = await requirement_at(t.project, 7, revision_title="Hidden", current_title="x")
    await decided(t.project, ada, item, revision, sam)
    t.project.restriction_categories = [RestrictionCategory.EXPORT_CONTROLLED.value]
    await flush()
    await sign_in_as(client, sam)

    assert await listed(client) == []


async def test_someone_elses_decision_is_left_out(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """DL-286: the caller's own rows only, even for an org admin who sees everything. Bug: the
    approver filter dropped."""
    vera = await viewer(t, "Vera Viewer")
    otto = await org_admin(t, "Otto Org")
    item, revision = await requirement_at(t.project, 7, revision_title="Vera's", current_title="x")
    await decided(t.project, ada, item, revision, vera)
    await sign_in_as(client, otto)

    assert await listed(client) == []


async def test_another_projects_decision_is_listed_with_its_own_project(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """§11: My work is across projects. Bug: the item's project read from the wrong join."""
    vera = await viewer(t, "Vera Viewer")
    other = await ProjectFactory.create_async(organization=t.org, key="OPS", name="Operations")
    await ProjectMembershipFactory.create_async(project=other, user=vera, role=ProjectRole.VIEWER)
    item, revision = await requirement_at(other, 3, revision_title="Ops item", current_title="x")
    await decided(other, ada, item, revision, vera)
    await sign_in_as(client, vera)

    response = await client.get(DECISIONS)

    assert [(i["project_key"], i["entity_number"]) for i in response.json()["items"]] == [
        ("OPS", 3)
    ]


# --- In GET /api/me/work --------------------------------------------------------------------


async def test_my_work_shows_the_first_ten_decisions_and_the_total(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """§11: each section's first 10 items and its total (DL-76). Bug: the section left out of
    the home page's one request, or not limited."""
    vera = await viewer(t, "Vera Viewer")
    for number in range(1, 12):  # setup only
        item, revision = await requirement_at(
            t.project, number, revision_title=f"Item {number:02}", current_title="x"
        )
        await decided(t.project, ada, item, revision, vera)
    await sign_in_as(client, vera)

    decisions = (await client.get(WORK)).json()["sections"]["decisions"]

    assert (decisions["available"], len(decisions["items"]), decisions["total"]) == (True, 10, 11)


async def test_a_decisions_section_whose_query_fails_leaves_the_approvals_section(
    client: AsyncClient, t: Tenancy, ada: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TD-40: each section in its own savepoint. Bug: the decisions query shares a savepoint
    with the approvals, or fails the whole page."""
    vera = await viewer(t, "Vera Viewer")
    item, revision = await requirement_at(t.project, 7, revision_title="Owed", current_title="x")
    await decided(
        t.project,
        ada,
        item,
        revision,
        vera,
        decision=ApprovalDecision.PENDING,
        status=ApprovalRequestStatus.PENDING,
    )
    await sign_in_as(client, vera)
    real = ApprovalRepository.decided_for

    def failing(self: ApprovalRepository, approver_id: object, scope: Scope) -> Select[Approval]:
        # A query Postgres rejects (no such column), so the savepoint really rolls back.
        return real(self, approver_id, scope).where(text("no_such_column = 1"))  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(ApprovalRepository, "decided_for", failing)

    sections = (await client.get(WORK)).json()["sections"]

    assert (sections["decisions"], [a["title"] for a in sections["approvals"]["items"]]) == (
        {"available": False, "items": [], "total": 0},
        ["Owed"],
    )
