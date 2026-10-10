"""The workspace and its staff, beyond who may call each endpoint (the authz spec tests cover
that): what each change does, its audit event, and its errors (build plan, "The workspace and org
API", DL-55; design-doc §4, §10.1)."""

from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionMaker
from app.core.security import verify_password
from app.core.settings import Settings
from app.enums import AuditAction, AuditEntityType, WorkspaceRole
from app.main import create_app
from app.models.audit_event import AuditEvent
from app.models.auth import UserSession
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from app.services import workspace as workspace_service
from app.services.workspace import MemberRemoval
from tests.factories.org import OrganizationFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory
from tests.support.api import api_client
from tests.support.authz import sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]


async def owner_of(client: AsyncClient, workspace: Workspace) -> User:
    """Sign `client` in as a new owner of `workspace`."""
    user = await UserFactory.create_async()
    await WorkspaceMembershipFactory.create_async(
        workspace=workspace, user=user, role=WorkspaceRole.OWNER
    )
    await sign_in_as(client, user)
    return user


async def events(session: AsyncSession) -> list[tuple[object, ...]]:
    rows = await session.execute(
        select(
            AuditEvent.action,
            AuditEvent.actor_id,
            AuditEvent.workspace_id,
            AuditEvent.target_user_id,
            AuditEvent.entity_type,
            AuditEvent.details,
        ).order_by(AuditEvent.id)
    )
    return [tuple(row) for row in rows]


async def role_of(session: AsyncSession, workspace: Workspace, user: User) -> WorkspaceRole | None:
    return await session.scalar(
        select(WorkspaceMembership.role).where(
            WorkspaceMembership.workspace_id == workspace.id,
            WorkspaceMembership.user_id == user.id,
        )
    )


def fields(body: dict[str, object]) -> list[tuple[list[object], str]]:
    details = body["details"]
    assert isinstance(details, dict)
    return [(f["loc"], f["type"]) for f in details["fields"]]  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]


@pytest.fixture
async def workspace() -> Workspace:
    return await WorkspaceFactory.create_async(name="Acme Consulting", slug="acme")


# --- The workspace ------------------------------------------------------------------------------


