"""Approver replacement on the project paths (design-doc §6.2 "Replacing an approver who loses
access"; §10; build plan S2-C12): a project membership removed directly, an explicit membership
removed on an export-controlled project, and the project marked export-controlled. The
departed approver's pending row becomes `replaced` and the requester gets a pending row, logged
on the request as an `approver_id` change; and a replacement can complete the request. The
rule itself is unit-tested in tests/unit/rules/."""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    ActivityEntityType,
    ApprovalDecision,
    ApprovalEntityType,
    ApprovalRequestStatus,
    OrgRole,
    ProjectRole,
    RequirementStatus,
    RestrictionCategory,
)
from app.models.approval import Approval, ApprovalRequest
from app.models.project import Project
from app.models.requirement import Requirement, RequirementRevision
from app.models.user import User
from tests.api.test_approval_decisions import (
    approval_state,
    flush,
    logged,
    request_state,
    requirement,
    viewer,
)
from tests.factories.approval import ApprovalFactory, ApprovalRequestFactory
from tests.factories.org import MembershipFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory, RequirementRevisionFactory
from tests.factories.user import UserFactory
from tests.support.authz import Tenancy, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

MEMBERS = "/api/projects/PMT/members"
PENDING = ApprovalDecision.PENDING
APPROVED = ApprovalDecision.APPROVED
REPLACED = ApprovalDecision.REPLACED
EARLIER = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


@pytest.fixture
async def ada(t: Tenancy) -> User:
    """Ada, an explicit project admin: the requester."""
    user = await UserFactory.create_async(name="Ada Admin", is_system_admin=False, is_active=True)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.ADMIN
    )
    return user


@pytest.fixture
async def otto(client: AsyncClient, t: Tenancy) -> User:
    """Otto, an org admin, signed in: the one whose action takes the access away."""
    user = await UserFactory.create_async(name="Otto Org", is_system_admin=False, is_active=True)
    await MembershipFactory.create_async(organization=t.org, user=user, role=OrgRole.ADMIN)
    await sign_in_as(client, user)
    return user


async def org_admin(t: Tenancy, name: str) -> User:
    """An org admin with no project membership: inherited project admin (§5)."""
    user = await UserFactory.create_async(name=name, is_system_admin=False, is_active=True)
    await MembershipFactory.create_async(organization=t.org, user=user, role=OrgRole.ADMIN)
    return user


async def request_by(
    project: Project,
    requester: User,
    revision: RequirementRevision,
    item: Requirement,
    *rows: tuple[User, ApprovalDecision, datetime | None],
) -> ApprovalRequest:
    """A pending request on `item` at `revision`, made by `requester`, with these rows."""
    request = await ApprovalRequestFactory.create_async(
        project=project,
        entity_type=ApprovalEntityType.REQUIREMENT,
        entity_id=item.id,
        requirement_revision_id=revision.id,
        status=ApprovalRequestStatus.PENDING,
        requester=requester,
        completed_at=None,
    )
    for approver, decision, decided_at in rows:
        await ApprovalFactory.create_async(
            approval_request=request, approver=approver, decision=decision, decided_at=decided_at
        )
    return request


async def rows(session: AsyncSession, request: ApprovalRequest) -> set[tuple[uuid.UUID, object]]:
    """The request's rows as `(approver_id, decision)`, re-read."""
    result = await session.execute(
        select(Approval.approver_id, Approval.decision).where(
            Approval.approval_request_id == request.id
        )
    )
    return {(a, ApprovalDecision(d)) for a, d in result.all()}


async def mark_export_controlled(t: Tenancy) -> None:
    t.project.restriction_categories = [RestrictionCategory.EXPORT_CONTROLLED.value]
    await flush()


# --- A membership removed directly --------------------------------------------------------------


