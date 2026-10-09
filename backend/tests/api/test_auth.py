"""Sign-in, sessions, sign-out, and `/me` (design-doc §4, "Sign-in" and "Sessions"; build plan,
"Authentication")."""

import hashlib
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from argon2 import PasswordHasher
from httpx import AsyncClient, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionMaker
from app.core.security import generate_token, hash_token, password_needs_rehash, verify_password
from app.core.settings import Settings
from app.enums import AuditAction, OrgRole, WorkspaceRole
from app.main import create_app
from app.models.audit_event import AuditEvent
from app.models.auth import UserSession
from app.models.user import User
from app.models.workspace import Workspace
from app.routers.deps import SignedInUserDep
from app.services import auth as auth_service
from tests.factories.auth import UserSessionFactory
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.user import FACTORY_PASSWORD, UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory
from tests.support.api import api_client

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

COOKIE = "__Host-session"


async def sign_in(client: AsyncClient, email: str, password: str = FACTORY_PASSWORD) -> Response:
    return await client.post("/api/auth/sign-in", json={"email": email, "password": password})


def set_cookie(response: Response) -> tuple[str, dict[str, str]]:
    """The one Set-Cookie header's value and its attributes (names lowercased)."""
    [header] = response.headers.get_list("set-cookie")
    pair, *attributes = header.split("; ")
    name, _, value = pair.partition("=")
    assert name == COOKIE
    pairs = [attribute.partition("=") for attribute in attributes]
    return value, {key.lower(): attribute_value for key, _, attribute_value in pairs}


async def session_rows(session: AsyncSession, user: User) -> list[UserSession]:
    return list(
        await session.scalars(
            select(UserSession)
            .where(UserSession.user_id == user.id)
            .execution_options(populate_existing=True)
        )
    )


async def session_for(user: User, session: AsyncSession, **times: object) -> str:
    """A session for `user`, its times set relative to the database clock; returns its token."""
    token = generate_token()
    row = await UserSessionFactory.create_async(user=user, token_hash=hash_token(token))
    if times:
        await session.execute(update(UserSession).where(UserSession.id == row.id).values(times))
    return token


def ago(**delta: float) -> object:
    return func.now() - timedelta(**delta)


# --- Sign-in ------------------------------------------------------------------------------------


