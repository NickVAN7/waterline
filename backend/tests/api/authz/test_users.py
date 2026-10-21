"""Authorization of the account API (build plan, "Users": "The account API", DL-72; "The account
actions", DL-73):

- deactivate, reactivate, reset password, sign out everywhere, and the admin profile edit need
  `user.manage`: the rank rule (design-doc §4, "Account management"); a user target the actor
  can't see is a 404 (the same as a user that doesn't exist, naming no one), one they see but may
  not act on a 403. The actor sees a user holding a membership in the actor's scope, themselves,
  and, as a workspace owner/admin or system admin, every user;
- the per-person access review needs `user.view_access` (workspace owners/admins, system admins,
  the user themselves, or the rank rule) and is a 404 on every denial (design-doc §5, "Access
  review"), so it never reveals who exists;
- the users list's rows carry the `user`-level actions; `PATCH /api/me` is for any signed-in
  user.

A denial changes nothing: the target stays active, keeps its name, password, and sessions, and
no audit event is recorded. Personas are tests/support/authz.py's, relative to org "Bolt Foods"
in workspace "Acme Consulting", with project "Payments" (PMT); "Tara Target" is the user acted on.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import OrgRole, ProjectRole, WorkspaceRole
from app.models.audit_event import AuditEvent
from app.models.auth import UserSession
from app.models.org import Organization
from app.models.user import User
from tests.factories.auth import UserSessionFactory
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.user import FACTORY_PASSWORD_HASH, UserFactory
from tests.factories.workspace import WorkspaceMembershipFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

TARGET_EMAIL = "tara@target.example"
TARGET_USERNAME = "tara-target"
TARGET_NAME = "Tara Target"
NEW_NAME = "Renamed Target"
TEMPORARY_PASSWORD = "Temporary-pass-42"


async def elm_supply(t: Tenancy) -> Organization:
    """Another client org in the same workspace."""
    return await OrganizationFactory.create_async(
        workspace=t.workspace, name="Elm Supply", slug="elm-supply"
    )


WORKSPACE_ROLES = {
    "workspace_owner": WorkspaceRole.OWNER,
    "workspace_admin": WorkspaceRole.ADMIN,
    "staff": WorkspaceRole.MEMBER,
}
ORG_ROLES = {
    "org_owner": OrgRole.OWNER,
    "org_admin": OrgRole.ADMIN,
    "org_member": OrgRole.MEMBER,
    "system_admin_in_org": OrgRole.MEMBER,
}


async def make_target(t: Tenancy, kind: str, *, is_active: bool = True) -> User:
    """Tara, holding what `kind` names, with one live session."""
    tara = await UserFactory.create_async(
        email=TARGET_EMAIL,
        username=TARGET_USERNAME,
        name=TARGET_NAME,
        is_active=is_active,
        is_system_admin=kind in ("system_admin", "system_admin_in_org"),
        must_change_password=False,
        hashed_password=FACTORY_PASSWORD_HASH,
    )
    match kind:
        case "workspace_owner" | "workspace_admin" | "staff":
            await WorkspaceMembershipFactory.create_async(
                workspace=t.workspace, user=tara, role=WORKSPACE_ROLES[kind]
            )
        case "org_owner" | "org_admin" | "org_member" | "system_admin_in_org":
            await MembershipFactory.create_async(
                organization=t.org, user=tara, role=ORG_ROLES[kind]
            )
        case "project_only":
            await ProjectMembershipFactory.create_async(
                project=t.project, user=tara, role=ProjectRole.MEMBER
            )
        case "other_org_member":
            await MembershipFactory.create_async(
                organization=await elm_supply(t), user=tara, role=OrgRole.MEMBER
            )
        case "member_of_two_orgs":
            await MembershipFactory.create_async(organization=t.org, user=tara, role=OrgRole.MEMBER)
            await MembershipFactory.create_async(
                organization=await elm_supply(t), user=tara, role=OrgRole.MEMBER
            )
        case "org_member_on_other_org_project":
            await MembershipFactory.create_async(organization=t.org, user=tara, role=OrgRole.MEMBER)
            elm_project = await ProjectFactory.create_async(
                organization=await elm_supply(t), key="ELM", name="Elm Ledger"
            )
            await ProjectMembershipFactory.create_async(
                project=elm_project, user=tara, role=ProjectRole.MEMBER
            )
        case "staff_and_org_member":
            await WorkspaceMembershipFactory.create_async(
                workspace=t.workspace, user=tara, role=WorkspaceRole.MEMBER
            )
            await MembershipFactory.create_async(organization=t.org, user=tara, role=OrgRole.MEMBER)
        case _:  # "system_admin", "no_memberships"
            pass
    await UserSessionFactory.create_async(user=tara)
    return tara


async def signed_in(client: AsyncClient, who: str) -> tuple[Tenancy, User]:
    t = await tenancy()
    actor = await persona_user(t, who)
    await sign_in_as(client, actor)
    return t, actor


@dataclass(frozen=True)
class Call:
    """One `user.manage` endpoint: how to call it, the state its target starts in, and the
    change it makes when allowed."""

    method: str
    suffix: str
    body: dict[str, Any] | None
    status: int
    starts_active: bool = True

    def path(self, user_id: uuid.UUID) -> str:
        return f"/api/users/{user_id}{self.suffix}"

    async def send(self, client: AsyncClient, user_id: uuid.UUID) -> Response:
        return await client.request(self.method, self.path(user_id), json=self.body)


DEACTIVATE = Call("POST", "/deactivate", None, 204)
REACTIVATE = Call("POST", "/reactivate", None, 204, starts_active=False)
RESET_PASSWORD = Call("POST", "/reset-password", {"password": TEMPORARY_PASSWORD}, 204)
SIGN_OUT_EVERYWHERE = Call("POST", "/sign-out-everywhere", None, 204)
UPDATE = Call("PATCH", "", {"name": NEW_NAME}, 200)
CALLS = {
    "deactivate": DEACTIVATE,
    "reactivate": REACTIVATE,
    "reset_password": RESET_PASSWORD,
    "sign_out_everywhere": SIGN_OUT_EVERYWHERE,
    "update": UPDATE,
}


@dataclass(frozen=True)
class Stored:
    is_active: bool
    name: str
    hashed_password: str
    must_change_password: bool
    sessions: int


async def stored(session: AsyncSession, user_id: uuid.UUID) -> Stored:
    """Tara as the database holds her now (a fresh query, not the loaded object)."""
    session.expunge_all()
    row = await session.get_one(User, user_id)
    sessions = await session.scalar(
        select(func.count()).select_from(UserSession).where(UserSession.user_id == user_id)
    )
    return Stored(
        row.is_active, row.name, row.hashed_password, row.must_change_password, sessions or 0
    )


async def audit_events(session: AsyncSession) -> int | None:
    return await session.scalar(select(func.count()).select_from(AuditEvent))


def untouched(is_active: bool) -> Stored:
    return Stored(is_active, TARGET_NAME, FACTORY_PASSWORD_HASH, False, 1)


# What each endpoint changed, read back from the database (build plan, "The account API").
EFFECTS: dict[str, Callable[[Stored], object]] = {
    "deactivate": lambda s: s.is_active,
    "reactivate": lambda s: s.is_active,
    "reset_password": lambda s: s.must_change_password,
    "sign_out_everywhere": lambda s: s.sessions,
    "update": lambda s: s.name,
}
CHANGED_TO: dict[str, object] = {
    "deactivate": False,
    "reactivate": True,
    "reset_password": True,
    "sign_out_everywhere": 0,
    "update": NEW_NAME,
}


def assert_names_no_one(response: Response) -> None:
    for leaked in (TARGET_EMAIL, TARGET_USERNAME, TARGET_NAME, "Bolt Foods", "bolt-foods"):
        assert leaked not in response.text


def assert_hidden(response: Response, missing: Response) -> None:
    """404 `not_found`, the same body as for a user that doesn't exist, naming no one."""
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    assert_names_no_one(response)


