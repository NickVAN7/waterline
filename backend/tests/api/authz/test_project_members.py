"""Authorization of the project members endpoints (build plan, "The project members API", DL-78;
the actions, DL-79; design-doc §4 "Visibility" and "Project admins" add people, §5 "Role
capabilities" and "Access review", §9 archiving):

- the member list (`project.view`): any project member reads it, viewer and up, and inherited
  admins; each row carries `project_member.manage` when the caller holds it;
- the picker, add, create, role change, and removal (`project_member.manage`): project admins,
  inherited included (any project admin changes any role, their own included: no last-admin guard,
  DL-71); 403 for a project member or viewer; 404, the same as a missing project and naming
  nothing, for whoever can't see the project; 403 on an archived project, to everyone (a
  mutation, DL-79);
- the picker lists the project org's members and the workspace's staff not yet on the project,
  never anyone else, nor a deactivated user; adding by `user_id` anyone else is a 404 that reads
  the same as for a user who doesn't exist;
- the access review (`project.view_access`): project admins, inherited included, archived
  projects too; a 404 to everyone else, members and viewers included (design-doc §5: "Anyone
  else gets a 404").

On every denial nothing is stored and no audit event is recorded. Personas are relative to
workspace "Acme Consulting", org "Bolt Foods" (bolt-foods), and project "Payments" (PMT)
(tests/support/authz.py, `tenancy`).
"""

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import OrgRole, ProjectRole, WorkspaceRole
from app.models.audit_event import AuditEvent
from app.models.org import Membership
from app.models.project import ProjectMembership
from app.models.user import User
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

INHERITED_ADMINS = ["system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"]
PROJECT_ADMINS = [*INHERITED_ADMINS, "project_admin"]
# See the project without being one of its admins.
SEE_ONLY = ["project_member", "project_viewer"]
PROJECT_UNSEEN = [
    "org_member",
    "other_project_admin",
    "workspace_member",
    "other_org_owner",
    "other_workspace_owner",
    "nobody",
]

ARCHIVED_AT = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
IVY = "ivy@bolt.example"
NEW_ACCOUNT: dict[str, Any] = {
    "email": "erin@bolt.example",
    "username": "erin-new",
    "name": "Erin New",
    "password": "plum-harbor-lantern-quietly",
    "role": "member",
}


async def signed_in(client: AsyncClient, who: str) -> tuple[Tenancy, User]:
    t = await tenancy()
    user = await persona_user(t, who)
    await sign_in_as(client, user)
    return t, user


async def archive(session: AsyncSession, t: Tenancy) -> None:
    t.project.archived_at = ARCHIVED_AT
    await session.flush()


async def user(email: str, name: str, *, is_active: bool = True) -> User:
    return await UserFactory.create_async(
        email=email, name=name, is_active=is_active, is_system_admin=False
    )


async def org_member(t: Tenancy, email: str, name: str, *, is_active: bool = True) -> User:
    person = await user(email, name, is_active=is_active)
    await MembershipFactory.create_async(organization=t.org, user=person, role=OrgRole.MEMBER)
    return person


async def staff(t: Tenancy, email: str, name: str) -> User:
    person = await user(email, name)
    await WorkspaceMembershipFactory.create_async(
        workspace=t.workspace, user=person, role=WorkspaceRole.MEMBER
    )
    return person


async def ivy(t: Tenancy) -> User:
    """A member of PMT (role member) with no other membership."""
    person = await user(IVY, "Ivy Moss")
    await ProjectMembershipFactory.create_async(
        project=t.project, user=person, role=ProjectRole.MEMBER
    )
    return person


async def stored_role(session: AsyncSession, t: Tenancy, user_id: uuid.UUID) -> str | None:
    return await session.scalar(
        select(ProjectMembership.role).where(
            ProjectMembership.project_id == t.project.id, ProjectMembership.user_id == user_id
        )
    )


async def audit_actions(session: AsyncSession) -> list[str]:
    return sorted(await session.scalars(select(AuditEvent.action)))


async def audit_events(session: AsyncSession) -> int | None:
    return await session.scalar(select(func.count()).select_from(AuditEvent))


def assert_forbidden(response: Response) -> None:
    assert (response.status_code, response.json()["code"]) == (403, "forbidden")


