"""Authorization of the org members endpoints (build plan, "The org members API", DL-67; the
actions, DL-68): `org_member.manage` for org owners/admins, workspace owners/admins, and system
admins (403 for anyone else who sees the org; 404, the same as a missing org and naming nothing,
for whoever can't see it); granting, changing, or removing an owner or admin role also needs
`org_member.manage_admins` (org owners, workspace owners/admins, system admins), except an admin
demoting or removing themselves (DL-59); each member row's `allowed_actions` follow the same rule.
A denial stores nothing.

Personas are relative to org "Bolt Foods" (bolt-foods) in workspace "Acme Consulting", with
project "Payments" (tests/support/authz.py, `tenancy`). Each test adds "keeper", a second owner,
so the last-owner guard (DL-59) never decides the outcome.
"""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import OrgRole
from app.models.audit_event import AuditEvent
from app.models.org import Membership
from app.models.user import User
from tests.factories.org import MembershipFactory
from tests.factories.user import UserFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

MANAGERS = ["system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"]
# See the org but may not manage its members.
SEE_ONLY = [
    "org_member",
    "project_admin",
    "project_member",
    "project_viewer",
    "other_project_admin",
]
UNSEEN = ["workspace_member", "other_org_owner", "other_workspace_owner", "nobody"]
BOTH = ["org_member.manage", "org_member.manage_admins"]


async def signed_in(client: AsyncClient, who: str) -> tuple[Tenancy, User]:
    t = await tenancy()
    user = await persona_user(t, who)
    await sign_in_as(client, user)
    return t, user


async def member(t: Tenancy, role: OrgRole, email: str) -> User:
    user = await UserFactory.create_async(email=email, is_system_admin=False)
    await MembershipFactory.create_async(organization=t.org, user=user, role=role)
    return user


async def keeper(t: Tenancy) -> User:
    return await member(t, OrgRole.OWNER, "keeper@bolt.example")


async def stored_role(session: AsyncSession, t: Tenancy, user_id: uuid.UUID) -> str | None:
    return await session.scalar(
        select(Membership.role).where(
            Membership.organization_id == t.org.id, Membership.user_id == user_id
        )
    )


async def audit_events(session: AsyncSession) -> int | None:
    return await session.scalar(select(func.count()).select_from(AuditEvent))


def assert_hidden(response: Response, missing: Response) -> None:
    """404 `not_found`, the same body as for an org that doesn't exist, naming nothing."""
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    assert "Bolt Foods" not in response.text
    assert "bolt-foods" not in response.text


def assert_forbidden(response: Response) -> None:
    assert (response.status_code, response.json()["code"]) == (403, "forbidden")


# --- GET members (org_member.manage) ------------------------------------------------------------


@pytest.mark.parametrize("who", MANAGERS)
async def test_the_member_list_is_for_member_managers(client: AsyncClient, who: str) -> None:
    t, _ = await signed_in(client, who)
    await keeper(t)

    response = await client.get(f"/api/orgs/{t.org.id}/members")

    assert response.status_code == 200
    roles = {row["email"]: row["role"] for row in response.json()["items"]}
    assert roles["keeper@bolt.example"] == "owner"


@pytest.mark.parametrize("who", SEE_ONLY)
async def test_the_member_list_is_403_to_others_who_see_the_org(
    client: AsyncClient, who: str
) -> None:
    t, _ = await signed_in(client, who)
    await keeper(t)

    response = await client.get(f"/api/orgs/{t.org.id}/members")

    assert_forbidden(response)
    assert "keeper@bolt.example" not in response.text


@pytest.mark.parametrize("who", UNSEEN)
async def test_the_member_list_is_404_to_whoever_cannot_see_the_org(
    client: AsyncClient, who: str
) -> None:
    t, _ = await signed_in(client, who)
    await keeper(t)

    response = await client.get(f"/api/orgs/{t.org.id}/members")

    assert_hidden(response, await client.get(f"/api/orgs/{uuid.uuid4()}/members"))
    assert "keeper@bolt.example" not in response.text


# --- Each row's allowed_actions (DL-67: the staff rows' rule) -----------------------------------


