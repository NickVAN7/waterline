"""An org add that adds the person to some of the org's projects too (Q12g, DL-379): the
memberships and events it stores, all or nothing, and the projects step's list
(`GET /api/orgs/{id}/member-projects`). Who may add org members at all is in
tests/api/authz/test_org_members.py (spec tests)."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AuditAction, OrgRole, ProjectRole, WorkspaceRole
from app.models.audit_event import AuditEvent
from app.models.org import Membership, Organization
from app.models.project import Project, ProjectMembership
from app.models.user import User
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceMembershipFactory
from tests.support.authz import sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

EC = "export_controlled"


@pytest.fixture
async def org() -> Organization:
    return await OrganizationFactory.create_async(name="Bolt Foods", slug="bolt")


async def signed_in(client: AsyncClient, org: Organization, role: OrgRole) -> User:
    person = await UserFactory.create_async()
    await MembershipFactory.create_async(organization=org, user=person, role=role)
    await sign_in_as(client, person)
    return person


async def project(org: Organization, key: str, name: str, **values: Any) -> Project:
    return await ProjectFactory.create_async(organization=org, key=key, name=name, **values)


async def project_roles(session: AsyncSession, email: str) -> dict[str, ProjectRole]:
    rows = await session.execute(
        select(Project.key, ProjectMembership.role)
        .join(ProjectMembership, ProjectMembership.project_id == Project.id)
        .join(User, User.id == ProjectMembership.user_id)
        .where(User.email == email)
    )
    return dict(rows.all())


async def org_role(session: AsyncSession, org: Organization, email: str) -> OrgRole | None:
    return await session.scalar(
        select(Membership.role)
        .join(User, User.id == Membership.user_id)
        .where(Membership.organization_id == org.id, User.email == email)
    )


async def added_events(session: AsyncSession) -> list[tuple[AuditAction, dict[str, Any]]]:
    rows = await session.execute(
        select(AuditEvent.action, AuditEvent.details)
        .where(
            AuditEvent.action.in_([AuditAction.ORG_MEMBER_ADDED, AuditAction.PROJECT_MEMBER_ADDED])
        )
        .order_by(AuditEvent.id)
    )
    return [(action, details) for action, details in rows]


def fields(body: dict[str, Any]) -> list[tuple[list[object], str]]:
    return [(e["loc"], e["type"]) for e in body["details"]["fields"]]


# --- The add -------------------------------------------------------------------------------------


async def test_an_add_puts_the_person_on_each_project_with_its_role_each_audited(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    """Bug: a project left out, a role not the one sent (Member when none is), or a project add
    without its own `project_member_added` (Q12g)."""
    await signed_in(client, org, OrgRole.ADMIN)
    await UserFactory.create_async(email="ann@bolt.example")
    pay = await project(org, "PAY", "Payments")
    ops = await project(org, "OPS", "Operations")
    await project(org, "HR", "People")  # not chosen

    response = await client.post(
        f"/api/orgs/{org.id}/members",
        json={
            "email": "ann@bolt.example",
            "role": "member",
            "projects": [
                {"project_id": str(pay.id), "role": "admin"},
                {"project_id": str(ops.id)},
            ],
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "ann@bolt.example"
    assert await org_role(session, org, "ann@bolt.example") == OrgRole.MEMBER
    assert await project_roles(session, "ann@bolt.example") == {
        "PAY": ProjectRole.ADMIN,
        "OPS": ProjectRole.MEMBER,
    }
    assert sorted((a.value, d["role"]) for a, d in await added_events(session)) == [
        ("org_member_added", "member"),
        ("project_member_added", "admin"),
        ("project_member_added", "member"),
    ]


async def test_a_create_puts_the_new_account_on_the_projects_too(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    """Bug: the create path ignoring `projects` (DL-379: both org adds take them)."""
    await signed_in(client, org, OrgRole.ADMIN)
    pay = await project(org, "PAY", "Payments")

    response = await client.post(
        f"/api/orgs/{org.id}/members/new",
        json={
            "email": "new@bolt.example",
            "name": "Nia New",
            "username": "nia",
            "password": "correct-horse-battery-1",
            "role": "member",
            "projects": [{"project_id": str(pay.id), "role": "viewer"}],
        },
    )

    assert response.status_code == 201
    assert await project_roles(session, "new@bolt.example") == {"PAY": ProjectRole.VIEWER}


async def test_an_add_without_projects_adds_only_the_org_member(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    """Bug: the step made required, or a project added that wasn't sent."""
    await signed_in(client, org, OrgRole.ADMIN)
    await UserFactory.create_async(email="ann@bolt.example")
    await project(org, "PAY", "Payments")

    response = await client.post(
        f"/api/orgs/{org.id}/members", json={"email": "ann@bolt.example", "role": "member"}
    )

    assert response.status_code == 201
    assert await project_roles(session, "ann@bolt.example") == {}


