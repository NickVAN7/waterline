"""The project members API's behavior beyond who may call it (build plan, "The project members
API"; DL-71, DL-78, DL-80): the email-first add and its four outcomes, `join_org`, the add by
`user_id` and its order of checks, create, role changes, removal and the lead, removal "with their
projects" across the org, workspace, and project areas, the picker's search, and the per-project
access review's content. Who gets 2xx/403/404 is in tests/api/authz/test_project_members.py (spec
tests)."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AuditAction, OrgRole, ProjectRole, WorkspaceRole
from app.models.audit_event import AuditEvent
from app.models.org import Membership
from app.models.project import Project, ProjectMembership
from app.models.user import User
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

MEMBERS = "/api/projects/PMT/members"


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


@pytest.fixture
async def admin(client: AsyncClient, t: Tenancy) -> User:
    """PMT's explicit admin, signed in."""
    user = await UserFactory.create_async(name="Ada Admin", email="ada@acme.example")
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.ADMIN
    )
    await sign_in_as(client, user)
    return user


async def org_member(t: Tenancy, **user: object) -> User:
    person = await UserFactory.create_async(**user)
    await MembershipFactory.create_async(organization=t.org, user=person, role=OrgRole.MEMBER)
    return person


async def staff(t: Tenancy, role: WorkspaceRole = WorkspaceRole.MEMBER, **user: object) -> User:
    person = await UserFactory.create_async(**user)
    await WorkspaceMembershipFactory.create_async(workspace=t.workspace, user=person, role=role)
    return person


async def outsider(**user: object) -> User:
    """A member of another org in the workspace: outside the project's org and the staff."""
    person = await UserFactory.create_async(**user)
    await MembershipFactory.create_async(user=person, role=OrgRole.MEMBER)
    return person


async def project_roles(session: AsyncSession, project: Project) -> dict[object, ProjectRole]:
    rows = await session.execute(
        select(ProjectMembership.user_id, ProjectMembership.role).where(
            ProjectMembership.project_id == project.id
        )
    )
    return dict(rows.all())


async def org_role(session: AsyncSession, t: Tenancy, user: User) -> OrgRole | None:
    return await session.scalar(
        select(Membership.role).where(
            Membership.organization_id == t.org.id, Membership.user_id == user.id
        )
    )


async def events(session: AsyncSession) -> list[tuple[object, ...]]:
    rows = await session.execute(
        select(
            AuditEvent.action,
            AuditEvent.actor_id,
            AuditEvent.project_id,
            AuditEvent.target_user_id,
            AuditEvent.details,
        ).order_by(AuditEvent.id)
    )
    return [tuple(row) for row in rows]


async def lead_of(session: AsyncSession, project: Project) -> object:
    return await session.scalar(
        select(Project.lead_id)
        .where(Project.id == project.id)
        .execution_options(populate_existing=True)
    )


def fields(body: dict[str, object]) -> list[tuple[list[object], str]]:
    return [(e["loc"], e["type"]) for e in body["details"]["fields"]]  # pyright: ignore[reportIndexIssue, reportUnknownVariableType, reportArgumentType]


# --- Add by email (email first, DL-78) ------------------------------------------------------------