async def row_actions(client: AsyncClient, t: Tenancy) -> dict[str, list[str]]:
    response = await client.get(f"/api/orgs/{t.org.id}/members")
    assert response.status_code == 200, response.text
    return {row["email"]: row["allowed_actions"] for row in response.json()["items"]}


async def test_an_org_admin_is_offered_actions_only_on_rows_they_may_change(
    client: AsyncClient,
) -> None:
    """None on an owner's or another admin's row; their own row carries `org_member.manage`, for
    stepping down (DL-59)."""
    t, me = await signed_in(client, "org_admin")
    await keeper(t)
    await member(t, OrgRole.ADMIN, "gina@bolt.example")
    await member(t, OrgRole.MEMBER, "frank@bolt.example")

    assert await row_actions(client, t) == {
        "keeper@bolt.example": [],
        "gina@bolt.example": [],
        "frank@bolt.example": ["org_member.manage"],
        me.email: ["org_member.manage"],
    }


@pytest.mark.parametrize("who", ["org_owner", "workspace_admin", "system_admin"])
async def test_a_holder_of_manage_admins_is_offered_both_actions_on_every_row(
    client: AsyncClient, who: str
) -> None:
    t, _ = await signed_in(client, who)
    await keeper(t)
    await member(t, OrgRole.ADMIN, "gina@bolt.example")
    await member(t, OrgRole.MEMBER, "frank@bolt.example")

    actions = await row_actions(client, t)

    assert actions["keeper@bolt.example"] == BOTH
    assert actions["gina@bolt.example"] == BOTH
    assert actions["frank@bolt.example"] == BOTH


# --- POST members: add an existing account by email ---------------------------------------------


async def newcomer() -> User:
    return await UserFactory.create_async(email="dana@cove.example", is_system_admin=False)


@pytest.mark.parametrize(
    ("who", "role"),
    [
        ("org_admin", OrgRole.MEMBER),
        ("org_owner", OrgRole.MEMBER),
        ("org_owner", OrgRole.ADMIN),
        ("org_owner", OrgRole.OWNER),
        ("workspace_admin", OrgRole.ADMIN),
        ("workspace_admin", OrgRole.OWNER),
        ("workspace_owner", OrgRole.OWNER),
        ("system_admin", OrgRole.ADMIN),
    ],
)
async def test_adding_a_member_with_a_role_the_caller_may_grant(
    client: AsyncClient, session: AsyncSession, who: str, role: OrgRole
) -> None:
    t, _ = await signed_in(client, who)
    dana = await newcomer()

    response = await client.post(
        f"/api/orgs/{t.org.id}/members", json={"email": "dana@cove.example", "role": role.value}
    )

    assert response.status_code == 201
    assert (response.json()["user_id"], response.json()["role"]) == (str(dana.id), role.value)
    assert await stored_role(session, t, dana.id) == role.value


@pytest.mark.parametrize("role", [OrgRole.ADMIN, OrgRole.OWNER])
async def test_an_org_admin_may_not_add_an_owner_or_admin(
    client: AsyncClient, session: AsyncSession, role: OrgRole
) -> None:
    t, _ = await signed_in(client, "org_admin")
    dana = await newcomer()

    response = await client.post(
        f"/api/orgs/{t.org.id}/members", json={"email": "dana@cove.example", "role": role.value}
    )

    assert_forbidden(response)
    assert await stored_role(session, t, dana.id) is None
    assert await audit_events(session) == 0


async def test_the_role_is_checked_before_the_email_on_an_add(client: AsyncClient) -> None:
    """An email with no account would be a 422 `no_account`; the role's 403 comes first."""
    t, _ = await signed_in(client, "org_admin")

    response = await client.post(
        f"/api/orgs/{t.org.id}/members", json={"email": "nobody@cove.example", "role": "admin"}
    )

    assert_forbidden(response)


