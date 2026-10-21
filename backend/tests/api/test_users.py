"""The account API's behavior beyond who may call it (build plan, "The account API", DL-72 to
DL-75): the users list, the account actions' effects and guards, profile edits, audit events and
their orgs, and the per-person access review. Who gets 2xx/403/404 is in
tests/api/authz/test_users.py (spec tests)."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.enums import AuditAction, OrgRole, ProjectRole, WorkspaceRole
from app.models.audit_event import AuditEvent
from app.models.auth import UserSession
from app.models.user import User
from tests.factories.auth import UserSessionFactory
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceMembershipFactory
from tests.support.authz import Tenancy, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

TEMPORARY = "a temporary passphrase"


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


async def staff(t: Tenancy, role: WorkspaceRole = WorkspaceRole.MEMBER, **user: object) -> User:
    person = await UserFactory.create_async(**user)
    await WorkspaceMembershipFactory.create_async(workspace=t.workspace, user=person, role=role)
    return person


async def org_member(t: Tenancy, role: OrgRole = OrgRole.MEMBER, **user: object) -> User:
    person = await UserFactory.create_async(**user)
    await MembershipFactory.create_async(organization=t.org, user=person, role=role)
    return person


async def signed_in(client: AsyncClient, user: User) -> User:
    await sign_in_as(client, user)
    return user


async def with_sessions(user: User, count: int = 2) -> User:
    for _ in range(count):
        await UserSessionFactory.create_async(user=user)
    return user


async def sessions_of(session: AsyncSession, user: User) -> int:
    count = select(func.count()).select_from(UserSession).where(UserSession.user_id == user.id)
    return (await session.execute(count)).scalar_one()


async def stored(session: AsyncSession, user: User) -> User:
    """The user's row as committed by the request, not the test's cached object."""
    statement = select(User).where(User.id == user.id).execution_options(populate_existing=True)
    return (await session.execute(statement)).scalar_one()


async def events(session: AsyncSession) -> list[tuple[object, ...]]:
    rows = await session.execute(
        select(
            AuditEvent.action,
            AuditEvent.actor_id,
            AuditEvent.workspace_id,
            AuditEvent.organization_id,
            AuditEvent.target_user_id,
            AuditEvent.details,
        ).order_by(AuditEvent.organization_id, AuditEvent.id)
    )
    return [tuple(row) for row in rows]


def fields(body: dict[str, object]) -> list[tuple[list[object], str]]:
    return [(e["loc"], e["type"]) for e in body["details"]["fields"]]  # pyright: ignore[reportIndexIssue, reportUnknownVariableType, reportArgumentType]


# --- The users list -----------------------------------------------------------------------------


async def test_the_users_list_holds_the_workspaces_people_and_accounts_with_no_memberships(
    client: AsyncClient, t: Tenancy
) -> None:
    await signed_in(client, await staff(t, WorkspaceRole.ADMIN, name="Ada Admin"))
    await org_member(t, name="Olga Member")
    project_only = await UserFactory.create_async(name="Pia Project")
    await ProjectMembershipFactory.create_async(project=t.project, user=project_only)
    await UserFactory.create_async(name="Nora Nobody")
    elsewhere = await OrganizationFactory.create_async(name="Far Away")  # another workspace
    await MembershipFactory.create_async(
        organization=elsewhere, user=await UserFactory.create_async(name="Fay Far")
    )

    response = await client.get(f"/api/workspaces/{t.workspace.id}/users")

    assert response.status_code == 200
    assert [row["name"] for row in response.json()["items"]] == [
        "Ada Admin",
        "Nora Nobody",
        "Olga Member",
        "Pia Project",
    ]


async def test_the_users_list_shows_who_holds_system_admin_and_filters_by_active(
    client: AsyncClient, t: Tenancy
) -> None:
    await signed_in(client, await staff(t, WorkspaceRole.OWNER, name="Ada Owner"))
    await staff(t, name="Sam System", is_system_admin=True)
    await staff(t, name="Dee Gone", is_active=False)

    everyone = await client.get(f"/api/workspaces/{t.workspace.id}/users")
    inactive = await client.get(
        f"/api/workspaces/{t.workspace.id}/users", params={"is_active": "false"}
    )

    assert [
        (r["name"], r["is_system_admin"], r["is_active"]) for r in everyone.json()["items"]
    ] == [
        ("Ada Owner", False, True),
        ("Dee Gone", False, False),
        ("Sam System", True, True),
    ]
    assert [r["name"] for r in inactive.json()["items"]] == ["Dee Gone"]


@pytest.mark.security
@pytest.mark.parametrize(
    ("make", "role"),
    [(staff, WorkspaceRole.MEMBER), (org_member, OrgRole.OWNER)],
    ids=["workspace_member", "org_owner"],
)
async def test_the_users_list_is_a_404_below_workspace_admin(
    client: AsyncClient, t: Tenancy, make: Callable[..., Awaitable[User]], role: object
) -> None:
    """Only workspace owners/admins and system admins see the workspace pages (design-doc §4)."""
    await signed_in(client, await make(t, role))
    await UserFactory.create_async(name="Nora Nobody")

    response = await client.get(f"/api/workspaces/{t.workspace.id}/users")

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert "Nora Nobody" not in response.text


# --- Deactivate and reactivate ------------------------------------------------------------------


@pytest.mark.security
async def test_deactivating_ends_the_users_sessions_and_records_it(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    admin = await signed_in(client, await staff(t, WorkspaceRole.ADMIN))
    bob = await with_sessions(await org_member(t))

    response = await client.post(f"/api/users/{bob.id}/deactivate")

    assert response.status_code == 204
    assert (await stored(session, bob)).is_active is False
    assert await sessions_of(session, bob) == 0
    assert await sessions_of(session, admin) == 1
    assert await events(session) == [
        (AuditAction.USER_DEACTIVATED, admin.id, t.workspace.id, None, bob.id, {})
    ]


async def test_deactivating_an_inactive_account_changes_and_records_nothing(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    await signed_in(client, await staff(t, WorkspaceRole.ADMIN))
    bob = await org_member(t, is_active=False)

    response = await client.post(f"/api/users/{bob.id}/deactivate")

    assert response.status_code == 204
    assert await events(session) == []


@pytest.mark.security
async def test_the_last_active_system_admin_cant_be_deactivated(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    sam = await signed_in(client, await staff(t, is_system_admin=True))
    await UserFactory.create_async(is_system_admin=True, is_active=False)  # doesn't count

    response = await client.post(f"/api/users/{sam.id}/deactivate")

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["path", "user_id"], "last_system_admin")],
    )
    assert (await stored(session, sam)).is_active is True


async def test_a_system_admin_can_be_deactivated_while_another_is_active(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    sam = await signed_in(client, await staff(t, is_system_admin=True))
    await UserFactory.create_async(is_system_admin=True)

    response = await client.post(f"/api/users/{sam.id}/deactivate")

    assert response.status_code == 204
    assert (await stored(session, sam)).is_active is False


@pytest.mark.security
@pytest.mark.parametrize("deactivated_owners", [0, 1])
async def test_the_last_active_owner_of_the_workspace_cant_be_deactivated(
    client: AsyncClient, session: AsyncSession, t: Tenancy, deactivated_owners: int
) -> None:
    """A deactivated owner doesn't count (DL-74)."""
    owner = await signed_in(client, await staff(t, WorkspaceRole.OWNER))
    await WorkspaceMembershipFactory.create_batch_async(
        deactivated_owners,
        workspace=t.workspace,
        user=await UserFactory.create_async(is_active=False),
        role=WorkspaceRole.OWNER,
    )

    response = await client.post(f"/api/users/{owner.id}/deactivate")

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["path", "user_id"], "last_owner")],
    )
    assert (await stored(session, owner)).is_active is True