async def test_removing_an_approver_replaces_their_pending_row_with_the_requesters(
    client: AsyncClient, session: AsyncSession, t: Tenancy, ada: User, otto: User
) -> None:
    """§6.2 "How": the row keeps its history as `replaced`, a pending row for the requester;
    logged on the request, `approver_id` old and new the two user IDs, `changed_by` the
    remover. Bug: the removal never calls the replacement."""
    item, (rev1,) = await requirement(t)
    vera = await viewer(t, "Vera Viewer")
    request = await request_by(t.project, ada, rev1, item, (vera, PENDING, None))

    response = await client.delete(f"{MEMBERS}/{vera.id}")

    assert response.status_code == 204
    assert await rows(session, request) == {(vera.id, REPLACED), (ada.id, PENDING)}
    assert await logged(session, ActivityEntityType.APPROVAL_REQUEST, request.id) == {
        ("approver_id", str(vera.id), str(ada.id), otto.id)
    }
    assert await request_state(session, request) == (ApprovalRequestStatus.PENDING, False)


async def test_removing_an_approver_who_still_inherits_admin_leaves_their_row_pending(
    client: AsyncClient, session: AsyncSession, t: Tenancy, ada: User, otto: User
) -> None:
    """§6.2: the rule is the loss of access. An org admin keeps content access without the
    membership on a project that isn't export-controlled. Bug: every removal replaces."""
    item, (rev1,) = await requirement(t)
    ivy = await org_admin(t, "Ivy Inherit")
    await ProjectMembershipFactory.create_async(
        project=t.project, user=ivy, role=ProjectRole.VIEWER
    )
    request = await request_by(t.project, ada, rev1, item, (ivy, PENDING, None))

    response = await client.delete(f"{MEMBERS}/{ivy.id}")

    assert response.status_code == 204
    assert await rows(session, request) == {(ivy.id, PENDING)}
    assert await logged(session, ActivityEntityType.APPROVAL_REQUEST, request.id) == set()


async def test_removing_an_inherited_admins_membership_on_an_export_controlled_project_replaces(
    client: AsyncClient, session: AsyncSession, t: Tenancy, ada: User, otto: User
) -> None:
    """§6.2 "Causes": their explicit membership on an export-controlled project removed; an
    inherited admin has no content access there (§3.1). Bug: the access check ignoring export
    control."""
    item, (rev1,) = await requirement(t)
    ivy = await org_admin(t, "Ivy Inherit")
    await ProjectMembershipFactory.create_async(
        project=t.project, user=ivy, role=ProjectRole.VIEWER
    )
    await mark_export_controlled(t)
    request = await request_by(t.project, ada, rev1, item, (ivy, PENDING, None))

    response = await client.delete(f"{MEMBERS}/{ivy.id}")

    assert response.status_code == 204
    assert await rows(session, request) == {(ivy.id, REPLACED), (ada.id, PENDING)}


async def test_a_requester_who_no_longer_holds_admin_leaves_the_row_pending(
    client: AsyncClient, session: AsyncSession, t: Tenancy, otto: User
) -> None:
    """§6.2 "If the requester no longer holds project admin either": the row stays pending, no
    row added, nothing logged. Bug: replacing whatever the requester holds."""
    item, (rev1,) = await requirement(t)
    vera, max_ = await viewer(t, "Vera Viewer"), await viewer(t, "Max Former")
    request = await request_by(t.project, max_, rev1, item, (vera, PENDING, None))

    response = await client.delete(f"{MEMBERS}/{vera.id}")

    assert response.status_code == 204
    assert await rows(session, request) == {(vera.id, PENDING)}
    assert await logged(session, ActivityEntityType.APPROVAL_REQUEST, request.id) == set()


async def test_a_deactivated_requester_no_longer_holds_admin(
    client: AsyncClient, session: AsyncSession, t: Tenancy, ada: User, otto: User
) -> None:
    """§6.2 "Causes": deactivation takes the access away, so a deactivated requester can't be
    given the row. Bug: the requester's roles checked without their account."""
    item, (rev1,) = await requirement(t)
    vera = await viewer(t, "Vera Viewer")
    ada.is_active = False
    await flush()
    request = await request_by(t.project, ada, rev1, item, (vera, PENDING, None))

    response = await client.delete(f"{MEMBERS}/{vera.id}")

    assert response.status_code == 204
    assert await rows(session, request) == {(vera.id, PENDING)}