async def test_an_org_members_email_adds_only_the_project_membership(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    bob = await org_member(t, email="bob@bolt.example", name="Bob")

    response = await client.post(MEMBERS, json={"email": " BOB@bolt.example ", "role": "viewer"})

    assert response.status_code == 201
    assert (response.json()["user_id"], response.json()["role"]) == (str(bob.id), "viewer")
    assert (await project_roles(session, t.project))[bob.id] is ProjectRole.VIEWER
    assert await events(session) == [
        (AuditAction.PROJECT_MEMBER_ADDED, admin.id, t.project.id, bob.id, {"role": "viewer"})
    ]


async def test_a_staff_members_email_adds_no_org_membership(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    sam = await staff(t, email="sam@acme.example")

    response = await client.post(MEMBERS, json={"email": "sam@acme.example", "role": "member"})

    assert response.status_code == 201
    assert (await project_roles(session, t.project))[sam.id] is ProjectRole.MEMBER
    assert await org_role(session, t, sam) is None


@pytest.mark.parametrize(
    ("email", "code"),
    [
        ("ada@acme.example", "already_member"),  # the signed-in admin, already on PMT
        ("nobody@acme.example", "no_account"),
        ("gone@bolt.example", "account_inactive"),
        ("out@other.example", "outside_org"),
    ],
)
async def test_the_email_first_add_explains_why_it_cant_add(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User, email: str, code: str
) -> None:
    await org_member(t, email="gone@bolt.example", is_active=False)
    await outsider(email="out@other.example")
    before = await project_roles(session, t.project)

    response = await client.post(MEMBERS, json={"email": email, "role": "member"})

    assert response.status_code == 422
    assert fields(response.json()) == [(["body", "email"], code)]
    assert await project_roles(session, t.project) == before
    assert await events(session) == []


async def test_someone_already_on_the_project_is_already_member_even_when_deactivated(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """DL-78's order: `already_member` before `account_inactive`."""
    gone = await org_member(t, email="gone@bolt.example", is_active=False)
    await ProjectMembershipFactory.create_async(project=t.project, user=gone)

    response = await client.post(MEMBERS, json={"email": "gone@bolt.example", "role": "member"})

    assert fields(response.json()) == [(["body", "email"], "already_member")]


async def test_join_org_adds_an_outsider_to_the_org_and_the_project(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    out = await outsider(email="out@other.example")

    response = await client.post(
        MEMBERS, json={"email": "out@other.example", "role": "member", "join_org": True}
    )

    assert response.status_code == 201
    assert await org_role(session, t, out) is OrgRole.MEMBER
    assert (await project_roles(session, t.project))[out.id] is ProjectRole.MEMBER
    assert [(e[0], e[1], e[3], e[4]) for e in await events(session)] == [
        (AuditAction.ORG_MEMBER_ADDED, admin.id, out.id, {"role": "member"}),
        (AuditAction.PROJECT_MEMBER_ADDED, admin.id, out.id, {"role": "member"}),
    ]


async def test_join_org_never_adds_a_deactivated_outsider(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    out = await outsider(email="out@other.example", is_active=False)

    response = await client.post(
        MEMBERS, json={"email": "out@other.example", "role": "member", "join_org": True}
    )

    assert fields(response.json()) == [(["body", "email"], "account_inactive")]
    assert await org_role(session, t, out) is None
    assert await events(session) == []


# --- Add by user_id (the picker) ----------------------------------------------------------------


async def test_adding_by_user_id_records_the_role(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    bob = await org_member(t)

    response = await client.post(MEMBERS, json={"user_id": str(bob.id), "role": "admin"})

    assert response.status_code == 201
    assert (await project_roles(session, t.project))[bob.id] is ProjectRole.ADMIN
    assert await events(session) == [
        (AuditAction.PROJECT_MEMBER_ADDED, admin.id, t.project.id, bob.id, {"role": "admin"})
    ]


@pytest.mark.parametrize("active", [True, False])
async def test_adding_by_user_id_someone_already_on_the_project_is_already_member(
    client: AsyncClient, t: Tenancy, admin: User, active: bool
) -> None:
    """DL-78's order: `already_member` before `account_inactive`."""
    bob = await org_member(t, is_active=active)
    await ProjectMembershipFactory.create_async(project=t.project, user=bob)

    response = await client.post(MEMBERS, json={"user_id": str(bob.id), "role": "member"})

    assert response.status_code == 422
    assert fields(response.json()) == [(["body", "user_id"], "already_member")]


async def test_adding_by_user_id_a_deactivated_account_is_refused(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    bob = await org_member(t, is_active=False)

    response = await client.post(MEMBERS, json={"user_id": str(bob.id), "role": "member"})

    assert response.status_code == 422
    assert fields(response.json()) == [(["body", "user_id"], "account_inactive")]
    assert bob.id not in await project_roles(session, t.project)


async def test_a_project_only_member_re_added_by_user_id_is_a_404(
    client: AsyncClient, t: Tenancy, admin: User
) -> None:
    """DL-78's order: outside the org's members and the staff is a 404 before `already_member`."""
    pat = await UserFactory.create_async()
    await ProjectMembershipFactory.create_async(project=t.project, user=pat)

    response = await client.post(MEMBERS, json={"user_id": str(pat.id), "role": "member"})

    assert (response.status_code, response.json()["code"]) == (404, "not_found")


@pytest.mark.parametrize(
    "body",
    [
        {"role": "member"},
        {"role": "member", "email": "a@b.example", "user_id": UserFactory.__faker__.uuid4()},
    ],
)
async def test_an_add_needs_exactly_one_of_user_id_and_email(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User, body: dict[str, object]
) -> None:
    response = await client.post(MEMBERS, json=body)

    assert response.status_code == 422
    assert fields(response.json()) == [(["body"], "one_parameter")]
    assert await events(session) == []


# --- Create ---------------------------------------------------------------------------------------


async def test_creating_a_member_makes_the_account_the_org_membership_and_the_project_role(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    response = await client.post(
        f"{MEMBERS}/new",
        json={
            "email": "New@Bolt.example",
            "username": "nina-new",
            "name": "Nina New",
            "password": "temporary-pass-1",
            "role": "viewer",
        },
    )

    assert response.status_code == 201
    nina = (await session.execute(select(User).where(User.username == "nina-new"))).scalar_one()
    assert (nina.email, nina.must_change_password) == ("new@bolt.example", True)
    assert await org_role(session, t, nina) is OrgRole.MEMBER
    assert (await project_roles(session, t.project))[nina.id] is ProjectRole.VIEWER
    assert [(e[0], e[1], e[3]) for e in await events(session)] == [
        (AuditAction.USER_CREATED, admin.id, nina.id),
        (AuditAction.ORG_MEMBER_ADDED, admin.id, nina.id),
        (AuditAction.PROJECT_MEMBER_ADDED, admin.id, nina.id),
    ]


async def test_creating_a_member_with_a_taken_email_creates_nothing(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    await org_member(t, email="bob@bolt.example")
    before = await project_roles(session, t.project)

    response = await client.post(
        f"{MEMBERS}/new",
        json={
            "email": "bob@bolt.example",
            "username": "bob-two",
            "name": "Bob Two",
            "password": "temporary-pass-1",
            "role": "member",
        },
    )

    assert fields(response.json()) == [(["body", "email"], "taken")]
    assert await project_roles(session, t.project) == before
    assert await events(session) == []


# --- Role change ---------------------------------------------------------------------------------


async def test_a_role_change_records_old_and_new(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    bob = await org_member(t)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=bob, role=ProjectRole.VIEWER
    )

    response = await client.patch(f"{MEMBERS}/{bob.id}", json={"role": "admin"})

    assert (response.status_code, response.json()["role"]) == (200, "admin")
    assert (await project_roles(session, t.project))[bob.id] is ProjectRole.ADMIN
    assert await events(session) == [
        (
            AuditAction.PROJECT_MEMBER_ROLE_CHANGED,
            admin.id,
            t.project.id,
            bob.id,
            {"old_role": "viewer", "new_role": "admin"},
        )
    ]


async def test_a_role_change_to_the_same_role_records_nothing(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    bob = await org_member(t)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=bob, role=ProjectRole.MEMBER
    )

    response = await client.patch(f"{MEMBERS}/{bob.id}", json={"role": "member"})

    assert (response.status_code, response.json()["role"]) == (200, "member")
    assert await events(session) == []


async def test_a_role_change_for_someone_not_on_the_project_is_a_404(
    client: AsyncClient, t: Tenancy, admin: User
) -> None:
    bob = await org_member(t)

    response = await client.patch(f"{MEMBERS}/{bob.id}", json={"role": "admin"})

    assert (response.status_code, response.json()["code"]) == (404, "not_found")


# --- Removal and the lead -------------------------------------------------------------------------


async def test_removing_the_lead_clears_the_lead_and_records_it(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    bob = await org_member(t)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=bob, role=ProjectRole.MEMBER
    )
    t.project.lead_id = bob.id
    await session.flush()

    response = await client.delete(f"{MEMBERS}/{bob.id}")

    assert response.status_code == 204
    assert bob.id not in await project_roles(session, t.project)
    assert await lead_of(session, t.project) is None
    assert await events(session) == [
        (
            AuditAction.PROJECT_MEMBER_REMOVED,
            admin.id,
            t.project.id,
            bob.id,
            {"role": "member", "lead_cleared": True},
        )
    ]


async def test_removing_someone_else_leaves_the_lead(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    bob = await org_member(t)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=bob, role=ProjectRole.VIEWER
    )
    t.project.lead_id = admin.id
    await session.flush()

    response = await client.delete(f"{MEMBERS}/{bob.id}")

    assert response.status_code == 204
    assert await lead_of(session, t.project) == admin.id
    assert [e[4] for e in await events(session)] == [{"role": "viewer"}]


async def test_removing_someone_not_on_the_project_is_a_404(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    bob = await org_member(t)

    response = await client.delete(f"{MEMBERS}/{bob.id}")

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert await events(session) == []


# --- Removal with their projects (the on_member_removed handler, across areas) --------------------


@pytest.fixture
async def ledger(t: Tenancy) -> Project:
    """A second project of the org, archived."""
    return await ProjectFactory.create_async(
        organization=t.org, key="LDG", name="Ledger", archived_at=datetime.now(UTC)
    )


@pytest.fixture
async def elsewhere(t: Tenancy) -> Project:
    """A project of another org in the same workspace."""
    org = await OrganizationFactory.create_async(workspace=t.workspace, slug="other-org")
    return await ProjectFactory.create_async(organization=org, key="ELS", name="Elsewhere")


async def test_removing_an_org_member_with_projects_removes_them_from_the_orgs_projects(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    ledger: Project,
    elsewhere: Project,
) -> None:
    owner = await UserFactory.create_async()
    await MembershipFactory.create_async(organization=t.org, user=owner, role=OrgRole.OWNER)
    bob = await org_member(t)
    for project in (t.project, ledger, elsewhere):
        await ProjectMembershipFactory.create_async(project=project, user=bob)
    ledger.lead_id = bob.id
    await session.flush()
    await sign_in_as(client, owner)

    response = await client.delete(f"/api/orgs/{t.org.id}/members/{bob.id}?with_projects=true")

    assert response.status_code == 204
    assert bob.id not in await project_roles(session, t.project)
    assert bob.id not in await project_roles(session, ledger)  # archived included
    assert bob.id in await project_roles(session, elsewhere)  # another org's project stays
    assert await lead_of(session, ledger) is None
    removed = [
        (e[1], e[2], e[4])
        for e in await events(session)
        if e[0] == AuditAction.PROJECT_MEMBER_REMOVED
    ]
    assert sorted(removed, key=str) == sorted(
        [
            (owner.id, t.project.id, {"role": "member", "via": "org_member_removed"}),
            (
                owner.id,
                ledger.id,
                {"role": "member", "lead_cleared": True, "via": "org_member_removed"},
            ),
        ],
        key=str,
    )


async def test_removing_an_org_member_without_projects_leaves_them(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    owner = await UserFactory.create_async()
    await MembershipFactory.create_async(organization=t.org, user=owner, role=OrgRole.OWNER)
    bob = await org_member(t)
    await ProjectMembershipFactory.create_async(project=t.project, user=bob)
    await sign_in_as(client, owner)

    response = await client.delete(f"/api/orgs/{t.org.id}/members/{bob.id}?with_projects=false")

    assert response.status_code == 204
    assert bob.id in await project_roles(session, t.project)


async def test_removing_staff_with_projects_removes_them_from_every_workspace_project(
    client: AsyncClient, session: AsyncSession, t: Tenancy, elsewhere: Project
) -> None:
    owner = await staff(t, role=WorkspaceRole.OWNER)
    sam = await staff(t)
    other_workspace = await WorkspaceFactory.create_async(slug="other-firm")
    other_org = await OrganizationFactory.create_async(workspace=other_workspace)
    abroad = await ProjectFactory.create_async(organization=other_org, key="ABR")
    for project in (t.project, elsewhere, abroad):
        await ProjectMembershipFactory.create_async(project=project, user=sam)
    await sign_in_as(client, owner)

    response = await client.delete(
        f"/api/workspaces/{t.workspace.id}/staff/{sam.id}?with_projects=true"
    )

    assert response.status_code == 204
    assert sam.id not in await project_roles(session, t.project)
    assert sam.id not in await project_roles(session, elsewhere)
    assert sam.id in await project_roles(session, abroad)  # another workspace's project stays
    removed = [
        (e[2], e[4]) for e in await events(session) if e[0] == AuditAction.PROJECT_MEMBER_REMOVED
    ]
    via = {"role": "member", "via": "workspace_member_removed"}
    assert sorted(removed, key=str) == sorted([(t.project.id, via), (elsewhere.id, via)], key=str)


# --- The picker and the member list ---------------------------------------------------------------


async def test_the_picker_searches_names_emails_and_usernames(
    client: AsyncClient, t: Tenancy, admin: User
) -> None:
    await org_member(t, name="Bob Baker", email="bob@bolt.example", username="bob-baker")
    await org_member(t, name="Carol Cook", email="carol@bolt.example", username="ccook")
    await staff(t, name="Dan Diaz", email="dan@acme.example", username="cook-fan")

    response = await client.get("/api/projects/PMT/member-candidates?q=cook")

    assert response.status_code == 200
    assert [c["name"] for c in response.json()["items"]] == ["Carol Cook", "Dan Diaz"]


async def test_the_member_list_is_sorted_by_name_and_filters_by_role(
    client: AsyncClient, t: Tenancy, admin: User
) -> None:
    for name, role in (("Zed", ProjectRole.VIEWER), ("Bea", ProjectRole.MEMBER)):
        user = await UserFactory.create_async(name=name)
        await ProjectMembershipFactory.create_async(project=t.project, user=user, role=role)

    everyone = await client.get(MEMBERS)
    viewers = await client.get(f"{MEMBERS}?role=viewer")

    assert [m["name"] for m in everyone.json()["items"]] == ["Ada Admin", "Bea", "Zed"]
    assert [m["name"] for m in viewers.json()["items"]] == ["Zed"]


async def test_project_member_rows_carry_no_account_fields(client: AsyncClient, t: Tenancy) -> None:
    """DL-102 covers staff and org member rows only. A workspace admin may open anyone's access
    review (design-doc §5), so `user.view_access` would show here if the rows carried it."""
    await sign_in_as(client, await staff(t, WorkspaceRole.ADMIN))
    bea = await UserFactory.create_async(name="Bea")
    await ProjectMembershipFactory.create_async(
        project=t.project, user=bea, role=ProjectRole.MEMBER
    )

    rows = {m["name"]: m for m in (await client.get(MEMBERS)).json()["items"]}

    assert "is_active" not in rows["Bea"]
    assert rows["Bea"]["allowed_actions"] == ["project_member.manage"]


UNSEEN = [
    "org_member",
    "other_project_admin",
    "workspace_member",
    "other_org_owner",
    "other_workspace_owner",
    "nobody",
]


@pytest.mark.parametrize("who", UNSEEN)
async def test_the_member_list_is_404_to_whoever_cannot_see_the_project(
    client: AsyncClient, t: Tenancy, who: str
) -> None:
    """The denial test for `project.view` on the member list (DL-32: the spec tests left it out,
    as it passes against both stub answers). It holds members' emails, so it must name nobody."""
    ivy = await UserFactory.create_async(email="ivy@bolt.example", name="Ivy Moss")
    await ProjectMembershipFactory.create_async(project=t.project, user=ivy)
    await sign_in_as(client, await persona_user(t, who))

    response = await client.get(MEMBERS)
    missing = await client.get("/api/projects/ZZZ/members")

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    assert "ivy@bolt.example" not in response.text
    assert "Ivy Moss" not in response.text


# --- The per-project access review ----------------------------------------------------------------


async def test_the_access_review_lists_everyone_who_reaches_the_project_and_why(
    client: AsyncClient, t: Tenancy, admin: User
) -> None:
    await UserFactory.create_async(name="Sys Admin", is_system_admin=True)
    await staff(t, role=WorkspaceRole.OWNER, name="Wendy Owner")
    await staff(t, role=WorkspaceRole.MEMBER, name="Walt Member")  # no project access
    olga = await UserFactory.create_async(name="Olga Orgadmin")
    await MembershipFactory.create_async(organization=t.org, user=olga, role=OrgRole.ADMIN)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=olga, role=ProjectRole.VIEWER
    )
    await org_member(t, name="Otto Orgmember")  # no project access
    await UserFactory.create_async(name="Vic Gone", is_active=False, is_system_admin=True)
    await persona_user(t, "other_org_owner")  # another client's admin: not listed
    await persona_user(t, "other_workspace_owner")  # another firm's admin: not listed

    response = await client.get("/api/projects/PMT/access")

    assert response.status_code == 200
    assert [
        (p["user"]["name"], p["user"]["is_active"], p["role"], p["reasons"])
        for p in response.json()["people"]
    ] == [
        ("Ada Admin", True, "admin", ["project_admin"]),
        ("Olga Orgadmin", True, "viewer", ["org_admin", "project_viewer"]),
        ("Sys Admin", True, None, ["system_admin"]),
        ("Vic Gone", False, None, ["system_admin"]),
        ("Wendy Owner", True, None, ["workspace_owner"]),
    ]