def assert_forbidden(response: Response) -> None:
    assert (response.status_code, response.json()["code"]) == (403, "forbidden")
    assert_names_no_one(response)


ENDPOINTS = list(CALLS)

# --- user.manage: allowed ----------------------------------------------------------------------

MANAGED = [
    ("org_admin", "org_member"),
    ("org_admin", "project_only"),  # a project-only user on the org's project
    ("org_owner", "org_admin"),
    ("workspace_admin", "org_member"),
    ("workspace_admin", "staff"),
    ("workspace_admin", "no_memberships"),
    ("workspace_owner", "workspace_admin"),
    ("system_admin", "workspace_admin"),
]


@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize(("who", "kind"), MANAGED)
async def test_an_account_action_is_allowed_under_the_rank_rule(
    client: AsyncClient, session: AsyncSession, who: str, kind: str, endpoint: str
) -> None:
    call = CALLS[endpoint]
    t, _ = await signed_in(client, who)
    tara = await make_target(t, kind, is_active=call.starts_active)

    response = await call.send(client, tara.id)

    assert response.status_code == call.status, response.text
    assert EFFECTS[endpoint](await stored(session, tara.id)) == CHANGED_TO[endpoint]


@pytest.mark.parametrize("who", ["org_admin", "workspace_admin"])
async def test_the_edited_row_carries_the_user_level_actions(client: AsyncClient, who: str) -> None:
    """`PATCH /api/users/{user_id}` returns a users-list row, with its `allowed_actions`."""
    t, _ = await signed_in(client, who)
    tara = await make_target(t, "org_member")

    response = await UPDATE.send(client, tara.id)

    assert response.status_code == 200, response.text
    assert response.json()["allowed_actions"] == ["user.manage", "user.view_access"]