async def test_a_requester_already_named_gets_no_second_row(
    client: AsyncClient, session: AsyncSession, t: Tenancy, ada: User, otto: User
) -> None:
    """§6.2 "How": if the requester is already a named approver, no new row is added; the
    replacement is still logged. Bug: a duplicate row (the unique constraint, a 500)."""
    item, (rev1,) = await requirement(t)
    vera = await viewer(t, "Vera Viewer")
    request = await request_by(
        t.project, ada, rev1, item, (vera, PENDING, None), (ada, PENDING, None)
    )

    response = await client.delete(f"{MEMBERS}/{vera.id}")

    assert response.status_code == 204
    assert await rows(session, request) == {(vera.id, REPLACED), (ada.id, PENDING)}
    assert await logged(session, ActivityEntityType.APPROVAL_REQUEST, request.id) == {
        ("approver_id", str(vera.id), str(ada.id), otto.id)
    }


async def test_a_decided_row_is_never_replaced(
    client: AsyncClient, session: AsyncSession, t: Tenancy, ada: User, otto: User
) -> None:
    """§6.2 "How": rows already decided are never replaced. Bug: every row of the departed
    approver replaced."""
    item, (rev1,) = await requirement(t)
    vera, max_ = await viewer(t, "Vera Viewer"), await viewer(t, "Max Moore")
    request = await request_by(
        t.project, ada, rev1, item, (vera, APPROVED, EARLIER), (max_, PENDING, None)
    )

    response = await client.delete(f"{MEMBERS}/{vera.id}")

    assert response.status_code == 204
    assert await rows(session, request) == {(vera.id, APPROVED), (max_.id, PENDING)}


async def test_a_removal_leaves_the_approvers_rows_in_other_projects_alone(
    client: AsyncClient, session: AsyncSession, t: Tenancy, ada: User, otto: User
) -> None:
    """The removal takes access to this project only. Bug: replacing the user's pending rows
    everywhere."""
    vera = await viewer(t, "Vera Viewer")
    other = await ProjectFactory.create_async(organization=t.org, key="OPS", name="Ops")
    await ProjectMembershipFactory.create_async(project=other, user=vera, role=ProjectRole.VIEWER)
    await ProjectMembershipFactory.create_async(project=other, user=ada, role=ProjectRole.ADMIN)
    elsewhere = await RequirementFactory.create_async(project=other, number=1)
    revision = await RequirementRevisionFactory.create_async(
        requirement=elsewhere, revision_number=1
    )
    request = await request_by(other, ada, revision, elsewhere, (vera, PENDING, None))

    response = await client.delete(f"{MEMBERS}/{vera.id}")

    assert response.status_code == 204
    assert await rows(session, request) == {(vera.id, PENDING)}


# --- Completion ---------------------------------------------------------------------------------


async def test_a_replacement_that_leaves_every_counted_row_approved_completes_the_request(
    client: AsyncClient, session: AsyncSession, t: Tenancy, ada: User, otto: User
) -> None:
    """§6.2 "It can complete the request": the requester already named and approved; the
    request completes, its `status` change logged as the remover, and the requirement approved
    at the request's revision by the counted approver with the latest `decided_at` (Ivy, not
    the requester). Bug: completion only ever on a decision."""
    item, (rev1,) = await requirement(t)
    vera, ivy = await viewer(t, "Vera Viewer"), await viewer(t, "Ivy Moss")
    request = await request_by(
        t.project,
        ada,
        rev1,
        item,
        (vera, PENDING, None),
        (ada, APPROVED, EARLIER),
        (ivy, APPROVED, LATER),
    )

    response = await client.delete(f"{MEMBERS}/{vera.id}")

    assert response.status_code == 204
    assert await request_state(session, request) == (ApprovalRequestStatus.APPROVED, True)
    assert await logged(session, ActivityEntityType.APPROVAL_REQUEST, request.id) == {
        ("approver_id", str(vera.id), str(ada.id), otto.id),
        ("status", "pending", "approved", otto.id),
    }
    assert await approval_state(session, item) == (RequirementStatus.APPROVED, rev1.id, ivy.id)


