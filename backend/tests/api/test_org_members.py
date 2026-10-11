"""An org's members (build plan, "The org members API", DL-67): the stored effects, audit events,
and 422s. Who may do what is in tests/api/authz/test_org_members.py (spec tests)."""

from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionMaker
from app.core.security import verify_password
from app.core.settings import Settings
from app.enums import AuditAction, AuditEntityType, OrgRole
from app.main import create_app
from app.models.audit_event import AuditEvent
from app.models.auth import UserSession
from app.models.org import Membership, Organization
from app.models.user import User
from app.services.roster import MemberRemoval
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.user import UserFactory
from tests.support.api import api_client
from tests.support.authz import sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]


@pytest.fixture
async def org() -> Organization:
    return await OrganizationFactory.create_async(name="Bolt Foods", slug="bolt")


async def member(org: Organization, role: OrgRole = OrgRole.MEMBER, **user: object) -> User:
    person = await UserFactory.create_async(**user)
    await MembershipFactory.create_async(organization=org, user=person, role=role)
    return person


async def signed_in(client: AsyncClient, org: Organization, role: OrgRole = OrgRole.OWNER) -> User:
    """Sign `client` in as a new member of `org` with `role`."""
    person = await member(org, role)
    await sign_in_as(client, person)
    return person


async def events(session: AsyncSession) -> list[tuple[object, ...]]:
    rows = await session.execute(
        select(
            AuditEvent.action,
            AuditEvent.actor_id,
            AuditEvent.workspace_id,
            AuditEvent.organization_id,
            AuditEvent.target_user_id,
            AuditEvent.entity_type,
            AuditEvent.entity_id,
            AuditEvent.details,
        ).order_by(AuditEvent.id)
    )
    return [tuple(row) for row in rows]


async def role_of(session: AsyncSession, org: Organization, user: User) -> OrgRole | None:
    return await session.scalar(
        select(Membership.role).where(
            Membership.organization_id == org.id, Membership.user_id == user.id
        )
    )


def fields(body: dict[str, object]) -> list[tuple[list[object], str]]:
    details = body["details"]
    assert isinstance(details, dict)
    return [(f["loc"], f["type"]) for f in details["fields"]]  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]


def event(
    action: AuditAction, actor: User, org: Organization, target: User, details: object
) -> tuple[object, ...]:
    """An org member event as `events` reads it: in the org's workspace and the org itself."""
    return (
        action,
        actor.id,
        org.workspace_id,
        org.id,
        target.id,
        AuditEntityType.ORGANIZATION,
        org.id,
        details,
    )


# --- The list -----------------------------------------------------------------------------------


async def test_the_member_list_is_sorted_by_name_and_filters_by_role(
    client: AsyncClient, org: Organization
) -> None:
    await signed_in(client, org)  # an owner: the role filter leaves them out
    await member(org, name="Cleo")
    await member(org, name="Abe")
    await member(await OrganizationFactory.create_async(), name="Elsewhere")

    response = await client.get(
        f"/api/orgs/{org.id}/members", params={"role": "member", "sort": "name"}
    )

    body = response.json()
    assert ([row["name"] for row in body["items"]], body["total"]) == (["Abe", "Cleo"], 2)


async def test_an_unknown_list_parameter_is_a_422(client: AsyncClient, org: Organization) -> None:
    await signed_in(client, org)

    response = await client.get(f"/api/orgs/{org.id}/members", params={"team": "x"})

    assert response.status_code == 422


# --- Adding and creating -----------------------------------------------------------------------