async def org_add(client: AsyncClient, org: Organization, *projects: dict[str, Any]) -> Any:
    return await client.post(
        f"/api/orgs/{org.id}/members",
        json={"email": "ann@bolt.example", "role": "member", "projects": list(projects)},
    )


async def test_a_project_outside_the_org_is_a_404_and_adds_nothing(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    """Bug: another org's project accepted, or the org add (and the good project) kept when a
    later entry fails: the add is all or nothing (DL-379)."""
    await signed_in(client, org, OrgRole.ADMIN)
    await UserFactory.create_async(email="ann@bolt.example")
    pay = await project(org, "PAY", "Payments")
    other = await OrganizationFactory.create_async(workspace_id=org.workspace_id)
    theirs = await project(other, "LDG", "Ledger")

    response = await org_add(
        client, org, {"project_id": str(pay.id)}, {"project_id": str(theirs.id)}
    )

    assert response.status_code == 404
    assert await org_role(session, org, "ann@bolt.example") is None
    assert await project_roles(session, "ann@bolt.example") == {}
    assert await added_events(session) == []


async def test_an_unknown_project_is_a_404(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    await signed_in(client, org, OrgRole.ADMIN)
    await UserFactory.create_async(email="ann@bolt.example")

    response = await org_add(client, org, {"project_id": str(uuid.uuid4())})

    assert response.status_code == 404
    assert await org_role(session, org, "ann@bolt.example") is None


async def test_an_archived_project_is_a_403_and_adds_nothing(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    """Bug: a member added to a read-only project (design-doc §5)."""
    await signed_in(client, org, OrgRole.ADMIN)
    await UserFactory.create_async(email="ann@bolt.example")
    old = await project(org, "OLD", "Old", archived_at=datetime(2026, 10, 1, tzinfo=UTC))

    response = await org_add(client, org, {"project_id": str(old.id)})

    assert response.status_code == 403
    assert await org_role(session, org, "ann@bolt.example") is None


async def test_a_project_sent_twice_is_a_422_on_its_second_entry(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    await signed_in(client, org, OrgRole.ADMIN)
    await UserFactory.create_async(email="ann@bolt.example")
    pay = await project(org, "PAY", "Payments")

    response = await org_add(
        client, org, {"project_id": str(pay.id)}, {"project_id": str(pay.id), "role": "admin"}
    )

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["body", "projects", 1, "project_id"], "duplicate")],
    )
    assert await org_role(session, org, "ann@bolt.example") is None


async def test_an_export_controlled_project_needs_its_confirmation_on_its_entry(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    """Bug: an add to an export-controlled project without the confirmation (design-doc §3.1,
    DL-81), or the error on the wrong entry."""
    await signed_in(client, org, OrgRole.ADMIN)
    await UserFactory.create_async(email="ann@bolt.example")
    pay = await project(org, "PAY", "Payments", id=uuid.UUID(int=2))
    # Its id sorts first, so the lock takes it first: the error must still name its entry, 1.
    sec = await project(org, "SEC", "Secure", restriction_categories=[EC], id=uuid.UUID(int=1))

    response = await org_add(client, org, {"project_id": str(pay.id)}, {"project_id": str(sec.id)})

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["body", "projects", 1, "export_control_confirmed"], "confirmation_required")],
    )
    assert await org_role(session, org, "ann@bolt.example") is None
    assert await project_roles(session, "ann@bolt.example") == {}


