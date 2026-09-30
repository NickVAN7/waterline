"""The commands behind each `wl` command, per half of the repo.

Tool configuration lives with each project (`backend/pyproject.toml`,
`tools/cli/pyproject.toml`); these functions only choose which tools to run and where.
"""

from collections.abc import Sequence

from waterline_cli.runner import Step, step

BACKEND = "backend"
FRONTEND = "frontend"
CLI = "tools/cli"

# Held to 100% line + branch coverage (docs/testing-strategy.md, "Coverage gates").
STRICT_COVERAGE_PACKAGES = ("app/authz/*", "app/rules/*")


def backend_lint() -> list[Step]:
    return [
        step("uv", "run", "ruff", "check", ".", cwd=BACKEND),
        step("uv", "run", "ruff", "format", "--check", ".", cwd=BACKEND),
        step("uv", "run", "pyright", cwd=BACKEND),
        step("uv", "run", "lint-imports", cwd=BACKEND),
    ]


def backend_fmt() -> list[Step]:
    return [
        step("uv", "run", "ruff", "format", ".", cwd=BACKEND),
        step("uv", "run", "ruff", "check", "--fix", ".", cwd=BACKEND),
    ]


def backend_test(extra: Sequence[str] = ()) -> list[Step]:
    """The full suite with coverage gates, or a filtered run (no coverage) when given arguments."""
    if extra:
        return [step("uv", "run", "pytest", "--no-cov", *extra, cwd=BACKEND)]
    return [
        step("uv", "run", "pytest", cwd=BACKEND),
        step(
            "uv",
            "run",
            "coverage",
            "report",
            "--fail-under=100",
            f"--include={','.join(STRICT_COVERAGE_PACKAGES)}",
            cwd=BACKEND,
        ),
    ]


def backend_check() -> list[Step]:
    return [
        step("uv", "lock", "--check", cwd=BACKEND),
        # backend/openapi.json matches the code (client freshness, first half).
        step("uv", "run", "python", "-m", "app.openapi_export", "--check", cwd=BACKEND),
        *backend_lint(),
        *backend_test(),
    ]


def backend_migration(message: str) -> list[Step]:
    return [step("uv", "run", "alembic", "revision", "--autogenerate", "-m", message, cwd=BACKEND)]


def migrate() -> list[Step]:
    """Apply migrations to the dev database with the Compose migrate service (its image rebuilt
    first, so a dependency change since the last `wl up` is included)."""
    return [step("docker", "compose", "run", "--rm", "--build", "migrate")]


def up(extra: Sequence[str] = ()) -> list[Step]:
    """Build the images, start the stack in the background, and wait until every service is up.
    `--renew-anon-volumes` refreshes the web container's node_modules from its image."""
    return [
        step(
            "docker",
            "compose",
            "up",
            "--detach",
            "--wait",
            "--build",
            "--renew-anon-volumes",
            *extra,
        )
    ]


def down(extra: Sequence[str] = ()) -> list[Step]:
    """Stop the stack. Data survives in the named volume unless `-v` is passed."""
    return [step("docker", "compose", "down", *extra)]


def logs(extra: Sequence[str] = ()) -> list[Step]:
    """Follow the stack's logs (one service's, when named)."""
    return [step("docker", "compose", "logs", "--follow", *extra)]


def gen_client() -> list[Step]:
    """Export the OpenAPI schema from the backend's code, then generate the frontend's types."""
    return [
        step("uv", "run", "python", "-m", "app.openapi_export", cwd=BACKEND),
        step("npm", "run", "gen:client", cwd=FRONTEND),
    ]


def frontend_lint() -> list[Step]:
    return [
        step("npm", "run", "lint", cwd=FRONTEND),
        step("npm", "run", "typecheck", cwd=FRONTEND),
    ]


def frontend_fmt() -> list[Step]:
    return [
        step("npm", "run", "format", cwd=FRONTEND),
        step("npm", "run", "lint:fix", cwd=FRONTEND),
    ]


def frontend_test(extra: Sequence[str] = ()) -> list[Step]:
    """All tests with the coverage gates, or a filtered run (no coverage) when given arguments."""
    if extra:
        return [step("npx", "vitest", "run", *extra, cwd=FRONTEND)]
    return [step("npm", "run", "test", cwd=FRONTEND)]


def frontend_check() -> list[Step]:
    return [
        # src/api/schema.d.ts matches backend/openapi.json (client freshness, second half).
        step("npm", "run", "check:client", cwd=FRONTEND),
        *frontend_lint(),
        *frontend_test(),
    ]


def cli_lint() -> list[Step]:
    return [
        step("uv", "run", "ruff", "check", ".", cwd=CLI),
        step("uv", "run", "ruff", "format", "--check", ".", cwd=CLI),
        step("uv", "run", "pyright", cwd=CLI),
    ]


def cli_fmt() -> list[Step]:
    return [
        step("uv", "run", "ruff", "format", ".", cwd=CLI),
        step("uv", "run", "ruff", "check", "--fix", ".", cwd=CLI),
    ]


def cli_test() -> list[Step]:
    return [step("uv", "run", "pytest", cwd=CLI)]


def cli_check() -> list[Step]:
    return [step("uv", "lock", "--check"), *cli_lint(), *cli_test()]
