"""What the requester's Approval section reads (build plan S2-C20): `flagged` on an approval
request's read and list (design-doc §6.2, DL-279), and `approved_revision_number` on the
requirement's read (DL-280)."""

import pytest
from httpx import AsyncClient

from app.enums import ApprovalDecision, ProjectRole
from app.models.approval import ApprovalRequest
from app.models.user import User
from tests.api.test_approval_decisions import approved_at, flush, requirement, viewer
from tests.api.test_approver_replacement import request_by
from tests.factories.project import ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.support.authz import Tenancy, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

MEMBERS = "/api/projects/PMT/members"
REQUESTS = "/api/projects/PMT/requirements/7/approval-requests"
PENDING = ApprovalDecision.PENDING


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


@pytest.fixture
async def ada(client: AsyncClient, t: Tenancy) -> User:
    """Ada, an explicit project admin, signed in: she reads, removes, and cancels."""
    user = await UserFactory.create_async(name="Ada Admin", is_system_admin=False, is_active=True)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.ADMIN
    )
    await sign_in_as(client, user)
    return user


async def flagged(client: AsyncClient, request: ApprovalRequest) -> tuple[bool, list[bool]]:
    """`flagged` on the request's read, and on each row of the requirement's list."""
    read = await client.get(f"/api/approval-requests/{request.id}")
    listed = await client.get(REQUESTS)
    assert (read.status_code, listed.status_code) == (200, 200)
    return read.json()["flagged"], [row["flagged"] for row in listed.json()["items"]]


async def test_a_request_whose_approver_lost_access_and_whose_requester_isnt_admin_is_flagged(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """§6.2: the row stays pending and the request is flagged, on the read and the list. Bug:
    `flagged` never set, or set on the read only."""
    item, (rev1,) = await requirement(t)
    vera, max_ = await viewer(t, "Vera Viewer"), await viewer(t, "Max Former")
    request = await request_by(t.project, max_, rev1, item, (vera, PENDING, None))
    assert (await client.delete(f"{MEMBERS}/{vera.id}")).status_code == 204

    assert await flagged(client, request) == (True, [True])


async def test_a_request_whose_approvers_all_have_access_isnt_flagged(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """DL-279's denied side. Bug: every pending request flagged."""
    item, (rev1,) = await requirement(t)
    vera, max_ = await viewer(t, "Vera Viewer"), await viewer(t, "Max Former")
    request = await request_by(t.project, max_, rev1, item, (vera, PENDING, None))

    assert await flagged(client, request) == (False, [False])


async def test_a_replaced_row_doesnt_flag_the_request(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """§6.2: a requester who still holds admin takes the row, so nothing is left for an admin to
    handle. Bug: a departed approver's row counted whatever its decision."""
    item, (rev1,) = await requirement(t)
    vera = await viewer(t, "Vera Viewer")
    request = await request_by(t.project, ada, rev1, item, (vera, PENDING, None))
    assert (await client.delete(f"{MEMBERS}/{vera.id}")).status_code == 204

    assert await flagged(client, request) == (False, [False])


async def test_a_cancelled_request_isnt_flagged(client: AsyncClient, t: Tenancy, ada: User) -> None:
    """DL-279: flagged only while pending. Bug: the request's status not checked."""
    item, (rev1,) = await requirement(t)
    vera, max_ = await viewer(t, "Vera Viewer"), await viewer(t, "Max Former")
    request = await request_by(t.project, max_, rev1, item, (vera, PENDING, None))
    assert (await client.delete(f"{MEMBERS}/{vera.id}")).status_code == 204
    assert (await client.post(f"/api/approval-requests/{request.id}/cancel")).status_code == 200

    assert await flagged(client, request) == (False, [False])


async def test_a_deactivated_approver_flags_the_request(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """§6.2 "Causes": deactivation takes the access away, whatever the account still holds. Bug:
    the approver's roles checked without their account."""
    item, (rev1,) = await requirement(t)
    vera, max_ = await viewer(t, "Vera Viewer"), await viewer(t, "Max Former")
    request = await request_by(t.project, max_, rev1, item, (vera, PENDING, None))
    vera.is_active = False
    await flush()

    assert await flagged(client, request) == (True, [True])


async def test_a_requirement_never_approved_has_no_approved_revision_number(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """DL-280: null while never approved. Bug: the current revision's number in its place."""
    await requirement(t, revisions=2)

    response = await client.get("/api/projects/PMT/requirements/7")

    assert response.status_code == 200
    assert response.json()["approved_revision_number"] is None


async def test_the_approved_revision_number_is_the_approved_ones_not_the_current(
    client: AsyncClient, t: Tenancy, ada: User
) -> None:
    """DL-280: "Approved · modified" at revision 3, approved at 2. Bug: the current revision's
    number, or the first's."""
    item, (_, rev2, _) = await requirement(t, revisions=3)
    await approved_at(item, rev2, ada)

    response = await client.get("/api/projects/PMT/requirements/7")

    assert response.status_code == 200
    assert response.json()["approved_revision_number"] == 2
