"""App admin commands, run inside the app against the database (build plan, "Developer CLI"):
`python -m app.cli <command>`, which the developer CLI runs as `wl seed` and `wl admin <command>`.

- `seed`: create the workspace and its first system admin, who is its owner. Each value comes
  from its flag (none for the password), else its `SEED_*` environment variable, else a prompt
  (only on a terminal), so CI runs it non-interactively.
- `grant-system-admin <email>` / `revoke-system-admin <email>`: the system-admin flag, which
  nothing else can change (design-doc §4, "Users").

Each command is one transaction, committed here (as the request dependency does for the API).
"""

import argparse
import asyncio
import getpass
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app import models  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers every model
from app.core.db import SessionMaker, create_engine, create_sessionmaker
from app.core.errors import AppError
from app.core.settings import get_settings
from app.services.auth import AuthService
from app.services.workspace import WorkspaceService


@dataclass(frozen=True)
class SeedField:
    name: str  # the service's keyword, the flag's name with `_` for `-`
    label: str
    secret: bool = False

    @property
    def env(self) -> str:
        return f"SEED_{self.name.upper()}"


SEED_FIELDS = (
    SeedField("workspace_name", "Workspace name"),
    SeedField("workspace_slug", "Workspace slug"),
    SeedField("email", "Admin email"),
    SeedField("username", "Admin username"),
    SeedField("name", "Admin name"),
    SeedField("password", "Admin password", secret=True),
)


def say(message: str, *, error: bool = False) -> None:
    """The command's output: a CLI talks to its terminal."""
    print(message, file=sys.stderr if error else sys.stdout)


class InputError(Exception):
    """A value the command needs and couldn't get."""


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="python -m app.cli", description="Waterline app admin commands."
    )
    commands = root.add_subparsers(dest="command", required=True)
    seed = commands.add_parser(
        "seed", help="Create the workspace and its first system admin (its owner)."
    )
    # No flag for the password: `wl seed` prints the command it runs, and a flag would put the
    # first system admin's password in the terminal, its scrollback, and CI logs.
    for field in SEED_FIELDS:
        if not field.secret:
            seed.add_argument(
                f"--{field.name.replace('_', '-')}", dest=field.name, help=f"or ${field.env}"
            )
    for command, verb in (("grant-system-admin", "Grant"), ("revoke-system-admin", "Revoke")):
        sub = commands.add_parser(command, help=f"{verb} the system-admin flag.")
        sub.add_argument("email")
    return root


def seed_values(
    args: argparse.Namespace,
    *,
    environ: Mapping[str, str],
    interactive: bool,
    ask: Callable[[str], str] = input,
    ask_secret: Callable[[str], str] = getpass.getpass,
) -> dict[str, str]:
    """Each seed value from its flag, its environment variable, or (on a terminal) a prompt;
    the password is asked twice. Raises `InputError` for a value it can't get."""
    values: dict[str, str] = {}
    missing: list[str] = []
    for field in SEED_FIELDS:
        # An empty value counts as missing (e.g. a variable set to nothing).
        value = getattr(args, field.name, None) or environ.get(field.env) or None
        if value is None and interactive:
            if field.secret:
                value = ask_secret(f"{field.label}: ")
                if ask_secret(f"{field.label} (again): ") != value:
                    raise InputError("The passwords don't match.")
            else:
                value = ask(f"{field.label}: ")
        if value is None:
            flag = "" if field.secret else f"--{field.name.replace('_', '-')} or "
            missing.append(f"{flag}${field.env}")
        else:
            values[field.name] = value
    if missing:
        raise InputError(f"Missing, and there's no terminal to ask: {', '.join(missing)}.")
    return values


async def run(
    args: argparse.Namespace, sessionmaker: SessionMaker, seed: Mapping[str, str] | None = None
) -> int:
    """Run one command in one transaction; prints the outcome and returns the exit code."""
    try:
        async with sessionmaker() as session, session.begin():
            say(await _command(session, args, seed or {}))
    except AppError as exc:
        say(f"Error: {exc.error_message}", error=True)
        fields = cast(list[dict[str, Any]], exc.details.get("fields", []))
        for field in fields:
            say(f"  {field['loc'][-1]}: {field['message']}", error=True)
        return 1
    return 0


async def _command(session: AsyncSession, args: argparse.Namespace, seed: Mapping[str, str]) -> str:
    auth = AuthService(session, get_settings())
    match args.command:
        case "seed":
            workspace, user = await WorkspaceService(session).seed(**seed)
            return f"Created workspace {workspace.slug} with system admin {user.email} as owner."
        case "grant-system-admin":
            granted = await auth.grant_system_admin(args.email)
            return f"{args.email} {'is now' if granted else 'was already'} a system admin."
        case _:  # "revoke-system-admin" (argparse allows no other)
            revoked = await auth.revoke_system_admin(args.email)
            return f"{args.email} {'is no longer' if revoked else 'was not'} a system admin."


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    seed: dict[str, str] = {}
    if args.command == "seed":
        try:
            seed = seed_values(args, environ=os.environ, interactive=sys.stdin.isatty())
        except InputError as exc:
            say(f"Error: {exc}", error=True)
            return 1

    async def run_with_engine() -> int:
        engine = create_engine(get_settings().database_url())
        try:
            return await run(args, create_sessionmaker(engine), seed)
        finally:
            await engine.dispose()

    return asyncio.run(run_with_engine())


if __name__ == "__main__":
    sys.exit(main())