# --- The project marked export-controlled -------------------------------------------------------


async def test_marking_the_project_export_controlled_replaces_inherited_admin_approvers(
    client: AsyncClient, session: AsyncSession, t: Tenancy, ada: User
) -> None:
    """§6.2 "Causes": the project marked export-controlled while they have no explicit
    membership; an explicit member keeps their row. Logged as the admin who marked it. Bug: the
    restriction change never calls the replacement."""
    item, (rev1,) = await requirement(t)
    ivy, vera = await org_admin(t, "Ivy Inherit"), await viewer(t, "Vera Viewer")
    request = await request_by(
        t.project, ada, rev1, item, (ivy, PENDING, None), (vera, PENDING, None)
    )
    await sign_in_as(client, ada)

    response = await client.put(
        "/api/projects/PMT/restriction",
        json={
            "level": None,
            "categories": ["export_controlled"],
            "export_control_confirmed": True,
            "confirmed_member_ids": [str(ada.id), str(vera.id)],
        },
    )

    assert response.status_code == 200
    assert await rows(session, request) == {
        (ivy.id, REPLACED),
        (vera.id, PENDING),
        (ada.id, PENDING),
    }
    assert await logged(session, ActivityEntityType.APPROVAL_REQUEST, request.id) == {
        ("approver_id", str(ivy.id), str(ada.id), ada.id)
    }


# --- The requester's admin, inherited --------------------------------------------------------


@pytest.mark.security
async def test_an_inherited_admin_requester_gets_the_row_on_a_project_that_isnt_export_controlled(
    client: AsyncClient, session: AsyncSession, t: Tenancy, otto: User
) -> None:
    """§6.2 "By whom": project admin, explicit or inherited. Bug: only an explicit admin
    counted."""
    item, (rev1,) = await requirement(t)
    ivy, vera = await org_admin(t, "Ivy Inherit"), await viewer(t, "Vera Viewer")
    request = await request_by(t.project, ivy, rev1, item, (vera, PENDING, None))

    response = await client.delete(f"{MEMBERS}/{vera.id}")

    assert response.status_code == 204
    assert await rows(session, request) == {(vera.id, REPLACED), (ivy.id, PENDING)}


@pytest.mark.security
async def test_an_inherited_admin_requester_gets_no_row_on_an_export_controlled_project(
    client: AsyncClient, session: AsyncSession, t: Tenancy, ada: User
) -> None:
    """§6.2 "By whom": on an export-controlled project, explicit only (§3.1). Marking it takes
    the access of both inherited admins, the requester Ivy and the approver Ivan, so Ivan's row
    stays pending and nothing is logged. Bug: the requester checked without export control,
    handing Ivy a row on content she's cleared out of."""
    item, (rev1,) = await requirement(t)
    ivy, ivan = await org_admin(t, "Ivy Inherit"), await org_admin(t, "Ivan Inherit")
    request = await request_by(t.project, ivy, rev1, item, (ivan, PENDING, None))
    await sign_in_as(client, ada)

    response = await client.put(
        "/api/projects/PMT/restriction",
        json={
            "level": None,
            "categories": ["export_controlled"],
            "export_control_confirmed": True,
            "confirmed_member_ids": [str(ada.id)],
        },
    )

    assert response.status_code == 200
    assert await rows(session, request) == {(ivan.id, PENDING)}
    assert await logged(session, ActivityEntityType.APPROVAL_REQUEST, request.id) == set()