@pytest.mark.parametrize("endpoint", ["deactivate", "sign_out_everywhere", "update"])
async def test_an_admin_may_act_on_their_own_account_through_the_admin_path(
    client: AsyncClient, session: AsyncSession, endpoint: str
) -> None:
    """design-doc §4: under the same rule (an org admin covers their own role); the own-email
    and own-password-reset exceptions are the services' (DL-73)."""
    _, me = await signed_in(client, "org_admin")

    response = await CALLS[endpoint].send(client, me.id)

    assert response.status_code == CALLS[endpoint].status, response.text
    assert EFFECTS[endpoint](await stored(session, me.id)) == CHANGED_TO[endpoint]


# --- user.manage: denied -------------------------------------------------------------------------

# Seen (a membership in the actor's scope, or the workspace admins' every user), not covered.
SEEN_NOT_MANAGED = [
    ("org_admin", "org_owner"),
    ("org_admin", "member_of_two_orgs"),
    ("org_admin", "org_member_on_other_org_project"),
    ("org_admin", "staff_and_org_member"),
    ("org_admin", "system_admin_in_org"),
    ("workspace_admin", "workspace_owner"),
    ("workspace_admin", "system_admin"),
]
# Outside the actor's scope.
UNSEEN = [
    ("org_admin", "other_org_member"),
    ("org_admin", "staff"),
    ("org_admin", "no_memberships"),
    ("org_admin", "system_admin"),
    ("org_owner", "workspace_admin"),
    ("other_org_owner", "org_member"),
    ("nobody", "org_member"),
]


@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize(("who", "kind"), SEEN_NOT_MANAGED)
async def test_an_account_action_is_403_on_a_user_seen_but_outranked(
    client: AsyncClient, session: AsyncSession, who: str, kind: str, endpoint: str
) -> None:
    call = CALLS[endpoint]
    t, _ = await signed_in(client, who)
    tara = await make_target(t, kind, is_active=call.starts_active)

    response = await call.send(client, tara.id)

    assert_forbidden(response)
    assert await stored(session, tara.id) == untouched(call.starts_active)
    assert await audit_events(session) == 0


@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize(("who", "kind"), UNSEEN)
async def test_an_account_action_is_404_on_a_user_outside_the_actors_scope(
    client: AsyncClient, session: AsyncSession, who: str, kind: str, endpoint: str
) -> None:
    call = CALLS[endpoint]
    t, _ = await signed_in(client, who)
    tara = await make_target(t, kind, is_active=call.starts_active)

    response = await call.send(client, tara.id)

    assert_hidden(response, await call.send(client, uuid.uuid4()))
    assert await stored(session, tara.id) == untouched(call.starts_active)
    assert await audit_events(session) == 0


@pytest.mark.parametrize("endpoint", ["deactivate", "reset_password", "sign_out_everywhere"])
@pytest.mark.parametrize("who", ["org_member", "project_viewer", "workspace_member", "nobody"])
async def test_an_account_action_on_ones_own_account_is_403_without_the_rank(
    client: AsyncClient, session: AsyncSession, who: str, endpoint: str
) -> None:
    """They see themselves (a 403, not a 404), but a member or project-only user has no account
    actions."""
    _, me = await signed_in(client, who)
    before = await stored(session, me.id)

    response = await CALLS[endpoint].send(client, me.id)

    assert (response.status_code, response.json()["code"]) == (403, "forbidden")
    assert await stored(session, me.id) == before
    assert await audit_events(session) == 0


@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize(
    ("who", "kind"),
    [
        ("org_member", "org_member"),
        ("project_admin", "project_only"),
        ("workspace_member", "org_member"),
    ],
)
async def test_members_and_project_admins_have_no_account_actions_on_others(
    client: AsyncClient, session: AsyncSession, who: str, kind: str, endpoint: str
) -> None:
    """Denied; whether they see the target (403) or not (404) is left open (a member role's
    "scope" is undecided), so only the denial is asserted."""
    call = CALLS[endpoint]
    t, _ = await signed_in(client, who)
    tara = await make_target(t, kind, is_active=call.starts_active)

    response = await call.send(client, tara.id)

    assert response.status_code in (403, 404)
    assert_names_no_one(response)
    assert await stored(session, tara.id) == untouched(call.starts_active)
    assert await audit_events(session) == 0


