import re

import pytest
import typer
from typer.core import TyperGroup
from typer.testing import CliRunner

from waterline_cli.main import app

runner = CliRunner()
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def help_text(path: tuple[str, ...]) -> str:
    """`--help` output without ANSI styling: Typer forces a styled terminal when it sees
    GITHUB_ACTIONS (or FORCE_COLOR), which splits words like `--dry-run` with escape codes."""
    result = runner.invoke(app, [*path, "--help"])
    assert result.exit_code == 0, result.output
    return _ANSI_ESCAPE.sub("", result.output)


BACKEND_LINT = [
    "(cd backend && uv run ruff check .)",
    "(cd backend && uv run ruff format --check .)",
    "(cd backend && uv run pyright)",
    "(cd backend && uv run lint-imports)",
]
BACKEND_FMT = [
    "(cd backend && uv run ruff format .)",
    "(cd backend && uv run ruff check --fix .)",
]
BACKEND_TEST = [
    "(cd backend && uv run pytest)",
    "(cd backend && uv run coverage report --fail-under=100 '--include=app/authz/*,app/rules/*')",
]
BACKEND_CHECK = [
    "(cd backend && uv lock --check)",
    "(cd backend && uv run python -m app.openapi_export --check)",
    *BACKEND_LINT,
    *BACKEND_TEST,
]
FRONTEND_LINT = ["(cd frontend && npm run lint)", "(cd frontend && npm run typecheck)"]
FRONTEND_FMT = ["(cd frontend && npm run format)", "(cd frontend && npm run lint:fix)"]
FRONTEND_TEST = ["(cd frontend && npm run test)"]
FRONTEND_CHECK = ["(cd frontend && npm run check:client)", *FRONTEND_LINT, *FRONTEND_TEST]
UP = "docker compose up --detach --wait --build --renew-anon-volumes"
CLI_LINT = [
    "(cd tools/cli && uv run ruff check .)",
    "(cd tools/cli && uv run ruff format --check .)",
    "(cd tools/cli && uv run pyright)",
]
CLI_FMT = [
    "(cd tools/cli && uv run ruff format .)",
    "(cd tools/cli && uv run ruff check --fix .)",
]
CLI_TEST = ["(cd tools/cli && uv run pytest)"]
CLI_CHECK = ["uv lock --check", *CLI_LINT, *CLI_TEST]


def command_tree() -> dict[tuple[str, ...], bool]:
    """Every command and group in the CLI, mapped to whether it is a leaf command."""
    tree: dict[tuple[str, ...], bool] = {}

    def walk(command: object, path: tuple[str, ...]) -> None:
        tree[path] = not isinstance(command, TyperGroup)
        if isinstance(command, TyperGroup):
            for name, sub in command.commands.items():
                walk(sub, (*path, name))

    walk(typer.main.get_command(app), ())
    return tree


@pytest.mark.parametrize("path", command_tree(), ids=lambda p: " ".join(p) or "wl")
def test_help_works_for_every_command(path: tuple[str, ...]) -> None:
    assert "Usage:" in help_text(path)


@pytest.mark.parametrize("path", [p for p, leaf in command_tree().items() if leaf], ids=" ".join)
def test_every_command_accepts_dry_run(path: tuple[str, ...]) -> None:
    assert "--dry-run" in help_text(path)


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        pytest.param(["check"], [*BACKEND_CHECK, *FRONTEND_CHECK, *CLI_CHECK], id="check"),
        pytest.param(["test"], [*BACKEND_TEST, *FRONTEND_TEST, *CLI_TEST], id="test"),
        pytest.param(["lint"], [*BACKEND_LINT, *FRONTEND_LINT, *CLI_LINT], id="lint"),
        pytest.param(["fmt"], [*BACKEND_FMT, *FRONTEND_FMT, *CLI_FMT], id="fmt"),
        pytest.param(["backend", "check"], BACKEND_CHECK, id="backend-check"),
        pytest.param(["backend", "test"], BACKEND_TEST, id="backend-test"),
        pytest.param(["backend", "lint"], BACKEND_LINT, id="backend-lint"),
        pytest.param(["backend", "fmt"], BACKEND_FMT, id="backend-fmt"),
        pytest.param(
            ["backend", "test", "-k", "approval", "-x"],
            ["(cd backend && uv run pytest --no-cov -k approval -x)"],
            id="backend-test-pass-through",
        ),
        pytest.param(["frontend", "check"], FRONTEND_CHECK, id="frontend-check"),
        pytest.param(["frontend", "test"], FRONTEND_TEST, id="frontend-test"),
        pytest.param(["frontend", "lint"], FRONTEND_LINT, id="frontend-lint"),
        pytest.param(["frontend", "fmt"], FRONTEND_FMT, id="frontend-fmt"),
        pytest.param(
            ["frontend", "test", "src/api", "-t", "network"],
            ["(cd frontend && npx vitest run src/api -t network)"],
            id="frontend-test-pass-through",
        ),
        pytest.param(["up"], [UP], id="up"),
        pytest.param(["up", "postgres"], [f"{UP} postgres"], id="up-service"),
        pytest.param(["down"], ["docker compose down"], id="down"),
        pytest.param(["down", "-v"], ["docker compose down -v"], id="down-volumes"),
        pytest.param(["logs"], ["docker compose logs --follow"], id="logs"),
        pytest.param(["logs", "api"], ["docker compose logs --follow api"], id="logs-service"),
        pytest.param(["migrate"], ["docker compose run --rm --build migrate"], id="migrate"),
        pytest.param(
            ["gen-client"],
            [
                "(cd backend && uv run python -m app.openapi_export)",
                "(cd frontend && npm run gen:client)",
            ],
            id="gen-client",
        ),
        pytest.param(
            ["backend", "migration", "add phase"],
            ["(cd backend && uv run alembic revision --autogenerate -m 'add phase')"],
            id="backend-migration",
        ),
        pytest.param(
            ["doctor"],
            [
                "git --version",
                "docker --version",
                "docker info --format '{{.ServerVersion}}'",
                "docker compose version --short",
                "uv --version",
                "uv python find 3.14",
                "node --version",
                "npm --version",
                "git rev-parse --path-format=absolute --git-path hooks/pre-commit",
            ],
            id="doctor",
        ),
    ],
)
def test_dry_run_prints_underlying_commands(args: list[str], expected: list[str]) -> None:
    result = runner.invoke(app, [*args, "--dry-run"])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == expected