async def test_sign_in_returns_the_me_body_and_stores_only_the_tokens_hash(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await UserFactory.create_async(
        email="ann@example.com", username="ann", name="Ann Lee", must_change_password=True
    )

    response = await sign_in(client, "ann@example.com")

    assert response.status_code == 200
    assert response.json() == {
        "user": {
            "id": str(user.id),
            "email": "ann@example.com",
            "username": "ann",
            "name": "Ann Lee",
        },
        "is_system_admin": False,
        "must_change_password": True,
        "workspaces": [],
        "orgs": [],
    }
    token, _ = set_cookie(response)
    [row] = await session_rows(session, user)
    assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in row.token_hash


@pytest.mark.parametrize(
    ("attribute", "value"),
    [("httponly", ""), ("secure", ""), ("samesite", "lax"), ("path", "/")],
)
async def test_the_session_cookie_has_each_required_attribute(
    client: AsyncClient, attribute: str, value: str
) -> None:
    await UserFactory.create_async(email="ann@example.com")

    _, attributes = set_cookie(await sign_in(client, "ann@example.com"))

    assert attributes[attribute].lower() == value


async def test_the_session_cookie_has_no_domain_and_lasts_the_session_lifetime(
    client: AsyncClient,
) -> None:
    await UserFactory.create_async(email="ann@example.com")

    _, attributes = set_cookie(await sign_in(client, "ann@example.com"))

    assert "domain" not in attributes
    assert attributes["max-age"] == str(30 * 24 * 60 * 60)


async def test_every_sign_in_starts_a_new_session_with_a_new_token(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await UserFactory.create_async(email="ann@example.com")

    first, _ = set_cookie(await sign_in(client, "ann@example.com"))
    # The client now sends the first session's cookie; it isn't reused.
    second, _ = set_cookie(await sign_in(client, "ann@example.com"))

    assert first != second
    assert {row.token_hash for row in await session_rows(session, user)} == {
        hash_token(first),
        hash_token(second),
    }


async def test_the_email_is_lowercased_before_lookup(client: AsyncClient) -> None:
    await UserFactory.create_async(email="ann@example.com")

    response = await sign_in(client, "Ann@Example.COM")

    assert response.status_code == 200


async def test_a_wrong_password_is_invalid_credentials_with_no_session(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await UserFactory.create_async(email="ann@example.com")

    response = await sign_in(client, "ann@example.com", "not the password")

    assert response.status_code == 401
    assert response.json() == {
        "code": "invalid_credentials",
        "message": "The email or password is incorrect.",
        "details": {},
    }
    assert "set-cookie" not in response.headers
    assert await session_rows(session, user) == []


async def test_an_unknown_email_is_the_same_error_and_still_verifies_a_password(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    real = auth_service.verify_password_for_unknown_user

    async def spy(password: str) -> bool:
        calls.append(password)
        return await real(password)

    monkeypatch.setattr(auth_service, "verify_password_for_unknown_user", spy)

    response = await sign_in(client, "nobody@example.com", "a guess")

    assert response.status_code == 401
    assert response.json() == {
        "code": "invalid_credentials",
        "message": "The email or password is incorrect.",
        "details": {},
    }
    assert calls == ["a guess"]


async def test_a_deactivated_account_with_its_password_is_account_inactive(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await UserFactory.create_async(email="ann@example.com", is_active=False)

    response = await sign_in(client, "ann@example.com")

    assert response.status_code == 403
    assert response.json()["code"] == "account_inactive"
    assert await session_rows(session, user) == []


async def test_a_deactivated_account_with_a_wrong_password_reveals_nothing(
    client: AsyncClient,
) -> None:
    await UserFactory.create_async(email="ann@example.com", is_active=False)

    response = await sign_in(client, "ann@example.com", "not the password")

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


async def test_a_hash_with_older_parameters_is_upgraded_on_sign_in(
    client: AsyncClient, session: AsyncSession
) -> None:
    old_hash = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash(FACTORY_PASSWORD)
    user = await UserFactory.create_async(email="ann@example.com", hashed_password=old_hash)

    response = await sign_in(client, "ann@example.com")

    stored = await session.scalar(select(User.hashed_password).where(User.id == user.id))
    assert response.status_code == 200
    assert stored is not None
    assert stored != old_hash
    assert "$m=65536,t=3,p=4$" in stored  # argon2-cffi's current defaults (RFC 9106 low-memory)
    assert await verify_password(stored, FACTORY_PASSWORD) is True


async def test_a_current_hash_is_left_alone_on_sign_in(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await UserFactory.create_async(email="ann@example.com")
    before = user.hashed_password
    assert password_needs_rehash(before) is False

    await sign_in(client, "ann@example.com")

    assert await session.scalar(select(User.hashed_password).where(User.id == user.id)) == before


# --- /me and the session --------------------------------------------------------------------------


async def test_me_after_sign_in_uses_the_cookie(client: AsyncClient) -> None:
    """The client sends the Secure cookie only over https (the shared client's base URL)."""
    await UserFactory.create_async(email="ann@example.com")
    signed_in = await sign_in(client, "ann@example.com")

    response = await client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json() == signed_in.json()


async def test_me_lists_workspaces_and_orgs_with_roles(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await UserFactory.create_async(is_system_admin=False)
    workspace = await WorkspaceFactory.create_async(name="Acme Consulting", slug="acme")
    await WorkspaceMembershipFactory.create_async(
        workspace=workspace, user=user, role=WorkspaceRole.MEMBER
    )
    org = await OrganizationFactory.create_async(
        workspace=workspace, name="Bolt Foods", slug="bolt"
    )
    await MembershipFactory.create_async(organization=org, user=user, role=OrgRole.ADMIN)
    client.cookies.set(COOKIE, await session_for(user, session))

    response = await client.get("/api/auth/me")

    body = response.json()
    assert body["workspaces"] == [
        {"id": str(workspace.id), "name": "Acme Consulting", "slug": "acme", "role": "member"}
    ]
    assert body["orgs"] == [
        {"id": str(org.id), "name": "Bolt Foods", "slug": "bolt", "role": "admin"}
    ]


async def test_me_without_a_session_is_401(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == {
        "code": "not_authenticated",
        "message": "Sign in to continue.",
        "details": {},
    }


async def test_me_with_an_unknown_token_is_401(client: AsyncClient) -> None:
    await UserSessionFactory.create_async()
    client.cookies.set(COOKIE, generate_token())

    response = await client.get("/api/auth/me")

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("times", "status"),
    [
        ({"last_seen_at": ago(days=7, seconds=-60)}, 200),
        ({"last_seen_at": ago(days=7)}, 401),
        ({"last_seen_at": ago(days=8)}, 401),
        ({"expires_at": ago(seconds=-60)}, 200),
        ({"expires_at": ago()}, 401),
        ({"expires_at": ago(days=1)}, 401),
    ],
    ids=["idle-just-under", "idle-at-7-days", "idle-over", "lifetime-left", "lifetime-at", "over"],
)
async def test_a_session_ends_at_its_idle_timeout_and_its_lifetime(
    client: AsyncClient, session: AsyncSession, times: dict[str, object], status: int
) -> None:
    user = await UserFactory.create_async()
    client.cookies.set(COOKIE, await session_for(user, session, **times))

    response = await client.get("/api/auth/me")

    assert response.status_code == status


async def test_a_deactivated_users_session_is_401(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await UserFactory.create_async(is_active=False)
    client.cookies.set(COOKIE, await session_for(user, session))

    response = await client.get("/api/auth/me")

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("seen", "updated"),
    [({"minutes": 4, "seconds": 59}, False), ({"minutes": 5, "seconds": 1}, True)],
    ids=["within-5-minutes", "after-5-minutes"],
)
async def test_last_seen_at_is_written_at_most_every_5_minutes(
    client: AsyncClient, session: AsyncSession, seen: dict[str, float], updated: bool
) -> None:
    user = await UserFactory.create_async()
    client.cookies.set(COOKIE, await session_for(user, session, last_seen_at=ago(**seen)))
    before = (await session_rows(session, user))[0].last_seen_at
    now = await session.scalar(select(func.now()))

    await client.get("/api/auth/me")

    after = (await session_rows(session, user))[0].last_seen_at
    assert after == (now if updated else before)
    assert (after != before) is updated


async def test_the_configured_session_lengths_are_the_ones_used(
    settings: Settings, sessionmaker: SessionMaker, session: AsyncSession
) -> None:
    """Not the defaults (which the `settings` fixture pins): a 1-hour idle timeout and a
    2-hour lifetime set the cookie, the new row, and which sessions are still live."""
    app = create_app(
        settings.model_copy(
            update={
                "session_idle_timeout": timedelta(hours=1),
                "session_lifetime": timedelta(hours=2),
            }
        ),
        sessionmaker=sessionmaker,
    )
    user = await UserFactory.create_async(email="ann@example.com")
    idle = await UserFactory.create_async()
    idle_token = await session_for(idle, session, last_seen_at=ago(minutes=61))
    async with api_client(app) as client:
        signed_in = await sign_in(client, "ann@example.com")
        client.cookies.clear()
        client.cookies.set(COOKIE, idle_token)
        idle_me = await client.get("/api/auth/me")

    _, attributes = set_cookie(signed_in)
    [row] = await session_rows(session, user)
    now = (await session.execute(select(func.now()))).scalar_one()
    assert attributes["max-age"] == "7200"
    assert row.expires_at == now + timedelta(hours=2)
    assert idle_me.status_code == 401


# --- Sign-out -------------------------------------------------------------------------------------


async def test_sign_out_ends_the_session_and_clears_the_cookie(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await UserFactory.create_async(email="ann@example.com")
    await sign_in(client, "ann@example.com")
    other = await session_for(user, session)  # another browser's session stays

    response = await client.post("/api/auth/sign-out")

    assert response.status_code == 204
    value, attributes = set_cookie(response)
    assert value in ("", '""')
    assert attributes["max-age"] == "0"
    assert {"secure", "path"} <= attributes.keys()  # a __Host- cookie is only cleared with them
    assert [row.token_hash for row in await session_rows(session, user)] == [hash_token(other)]
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_sign_out_without_a_session_succeeds(client: AsyncClient) -> None:
    response = await client.post("/api/auth/sign-out")

    assert response.status_code == 204


# --- The Origin and JSON-only checks, wired into the app ---------------------------------------


async def test_a_mutation_from_another_origin_is_403_and_never_touches_the_session(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await UserFactory.create_async()
    token = await session_for(user, session)
    client.cookies.set(COOKIE, token)

    response = await client.post("/api/auth/sign-out", headers={"Origin": "https://evil.example"})

    assert response.status_code == 403
    assert response.json()["code"] == "origin_rejected"
    assert [row.token_hash for row in await session_rows(session, user)] == [hash_token(token)]


async def test_a_mutation_with_no_origin_is_403(client: AsyncClient) -> None:
    del client.headers["Origin"]

    response = await client.post("/api/auth/sign-out")

    assert response.status_code == 403
    assert response.json()["code"] == "origin_rejected"


async def test_a_form_encoded_sign_in_is_415(client: AsyncClient) -> None:
    await UserFactory.create_async(email="ann@example.com")

    response = await client.post(
        "/api/auth/sign-in", data={"email": "ann@example.com", "password": FACTORY_PASSWORD}
    )

    assert response.status_code == 415
    assert response.json()["code"] == "unsupported_media_type"


async def test_a_json_body_with_a_charset_is_accepted(client: AsyncClient) -> None:
    await UserFactory.create_async(email="ann@example.com")

    response = await client.post(
        "/api/auth/sign-in",
        content=f'{{"email": "ann@example.com", "password": "{FACTORY_PASSWORD}"}}',
        headers={"Content-Type": "application/json; charset=utf-8"},
    )

    assert response.status_code == 200


# --- Change password (design-doc §4, "Sign-in" and "Sessions") -------------------------------

NEW_PASSWORD = "a brand new passphrase"


async def change_password(
    client: AsyncClient, new: str = NEW_PASSWORD, current: str = FACTORY_PASSWORD
) -> Response:
    return await client.post(
        "/api/auth/change-password", json={"current_password": current, "new_password": new}
    )


async def stored_hash(session: AsyncSession, user: User) -> str:
    return (
        await session.execute(select(User.hashed_password).where(User.id == user.id))
    ).scalar_one()


async def test_change_password_stores_the_new_one_and_clears_the_forced_change(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await UserFactory.create_async(email="ann@example.com", must_change_password=True)
    await sign_in(client, "ann@example.com")

    response = await change_password(client)

    assert response.status_code == 204
    new_hash = await stored_hash(session, user)
    assert await verify_password(new_hash, NEW_PASSWORD) is True
    assert await verify_password(new_hash, FACTORY_PASSWORD) is False
    must_change = await session.scalar(select(User.must_change_password).where(User.id == user.id))
    assert must_change is False


async def test_change_password_replaces_this_sessions_token_and_ends_the_others(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await UserFactory.create_async(email="ann@example.com")
    old_token, _ = set_cookie(await sign_in(client, "ann@example.com"))
    [this_session] = await session_rows(session, user)
    await session_for(user, session)  # another browser
    bystander = await UserFactory.create_async()
    bystanders_token = await session_for(bystander, session)

    response = await change_password(client)

    new_token, attributes = set_cookie(response)
    assert new_token != old_token
    assert {"secure", "httponly", "path"} <= attributes.keys()
    rows = await session_rows(session, user)
    assert [(row.id, row.token_hash) for row in rows] == [(this_session.id, hash_token(new_token))]
    assert [row.token_hash for row in await session_rows(session, bystander)] == [
        hash_token(bystanders_token)
    ]
    assert (await client.get("/api/auth/me")).status_code == 200  # the new cookie works
    client.cookies.set(COOKIE, old_token)
    assert (await client.get("/api/auth/me")).status_code == 401  # the old token doesn't


async def belong(user: User, how: str) -> Workspace:
    """Put `user` in a new workspace as staff, an org member, or a project member."""
    workspace = await WorkspaceFactory.create_async()
    org = await OrganizationFactory.create_async(workspace=workspace)
    match how:
        case "staff":
            await WorkspaceMembershipFactory.create_async(workspace=workspace, user=user)
        case "org_member":
            await MembershipFactory.create_async(organization=org, user=user)
        case "project_member":
            project = await ProjectFactory.create_async(organization=org, workspace_id=workspace.id)
            await ProjectMembershipFactory.create_async(project=project, user=user)
        case _:
            raise AssertionError(f"unknown membership {how!r}")
    return workspace


@pytest.mark.parametrize("how", ["staff", "org_member", "project_member"])
async def test_change_password_records_the_event_in_the_users_workspace(
    client: AsyncClient, session: AsyncSession, how: str
) -> None:
    user = await UserFactory.create_async(email="ann@example.com")
    workspace = await belong(user, how)
    await sign_in(client, "ann@example.com")

    await change_password(client)

    events = await session.execute(
        select(
            AuditEvent.action,
            AuditEvent.actor_id,
            AuditEvent.target_user_id,
            AuditEvent.workspace_id,
            AuditEvent.organization_id,
            AuditEvent.details,
        )
    )
    assert events.all() == [
        (AuditAction.PASSWORD_CHANGED, user.id, user.id, workspace.id, None, {})
    ]


async def test_change_password_by_staff_who_are_also_org_members_records_their_workspace(
    client: AsyncClient, session: AsyncSession
) -> None:
    """One workspace reached two ways (design-doc §4: staff may also hold org memberships)."""
    user = await UserFactory.create_async(email="ann@example.com")
    workspace = await WorkspaceFactory.create_async()
    org = await OrganizationFactory.create_async(workspace=workspace)
    await WorkspaceMembershipFactory.create_async(workspace=workspace, user=user)
    await MembershipFactory.create_async(organization=org, user=user)
    await sign_in(client, "ann@example.com")

    await change_password(client)

    recorded = await session.execute(select(AuditEvent.action, AuditEvent.workspace_id))
    assert recorded.all() == [(AuditAction.PASSWORD_CHANGED, workspace.id)]


async def test_change_password_with_no_membership_records_the_only_workspace(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A user left with no memberships can still sign in (design-doc §4); the event is in the
    one workspace v1 deploys."""
    await UserFactory.create_async(email="ann@example.com")
    workspace = await WorkspaceFactory.create_async()
    await sign_in(client, "ann@example.com")

    await change_password(client)

    recorded = await session.execute(select(AuditEvent.action, AuditEvent.workspace_id))
    assert recorded.all() == [(AuditAction.PASSWORD_CHANGED, workspace.id)]


async def test_change_password_with_no_membership_and_two_workspaces_records_none(
    client: AsyncClient, session: AsyncSession
) -> None:
    await UserFactory.create_async(email="ann@example.com")
    await WorkspaceFactory.create_async()
    await WorkspaceFactory.create_async()
    await sign_in(client, "ann@example.com")

    await change_password(client)

    recorded = await session.execute(select(AuditEvent.action, AuditEvent.workspace_id))
    assert recorded.all() == [(AuditAction.PASSWORD_CHANGED, None)]


async def test_change_password_in_two_workspaces_records_no_workspace(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Which one would be undecided while there's one workspace (design-doc §4)."""
    user = await UserFactory.create_async(email="ann@example.com")
    await belong(user, "staff")
    await belong(user, "org_member")
    await sign_in(client, "ann@example.com")

    await change_password(client)

    recorded = await session.execute(select(AuditEvent.action, AuditEvent.workspace_id))
    assert recorded.all() == [(AuditAction.PASSWORD_CHANGED, None)]


async def test_a_wrong_current_password_changes_nothing(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await UserFactory.create_async(email="ann@example.com")
    token, _ = set_cookie(await sign_in(client, "ann@example.com"))
    before = await stored_hash(session, user)

    response = await change_password(client, current="not my password")

    assert response.status_code == 422
    assert response.json()["details"]["fields"] == [
        {
            "loc": ["body", "current_password"],
            "message": "This isn't your password.",
            "type": "incorrect",
        }
    ]
    assert await stored_hash(session, user) == before
    assert [row.token_hash for row in await session_rows(session, user)] == [hash_token(token)]
    assert (await session.execute(select(func.count()).select_from(AuditEvent))).scalar_one() == 0


@pytest.mark.parametrize(
    ("new", "problem"),
    [
        ("seven77", "too_short"),
        ("x" * 257, "too_long"),
        ("Ann@Example.com", "same_as_email"),
        ("ANN-LEE-PARK", "same_as_username"),
        (FACTORY_PASSWORD, "same_as_current"),
    ],
)
async def test_a_new_password_against_the_policy_is_422(
    client: AsyncClient, session: AsyncSession, new: str, problem: str
) -> None:
    user = await UserFactory.create_async(email="ann@example.com", username="ann-lee-park")
    await sign_in(client, "ann@example.com")
    before = await stored_hash(session, user)

    response = await change_password(client, new)

    assert response.status_code == 422
    assert [(f["loc"], f["type"]) for f in response.json()["details"]["fields"]] == [
        (["body", "new_password"], problem)
    ]
    assert await stored_hash(session, user) == before


@pytest.mark.parametrize("new", ["eight888", "x" * 256], ids=["8-characters", "256-characters"])
async def test_a_new_password_at_the_length_limits_is_accepted(
    client: AsyncClient, new: str
) -> None:
    await UserFactory.create_async(email="ann@example.com")
    await sign_in(client, "ann@example.com")

    response = await change_password(client, new)

    assert response.status_code == 204


async def test_change_password_without_a_session_is_401(client: AsyncClient) -> None:
    response = await change_password(client)

    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


# --- The forced change (design-doc §4, "Forced change"; S1-plan F1) ---------------------------


@pytest.fixture
async def gated_client(
    settings: Settings, sessionmaker: SessionMaker
) -> AsyncIterator[AsyncClient]:
    """The real app plus a test-only endpoint that needs a signed-in user, the way every
    endpoint but `/me` and change-password will."""
    app = create_app(settings, sessionmaker=sessionmaker)

    @app.post("/api/test/needs-a-user")
    async def needs_a_user(user: SignedInUserDep) -> dict[str, str]:
        return {"email": user.email}

    async with api_client(app) as client:
        yield client


async def test_a_forced_change_blocks_every_other_endpoint(gated_client: AsyncClient) -> None:
    await UserFactory.create_async(email="ann@example.com", must_change_password=True)
    await sign_in(gated_client, "ann@example.com")

    response = await gated_client.post("/api/test/needs-a-user")

    assert response.status_code == 403
    assert response.json() == {
        "code": "password_change_required",
        "message": "Choose a new password to continue.",
        "details": {},
    }


async def test_without_a_forced_change_the_endpoint_is_reachable(
    gated_client: AsyncClient,
) -> None:
    await UserFactory.create_async(email="ann@example.com", must_change_password=False)
    await sign_in(gated_client, "ann@example.com")

    response = await gated_client.post("/api/test/needs-a-user")

    assert (response.status_code, response.json()) == (200, {"email": "ann@example.com"})


async def test_a_forced_change_still_allows_me_change_password_and_sign_out(
    gated_client: AsyncClient, session: AsyncSession
) -> None:
    user = await UserFactory.create_async(email="ann@example.com", must_change_password=True)
    await sign_in(gated_client, "ann@example.com")

    me = await gated_client.get("/api/auth/me")
    changed = await change_password(gated_client)
    unblocked = await gated_client.post("/api/test/needs-a-user")
    signed_out = await gated_client.post("/api/auth/sign-out")

    assert (me.status_code, me.json()["must_change_password"]) == (200, True)
    assert changed.status_code == 204
    assert unblocked.status_code == 200
    assert signed_out.status_code == 204
    assert await session_rows(session, user) == []


async def test_sign_out_works_during_a_forced_change(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await UserFactory.create_async(email="ann@example.com", must_change_password=True)
    await sign_in(client, "ann@example.com")

    response = await client.post("/api/auth/sign-out")

    assert response.status_code == 204
    assert await session_rows(session, user) == []


async def test_the_origin_check_runs_before_the_forced_change_check(
    gated_client: AsyncClient,
) -> None:
    await UserFactory.create_async(email="ann@example.com", must_change_password=True)
    await sign_in(gated_client, "ann@example.com")

    response = await gated_client.post(
        "/api/test/needs-a-user", headers={"Origin": "https://evil.example"}
    )

    assert response.status_code == 403
    assert response.json()["code"] == "origin_rejected"