async def test_renaming_the_workspace_records_old_and_new_values(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    owner = await owner_of(client, workspace)

    response = await client.patch(
        f"/api/workspaces/{workspace.id}", json={"name": "Acme Partners", "slug": "acme-partners"}
    )

    assert (response.status_code, response.json()["name"], response.json()["slug"]) == (
        200,
        "Acme Partners",
        "acme-partners",
    )
    stored = (await session.execute(select(Workspace.name, Workspace.slug))).one()
    assert tuple(stored) == ("Acme Partners", "acme-partners")
    assert await events(session) == [
        (
            AuditAction.WORKSPACE_UPDATED,
            owner.id,
            workspace.id,
            None,
            AuditEntityType.WORKSPACE,
            {
                "old": {"name": "Acme Consulting", "slug": "acme"},
                "new": {"name": "Acme Partners", "slug": "acme-partners"},
            },
        )
    ]


async def test_an_update_that_changes_nothing_records_nothing(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    await owner_of(client, workspace)

    response = await client.patch(f"/api/workspaces/{workspace.id}", json={"slug": "acme"})

    assert response.status_code == 200
    assert await events(session) == []


@pytest.mark.parametrize(
    ("body", "field", "type_"),
    [
        ({"slug": "api"}, "slug", "reserved"),
        ({"slug": "Acme"}, "slug", "invalid_characters"),
        ({"name": "  "}, "name", "missing"),
    ],
)
async def test_an_invalid_name_or_slug_is_a_422(
    client: AsyncClient, workspace: Workspace, body: dict[str, str], field: str, type_: str
) -> None:
    await owner_of(client, workspace)

    response = await client.patch(f"/api/workspaces/{workspace.id}", json=body)

    assert response.status_code == 422
    assert fields(response.json()) == [(["body", field], type_)]


async def test_a_slug_another_workspace_has_is_a_422_taken(
    client: AsyncClient, workspace: Workspace
) -> None:
    await WorkspaceFactory.create_async(slug="taken-one")
    await owner_of(client, workspace)

    response = await client.patch(f"/api/workspaces/{workspace.id}", json={"slug": "taken-one"})

    assert (response.status_code, fields(response.json())) == (422, [(["body", "slug"], "taken")])


@pytest.mark.parametrize(
    ("slug", "expected"),
    [
        ("fresh-slug", {"available": True, "problem": None}),
        ("acme", {"available": True, "problem": None}),
        ("taken-one", {"available": False, "problem": "taken"}),
        ("status", {"available": False, "problem": "reserved"}),
        ("a", {"available": False, "problem": "too_short"}),
    ],
    ids=["free", "own", "taken", "reserved", "invalid"],
)
async def test_slug_availability_reports_the_rule_then_taken(
    client: AsyncClient, workspace: Workspace, slug: str, expected: dict[str, object]
) -> None:
    await WorkspaceFactory.create_async(slug="taken-one")
    await owner_of(client, workspace)

    response = await client.get(
        f"/api/workspaces/{workspace.id}/slug-availability", params={"slug": slug}
    )

    assert response.json() == expected


async def test_the_openapi_schema_carries_the_reserved_slugs(client: AsyncClient) -> None:
    """DL-55: the frontend's router test (S1-C14) reads them from the generated schema."""
    schema = (await client.get("/api/openapi.json")).json()

    assert schema["components"]["schemas"]["ReservedSlug"]["enum"] == [
        "account",
        "api",
        "assets",
        "sign-in",
        "status",
        "workspace",
    ]


# --- Staff -------------------------------------------------------------------------------------


async def test_the_staff_list_is_sorted_by_name_and_filters_by_role(
    client: AsyncClient, workspace: Workspace
) -> None:
    await owner_of(client, workspace)  # an owner: the role filter leaves them out
    cleo = await UserFactory.create_async(name="Cleo")
    abe = await UserFactory.create_async(name="Abe")
    await WorkspaceMembershipFactory.create_async(workspace=workspace, user=cleo)
    await WorkspaceMembershipFactory.create_async(workspace=workspace, user=abe)

    response = await client.get(
        f"/api/workspaces/{workspace.id}/staff", params={"role": "member", "sort": "name"}
    )

    body = response.json()
    assert ([row["name"] for row in body["items"]], body["total"]) == (["Abe", "Cleo"], 2)


async def staff_row_actions(client: AsyncClient, workspace: Workspace) -> dict[str, list[str]]:
    """Each staff row's `allowed_actions`, by the member's name."""
    response = await client.get(f"/api/workspaces/{workspace.id}/staff")
    return {row["name"]: row["allowed_actions"] for row in response.json()["items"]}


async def test_a_workspace_admin_sees_staff_actions_only_on_rows_they_may_change(
    client: AsyncClient, workspace: Workspace
) -> None:
    """An owner's or admin's row needs `workspace_staff.manage_admins` (DL-56), so a workspace
    admin is offered nothing there, except on their own row, for stepping down (DL-59)."""
    admin = await UserFactory.create_async(name="Ada Admin")
    await WorkspaceMembershipFactory.create_async(
        workspace=workspace, user=admin, role=WorkspaceRole.ADMIN
    )
    await WorkspaceMembershipFactory.create_async(
        workspace=workspace,
        user=await UserFactory.create_async(name="Olga Owner"),
        role=WorkspaceRole.OWNER,
    )
    await WorkspaceMembershipFactory.create_async(
        workspace=workspace, user=await UserFactory.create_async(name="Mo Member")
    )
    await sign_in_as(client, admin)

    assert await staff_row_actions(client, workspace) == {
        "Ada Admin": ["workspace_staff.manage"],
        "Mo Member": ["workspace_staff.manage"],
        "Olga Owner": [],
    }


async def test_a_workspace_owner_sees_both_staff_actions_on_every_row(
    client: AsyncClient, workspace: Workspace
) -> None:
    owner = await UserFactory.create_async(name="Olga Owner")
    await WorkspaceMembershipFactory.create_async(
        workspace=workspace, user=owner, role=WorkspaceRole.OWNER
    )
    await WorkspaceMembershipFactory.create_async(
        workspace=workspace,
        user=await UserFactory.create_async(name="Ada Admin"),
        role=WorkspaceRole.ADMIN,
    )
    await sign_in_as(client, owner)

    both = ["workspace_staff.manage", "workspace_staff.manage_admins"]
    assert await staff_row_actions(client, workspace) == {"Ada Admin": both, "Olga Owner": both}


async def test_a_role_change_to_the_same_role_changes_and_records_nothing(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    """Not a demotion, so the last owner may "change" to owner (no `last_owner`)."""
    owner = await owner_of(client, workspace)

    response = await client.patch(
        f"/api/workspaces/{workspace.id}/staff/{owner.id}", json={"role": "owner"}
    )

    assert (response.status_code, response.json()["role"]) == (200, "owner")
    assert await events(session) == []


async def test_adding_staff_by_email_adds_the_account_and_records_it(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    owner = await owner_of(client, workspace)
    ann = await UserFactory.create_async(email="ann@acme.example", name="Ann Lee")

    response = await client.post(
        f"/api/workspaces/{workspace.id}/staff",
        json={"email": "Ann@Acme.example", "role": "member"},
    )

    assert response.status_code == 201
    assert (response.json()["user_id"], response.json()["role"]) == (str(ann.id), "member")
    assert await role_of(session, workspace, ann) is WorkspaceRole.MEMBER
    assert await events(session) == [
        (
            AuditAction.WORKSPACE_MEMBER_ADDED,
            owner.id,
            workspace.id,
            ann.id,
            AuditEntityType.WORKSPACE,
            {"role": "member"},
        )
    ]


@pytest.mark.parametrize(
    ("email", "type_"),
    [
        ("nobody@acme.example", "no_account"),
        ("gone@acme.example", "account_inactive"),
        ("staff@acme.example", "already_member"),
    ],
)
async def test_the_email_first_add_explains_why_it_cant_add(
    client: AsyncClient, session: AsyncSession, workspace: Workspace, email: str, type_: str
) -> None:
    await owner_of(client, workspace)
    await UserFactory.create_async(email="gone@acme.example", is_active=False)
    staff = await UserFactory.create_async(email="staff@acme.example")
    await WorkspaceMembershipFactory.create_async(workspace=workspace, user=staff)
    before = await events(session)

    response = await client.post(
        f"/api/workspaces/{workspace.id}/staff", json={"email": email, "role": "member"}
    )

    assert (response.status_code, fields(response.json())) == (422, [(["body", "email"], type_)])
    assert await events(session) == before


@pytest.mark.security
async def test_the_role_is_checked_before_the_email_on_an_add(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    """A workspace admin granting admin gets the 403 even for an email with no account, so a
    caller who may not grant the role learns nothing about which emails exist."""
    admin = await UserFactory.create_async()
    await WorkspaceMembershipFactory.create_async(
        workspace=workspace, user=admin, role=WorkspaceRole.ADMIN
    )
    await sign_in_as(client, admin)

    response = await client.post(
        f"/api/workspaces/{workspace.id}/staff",
        json={"email": "nobody@acme.example", "role": "admin"},
    )

    assert (response.status_code, response.json()["code"]) == (403, "forbidden")
    assert await events(session) == []


async def test_creating_staff_makes_the_account_and_the_membership(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    owner = await owner_of(client, workspace)

    response = await client.post(
        f"/api/workspaces/{workspace.id}/staff/new",
        json={
            "email": "New@Acme.example",
            "username": "new-hire",
            "name": "New Hire",
            "password": "a temporary passphrase",
            "role": "admin",
        },
    )

    assert response.status_code == 201
    user = (await session.execute(select(User).where(User.username == "new-hire"))).scalar_one()
    assert (user.email, user.must_change_password) == ("new@acme.example", True)
    assert await verify_password(user.hashed_password, "a temporary passphrase") is True
    assert await role_of(session, workspace, user) is WorkspaceRole.ADMIN
    assert [(action, actor, target) for action, actor, _, target, *_ in await events(session)] == [
        (AuditAction.USER_CREATED, owner.id, user.id),
        (AuditAction.WORKSPACE_MEMBER_ADDED, owner.id, user.id),
    ]


async def test_creating_staff_with_invalid_values_creates_nothing(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    await owner_of(client, workspace)
    users_before = (await session.execute(select(func.count()).select_from(User))).scalar_one()

    response = await client.post(
        f"/api/workspaces/{workspace.id}/staff/new",
        json={
            "email": "not-an-email",
            "username": "9bad",
            "name": "",
            "password": "short",
            "role": "member",
        },
    )

    assert response.status_code == 422
    assert fields(response.json()) == [
        (["body", "email"], "invalid_email"),
        (["body", "username"], "must_start_with_letter"),
        (["body", "name"], "missing"),
        (["body", "password"], "too_short"),
    ]
    users_after = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    assert users_after == users_before


async def test_changing_a_role_records_old_and_new(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    owner = await owner_of(client, workspace)
    bob = await UserFactory.create_async()
    await WorkspaceMembershipFactory.create_async(
        workspace=workspace, user=bob, role=WorkspaceRole.MEMBER
    )

    response = await client.patch(
        f"/api/workspaces/{workspace.id}/staff/{bob.id}", json={"role": "admin"}
    )

    assert (response.status_code, response.json()["role"]) == (200, "admin")
    assert await role_of(session, workspace, bob) is WorkspaceRole.ADMIN
    assert await events(session) == [
        (
            AuditAction.WORKSPACE_MEMBER_ROLE_CHANGED,
            owner.id,
            workspace.id,
            bob.id,
            AuditEntityType.WORKSPACE,
            {"old_role": "member", "new_role": "admin"},
        )
    ]


async def test_a_role_change_for_someone_not_on_staff_is_a_404(
    client: AsyncClient, workspace: Workspace
) -> None:
    await owner_of(client, workspace)
    outsider = await UserFactory.create_async()

    response = await client.patch(
        f"/api/workspaces/{workspace.id}/staff/{outsider.id}", json={"role": "admin"}
    )

    assert (response.status_code, response.json()["code"]) == (404, "not_found")


async def test_the_last_owner_cant_be_demoted(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    owner = await owner_of(client, workspace)

    response = await client.patch(
        f"/api/workspaces/{workspace.id}/staff/{owner.id}", json={"role": "admin"}
    )

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["body", "role"], "last_owner")],
    )
    assert await role_of(session, workspace, owner) is WorkspaceRole.OWNER


async def test_an_owner_can_be_demoted_while_another_owner_remains(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    owner = await owner_of(client, workspace)
    await WorkspaceMembershipFactory.create_async(workspace=workspace, role=WorkspaceRole.OWNER)

    response = await client.patch(
        f"/api/workspaces/{workspace.id}/staff/{owner.id}", json={"role": "admin"}
    )

    assert response.status_code == 200
    assert await role_of(session, workspace, owner) is WorkspaceRole.ADMIN


async def test_the_last_owner_cant_be_removed(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    owner = await owner_of(client, workspace)

    response = await client.delete(f"/api/workspaces/{workspace.id}/staff/{owner.id}")

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["path", "user_id"], "last_owner")],
    )
    assert await role_of(session, workspace, owner) is WorkspaceRole.OWNER


@pytest.mark.parametrize("with_projects", [True, False])
async def test_removing_staff_removes_the_membership_and_records_it(
    client: AsyncClient, session: AsyncSession, workspace: Workspace, with_projects: bool
) -> None:
    owner = await owner_of(client, workspace)
    bob = await UserFactory.create_async()
    await WorkspaceMembershipFactory.create_async(workspace=workspace, user=bob)

    response = await client.delete(
        f"/api/workspaces/{workspace.id}/staff/{bob.id}",
        params={"with_projects": str(with_projects).lower()},
    )

    assert response.status_code == 204
    assert await role_of(session, workspace, bob) is None
    assert await events(session) == [
        (
            AuditAction.WORKSPACE_MEMBER_REMOVED,
            owner.id,
            workspace.id,
            bob.id,
            AuditEntityType.WORKSPACE,
            {"role": "member", "with_projects": with_projects},
        )
    ]


@pytest.fixture
def removals(monkeypatch: pytest.MonkeyPatch) -> list[MemberRemoval]:
    """What the `on_member_removed` handler receives: the project area registers the real one in
    S1-C12; this stands in for it."""
    calls: list[MemberRemoval] = []

    async def handler(_session: AsyncSession, removal: MemberRemoval) -> None:
        calls.append(removal)

    monkeypatch.setattr(workspace_service, "_ON_MEMBER_REMOVED", [handler])
    return calls


async def test_removing_with_projects_calls_the_handler(
    client: AsyncClient, workspace: Workspace, removals: list[MemberRemoval]
) -> None:
    owner = await owner_of(client, workspace)
    bob = await UserFactory.create_async()
    await WorkspaceMembershipFactory.create_async(workspace=workspace, user=bob)

    await client.delete(
        f"/api/workspaces/{workspace.id}/staff/{bob.id}", params={"with_projects": "true"}
    )

    assert removals == [MemberRemoval(bob.id, workspace.id, None, owner.id)]


async def test_removing_without_projects_leaves_them(
    client: AsyncClient, workspace: Workspace, removals: list[MemberRemoval]
) -> None:
    await owner_of(client, workspace)
    bob = await UserFactory.create_async()
    await WorkspaceMembershipFactory.create_async(workspace=workspace, user=bob)

    await client.delete(
        f"/api/workspaces/{workspace.id}/staff/{bob.id}", params={"with_projects": "false"}
    )

    assert removals == []


async def test_removing_with_projects_is_the_default(
    client: AsyncClient, workspace: Workspace, removals: list[MemberRemoval]
) -> None:
    await owner_of(client, workspace)
    bob = await UserFactory.create_async()
    await WorkspaceMembershipFactory.create_async(workspace=workspace, user=bob)

    await client.delete(f"/api/workspaces/{workspace.id}/staff/{bob.id}")

    assert [removal.user_id for removal in removals] == [bob.id]


# --- Orgs in the workspace ------------------------------------------------------------------


async def test_the_org_list_is_the_workspaces_orgs_by_name(
    client: AsyncClient, workspace: Workspace
) -> None:
    await owner_of(client, workspace)
    await OrganizationFactory.create_async(workspace=workspace, name="Cove")
    await OrganizationFactory.create_async(workspace=workspace, name="Bolt")
    await OrganizationFactory.create_async(name="Elsewhere")

    response = await client.get(f"/api/workspaces/{workspace.id}/orgs")

    assert [org["name"] for org in response.json()["items"]] == ["Bolt", "Cove"]


# --- Access ends on the next request (design-doc §4, "Sessions") ------------------------------


@pytest.fixture
async def bobs_client(
    settings: Settings, sessionmaker: SessionMaker, workspace: Workspace
) -> AsyncIterator[tuple[AsyncClient, User]]:
    """A second browser, signed in as Bob, a workspace admin."""
    bob = await UserFactory.create_async()
    await WorkspaceMembershipFactory.create_async(
        workspace=workspace, user=bob, role=WorkspaceRole.ADMIN
    )
    async with api_client(create_app(settings, sessionmaker=sessionmaker)) as bobs:
        await sign_in_as(bobs, bob)
        yield bobs, bob


async def sessions_of(session: AsyncSession, user: User) -> int:
    return (
        await session.execute(
            select(func.count()).select_from(UserSession).where(UserSession.user_id == user.id)
        )
    ).scalar_one()


@pytest.mark.security
async def test_a_demoted_admin_loses_access_on_the_next_request_keeping_the_session(
    client: AsyncClient,
    session: AsyncSession,
    workspace: Workspace,
    bobs_client: tuple[AsyncClient, User],
) -> None:
    """Every request reloads the memberships, so nothing waits for the session to end."""
    bobs, bob = bobs_client
    await owner_of(client, workspace)
    before = await bobs.get(f"/api/workspaces/{workspace.id}")

    await client.patch(f"/api/workspaces/{workspace.id}/staff/{bob.id}", json={"role": "member"})

    after = await bobs.get(f"/api/workspaces/{workspace.id}")
    assert (before.status_code, after.status_code) == (200, 404)
    assert await sessions_of(session, bob) == 1


@pytest.mark.security
async def test_a_removed_admin_loses_access_on_the_next_request_keeping_the_session(
    client: AsyncClient,
    session: AsyncSession,
    workspace: Workspace,
    bobs_client: tuple[AsyncClient, User],
) -> None:
    bobs, bob = bobs_client
    await owner_of(client, workspace)
    before = await bobs.get(f"/api/workspaces/{workspace.id}")

    await client.delete(f"/api/workspaces/{workspace.id}/staff/{bob.id}")

    after = await bobs.get(f"/api/workspaces/{workspace.id}")
    assert (before.status_code, after.status_code) == (200, 404)
    assert await sessions_of(session, bob) == 1


# --- Stepping down and the owner handover (DL-59, S1-C8a) ------------------------------------


async def admin_of(client: AsyncClient, workspace: Workspace) -> User:
    user = await UserFactory.create_async()
    await WorkspaceMembershipFactory.create_async(
        workspace=workspace, user=user, role=WorkspaceRole.ADMIN
    )
    await sign_in_as(client, user)
    return user


async def staff(workspace: Workspace, role: WorkspaceRole = WorkspaceRole.MEMBER) -> User:
    user = await UserFactory.create_async()
    await WorkspaceMembershipFactory.create_async(workspace=workspace, user=user, role=role)
    return user


@pytest.mark.security
async def test_an_admin_may_step_down_to_member(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    admin = await admin_of(client, workspace)

    response = await client.patch(
        f"/api/workspaces/{workspace.id}/staff/{admin.id}", json={"role": "member"}
    )

    assert response.status_code == 200
    assert await role_of(session, workspace, admin) is WorkspaceRole.MEMBER


@pytest.mark.security
async def test_an_admin_may_leave(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    admin = await admin_of(client, workspace)

    response = await client.delete(f"/api/workspaces/{workspace.id}/staff/{admin.id}")

    assert response.status_code == 204
    assert await role_of(session, workspace, admin) is None


async def test_an_admin_re_sending_their_own_role_changes_nothing(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    """The same no-op as on anyone else's row (a role picker may send the current role)."""
    admin = await admin_of(client, workspace)

    response = await client.patch(
        f"/api/workspaces/{workspace.id}/staff/{admin.id}", json={"role": "admin"}
    )

    assert (response.status_code, response.json()["role"]) == (200, "admin")
    assert await events(session) == []


@pytest.mark.security
async def test_an_admin_may_not_promote_themselves_to_owner(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    """Stepping down is the exception, not stepping up."""
    admin = await admin_of(client, workspace)

    response = await client.patch(
        f"/api/workspaces/{workspace.id}/staff/{admin.id}", json={"role": "owner"}
    )

    assert (response.status_code, response.json()["code"]) == (403, "forbidden")
    assert await role_of(session, workspace, admin) is WorkspaceRole.ADMIN


@pytest.mark.security
async def test_an_admin_may_still_not_demote_another_admin(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    await admin_of(client, workspace)
    other = await staff(workspace, WorkspaceRole.ADMIN)

    response = await client.patch(
        f"/api/workspaces/{workspace.id}/staff/{other.id}", json={"role": "member"}
    )

    assert response.status_code == 403
    assert await role_of(session, workspace, other) is WorkspaceRole.ADMIN


@pytest.mark.security
async def test_the_last_owner_steps_down_by_naming_a_replacement(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    owner = await owner_of(client, workspace)
    bob = await staff(workspace)

    response = await client.patch(
        f"/api/workspaces/{workspace.id}/staff/{owner.id}",
        json={"role": "admin", "new_owner_id": str(bob.id)},
    )

    assert response.status_code == 200
    assert (await role_of(session, workspace, owner), await role_of(session, workspace, bob)) == (
        WorkspaceRole.ADMIN,
        WorkspaceRole.OWNER,
    )
    assert [(target, details) for _, _, _, target, _, details in await events(session)] == [
        (bob.id, {"old_role": "member", "new_role": "owner"}),
        (owner.id, {"old_role": "owner", "new_role": "admin"}),
    ]


@pytest.mark.security
async def test_the_last_owner_leaves_by_naming_a_replacement(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    owner = await owner_of(client, workspace)
    bob = await staff(workspace)

    response = await client.delete(
        f"/api/workspaces/{workspace.id}/staff/{owner.id}", params={"new_owner_id": str(bob.id)}
    )

    assert response.status_code == 204
    assert (await role_of(session, workspace, owner), await role_of(session, workspace, bob)) == (
        None,
        WorkspaceRole.OWNER,
    )


@pytest.mark.security
async def test_a_system_admin_may_hand_over_for_the_last_owner(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    """Whoever may demote an owner may name the replacement (DL-59)."""
    owner = await staff(workspace, WorkspaceRole.OWNER)
    bob = await staff(workspace)
    await sign_in_as(client, await UserFactory.create_async(is_system_admin=True))

    response = await client.delete(
        f"/api/workspaces/{workspace.id}/staff/{owner.id}", params={"new_owner_id": str(bob.id)}
    )

    assert response.status_code == 204
    assert await role_of(session, workspace, bob) is WorkspaceRole.OWNER


@pytest.mark.security
@pytest.mark.parametrize(
    ("who", "type_"),
    [("outsider", "not_member"), ("gone", "account_inactive"), ("self", "same_user")],
)
async def test_a_replacement_that_cant_be_owner_is_a_422(
    client: AsyncClient, session: AsyncSession, workspace: Workspace, who: str, type_: str
) -> None:
    owner = await owner_of(client, workspace)
    gone = await UserFactory.create_async(is_active=False)
    await WorkspaceMembershipFactory.create_async(workspace=workspace, user=gone)
    candidates = {"outsider": await UserFactory.create_async(), "gone": gone, "self": owner}

    response = await client.patch(
        f"/api/workspaces/{workspace.id}/staff/{owner.id}",
        json={"role": "admin", "new_owner_id": str(candidates[who].id)},
    )

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["body", "new_owner_id"], type_)],
    )
    assert await role_of(session, workspace, owner) is WorkspaceRole.OWNER


@pytest.mark.security
async def test_naming_a_replacement_for_someone_not_an_owner_is_a_422(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    await owner_of(client, workspace)
    admin = await staff(workspace, WorkspaceRole.ADMIN)
    bob = await staff(workspace)

    response = await client.delete(
        f"/api/workspaces/{workspace.id}/staff/{admin.id}", params={"new_owner_id": str(bob.id)}
    )

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["query", "new_owner_id"], "not_owner")],
    )
    assert await role_of(session, workspace, bob) is WorkspaceRole.MEMBER


@pytest.mark.security
@pytest.mark.parametrize("successor", ["themselves", "a member"])
async def test_a_workspace_admin_cant_name_a_replacement_owner_by_role_change(
    client: AsyncClient, session: AsyncSession, workspace: Workspace, successor: str
) -> None:
    """Naming a replacement needs the right to act on an owner's row (DL-59): an admin can't
    use it to make themselves or a friend owner."""
    owner = await staff(workspace, WorkspaceRole.OWNER)
    admin = await admin_of(client, workspace)
    member = await staff(workspace)
    named = {"themselves": admin, "a member": member}[successor]

    response = await client.patch(
        f"/api/workspaces/{workspace.id}/staff/{owner.id}",
        json={"role": "admin", "new_owner_id": str(named.id)},
    )

    assert (response.status_code, response.json()["code"]) == (403, "forbidden")
    assert (await role_of(session, workspace, owner), await role_of(session, workspace, named)) == (
        WorkspaceRole.OWNER,
        {"themselves": WorkspaceRole.ADMIN, "a member": WorkspaceRole.MEMBER}[successor],
    )
    assert await events(session) == []


@pytest.mark.security
async def test_a_workspace_admin_cant_name_a_replacement_owner_by_removal(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    owner = await staff(workspace, WorkspaceRole.OWNER)
    admin = await admin_of(client, workspace)

    response = await client.delete(
        f"/api/workspaces/{workspace.id}/staff/{owner.id}", params={"new_owner_id": str(admin.id)}
    )

    assert (response.status_code, response.json()["code"]) == (403, "forbidden")
    assert await role_of(session, workspace, owner) is WorkspaceRole.OWNER
    assert await role_of(session, workspace, admin) is WorkspaceRole.ADMIN
    assert await events(session) == []


async def test_naming_someone_already_an_owner_is_accepted(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    """Nothing to promote: the step-down goes ahead and records only itself."""
    owner = await owner_of(client, workspace)
    other = await staff(workspace, WorkspaceRole.OWNER)

    response = await client.patch(
        f"/api/workspaces/{workspace.id}/staff/{owner.id}",
        json={"role": "admin", "new_owner_id": str(other.id)},
    )

    assert response.status_code == 200
    assert [target for _, _, _, target, *_ in await events(session)] == [owner.id]