@pytest.mark.parametrize("who", SEE_ONLY)
async def test_adding_a_member_is_403_to_others_who_see_the_org(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    dana = await newcomer()

    response = await client.post(
        f"/api/orgs/{t.org.id}/members", json={"email": "dana@cove.example", "role": "member"}
    )

    assert_forbidden(response)
    assert await stored_role(session, t, dana.id) is None
    assert await audit_events(session) == 0


@pytest.mark.parametrize("who", UNSEEN)
async def test_adding_a_member_is_404_to_whoever_cannot_see_the_org(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    dana = await newcomer()
    body = {"email": "dana@cove.example", "role": "member"}

    response = await client.post(f"/api/orgs/{t.org.id}/members", json=body)

    assert_hidden(response, await client.post(f"/api/orgs/{uuid.uuid4()}/members", json=body))
    assert await stored_role(session, t, dana.id) is None
    assert await audit_events(session) == 0


# --- POST members/new: create the account and the membership ------------------------------------


def new_account(role: OrgRole) -> dict[str, Any]:
    return {
        "email": "erin@bolt.example",
        "username": "erin-new",
        "name": "Erin New",
        "password": "plum-harbor-lantern-quietly",
        "role": role.value,
    }


async def stored_user_id(session: AsyncSession) -> uuid.UUID | None:
    return await session.scalar(select(User.id).where(User.email == "erin@bolt.example"))


@pytest.mark.parametrize(
    ("who", "role"),
    [
        ("org_admin", OrgRole.MEMBER),
        ("org_owner", OrgRole.ADMIN),
        ("org_owner", OrgRole.OWNER),
        ("workspace_admin", OrgRole.OWNER),
        ("workspace_owner", OrgRole.ADMIN),
        ("system_admin", OrgRole.OWNER),
    ],
)
async def test_creating_a_member_with_a_role_the_caller_may_grant(
    client: AsyncClient, session: AsyncSession, who: str, role: OrgRole
) -> None:
    t, _ = await signed_in(client, who)

    response = await client.post(f"/api/orgs/{t.org.id}/members/new", json=new_account(role))

    assert response.status_code == 201
    erin = await stored_user_id(session)
    assert erin is not None
    assert (response.json()["user_id"], response.json()["role"]) == (str(erin), role.value)
    assert await stored_role(session, t, erin) == role.value


@pytest.mark.parametrize("role", [OrgRole.ADMIN, OrgRole.OWNER])
async def test_an_org_admin_may_not_create_an_owner_or_admin(
    client: AsyncClient, session: AsyncSession, role: OrgRole
) -> None:
    """Nothing is created: no account, no membership, no event."""
    t, _ = await signed_in(client, "org_admin")

    response = await client.post(f"/api/orgs/{t.org.id}/members/new", json=new_account(role))

    assert_forbidden(response)
    assert await stored_user_id(session) is None
    assert await audit_events(session) == 0


@pytest.mark.parametrize("who", SEE_ONLY)
async def test_creating_a_member_is_403_to_others_who_see_the_org(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)

    response = await client.post(
        f"/api/orgs/{t.org.id}/members/new", json=new_account(OrgRole.MEMBER)
    )

    assert_forbidden(response)
    assert await stored_user_id(session) is None
    assert await audit_events(session) == 0


@pytest.mark.parametrize("who", UNSEEN)
async def test_creating_a_member_is_404_to_whoever_cannot_see_the_org(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    body = new_account(OrgRole.MEMBER)

    response = await client.post(f"/api/orgs/{t.org.id}/members/new", json=body)

    missing = await client.post(f"/api/orgs/{uuid.uuid4()}/members/new", json=body)
    assert_hidden(response, missing)
    assert await stored_user_id(session) is None
    assert await audit_events(session) == 0


# --- PATCH members/{user_id}: change a role -----------------------------------------------------
# Every change but member to member touches an owner or admin role, so an org admin changes no
# one else's role.


@pytest.mark.parametrize(
    ("who", "old", "new"),
    [
        ("org_owner", OrgRole.MEMBER, OrgRole.ADMIN),
        ("org_owner", OrgRole.ADMIN, OrgRole.MEMBER),
        ("org_owner", OrgRole.OWNER, OrgRole.ADMIN),
        ("workspace_admin", OrgRole.MEMBER, OrgRole.OWNER),
        ("workspace_admin", OrgRole.OWNER, OrgRole.MEMBER),
        ("workspace_owner", OrgRole.ADMIN, OrgRole.OWNER),
        ("system_admin", OrgRole.OWNER, OrgRole.MEMBER),
    ],
)
async def test_holders_of_manage_admins_change_owner_and_admin_roles(
    client: AsyncClient, session: AsyncSession, who: str, old: OrgRole, new: OrgRole
) -> None:
    t, _ = await signed_in(client, who)
    await keeper(t)
    target = await member(t, old, "frank@bolt.example")

    response = await client.patch(
        f"/api/orgs/{t.org.id}/members/{target.id}", json={"role": new.value}
    )

    assert (response.status_code, response.json()["role"]) == (200, new.value)
    assert await stored_role(session, t, target.id) == new.value


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (OrgRole.MEMBER, OrgRole.ADMIN),
        (OrgRole.MEMBER, OrgRole.OWNER),
        (OrgRole.ADMIN, OrgRole.MEMBER),
        (OrgRole.ADMIN, OrgRole.OWNER),
        (OrgRole.OWNER, OrgRole.ADMIN),
        (OrgRole.OWNER, OrgRole.MEMBER),
    ],
)
async def test_an_org_admin_may_not_grant_change_or_remove_another_owner_or_admin_role(
    client: AsyncClient, session: AsyncSession, old: OrgRole, new: OrgRole
) -> None:
    t, _ = await signed_in(client, "org_admin")
    await keeper(t)
    target = await member(t, old, "frank@bolt.example")

    response = await client.patch(
        f"/api/orgs/{t.org.id}/members/{target.id}", json={"role": new.value}
    )

    assert_forbidden(response)
    assert await stored_role(session, t, target.id) == old.value
    assert await audit_events(session) == 0


async def test_an_org_admin_may_step_down_to_member(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-59: without `org_member.manage_admins`."""
    t, me = await signed_in(client, "org_admin")
    await keeper(t)

    response = await client.patch(f"/api/orgs/{t.org.id}/members/{me.id}", json={"role": "member"})

    assert (response.status_code, response.json()["role"]) == (200, "member")
    assert await stored_role(session, t, me.id) == "member"


async def test_an_org_admin_may_not_promote_themselves_to_owner(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Stepping down is the exception, not stepping up."""
    t, me = await signed_in(client, "org_admin")
    await keeper(t)

    response = await client.patch(f"/api/orgs/{t.org.id}/members/{me.id}", json={"role": "owner"})

    assert_forbidden(response)
    assert await stored_role(session, t, me.id) == "admin"
    assert await audit_events(session) == 0


@pytest.mark.parametrize("successor", ["themselves", "a member"])
async def test_an_org_admin_may_not_name_a_replacement_owner(
    client: AsyncClient, session: AsyncSession, successor: str
) -> None:
    """Naming a replacement needs the right to act on the owner's row (DL-59)."""
    t, me = await signed_in(client, "org_admin")
    owner = await keeper(t)
    frank = await member(t, OrgRole.MEMBER, "frank@bolt.example")
    named = {"themselves": me, "a member": frank}[successor]

    response = await client.patch(
        f"/api/orgs/{t.org.id}/members/{owner.id}",
        json={"role": "admin", "new_owner_id": str(named.id)},
    )

    assert_forbidden(response)
    assert await stored_role(session, t, owner.id) == "owner"
    assert (
        await stored_role(session, t, named.id)
        == {"themselves": "admin", "a member": "member"}[successor]
    )
    assert await audit_events(session) == 0


@pytest.mark.parametrize("who", SEE_ONLY)
async def test_changing_a_role_is_403_to_others_who_see_the_org(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """Even a change to the role already held (no owner or admin role involved)."""
    t, _ = await signed_in(client, who)
    target = await member(t, OrgRole.MEMBER, "frank@bolt.example")

    response = await client.patch(
        f"/api/orgs/{t.org.id}/members/{target.id}", json={"role": "member"}
    )

    assert_forbidden(response)
    assert await stored_role(session, t, target.id) == "member"


@pytest.mark.parametrize("who", UNSEEN)
async def test_changing_a_role_is_404_to_whoever_cannot_see_the_org(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    target = await member(t, OrgRole.MEMBER, "frank@bolt.example")

    response = await client.patch(
        f"/api/orgs/{t.org.id}/members/{target.id}", json={"role": "admin"}
    )

    missing = await client.patch(
        f"/api/orgs/{uuid.uuid4()}/members/{target.id}", json={"role": "admin"}
    )
    assert_hidden(response, missing)
    assert "frank@bolt.example" not in response.text
    assert await stored_role(session, t, target.id) == "member"
    assert await audit_events(session) == 0


# --- DELETE members/{user_id}: remove -----------------------------------------------------------


@pytest.mark.parametrize(
    ("who", "role"),
    [
        ("org_admin", OrgRole.MEMBER),
        ("org_owner", OrgRole.MEMBER),
        ("org_owner", OrgRole.ADMIN),
        ("org_owner", OrgRole.OWNER),
        ("workspace_admin", OrgRole.OWNER),
        ("workspace_owner", OrgRole.ADMIN),
        ("system_admin", OrgRole.ADMIN),
    ],
)
async def test_removing_a_member_whose_role_the_caller_may_remove(
    client: AsyncClient, session: AsyncSession, who: str, role: OrgRole
) -> None:
    t, _ = await signed_in(client, who)
    await keeper(t)
    target = await member(t, role, "frank@bolt.example")

    response = await client.delete(f"/api/orgs/{t.org.id}/members/{target.id}")

    assert response.status_code == 204
    assert await stored_role(session, t, target.id) is None


@pytest.mark.parametrize("role", [OrgRole.ADMIN, OrgRole.OWNER])
async def test_an_org_admin_may_not_remove_another_owner_or_admin(
    client: AsyncClient, session: AsyncSession, role: OrgRole
) -> None:
    t, _ = await signed_in(client, "org_admin")
    await keeper(t)
    target = await member(t, role, "frank@bolt.example")

    response = await client.delete(f"/api/orgs/{t.org.id}/members/{target.id}")

    assert_forbidden(response)
    assert await stored_role(session, t, target.id) == role.value
    assert await audit_events(session) == 0


async def test_an_org_admin_may_leave(client: AsyncClient, session: AsyncSession) -> None:
    """DL-59: without `org_member.manage_admins`."""
    t, me = await signed_in(client, "org_admin")
    await keeper(t)

    response = await client.delete(f"/api/orgs/{t.org.id}/members/{me.id}")

    assert response.status_code == 204
    assert await stored_role(session, t, me.id) is None


async def test_an_org_admin_may_not_name_a_replacement_owner_by_removal(
    client: AsyncClient, session: AsyncSession
) -> None:
    t, me = await signed_in(client, "org_admin")
    owner = await keeper(t)

    response = await client.delete(
        f"/api/orgs/{t.org.id}/members/{owner.id}", params={"new_owner_id": str(me.id)}
    )

    assert_forbidden(response)
    assert await stored_role(session, t, owner.id) == "owner"
    assert await stored_role(session, t, me.id) == "admin"
    assert await audit_events(session) == 0


async def test_a_workspace_admin_may_hand_over_for_the_orgs_last_owner(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Whoever may remove an owner may name the replacement (DL-59); at the org level that
    includes workspace admins (DL-68)."""
    t, _ = await signed_in(client, "workspace_admin")
    owner = await keeper(t)
    frank = await member(t, OrgRole.MEMBER, "frank@bolt.example")

    response = await client.delete(
        f"/api/orgs/{t.org.id}/members/{owner.id}", params={"new_owner_id": str(frank.id)}
    )

    assert response.status_code == 204
    assert await stored_role(session, t, owner.id) is None
    assert await stored_role(session, t, frank.id) == "owner"


@pytest.mark.parametrize("who", SEE_ONLY)
async def test_removing_a_member_is_403_to_others_who_see_the_org(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    target = await member(t, OrgRole.MEMBER, "frank@bolt.example")

    response = await client.delete(f"/api/orgs/{t.org.id}/members/{target.id}")

    assert_forbidden(response)
    assert await stored_role(session, t, target.id) == "member"
    assert await audit_events(session) == 0


@pytest.mark.parametrize("who", UNSEEN)
async def test_removing_a_member_is_404_to_whoever_cannot_see_the_org(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    target = await member(t, OrgRole.MEMBER, "frank@bolt.example")

    response = await client.delete(f"/api/orgs/{t.org.id}/members/{target.id}")

    missing = await client.delete(f"/api/orgs/{uuid.uuid4()}/members/{target.id}")
    assert_hidden(response, missing)
    assert await stored_role(session, t, target.id) == "member"
    assert await audit_events(session) == 0
