"""The app admin commands (`app/cli.py`): the seed (build plan, "Authentication", Seed command;
S1-plan F6) and the system-admin flag (design-doc §4, "Users"), run in the test transaction."""

import argparse
from collections.abc import Callable

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli import InputError, main, parser, run, seed_values
from app.core.db import SessionMaker
from app.core.security import verify_password
from app.enums import AuditAction, AuditEntityType, WorkspaceRole
from app.models.audit_event import AuditEvent
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory

pytestmark = [pytest.mark.anyio, pytest.mark.security]

SEED = {
    "workspace_name": "Acme Consulting",
    "workspace_slug": "acme",
    "email": "Admin@Acme.example",
    "username": "admin",
    "name": "Ada Admin",
    "password": "a long admin passphrase",
}


def args(*argv: str) -> argparse.Namespace:
    return parser().parse_args(argv)


async def count(session: AsyncSession, model: type[object]) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def events(session: AsyncSession) -> list[tuple[object, ...]]:
    rows = await session.execute(
        select(
            AuditEvent.action,
            AuditEvent.actor_id,
            AuditEvent.workspace_id,
            AuditEvent.target_user_id,
            AuditEvent.entity_type,
            AuditEvent.entity_id,
            AuditEvent.details,
        ).order_by(AuditEvent.id)
    )
    return [tuple(row) for row in rows]


# --- seed -----------------------------------------------------------------------------------------