async def test_adding_a_member_by_email_adds_the_account_and_records_it(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    owner = await signed_in(client, org)
    ann = await UserFactory.create_async(email="ann@bolt.example", name="Ann Lee")

    response = await client.post(
        f"/api/orgs/{org.id}/members", json={"email": "Ann@Bolt.example", "role": "member"}
    )

    assert response.status_code == 201
    assert (response.json()["user_id"], response.json()["role"]) == (str(ann.id), "member")
    assert await role_of(session, org, ann) is OrgRole.MEMBER
    assert await events(session) == [
        event(AuditAction.ORG_MEMBER_ADDED, owner, org, ann, {"role": "member"})
    ]


async def test_someone_from_another_org_can_be_added(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    """Design-doc §4: org admins add existing users, whoever else they belong to."""
    await signed_in(client, org)
    other = await member(await OrganizationFactory.create_async(), email="cy@cove.example")

    response = await client.post(
        f"/api/orgs/{org.id}/members", json={"email": "cy@cove.example", "role": "member"}
    )

    assert response.status_code == 201
    assert await role_of(session, org, other) is OrgRole.MEMBER


@pytest.mark.parametrize(
    ("email", "type_"),
    [
        ("nobody@bolt.example", "no_account"),
        ("gone@bolt.example", "account_inactive"),
        ("member@bolt.example", "already_member"),
    ],
)
async def test_the_email_first_add_explains_why_it_cant_add(
    client: AsyncClient, session: AsyncSession, org: Organization, email: str, type_: str
) -> None:
    await signed_in(client, org)
    await UserFactory.create_async(email="gone@bolt.example", is_active=False)
    await member(org, email="member@bolt.example")

    response = await client.post(
        f"/api/orgs/{org.id}/members", json={"email": email, "role": "member"}
    )

    assert (response.status_code, fields(response.json())) == (422, [(["body", "email"], type_)])
    assert await events(session) == []


async def test_creating_a_member_makes_the_account_and_the_membership(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    owner = await signed_in(client, org)

    response = await client.post(
        f"/api/orgs/{org.id}/members/new",
        json={
            "email": "New@Bolt.example",
            "username": "new-hire",
            "name": "New Hire",
            "password": "a temporary passphrase",
            "role": "admin",
        },
    )

    assert response.status_code == 201
    user = (await session.execute(select(User).where(User.username == "new-hire"))).scalar_one()
    assert (user.email, user.must_change_password) == ("new@bolt.example", True)
    assert await verify_password(user.hashed_password, "a temporary passphrase") is True
    assert await role_of(session, org, user) is OrgRole.ADMIN
    # Made as the org's owner, so `user_created` is the org's too (design-doc §10.1, "Scope").
    assert await events(session) == [
        (
            AuditAction.USER_CREATED,
            owner.id,
            org.workspace_id,
            org.id,
            user.id,
            None,
            None,
            {},
        ),
        event(AuditAction.ORG_MEMBER_ADDED, owner, org, user, {"role": "admin"}),
    ]


async def test_creating_a_member_with_invalid_or_taken_values_creates_nothing(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    await signed_in(client, org)
    await UserFactory.create_async(email="taken@bolt.example", username="taken-name")
    users_before = (await session.execute(select(func.count()).select_from(User))).scalar_one()

    response = await client.post(
        f"/api/orgs/{org.id}/members/new",
        json={
            "email": "Taken@Bolt.example",
            "username": "taken-name",
            "name": "",
            "password": "short",
            "role": "member",
        },
    )

    assert response.status_code == 422
    assert fields(response.json()) == [
        (["body", "name"], "missing"),
        (["body", "password"], "too_short"),
        (["body", "email"], "taken"),
        (["body", "username"], "taken"),
    ]
    users_after = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    assert users_after == users_before
    assert await events(session) == []


# --- Role changes -------------------------------------------------------------------------------


async def test_changing_a_role_records_old_and_new(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    owner = await signed_in(client, org)
    bob = await member(org)

    response = await client.patch(f"/api/orgs/{org.id}/members/{bob.id}", json={"role": "admin"})

    assert (response.status_code, response.json()["role"]) == (200, "admin")
    assert await role_of(session, org, bob) is OrgRole.ADMIN
    assert await events(session) == [
        event(
            AuditAction.ORG_MEMBER_ROLE_CHANGED,
            owner,
            org,
            bob,
            {"old_role": "member", "new_role": "admin"},
        )
    ]


async def test_a_role_change_to_the_same_role_changes_and_records_nothing(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    """Not a demotion, so the last owner may "change" to owner (no `last_owner`)."""
    owner = await signed_in(client, org)

    response = await client.patch(f"/api/orgs/{org.id}/members/{owner.id}", json={"role": "owner"})

    assert (response.status_code, response.json()["role"]) == (200, "owner")
    assert await events(session) == []


@pytest.mark.security
async def test_a_role_change_for_someone_not_a_member_is_a_404(
    client: AsyncClient, org: Organization
) -> None:
    await signed_in(client, org)
    outsider = await member(await OrganizationFactory.create_async())

    response = await client.patch(
        f"/api/orgs/{org.id}/members/{outsider.id}", json={"role": "admin"}
    )

    assert (response.status_code, response.json()["code"]) == (404, "not_found")


@pytest.mark.security
async def test_removing_a_member_of_another_org_is_a_404_and_leaves_them(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    await signed_in(client, org)
    other_org = await OrganizationFactory.create_async()
    outsider = await member(other_org)

    response = await client.delete(f"/api/orgs/{org.id}/members/{outsider.id}")

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert await role_of(session, other_org, outsider) == OrgRole.MEMBER
    assert await events(session) == []


async def test_the_last_owner_cant_be_demoted(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    owner = await signed_in(client, org)
    # An owner of another org doesn't count.
    await member(await OrganizationFactory.create_async(), OrgRole.OWNER)

    response = await client.patch(f"/api/orgs/{org.id}/members/{owner.id}", json={"role": "admin"})

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["body", "role"], "last_owner")],
    )
    assert await role_of(session, org, owner) is OrgRole.OWNER


async def test_an_owner_can_be_demoted_while_another_owner_remains(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    owner = await signed_in(client, org)
    await member(org, OrgRole.OWNER)

    response = await client.patch(f"/api/orgs/{org.id}/members/{owner.id}", json={"role": "admin"})

    assert response.status_code == 200
    assert await role_of(session, org, owner) is OrgRole.ADMIN


# --- Removal ------------------------------------------------------------------------------------


async def test_the_last_owner_cant_be_removed(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    owner = await signed_in(client, org)

    response = await client.delete(f"/api/orgs/{org.id}/members/{owner.id}")

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["path", "user_id"], "last_owner")],
    )
    assert await role_of(session, org, owner) is OrgRole.OWNER


@pytest.mark.parametrize("with_projects", [True, False])
async def test_removing_a_member_removes_the_membership_and_records_it(
    client: AsyncClient, session: AsyncSession, org: Organization, with_projects: bool
) -> None:
    owner = await signed_in(client, org)
    bob = await member(org)

    response = await client.delete(
        f"/api/orgs/{org.id}/members/{bob.id}",
        params={"with_projects": str(with_projects).lower()},
    )

    assert response.status_code == 204
    assert await role_of(session, org, bob) is None
    assert await events(session) == [
        event(
            AuditAction.ORG_MEMBER_REMOVED,
            owner,
            org,
            bob,
            {"role": "member", "with_projects": with_projects},
        )
    ]


async def test_removing_with_projects_calls_the_handler_with_the_org(
    client: AsyncClient, org: Organization, removals: list[MemberRemoval]
) -> None:
    owner = await signed_in(client, org)
    bob = await member(org)

    await client.delete(f"/api/orgs/{org.id}/members/{bob.id}")  # with projects by default

    assert removals == [MemberRemoval(bob.id, org.workspace_id, org.id, owner.id)]


async def test_removing_without_projects_leaves_them(
    client: AsyncClient, org: Organization, removals: list[MemberRemoval]
) -> None:
    await signed_in(client, org)
    bob = await member(org)

    await client.delete(f"/api/orgs/{org.id}/members/{bob.id}", params={"with_projects": "false"})

    assert removals == []


@pytest.fixture
async def bobs_client(
    settings: Settings, sessionmaker: SessionMaker, org: Organization
) -> AsyncIterator[tuple[AsyncClient, User]]:
    """A second browser, signed in as Bob, an admin of `org`."""
    bob = await member(org, OrgRole.ADMIN)
    async with api_client(create_app(settings, sessionmaker=sessionmaker)) as bobs:
        await sign_in_as(bobs, bob)
        yield bobs, bob


@pytest.mark.security
async def test_a_removed_admin_loses_access_on_the_next_request_keeping_the_session(
    client: AsyncClient,
    session: AsyncSession,
    org: Organization,
    bobs_client: tuple[AsyncClient, User],
) -> None:
    """Every request reloads the memberships, so nothing waits for the session to end."""
    bobs, bob = bobs_client
    await signed_in(client, org)
    before = await bobs.get(f"/api/orgs/{org.id}/members")

    await client.delete(f"/api/orgs/{org.id}/members/{bob.id}")

    after = await bobs.get(f"/api/orgs/{org.id}/members")
    sessions = (
        await session.execute(
            select(func.count()).select_from(UserSession).where(UserSession.user_id == bob.id)
        )
    ).scalar_one()
    assert (before.status_code, after.status_code, sessions) == (200, 404, 1)


# --- The owner handover (DL-59) -----------------------------------------------------------------


@pytest.mark.security
async def test_the_last_owner_steps_down_by_naming_a_replacement(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    owner = await signed_in(client, org)
    bob = await member(org)

    response = await client.patch(
        f"/api/orgs/{org.id}/members/{owner.id}",
        json={"role": "admin", "new_owner_id": str(bob.id)},
    )

    assert response.status_code == 200
    assert (await role_of(session, org, owner), await role_of(session, org, bob)) == (
        OrgRole.ADMIN,
        OrgRole.OWNER,
    )
    assert [(e[4], e[7]) for e in await events(session)] == [
        (bob.id, {"old_role": "member", "new_role": "owner"}),
        (owner.id, {"old_role": "owner", "new_role": "admin"}),
    ]


@pytest.mark.security
async def test_the_last_owner_leaves_by_naming_a_replacement(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    owner = await signed_in(client, org)
    bob = await member(org)

    response = await client.delete(
        f"/api/orgs/{org.id}/members/{owner.id}", params={"new_owner_id": str(bob.id)}
    )

    assert response.status_code == 204
    assert (await role_of(session, org, owner), await role_of(session, org, bob)) == (
        None,
        OrgRole.OWNER,
    )


@pytest.mark.security
@pytest.mark.parametrize(
    ("who", "type_"),
    [("outsider", "not_member"), ("gone", "account_inactive"), ("self", "same_user")],
)
async def test_a_replacement_that_cant_be_owner_is_a_422(
    client: AsyncClient, session: AsyncSession, org: Organization, who: str, type_: str
) -> None:
    owner = await signed_in(client, org)
    gone = await member(org, is_active=False)
    # A member of another org isn't a member here.
    outsider = await member(await OrganizationFactory.create_async())
    candidates = {"outsider": outsider, "gone": gone, "self": owner}

    response = await client.patch(
        f"/api/orgs/{org.id}/members/{owner.id}",
        json={"role": "admin", "new_owner_id": str(candidates[who].id)},
    )

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["body", "new_owner_id"], type_)],
    )
    assert await role_of(session, org, owner) is OrgRole.OWNER


@pytest.mark.security
async def test_naming_a_replacement_for_someone_not_an_owner_is_a_422(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    await signed_in(client, org)
    admin = await member(org, OrgRole.ADMIN)
    bob = await member(org)

    response = await client.delete(
        f"/api/orgs/{org.id}/members/{admin.id}", params={"new_owner_id": str(bob.id)}
    )

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["query", "new_owner_id"], "not_owner")],
    )
    assert await role_of(session, org, bob) is OrgRole.MEMBER


async def test_naming_someone_already_an_owner_is_accepted(
    client: AsyncClient, session: AsyncSession, org: Organization
) -> None:
    """Nothing to promote: the step-down goes ahead and records only itself."""
    owner = await signed_in(client, org)
    other = await member(org, OrgRole.OWNER)

    response = await client.patch(
        f"/api/orgs/{org.id}/members/{owner.id}",
        json={"role": "admin", "new_owner_id": str(other.id)},
    )

    assert response.status_code == 200
    assert [e[4] for e in await events(session)] == [owner.id]