async def test_an_owner_can_be_deactivated_while_another_owner_is_active(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    owner = await signed_in(client, await staff(t, WorkspaceRole.OWNER))
    await staff(t, WorkspaceRole.OWNER)

    response = await client.post(f"/api/users/{owner.id}/deactivate")

    assert response.status_code == 204
    assert (await stored(session, owner)).is_active is False


@pytest.mark.security
async def test_the_last_active_owner_of_an_org_cant_be_deactivated(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    await signed_in(client, await staff(t, WorkspaceRole.ADMIN))
    olive = await org_member(t, OrgRole.OWNER)
    # An owner of another org doesn't count.
    other = await OrganizationFactory.create_async(workspace=t.workspace)
    await MembershipFactory.create_async(
        organization=other, user=await UserFactory.create_async(), role=OrgRole.OWNER
    )

    response = await client.post(f"/api/users/{olive.id}/deactivate")

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["path", "user_id"], "last_owner")],
    )
    assert (await stored(session, olive)).is_active is True


async def test_reactivating_lets_the_account_back_and_records_it(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    admin = await signed_in(client, await staff(t, WorkspaceRole.ADMIN))
    bob = await org_member(t, is_active=False)

    response = await client.post(f"/api/users/{bob.id}/reactivate")
    again = await client.post(f"/api/users/{bob.id}/reactivate")

    assert (response.status_code, again.status_code) == (204, 204)
    assert (await stored(session, bob)).is_active is True
    assert await events(session) == [
        (AuditAction.USER_REACTIVATED, admin.id, t.workspace.id, None, bob.id, {})
    ]


# --- Reset password and sign out everywhere -----------------------------------------------------


@pytest.mark.security
async def test_a_password_reset_sets_a_temporary_password_and_ends_the_sessions(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    admin = await signed_in(client, await staff(t, WorkspaceRole.ADMIN))
    bob = await with_sessions(await org_member(t))

    response = await client.post(
        f"/api/users/{bob.id}/reset-password", json={"password": TEMPORARY}
    )

    assert response.status_code == 204
    row = await stored(session, bob)
    assert await verify_password(row.hashed_password, TEMPORARY)
    assert row.must_change_password is True
    assert await sessions_of(session, bob) == 0
    assert await events(session) == [
        (AuditAction.PASSWORD_RESET, admin.id, t.workspace.id, None, bob.id, {})
    ]


async def test_a_temporary_password_follows_the_policy(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    await signed_in(client, await staff(t, WorkspaceRole.ADMIN))
    bob = await org_member(t)
    before = (await stored(session, bob)).hashed_password

    response = await client.post(f"/api/users/{bob.id}/reset-password", json={"password": "short"})

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["body", "password"], "too_short")],
    )
    assert (await stored(session, bob)).hashed_password == before


