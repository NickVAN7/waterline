"""Slice 2's "Done when" (build plan): on a project marked export-controlled through the API, an
inherited admin without an explicit membership gets a 404 for every requirement read and list,
revisions, history, approvals, and the trash; management still works; once added (with the
confirmation) they see the content (design-doc §3.1). Each endpoint's own 404 is tested in its
area's tests against a factory-set flag; this walks the flow through the real endpoints."""

import uuid
from dataclasses import dataclass

import pytest
from httpx import AsyncClient

from app.enums import ApprovalEntityType, ApprovalRequestStatus
from app.models.user import User
from tests.factories.approval import ApprovalRequestFactory
from tests.factories.requirement import RequirementFactory, RequirementRevisionFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

TITLE = "Refunds above the card limit"
REQUIREMENT = "/api/projects/PMT/requirements/7"
CONTENT = [
    "/api/projects/PMT/requirements",
    REQUIREMENT,
    REQUIREMENT + "/revisions",
    REQUIREMENT + "/revisions/1",
    REQUIREMENT + "/activity",
    REQUIREMENT + "/approval-requests",
    "/api/approval-requests/{request}",
    "/api/projects/PMT/trash",
]


async def marked_export_controlled(client: AsyncClient, admin: User) -> None:
    await sign_in_as(client, admin)
    response = await client.put(
        "/api/projects/PMT/restriction",
        json={
            "level": None,
            "categories": ["export_controlled"],
            "export_control_confirmed": True,
            "confirmed_member_ids": [str(admin.id)],
        },
    )
    assert response.status_code == 200


@dataclass
class Ivy:
    user: User
    request_id: uuid.UUID

    def path(self, template: str) -> str:
        return template.format(request=self.request_id)


@pytest.fixture
async def ivy(client: AsyncClient) -> Ivy:
    """Ivy, an admin of PMT's org with no membership there, after PMT's explicit admin marks it
    export-controlled; RQ-7 has its first revision and a pending approval request."""
    t: Tenancy = await tenancy()
    requirement = await RequirementFactory.create_async(project=t.project, number=7, title=TITLE)
    revision = await RequirementRevisionFactory.create_async(
        requirement=requirement, revision_number=1, title=TITLE
    )
    admin = await persona_user(t, "project_admin")
    request = await ApprovalRequestFactory.create_async(
        project=t.project,
        entity_type=ApprovalEntityType.REQUIREMENT,
        entity_id=requirement.id,
        requirement_revision_id=revision.id,
        status=ApprovalRequestStatus.PENDING,
        requester=admin,
        completed_at=None,
    )
    await marked_export_controlled(client, admin)
    user = await persona_user(t, "org_admin")
    await sign_in_as(client, user)
    return Ivy(user, request.id)


@pytest.mark.parametrize("path", CONTENT)
async def test_an_inherited_admin_gets_404_for_the_content_once_marked_through_the_api(
    client: AsyncClient, ivy: Ivy, path: str
) -> None:
    response = await client.get(ivy.path(path))

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert TITLE not in response.text


@pytest.mark.parametrize("path", ["/api/projects/PMT", "/api/projects/PMT/members"])
async def test_the_inherited_admin_still_manages_the_project(
    client: AsyncClient, ivy: Ivy, path: str
) -> None:
    response = await client.get(path)

    assert response.status_code == 200


async def test_adding_them_needs_the_confirmation(client: AsyncClient, ivy: Ivy) -> None:
    response = await client.post(
        "/api/projects/PMT/members", json={"role": "viewer", "user_id": str(ivy.user.id)}
    )

    assert (response.status_code, response.json()["code"]) == (422, "validation_error")
    assert (await client.get(REQUIREMENT)).status_code == 404


@pytest.mark.parametrize("path", CONTENT)
async def test_once_added_with_the_confirmation_they_see_the_content(
    client: AsyncClient, ivy: Ivy, path: str
) -> None:
    added = await client.post(
        "/api/projects/PMT/members",
        json={"role": "viewer", "user_id": str(ivy.user.id), "export_control_confirmed": True},
    )
    assert added.status_code == 201

    response = await client.get(ivy.path(path))

    assert response.status_code == 200


async def test_once_added_they_see_the_pending_request(client: AsyncClient, ivy: Ivy) -> None:
    added = await client.post(
        "/api/projects/PMT/members",
        json={"role": "viewer", "user_id": str(ivy.user.id), "export_control_confirmed": True},
    )
    assert added.status_code == 201

    body = (await client.get(REQUIREMENT + "/approval-requests")).json()

    assert [item["id"] for item in body["items"]] == [str(ivy.request_id)]