def assert_hidden(response: Response, missing: Response) -> None:
    """404 `not_found`, the same body as for a project that doesn't exist, naming nothing."""
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    for name in ("Bolt Foods", "bolt-foods", "Payments", "PMT", IVY, "Ivy Moss"):
        assert name not in response.text


# --- GET /api/projects/{key}/members (project.view) ---------------------------------------------


@pytest.mark.parametrize("who", [*PROJECT_ADMINS, *SEE_ONLY])
async def test_every_project_member_and_inherited_admin_reads_the_member_list(
    client: AsyncClient, who: str
) -> None:
    """DL-78: any project member reads it, through `project.view`."""
    t, _ = await signed_in(client, who)
    await ivy(t)

    response = await client.get("/api/projects/PMT/members")

    assert response.status_code == 200
    roles = {row["email"]: row["role"] for row in response.json()["items"]}
    assert roles[IVY] == "member"


@pytest.mark.parametrize("who", ["project_admin", "project_viewer"])
async def test_an_archived_projects_member_list_is_still_readable(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """design-doc §9: archived is read-only, still browsable."""
    t, _ = await signed_in(client, who)
    await ivy(t)
    await archive(session, t)

    response = await client.get("/api/projects/PMT/members")

    assert response.status_code == 200
    roles = {row["email"]: row["role"] for row in response.json()["items"]}
    assert roles[IVY] == "member"


@pytest.mark.parametrize(
    ("who", "carried"),
    [
        ("system_admin", True),
        ("workspace_owner", True),
        ("workspace_admin", True),
        ("org_owner", True),
        ("org_admin", True),
        ("project_admin", True),
        ("project_member", False),
        ("project_viewer", False),
    ],
)
async def test_a_member_row_carries_manage_when_the_caller_holds_it(
    client: AsyncClient, who: str, carried: bool
) -> None:
    """Build plan, "The project members API": a member row carries `project_member.manage` when
    the caller holds it."""
    t, _ = await signed_in(client, who)
    await ivy(t)

    response = await client.get("/api/projects/PMT/members")

    assert response.status_code == 200
    actions = {row["email"]: row["allowed_actions"] for row in response.json()["items"]}
    assert ("project_member.manage" in actions[IVY]) is carried


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_no_member_row_of_an_archived_project_carries_manage(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    await ivy(t)
    await archive(session, t)

    response = await client.get("/api/projects/PMT/members")

    assert response.status_code == 200
    actions = {row["email"]: row["allowed_actions"] for row in response.json()["items"]}
    assert "project_member.manage" not in actions[IVY]


# --- GET /api/projects/{key}/member-candidates (project_member.manage) --------------------------


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_project_admins_inherited_included_open_the_picker(
    client: AsyncClient, who: str
) -> None:
    t, _ = await signed_in(client, who)
    await org_member(t, "ava@bolt.example", "Ava Org")

    response = await client.get("/api/projects/PMT/member-candidates")

    assert response.status_code == 200
    assert "ava@bolt.example" in [row["email"] for row in response.json()["items"]]


async def test_the_picker_lists_only_the_orgs_members_and_the_staff_not_yet_on_the_project(
    client: AsyncClient,
) -> None:
    """design-doc §4: never other clients' users; build plan: not yet on the project, sorted by
    name; DL-78: the picker hides deactivated users."""
    t, _ = await signed_in(client, "project_admin")
    await org_member(t, "ava@bolt.example", "Ava Org")
    await staff(t, "ben@acme.example", "Ben Staff")
    done = await org_member(t, "cal@bolt.example", "Cal Done")
    await ProjectMembershipFactory.create_async(
        project=t.project, user=done, role=ProjectRole.VIEWER
    )
    await org_member(t, "dee@bolt.example", "Dee Gone", is_active=False)
    cove = await OrganizationFactory.create_async(
        workspace=t.workspace, name="Cove Retail", slug="cove-retail"
    )
    eli = await user("eli@cove.example", "Eli Other")
    await MembershipFactory.create_async(organization=cove, user=eli, role=OrgRole.MEMBER)
    delta = await WorkspaceFactory.create_async(name="Delta Partners", slug="delta")
    fay = await user("fay@delta.example", "Fay Elsewhere")
    await WorkspaceMembershipFactory.create_async(
        workspace=delta, user=fay, role=WorkspaceRole.MEMBER
    )
    ledger = await ProjectFactory.create_async(organization=t.org, key="LDG", name="Ledger")
    gus = await user("gus@bolt.example", "Gus Project")
    await ProjectMembershipFactory.create_async(project=ledger, user=gus, role=ProjectRole.ADMIN)

    response = await client.get("/api/projects/PMT/member-candidates")

    assert response.status_code == 200
    body = response.json()
    assert ([row["name"] for row in body["items"]], body["total"]) == (["Ava Org", "Ben Staff"], 2)


@pytest.mark.parametrize("who", SEE_ONLY)
async def test_the_picker_is_403_to_project_members_and_viewers(
    client: AsyncClient, who: str
) -> None:
    t, _ = await signed_in(client, who)
    await org_member(t, "ava@bolt.example", "Ava Org")

    response = await client.get("/api/projects/PMT/member-candidates")

    assert_forbidden(response)
    assert "ava@bolt.example" not in response.text


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_the_picker_is_404_to_whoever_cannot_see_the_project(
    client: AsyncClient, who: str
) -> None:
    t, _ = await signed_in(client, who)
    await org_member(t, "ava@bolt.example", "Ava Org")

    response = await client.get("/api/projects/PMT/member-candidates")

    assert_hidden(response, await client.get("/api/projects/ZZZ/member-candidates"))
    assert "ava@bolt.example" not in response.text


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_the_picker_is_403_on_an_archived_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """DL-79: `project_member.manage` is a mutation, so an archived project denies it."""
    t, _ = await signed_in(client, who)
    await org_member(t, "ava@bolt.example", "Ava Org")
    await archive(session, t)

    response = await client.get("/api/projects/PMT/member-candidates")

    assert_forbidden(response)


# --- POST /api/projects/{key}/members (project_member.manage) -----------------------------------


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_project_admins_inherited_included_add_an_org_member(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    ava = await org_member(t, "ava@bolt.example", "Ava Org")

    response = await client.post(
        "/api/projects/PMT/members", json={"user_id": str(ava.id), "role": "member"}
    )

    assert response.status_code == 201
    assert (response.json()["user_id"], response.json()["role"]) == (str(ava.id), "member")
    assert await stored_role(session, t, ava.id) == "member"
    assert await audit_actions(session) == ["project_member_added"]


async def test_a_project_admin_adds_workspace_staff(
    client: AsyncClient, session: AsyncSession
) -> None:
    """design-doc §4: from the org's members and the workspace's staff."""
    t, _ = await signed_in(client, "project_admin")
    ben = await staff(t, "ben@acme.example", "Ben Staff")

    response = await client.post(
        "/api/projects/PMT/members", json={"user_id": str(ben.id), "role": "viewer"}
    )

    assert response.status_code == 201
    assert await stored_role(session, t, ben.id) == "viewer"


@pytest.mark.parametrize("who", SEE_ONLY)
async def test_adding_a_member_is_403_to_project_members_and_viewers(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    ava = await org_member(t, "ava@bolt.example", "Ava Org")

    response = await client.post(
        "/api/projects/PMT/members", json={"user_id": str(ava.id), "role": "member"}
    )

    assert_forbidden(response)
    assert await stored_role(session, t, ava.id) is None
    assert await audit_events(session) == 0


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_adding_a_member_is_404_to_whoever_cannot_see_the_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    ava = await org_member(t, "ava@bolt.example", "Ava Org")
    body = {"user_id": str(ava.id), "role": "member"}

    response = await client.post("/api/projects/PMT/members", json=body)

    assert_hidden(response, await client.post("/api/projects/ZZZ/members", json=body))
    assert await stored_role(session, t, ava.id) is None
    assert await audit_events(session) == 0


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_adding_a_member_to_an_archived_project_is_403(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    ava = await org_member(t, "ava@bolt.example", "Ava Org")
    await archive(session, t)

    response = await client.post(
        "/api/projects/PMT/members", json={"user_id": str(ava.id), "role": "member"}
    )

    assert_forbidden(response)
    assert await stored_role(session, t, ava.id) is None
    assert await audit_events(session) == 0


async def _no_memberships(_t: Tenancy) -> User:
    return await user("zed@elsewhere.example", "Zed Quill")


async def _on_another_project_of_the_org(t: Tenancy) -> User:
    """A project membership in the org is neither an org membership nor staff."""
    person = await _no_memberships(t)
    ledger = await ProjectFactory.create_async(organization=t.org, key="LDG", name="Ledger")
    await ProjectMembershipFactory.create_async(project=ledger, user=person, role=ProjectRole.ADMIN)
    return person


async def _other_workspace_staff(t: Tenancy) -> User:
    person = await _no_memberships(t)
    delta = await WorkspaceFactory.create_async(name="Delta Partners", slug="delta")
    await WorkspaceMembershipFactory.create_async(
        workspace=delta, user=person, role=WorkspaceRole.ADMIN
    )
    return person


async def _other_org_member(t: Tenancy) -> User:
    person = await _no_memberships(t)
    cove = await OrganizationFactory.create_async(
        workspace=t.workspace, name="Cove Retail", slug="cove-retail"
    )
    await MembershipFactory.create_async(organization=cove, user=person, role=OrgRole.OWNER)
    return person


@pytest.mark.parametrize(
    "outsider",
    [_no_memberships, _on_another_project_of_the_org, _other_workspace_staff, _other_org_member],
)
@pytest.mark.parametrize("who", ["project_admin", "org_admin"])
async def test_adding_by_user_id_anyone_outside_the_org_and_the_staff_is_404(
    client: AsyncClient,
    session: AsyncSession,
    who: str,
    outsider: Callable[[Tenancy], Awaitable[User]],
) -> None:
    """design-doc §4: adding by user ID rejects anyone else with a 404, which reads the same as
    for a user who doesn't exist, so it doesn't reveal whether the user exists."""
    t, _ = await signed_in(client, who)
    zed = await outsider(t)

    response = await client.post(
        "/api/projects/PMT/members", json={"user_id": str(zed.id), "role": "member"}
    )

    nobody = await client.post(
        "/api/projects/PMT/members", json={"user_id": str(uuid.uuid4()), "role": "member"}
    )
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == nobody.json()
    assert "zed@elsewhere.example" not in response.text
    assert "Zed Quill" not in response.text
    assert await stored_role(session, t, zed.id) is None
    assert await audit_events(session) == 0


# --- POST /api/projects/{key}/members/new (project_member.manage) -------------------------------


async def stored_new_account(session: AsyncSession, t: Tenancy) -> tuple[str | None, str | None]:
    """The new account's org role and project role, re-read from the database."""
    erin = User.email == "erin@bolt.example"
    org_role = await session.scalar(
        select(Membership.role)
        .join(User, User.id == Membership.user_id)
        .where(erin, Membership.organization_id == t.org.id)
    )
    project_role = await session.scalar(
        select(ProjectMembership.role)
        .join(User, User.id == ProjectMembership.user_id)
        .where(erin, ProjectMembership.project_id == t.project.id)
    )
    return (org_role, project_role)


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_project_admins_inherited_included_create_a_member(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """Build plan: the user, their org membership (role member), and the project membership in
    one step (`user_created`, `org_member_added`, `project_member_added`)."""
    t, _ = await signed_in(client, who)

    response = await client.post("/api/projects/PMT/members/new", json=NEW_ACCOUNT)

    assert (response.status_code, response.json()["email"]) == (201, "erin@bolt.example")
    assert await stored_new_account(session, t) == ("member", "member")
    assert await audit_actions(session) == [
        "org_member_added",
        "project_member_added",
        "user_created",
    ]


@pytest.mark.parametrize("who", SEE_ONLY)
async def test_creating_a_member_is_403_to_project_members_and_viewers(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)

    response = await client.post("/api/projects/PMT/members/new", json=NEW_ACCOUNT)

    assert_forbidden(response)
    assert await stored_new_account(session, t) == (None, None)
    assert await audit_events(session) == 0


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_creating_a_member_is_404_to_whoever_cannot_see_the_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)

    response = await client.post("/api/projects/PMT/members/new", json=NEW_ACCOUNT)

    missing = await client.post("/api/projects/ZZZ/members/new", json=NEW_ACCOUNT)
    assert_hidden(response, missing)
    assert await stored_new_account(session, t) == (None, None)
    assert await audit_events(session) == 0


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_creating_a_member_on_an_archived_project_is_403(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    await archive(session, t)

    response = await client.post("/api/projects/PMT/members/new", json=NEW_ACCOUNT)

    assert_forbidden(response)
    assert await stored_new_account(session, t) == (None, None)
    assert await audit_events(session) == 0


# --- PATCH /api/projects/{key}/members/{user_id} (project_member.manage) ------------------------


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_project_admins_inherited_included_change_a_role(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    target = await ivy(t)

    response = await client.patch(f"/api/projects/PMT/members/{target.id}", json={"role": "admin"})

    assert (response.status_code, response.json()["role"]) == (200, "admin")
    assert await stored_role(session, t, target.id) == "admin"
    assert await audit_actions(session) == ["project_member_role_changed"]


async def test_the_only_project_admin_may_demote_themselves(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-71, DL-79: no last-admin guard; a project admin changes any role, their own included."""
    t, admin = await signed_in(client, "project_admin")

    response = await client.patch(f"/api/projects/PMT/members/{admin.id}", json={"role": "viewer"})

    assert (response.status_code, response.json()["role"]) == (200, "viewer")
    assert await stored_role(session, t, admin.id) == "viewer"


@pytest.mark.parametrize("who", SEE_ONLY)
async def test_changing_a_role_is_403_to_project_members_and_viewers(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    target = await ivy(t)

    response = await client.patch(f"/api/projects/PMT/members/{target.id}", json={"role": "admin"})

    assert_forbidden(response)
    assert await stored_role(session, t, target.id) == "member"
    assert await audit_events(session) == 0


@pytest.mark.parametrize("who", SEE_ONLY)
async def test_a_project_member_or_viewer_may_not_promote_themselves(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, me = await signed_in(client, who)
    before = await stored_role(session, t, me.id)

    response = await client.patch(f"/api/projects/PMT/members/{me.id}", json={"role": "admin"})

    assert_forbidden(response)
    assert await stored_role(session, t, me.id) == before
    assert await audit_events(session) == 0


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_changing_a_role_is_404_to_whoever_cannot_see_the_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    target = await ivy(t)
    path = f"members/{target.id}"

    response = await client.patch(f"/api/projects/PMT/{path}", json={"role": "admin"})

    missing = await client.patch(f"/api/projects/ZZZ/{path}", json={"role": "admin"})
    assert_hidden(response, missing)
    assert await stored_role(session, t, target.id) == "member"
    assert await audit_events(session) == 0


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_changing_a_role_on_an_archived_project_is_403(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    target = await ivy(t)
    await archive(session, t)

    response = await client.patch(f"/api/projects/PMT/members/{target.id}", json={"role": "admin"})

    assert_forbidden(response)
    assert await stored_role(session, t, target.id) == "member"
    assert await audit_events(session) == 0


# --- DELETE /api/projects/{key}/members/{user_id} (project_member.manage) -----------------------


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_project_admins_inherited_included_remove_a_member(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    target = await ivy(t)

    response = await client.delete(f"/api/projects/PMT/members/{target.id}")

    assert response.status_code == 204
    assert await stored_role(session, t, target.id) is None
    assert await audit_actions(session) == ["project_member_removed"]


async def test_the_only_project_admin_may_remove_themselves(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-71, DL-79: no last-admin guard."""
    t, admin = await signed_in(client, "project_admin")

    response = await client.delete(f"/api/projects/PMT/members/{admin.id}")

    assert response.status_code == 204
    assert await stored_role(session, t, admin.id) is None


async def test_a_removed_member_loses_the_project_on_their_next_request(
    client: AsyncClient,
) -> None:
    """testing-strategy, security: removing a membership ends access on the user's next request
    (design-doc §4: their sessions are left alone)."""
    t, admin = await signed_in(client, "project_admin")
    target = await ivy(t)
    await sign_in_as(client, target)
    assert (await client.get("/api/projects/PMT")).status_code == 200
    await sign_in_as(client, admin)

    removed = await client.delete(f"/api/projects/PMT/members/{target.id}")

    assert removed.status_code == 204
    await sign_in_as(client, target)
    assert_hidden(await client.get("/api/projects/PMT"), await client.get("/api/projects/ZZZ"))


@pytest.mark.parametrize("who", SEE_ONLY)
async def test_removing_a_member_is_403_to_project_members_and_viewers(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    target = await ivy(t)

    response = await client.delete(f"/api/projects/PMT/members/{target.id}")

    assert_forbidden(response)
    assert await stored_role(session, t, target.id) == "member"
    assert await audit_events(session) == 0


@pytest.mark.parametrize("who", SEE_ONLY)
async def test_a_project_member_or_viewer_may_not_remove_themselves(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """Managing members is a project admin's (design-doc §5, "Project roles"); projects have no
    stepping down (DL-71)."""
    t, me = await signed_in(client, who)
    before = await stored_role(session, t, me.id)

    response = await client.delete(f"/api/projects/PMT/members/{me.id}")

    assert_forbidden(response)
    assert await stored_role(session, t, me.id) == before
    assert await audit_events(session) == 0


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_removing_a_member_is_404_to_whoever_cannot_see_the_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    target = await ivy(t)

    response = await client.delete(f"/api/projects/PMT/members/{target.id}")

    missing = await client.delete(f"/api/projects/ZZZ/members/{target.id}")
    assert_hidden(response, missing)
    assert await stored_role(session, t, target.id) == "member"
    assert await audit_events(session) == 0


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_removing_a_member_directly_from_an_archived_project_is_403(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """testing-strategy: removing a project member directly is still denied there (only removal
    with their projects is archive-exempt, design-doc §5, step 1)."""
    t, _ = await signed_in(client, who)
    target = await ivy(t)
    await archive(session, t)

    response = await client.delete(f"/api/projects/PMT/members/{target.id}")

    assert_forbidden(response)
    assert await stored_role(session, t, target.id) == "member"
    assert await audit_events(session) == 0


# --- GET /api/projects/{key}/access (project.view_access; every denial a 404) -------------------


@pytest.mark.parametrize(
    ("who", "role", "reasons"),
    [
        ("system_admin", None, ["system_admin"]),
        ("workspace_owner", None, ["workspace_owner"]),
        ("workspace_admin", None, ["workspace_admin"]),
        ("org_owner", None, ["org_owner"]),
        ("org_admin", None, ["org_admin"]),
        ("project_admin", "admin", ["project_admin"]),
    ],
)
async def test_project_admins_inherited_included_open_the_access_review(
    client: AsyncClient, who: str, role: str | None, reasons: list[str]
) -> None:
    """design-doc §5, "Access review": everyone with access and why, an explicit project role or
    inherited admin and through which role; the caller is among them."""
    t, me = await signed_in(client, who)
    await ivy(t)

    response = await client.get("/api/projects/PMT/access")

    assert response.status_code == 200
    people = {p["user"]["email"]: (p["role"], p["reasons"]) for p in response.json()["people"]}
    assert people[IVY] == ("member", ["project_member"])
    assert people[me.email] == (role, reasons)


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_an_archived_projects_access_review_is_still_open_to_its_admins(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """DL-79: `project.view_access` is not a mutation."""
    t, _ = await signed_in(client, who)
    await ivy(t)
    await archive(session, t)

    response = await client.get("/api/projects/PMT/access")

    assert response.status_code == 200
    people = {p["user"]["email"]: (p["role"], p["reasons"]) for p in response.json()["people"]}
    assert people[IVY] == ("member", ["project_member"])


@pytest.mark.parametrize("who", [*SEE_ONLY, *PROJECT_UNSEEN])
async def test_the_access_review_is_404_to_everyone_else(client: AsyncClient, who: str) -> None:
    """design-doc §5, "Access review": anyone else gets a 404, project members and viewers
    included, though they see the project."""
    t, _ = await signed_in(client, who)
    await ivy(t)

    response = await client.get("/api/projects/PMT/access")

    assert_hidden(response, await client.get("/api/projects/ZZZ/access"))


@pytest.mark.parametrize("who", SEE_ONLY)
async def test_an_archived_projects_access_review_is_404_to_members_and_viewers(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    await ivy(t)
    await archive(session, t)

    response = await client.get("/api/projects/PMT/access")

    assert_hidden(response, await client.get("/api/projects/ZZZ/access"))
