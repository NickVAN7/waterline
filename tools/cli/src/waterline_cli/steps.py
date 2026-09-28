"""The commands behind each `wl` command, per half of the repo.

Tool configuration lives with each project (`backend/pyproject.toml`,
`tools/cli/pyproject.toml`); these functions only choose which tools to run and where.
"""

from collections.abc import Sequence

from waterline_cli.runner import Step, step

BACKEND = "backend"
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
    return [step("uv", "lock", "--check", cwd=BACKEND), *backend_lint(), *backend_test()]


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
