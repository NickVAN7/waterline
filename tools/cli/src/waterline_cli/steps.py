"""The commands behind each `wl` command, per half of the repo.

Tool configuration lives with each project (`backend/pyproject.toml`,
`tools/cli/pyproject.toml`); these functions only choose which tools to run and where.
"""

from collections.abc import Sequence

from waterline_cli.runner import Step, step

BACKEND = "backend"
FRONTEND = "frontend"
CLI = "tools/cli"


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
    """The full suite with coverage gates, or a filtered run (no coverage) when given arguments.
    pytest enforces both gates itself: coverage's fail_under, and 100% for app/authz and
    app/rules (a hook in backend/tests/conftest.py)."""
    if extra:
        return [step("uv", "run", "pytest", "--no-cov", *extra, cwd=BACKEND)]
    return [step("uv", "run", "pytest", cwd=BACKEND)]


def backend_mutate() -> list[Step]:
    """Mutation testing over app/rules and app/authz ([tool.mutmut] in backend/pyproject.toml),
    from a clean slate; fails on any mutant not killed (mutmut itself always exits 0)."""
    gate = ("uv", "run", "python", "-m", "tests.support.mutation_gate")
    return [
        step(*gate, "clean", cwd=BACKEND),
        step("uv", "run", "mutmut", "run", cwd=BACKEND),
        step("uv", "run", "mutmut", "export-cicd-stats", cwd=BACKEND),
        step(*gate, "check", cwd=BACKEND),
    ]


def backend_check() -> list[Step]:
    return [
        step("uv", "lock", "--check", cwd=BACKEND),
        # backend/openapi.json matches the code (client freshness, first half).
        step("uv", "run", "python", "-m", "app.openapi_export", "--check", cwd=BACKEND),
        *backend_lint(),
        *backend_test(),
        *backend_mutate(),
    ]


def backend_migration(message: str) -> list[Step]:
    return [step("uv", "run", "alembic", "revision", "--autogenerate", "-m", message, cwd=BACKEND)]


def migrate() -> list[Step]:
    """Apply migrations to the dev database with the Compose migrate service (its image rebuilt
    first, so a dependency change since the last `wl up` is included)."""
    return [step("docker", "compose", "run", "--rm", "--build", "migrate")]


# The seed command's environment variables (backend/app/cli.py), passed into the container
# when they're set, so `wl seed` runs non-interactively from them (CI).
SEED_ENV = (
    "SEED_WORKSPACE_NAME",
    "SEED_WORKSPACE_SLUG",
    "SEED_EMAIL",
    "SEED_USERNAME",
    "SEED_NAME",
    "SEED_PASSWORD",
)


def app_cli(args: Sequence[str], env: Sequence[str] = ()) -> list[Step]:
    """Run an app admin command (`python -m app.cli`) in a one-off container from the api
    service's image; Compose runs the migrations first (the api service depends on them)."""
    passed = [flag for name in env for flag in ("-e", name)]
    return [
        step("docker", "compose", "run", "--rm", *passed, "api", "python", "-m", "app.cli", *args)
    ]


def seed(extra: Sequence[str] = ()) -> list[Step]:
    return app_cli(["seed", *extra], env=SEED_ENV)


def admin(extra: Sequence[str] = ()) -> list[Step]:
    return app_cli(extra)


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


# The Claude Code hooks are linted, formatted, type-checked, and tested with the CLI
# (tools/cli/pyproject.toml).
HOOKS = "../../.claude/hooks"


def cli_lint() -> list[Step]:
    return [
        step("uv", "run", "ruff", "check", ".", HOOKS, cwd=CLI),
        step("uv", "run", "ruff", "format", "--check", ".", HOOKS, cwd=CLI),
        step("uv", "run", "pyright", cwd=CLI),
    ]


def cli_fmt() -> list[Step]:
    return [
        step("uv", "run", "ruff", "format", ".", HOOKS, cwd=CLI),
        step("uv", "run", "ruff", "check", "--fix", ".", HOOKS, cwd=CLI),
    ]


def cli_test() -> list[Step]:
    return [step("uv", "run", "pytest", cwd=CLI)]


def cli_check() -> list[Step]:
    return [step("uv", "lock", "--check"), *cli_lint(), *cli_test()]


def audit(uv_ignores: Sequence[str] = ()) -> list[Step]:
    """Supply-chain gates (DL-13): known vulnerabilities in both Python lockfiles and the npm
    lockfile, dev dependencies included, and secrets anywhere in the git history. Needs the
    network. `uv_ignores` are the allowlisted Python advisories (`--ignore <id>` pairs); the npm
    gate reads the allowlist itself (waterline_cli/audit.py)."""
    uv_audit = ("uv", "audit", "--frozen", "--preview-features", "audit-command", *uv_ignores)
    helper = ("uv", "run", "python", "-m", "waterline_cli.audit")
    return [
        step(*helper, "network"),
        step(*uv_audit),
        step(*uv_audit, cwd=BACKEND),
        step(*helper, "npm"),
        step(
            "uv",
            "run",
            "pre-commit",
            "run",
            "gitleaks-history",
            "--hook-stage",
            "manual",
            "--all-files",
        ),
    ]