# --- The per-person access review (user.view_access; 404 on every denial) -----------------------

REVIEWERS = [
    ("workspace_admin", "workspace_owner"),  # by role, where user.manage is a 403
    ("workspace_admin", "system_admin"),
    ("workspace_admin", "no_memberships"),
    ("workspace_owner", "org_member"),
    ("system_admin", "workspace_owner"),
    ("org_admin", "org_member"),
    ("org_admin", "project_only"),
    ("org_owner", "org_admin"),
]


@pytest.mark.parametrize(("who", "kind"), REVIEWERS)
async def test_the_access_review_is_open_to_workspace_admins_and_those_with_the_rank(
    client: AsyncClient, who: str, kind: str
) -> None:
    t, _ = await signed_in(client, who)
    tara = await make_target(t, kind)

    response = await client.get(f"/api/users/{tara.id}/access")

    assert response.status_code == 200, response.text
    assert (response.json()["user"]["id"], response.json()["user"]["email"]) == (
        str(tara.id),
        TARGET_EMAIL,
    )


@pytest.mark.parametrize(
    "who", ["org_member", "project_viewer", "workspace_member", "other_project_admin", "nobody"]
)
async def test_everyone_may_open_their_own_access_review(client: AsyncClient, who: str) -> None:
    _, me = await signed_in(client, who)

    response = await client.get(f"/api/users/{me.id}/access")

    assert response.status_code == 200, response.text
    assert (response.json()["user"]["id"], response.json()["user"]["email"]) == (
        str(me.id),
        me.email,
    )


@pytest.mark.parametrize(
    ("who", "kind"),
    [
        # Seen, but not every membership is covered: still a 404 (the full rank rule, §5).
        ("org_admin", "org_owner"),
        ("org_admin", "member_of_two_orgs"),
        ("org_admin", "org_member_on_other_org_project"),
        ("org_admin", "system_admin_in_org"),
        # Not seen.
        ("org_admin", "other_org_member"),
        ("org_admin", "staff"),
        ("org_admin", "no_memberships"),
        ("other_org_owner", "org_member"),
        ("nobody", "org_member"),
        # No role that opens it.
        ("org_member", "org_member"),
        ("project_admin", "project_only"),
        ("workspace_member", "org_member"),
    ],
)
async def test_the_access_review_is_404_on_every_denial(
    client: AsyncClient, who: str, kind: str
) -> None:
    t, _ = await signed_in(client, who)
    tara = await make_target(t, kind)

    response = await client.get(f"/api/users/{tara.id}/access")

    assert_hidden(response, await client.get(f"/api/users/{uuid.uuid4()}/access"))


# --- The users list: each row's user-level actions ----------------------------------------------


async def list_actions(client: AsyncClient, t: Tenancy) -> dict[str, list[str]]:
    response = await client.get(f"/api/workspaces/{t.workspace.id}/users")
    assert response.status_code == 200, response.text
    return {row["email"]: row["allowed_actions"] for row in response.json()["items"]}


async def add_owner(t: Tenancy) -> None:
    olive = await UserFactory.create_async(email="olive@acme.example", is_system_admin=False)
    await WorkspaceMembershipFactory.create_async(
        workspace=t.workspace, user=olive, role=WorkspaceRole.OWNER
    )


async def test_a_workspace_admins_rows_offer_what_the_rank_rule_allows(
    client: AsyncClient,
) -> None:
    """The owner's row offers only the access review; an org member's and their own, both."""
    t, me = await signed_in(client, "workspace_admin")
    await add_owner(t)
    await make_target(t, "org_member")

    actions = await list_actions(client, t)

    assert actions["olive@acme.example"] == ["user.view_access"]
    assert actions[TARGET_EMAIL] == ["user.manage", "user.view_access"]
    assert actions[me.email] == ["user.manage", "user.view_access"]


async def test_a_system_admins_rows_offer_both_actions_on_everyone(client: AsyncClient) -> None:
    t, _ = await signed_in(client, "system_admin")
    await add_owner(t)
    await make_target(t, "system_admin")

    actions = await list_actions(client, t)

    assert actions["olive@acme.example"] == ["user.manage", "user.view_access"]
    assert actions[TARGET_EMAIL] == ["user.manage", "user.view_access"]


# --- PATCH /api/me: any signed-in user ----------------------------------------------------------


@pytest.mark.parametrize("who", ["nobody", "project_viewer", "org_member"])
async def test_any_signed_in_user_may_edit_their_own_profile(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    _, me = await signed_in(client, who)

    response = await client.patch("/api/me", json={"name": NEW_NAME})

    assert response.status_code == 200, response.text
    assert response.json()["name"] == NEW_NAME
    assert (await stored(session, me.id)).name == NEW_NAME