async def test_a_confirmed_export_controlled_add_records_the_confirmation(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    await signed_in(client, org, OrgRole.ADMIN)
    await UserFactory.create_async(email="ann@bolt.example")
    sec = await project(org, "SEC", "Secure", restriction_categories=[EC])

    response = await org_add(
        client, org, {"project_id": str(sec.id), "export_control_confirmed": True}
    )

    assert response.status_code == 201
    assert await project_roles(session, "ann@bolt.example") == {"SEC": ProjectRole.MEMBER}
    assert (
        AuditAction.PROJECT_MEMBER_ADDED,
        {"role": "member", "export_control_confirmed": True},
    ) in (await added_events(session))


async def test_a_confirmation_on_a_project_that_needs_none_is_a_422(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    await signed_in(client, org, OrgRole.ADMIN)
    await UserFactory.create_async(email="ann@bolt.example")
    pay = await project(org, "PAY", "Payments")

    response = await org_add(
        client, org, {"project_id": str(pay.id), "export_control_confirmed": True}
    )

    assert fields(response.json()) == [
        (["body", "projects", 0, "export_control_confirmed"], "confirmation_not_needed")
    ]


async def test_an_org_add_that_fails_adds_no_project(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    """Bug: the projects added though the org add was refused (already a member)."""
    await signed_in(client, org, OrgRole.ADMIN)
    ann = await UserFactory.create_async(email="ann@bolt.example")
    await MembershipFactory.create_async(organization=org, user=ann, role=OrgRole.MEMBER)
    pay = await project(org, "PAY", "Payments")

    response = await org_add(client, org, {"project_id": str(pay.id)})

    assert fields(response.json()) == [(["body", "email"], "already_member")]
    assert await project_roles(session, "ann@bolt.example") == {}


async def test_staff_already_on_a_chosen_project_get_the_error_on_that_entry(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    """Bug: workspace staff, who can be on a project outside its org, added to the org with that
    project chosen: the roster's `already_member` landed on `email`, saying nothing of which
    project, and the org membership kept."""
    await signed_in(client, org, OrgRole.ADMIN)
    ann = await UserFactory.create_async(email="ann@bolt.example")
    await WorkspaceMembershipFactory.create_async(
        workspace_id=org.workspace_id, user=ann, role=WorkspaceRole.MEMBER
    )
    pay = await project(org, "PAY", "Payments")
    await ProjectMembershipFactory.create_async(project=pay, user=ann, role=ProjectRole.VIEWER)

    response = await org_add(client, org, {"project_id": str(pay.id)})

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["body", "projects", 0, "project_id"], "already_member")],
    )
    assert await org_role(session, org, "ann@bolt.example") is None


async def test_an_org_member_without_member_management_is_refused(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    """Bug: the projects step opening a way in for someone who can't add org members."""
    await signed_in(client, org, OrgRole.MEMBER)
    await UserFactory.create_async(email="ann@bolt.example")
    pay = await project(org, "PAY", "Payments")

    response = await org_add(client, org, {"project_id": str(pay.id)})

    assert response.status_code == 403
    assert await project_roles(session, "ann@bolt.example") == {}


# --- The projects step's list ---------------------------------------------------------------------


async def test_the_step_lists_the_orgs_live_projects_by_name_with_export_control(
    client: AsyncClient, org: Organization
) -> None:
    """Bug: an archived or another org's project offered, the order not by name, or the
    export-control flag wrong (the step asks for the confirmation from it)."""
    await signed_in(client, org, OrgRole.ADMIN)
    await project(org, "PAY", "Payments")
    await project(org, "SEC", "Accounts", restriction_categories=[EC])
    await project(org, "OLD", "Archive", archived_at=datetime(2026, 10, 1, tzinfo=UTC))
    other = await OrganizationFactory.create_async(workspace_id=org.workspace_id)
    await project(other, "LDG", "Ledger")

    response = await client.get(f"/api/orgs/{org.id}/member-projects", params={"limit": 200})

    assert response.status_code == 200
    assert [(p["key"], p["name"], p["export_controlled"]) for p in response.json()["items"]] == [
        ("SEC", "Accounts", True),
        ("PAY", "Payments", False),
    ]


async def test_the_step_list_is_refused_to_an_org_member_who_cannot_add_people(
    client: AsyncClient, org: Organization
) -> None:
    """Bug: the list open to an org member without `org_member.manage`."""
    await signed_in(client, org, OrgRole.MEMBER)

    response = await client.get(f"/api/orgs/{org.id}/member-projects")

    assert response.status_code == 403


async def test_the_step_list_is_a_404_to_someone_outside_the_org(
    client: AsyncClient, org: Organization
) -> None:
    """Bug: the org's projects listed to someone who can't see the org."""
    await sign_in_as(client, await UserFactory.create_async())

    response = await client.get(f"/api/orgs/{org.id}/member-projects")

    assert response.status_code == 404