@pytest.mark.security
async def test_an_admin_cant_reset_their_own_password(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """An admin reset asks for no current password, so someone holding the admin's session could
    take the account (design-doc §4; S1-C4 security review)."""
    admin = await signed_in(client, await staff(t, WorkspaceRole.ADMIN))
    before = (await stored(session, admin)).hashed_password

    response = await client.post(
        f"/api/users/{admin.id}/reset-password", json={"password": TEMPORARY}
    )

    assert (response.status_code, response.json()["code"]) == (403, "forbidden")
    assert (await stored(session, admin)).hashed_password == before
    assert await events(session) == []


@pytest.mark.security
async def test_signing_out_everywhere_ends_every_session_and_records_it(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    admin = await signed_in(client, await staff(t, WorkspaceRole.ADMIN))
    bob = await with_sessions(await org_member(t), 3)

    response = await client.post(f"/api/users/{bob.id}/sign-out-everywhere")

    assert response.status_code == 204
    assert await sessions_of(session, bob) == 0
    assert await sessions_of(session, admin) == 1
    assert await events(session) == [
        (AuditAction.SIGNED_OUT_EVERYWHERE, admin.id, t.workspace.id, None, bob.id, {})
    ]


# --- The orgs on account-action events (DL-75) --------------------------------------------------


async def test_an_org_admins_action_is_recorded_in_their_org(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    admin = await signed_in(client, await org_member(t, OrgRole.ADMIN))
    bob = await org_member(t)

    await client.post(f"/api/users/{bob.id}/sign-out-everywhere")

    assert await events(session) == [
        (AuditAction.SIGNED_OUT_EVERYWHERE, admin.id, t.workspace.id, t.org.id, bob.id, {})
    ]


async def test_an_action_through_two_orgs_roles_is_recorded_in_each(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    other = await OrganizationFactory.create_async(workspace=t.workspace)
    admin = await signed_in(client, await org_member(t, OrgRole.ADMIN))
    await MembershipFactory.create_async(organization=other, user=admin, role=OrgRole.ADMIN)
    bob = await org_member(t)
    await MembershipFactory.create_async(organization=other, user=bob)

    response = await client.patch(f"/api/users/{bob.id}", json={"name": "Robert"})

    assert response.status_code == 200
    expected = [
        (AuditAction.USER_UPDATED, admin.id, t.workspace.id, org_id, bob.id, details)
        for org_id in sorted([t.org.id, other.id])
        for details in [{"old": {"name": bob.name}, "new": {"name": "Robert"}}]
    ]
    assert await events(session) == expected


# --- Profile edits --------------------------------------------------------------------------------


@pytest.mark.security
async def test_an_email_change_is_lowercased_ends_the_sessions_and_records_old_and_new(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    admin = await signed_in(client, await staff(t, WorkspaceRole.ADMIN))
    bob = await with_sessions(await org_member(t, email="bob@acme.example"))

    response = await client.patch(f"/api/users/{bob.id}", json={"email": " Robert@Acme.example "})

    assert (response.status_code, response.json()["email"]) == (200, "robert@acme.example")
    assert (await stored(session, bob)).email == "robert@acme.example"
    assert await sessions_of(session, bob) == 0
    assert await sessions_of(session, admin) == 1
    assert await events(session) == [
        (
            AuditAction.USER_UPDATED,
            admin.id,
            t.workspace.id,
            None,
            bob.id,
            {"old": {"email": "bob@acme.example"}, "new": {"email": "robert@acme.example"}},
        )
    ]


async def test_a_name_or_username_change_keeps_the_sessions(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    await signed_in(client, await staff(t, WorkspaceRole.ADMIN))
    bob = await with_sessions(await org_member(t, name="Bob", username="bob"))

    response = await client.patch(
        f"/api/users/{bob.id}", json={"name": " Robert ", "username": "robert"}
    )

    assert (response.json()["name"], response.json()["username"]) == ("Robert", "robert")
    assert await sessions_of(session, bob) == 2
    [(_, _, _, _, _, details)] = await events(session)
    assert details == {
        "old": {"name": "Bob", "username": "bob"},
        "new": {"name": "Robert", "username": "robert"},
    }


async def test_an_edit_that_changes_nothing_records_nothing(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    await signed_in(client, await staff(t, WorkspaceRole.ADMIN))
    bob = await org_member(t, email="bob@acme.example", name="Bob")

    response = await client.patch(
        f"/api/users/{bob.id}", json={"email": "BOB@acme.example", "name": "Bob"}
    )

    assert response.status_code == 200
    assert await events(session) == []


async def test_a_taken_email_or_username_is_refused(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    await signed_in(client, await staff(t, WorkspaceRole.ADMIN))
    await UserFactory.create_async(email="ann@acme.example", username="ann")
    bob = await org_member(t, email="bob@acme.example")

    response = await client.patch(
        f"/api/users/{bob.id}", json={"email": "ANN@acme.example", "username": "ann"}
    )

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["body", "email"], "taken"), (["body", "username"], "taken")],
    )
    assert (await stored(session, bob)).email == "bob@acme.example"


async def test_a_bad_username_email_or_blank_name_is_refused(
    client: AsyncClient, t: Tenancy
) -> None:
    await signed_in(client, await staff(t, WorkspaceRole.ADMIN))
    bob = await org_member(t)

    response = await client.patch(
        f"/api/users/{bob.id}", json={"email": "not an email", "name": " ", "username": "2bob"}
    )

    assert (response.status_code, fields(response.json())) == (
        422,
        [
            (["body", "email"], "invalid_email"),
            (["body", "name"], "missing"),
            (["body", "username"], "must_start_with_letter"),
        ],
    )


@pytest.mark.security
async def test_an_admin_cant_change_their_own_email_but_can_their_name(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    admin = await signed_in(client, await staff(t, WorkspaceRole.ADMIN, email="ada@acme.example"))

    email = await client.patch(f"/api/users/{admin.id}", json={"email": "ada2@acme.example"})
    name = await client.patch(f"/api/users/{admin.id}", json={"name": "Ada L."})

    assert (email.status_code, fields(email.json())) == (422, [(["body", "email"], "own_email")])
    assert (name.status_code, name.json()["name"]) == (200, "Ada L.")
    assert (await stored(session, admin)).email == "ada@acme.example"


async def test_users_edit_their_own_name_and_username(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    pia = await signed_in(client, await org_member(t, name="Pia", username="pia"))

    response = await client.patch("/api/me", json={"name": "Pia P.", "username": "pia-p"})

    assert response.json() == {
        "id": str(pia.id),
        "email": pia.email,
        "username": "pia-p",
        "name": "Pia P.",
    }
    assert await events(session) == [
        (
            AuditAction.USER_UPDATED,
            pia.id,
            t.workspace.id,
            None,
            pia.id,
            {
                "old": {"name": "Pia", "username": "pia"},
                "new": {"name": "Pia P.", "username": "pia-p"},
            },
        )
    ]


async def test_an_own_username_already_taken_is_refused(client: AsyncClient, t: Tenancy) -> None:
    await UserFactory.create_async(username="ann")
    await signed_in(client, await org_member(t))

    response = await client.patch("/api/me", json={"username": "ann"})

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["body", "username"], "taken")],
    )


@pytest.mark.security
async def test_editing_ones_profile_needs_a_session(client: AsyncClient) -> None:
    response = await client.patch("/api/me", json={"name": "Anyone"})

    assert (response.status_code, response.json()["code"]) == (401, "not_authenticated")


# --- The per-person access review ---------------------------------------------------------------


async def test_the_access_review_lists_each_org_and_project_with_its_reasons(
    client: AsyncClient, t: Tenancy
) -> None:
    await signed_in(client, await staff(t, WorkspaceRole.ADMIN))
    other = await OrganizationFactory.create_async(workspace=t.workspace, name="Cove Retail")
    archived = await ProjectFactory.create_async(
        organization=other, key="ARC", name="Archive", archived_at=datetime.now(UTC)
    )
    await ProjectFactory.create_async(organization=other, key="NOP", name="Not Theirs")
    pia = await org_member(t, OrgRole.ADMIN)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=pia, role=ProjectRole.MEMBER
    )
    await ProjectMembershipFactory.create_async(project=archived, user=pia, role=ProjectRole.VIEWER)

    response = await client.get(f"/api/users/{pia.id}/access")

    body = response.json()
    assert body["user"]["workspace_role"] is None
    assert [(o["name"], o["reasons"]) for o in body["orgs"]] == [
        ("Bolt Foods", ["org_admin", "project_membership"]),
        ("Cove Retail", ["project_membership"]),
    ]
    assert [(p["key"], p["archived"], p["reasons"]) for p in body["projects"]] == [
        ("ARC", True, ["project_viewer"]),
        ("PMT", False, ["org_admin", "project_member"]),
    ]


async def test_a_workspace_admin_reaches_every_org_and_project(
    client: AsyncClient, t: Tenancy
) -> None:
    ada = await signed_in(client, await staff(t, WorkspaceRole.ADMIN, is_system_admin=True))

    response = await client.get(f"/api/users/{ada.id}/access")

    body = response.json()
    assert body["user"]["workspace_role"] == "admin"
    assert [(o["name"], o["reasons"]) for o in body["orgs"]] == [
        ("Bolt Foods", ["system_admin", "workspace_admin"])
    ]
    assert [(p["key"], p["reasons"]) for p in body["projects"]] == [
        ("PMT", ["system_admin", "workspace_admin"])
    ]


async def test_a_plain_member_reaches_only_their_org(client: AsyncClient, t: Tenancy) -> None:
    olga = await signed_in(client, await org_member(t))

    response = await client.get(f"/api/users/{olga.id}/access")

    assert [(o["name"], o["reasons"]) for o in response.json()["orgs"]] == [
        ("Bolt Foods", ["org_member"])
    ]
    assert response.json()["projects"] == []