async def test_seed_creates_the_workspace_and_its_owner_a_system_admin(
    sessionmaker: SessionMaker, session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    code = await run(args("seed"), sessionmaker, SEED)

    workspace = (await session.execute(select(Workspace))).scalar_one()
    user = (await session.execute(select(User))).scalar_one()
    membership = (await session.execute(select(WorkspaceMembership))).scalar_one()
    assert code == 0
    assert (workspace.name, workspace.slug) == ("Acme Consulting", "acme")
    assert (user.email, user.username, user.name) == ("admin@acme.example", "admin", "Ada Admin")
    assert (user.is_system_admin, user.is_active, user.must_change_password) == (True, True, False)
    assert await verify_password(user.hashed_password, "a long admin passphrase") is True
    assert (membership.workspace_id, membership.user_id, membership.role) == (
        workspace.id,
        user.id,
        WorkspaceRole.OWNER,
    )
    assert "Created workspace acme with system admin admin@acme.example" in capsys.readouterr().out


async def test_seed_records_its_four_events_with_no_actor(
    sessionmaker: SessionMaker, session: AsyncSession
) -> None:
    await run(args("seed"), sessionmaker, SEED)

    workspace = (await session.execute(select(Workspace))).scalar_one()
    user = (await session.execute(select(User))).scalar_one()
    ws, ws_type = workspace.id, AuditEntityType.WORKSPACE
    assert await events(session) == [
        (
            AuditAction.WORKSPACE_CREATED,
            None,
            ws,
            None,
            ws_type,
            ws,
            {"name": "Acme Consulting", "slug": "acme"},
        ),
        (AuditAction.USER_CREATED, None, ws, user.id, None, None, {}),
        (AuditAction.SYSTEM_ADMIN_GRANTED, None, None, user.id, None, None, {}),
        (AuditAction.WORKSPACE_MEMBER_ADDED, None, ws, user.id, ws_type, ws, {"role": "owner"}),
    ]


async def test_seed_refuses_when_a_workspace_exists(
    sessionmaker: SessionMaker, session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    await WorkspaceFactory.create_async()

    code = await run(args("seed"), sessionmaker, SEED)

    assert code == 1
    assert "A workspace already exists." in capsys.readouterr().err
    assert (await count(session, Workspace), await count(session, User)) == (1, 0)


@pytest.mark.parametrize(
    ("field", "value", "problem"),
    [
        ("workspace_name", "  ", "This is required."),
        ("workspace_slug", "api", "This name is reserved."),
        ("workspace_slug", "Acme", "Use only lowercase letters, digits, and hyphens."),
        ("email", "admin.acme.example", "Enter an email address."),
        ("email", "admin@localhost", "Enter an email address."),
        ("username", "9admin", "Start with a letter."),
        ("name", "", "This is required."),
        ("password", "short", "Use at least 8 characters."),
        ("password", "ADMIN@acme.example", "The password can't be the account's email."),
    ],
)
async def test_seed_refuses_an_invalid_value_and_creates_nothing(
    sessionmaker: SessionMaker,
    session: AsyncSession,
    capsys: pytest.CaptureFixture[str],
    field: str,
    value: str,
    problem: str,
) -> None:
    code = await run(args("seed"), sessionmaker, {**SEED, field: value})

    assert code == 1
    assert f"  {field}: {problem}" in capsys.readouterr().err
    assert (await count(session, Workspace), await count(session, User)) == (0, 0)
    assert await count(session, AuditEvent) == 0


def no_prompt(label: str) -> str:
    raise AssertionError(f"asked for {label!r}")


def answers(*replies: str) -> Callable[[str], str]:
    pending = list(replies)
    return lambda _label: pending.pop(0)


def test_seed_values_come_from_flags_then_the_environment() -> None:
    parsed = args("seed", "--workspace-name", "From flag", "--email", "flag@acme.example")
    environ = {
        "SEED_WORKSPACE_NAME": "From env",
        "SEED_WORKSPACE_SLUG": "acme",
        "SEED_USERNAME": "admin",
        "SEED_NAME": "Ada",
        "SEED_PASSWORD": "env passphrase",
    }

    values = seed_values(parsed, environ=environ, interactive=False)

    assert values == {
        "workspace_name": "From flag",
        "workspace_slug": "acme",
        "email": "flag@acme.example",
        "username": "admin",
        "name": "Ada",
        "password": "env passphrase",
    }


def test_an_empty_seed_variable_counts_as_missing() -> None:
    """`docker compose run -e NAME` can pass a variable set to nothing."""
    with pytest.raises(InputError, match=r"\$SEED_PASSWORD\.$"):
        seed_values(
            args("seed", "--workspace-name", "Acme", "--workspace-slug", "acme"),
            environ={
                "SEED_EMAIL": "ann@acme.example",
                "SEED_USERNAME": "ann",
                "SEED_NAME": "Ann",
                "SEED_PASSWORD": "",
            },
            interactive=False,
        )


def test_seed_values_are_asked_for_on_a_terminal_the_password_twice() -> None:
    parsed = args("seed", "--workspace-name", "Acme", "--workspace-slug", "acme")

    values = seed_values(
        parsed,
        environ={},
        interactive=True,
        ask=answers("ann@acme.example", "ann", "Ann"),
        ask_secret=answers("typed twice", "typed twice"),
    )

    assert values == {
        "workspace_name": "Acme",
        "workspace_slug": "acme",
        "email": "ann@acme.example",
        "username": "ann",
        "name": "Ann",
        "password": "typed twice",
    }


def test_seed_values_refuse_two_different_passwords() -> None:
    with pytest.raises(InputError, match=r"The passwords don't match\."):
        seed_values(
            args("seed"),
            environ=dict.fromkeys(("SEED_WORKSPACE_NAME", "SEED_WORKSPACE_SLUG"), "x"),
            interactive=True,
            ask=answers("ann@acme.example", "ann", "Ann"),
            ask_secret=answers("first", "second"),
        )


def test_seed_values_without_a_terminal_name_every_missing_value() -> None:
    with pytest.raises(InputError, match=r"--username or \$SEED_USERNAME, \$SEED_PASSWORD\.$"):
        seed_values(
            args("seed", "--workspace-name", "Acme", "--workspace-slug", "acme"),
            environ={"SEED_EMAIL": "ann@acme.example", "SEED_NAME": "Ann"},
            interactive=False,
            ask=no_prompt,
            ask_secret=no_prompt,
        )


def test_the_password_has_no_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """`wl seed` prints the command it runs, so a flag would show the password."""
    with pytest.raises(SystemExit):
        args("seed", "--password", "a long admin passphrase")
    assert "unrecognized arguments: --password" in capsys.readouterr().err


def test_main_seed_without_a_terminal_or_values_fails_before_touching_the_database(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for key in ("WORKSPACE_NAME", "WORKSPACE_SLUG", "EMAIL", "USERNAME", "NAME", "PASSWORD"):
        monkeypatch.delenv(f"SEED_{key}", raising=False)

    assert main(["seed"]) == 1  # pytest's stdin isn't a terminal
    assert "Missing, and there's no terminal to ask" in capsys.readouterr().err


# --- grant-system-admin / revoke-system-admin ----------------------------------------------------


async def is_system_admin(session: AsyncSession, user: User) -> bool:
    return (
        await session.execute(select(User.is_system_admin).where(User.id == user.id))
    ).scalar_one()


async def test_grant_sets_the_flag_and_records_an_instance_level_event(
    sessionmaker: SessionMaker, session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    user = await UserFactory.create_async(email="ann@acme.example", is_system_admin=False)

    code = await run(args("grant-system-admin", "Ann@Acme.example"), sessionmaker)

    assert code == 0
    assert await is_system_admin(session, user) is True
    assert await events(session) == [
        (AuditAction.SYSTEM_ADMIN_GRANTED, None, None, user.id, None, None, {})
    ]
    assert "is now a system admin" in capsys.readouterr().out


async def test_granting_an_admin_again_changes_nothing(
    sessionmaker: SessionMaker, session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    await UserFactory.create_async(email="ann@acme.example", is_system_admin=True)

    code = await run(args("grant-system-admin", "ann@acme.example"), sessionmaker)

    assert code == 0
    assert await events(session) == []
    assert "was already a system admin" in capsys.readouterr().out


@pytest.mark.parametrize("command", ["grant-system-admin", "revoke-system-admin"])
async def test_an_unknown_email_is_an_error(
    sessionmaker: SessionMaker, capsys: pytest.CaptureFixture[str], command: str
) -> None:
    code = await run(args(command, "nobody@acme.example"), sessionmaker)

    assert code == 1
    assert "No account has that email." in capsys.readouterr().err


async def test_revoke_clears_the_flag_and_records_an_event(
    sessionmaker: SessionMaker, session: AsyncSession
) -> None:
    user = await UserFactory.create_async(email="ann@acme.example", is_system_admin=True)
    await UserFactory.create_async(is_system_admin=True, is_active=True)

    code = await run(args("revoke-system-admin", "ann@acme.example"), sessionmaker)

    assert code == 0
    assert await is_system_admin(session, user) is False
    assert await events(session) == [
        (AuditAction.SYSTEM_ADMIN_REVOKED, None, None, user.id, None, None, {})
    ]


async def test_revoking_the_last_active_system_admin_is_refused(
    sessionmaker: SessionMaker, session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    """An inactive system admin doesn't count: they can't sign in."""
    user = await UserFactory.create_async(email="ann@acme.example", is_system_admin=True)
    await UserFactory.create_async(is_system_admin=True, is_active=False)

    code = await run(args("revoke-system-admin", "ann@acme.example"), sessionmaker)

    assert code == 1
    assert "This is the last active system admin." in capsys.readouterr().err
    assert await is_system_admin(session, user) is True
    assert await events(session) == []


async def test_revoking_a_non_admin_changes_nothing(
    sessionmaker: SessionMaker, session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    await UserFactory.create_async(email="ann@acme.example", is_system_admin=False)

    code = await run(args("revoke-system-admin", "ann@acme.example"), sessionmaker)

    assert code == 0
    assert await events(session) == []
    assert "was not a system admin" in capsys.readouterr().out
