import os
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from waterline_cli import doctor, main
from waterline_cli.doctor import (
    CHECKS,
    Probe,
    Result,
    Status,
    parse_version,
    run_checks,
)

HOOKS_CMD = "git rev-parse --path-format=absolute --git-path hooks/pre-commit"

HEALTHY: dict[str, Probe] = {
    "git --version": Probe(0, "git version 2.53.0"),
    "docker --version": Probe(0, "Docker version 29.8.1, build 4a63305"),
    "docker info --format {{.ServerVersion}}": Probe(0, "29.8.1\n"),
    "docker compose version --short": Probe(0, "2.29.1\n"),
    "uv --version": Probe(0, "uv 0.12.19 (x86_64-unknown-linux-gnu)"),
    "uv python find 3.14": Probe(0, "/usr/bin/python3.14\n"),
    "node --version": Probe(0, "v22.23.3\n"),
    "npm --version": Probe(0, "10.9.9\n"),
    HOOKS_CMD: Probe(0, "/nonexistent/.git/hooks/pre-commit\n"),
}


def prober(overrides: dict[str, Probe] | None = None) -> doctor.Prober:
    probes = {**HEALTHY, **(overrides or {})}
    return lambda cmd: probes[" ".join(cmd)]


def by_name(results: list[Result]) -> dict[str, Result]:
    return {r.name: r for r in results}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("git version 2.53.0", (2, 53, 0)),
        ("v22.23.3", (22, 23, 3)),
        ("uv 0.12.19 (x86_64)", (0, 12, 19)),
        ("2.29", (2, 29)),
        ("no digits here", None),
    ],
)
def test_parse_version(text: str, expected: tuple[int, ...] | None) -> None:
    assert parse_version(text) == expected


def test_every_command_probed_by_checks_has_a_healthy_fixture() -> None:
    assert {" ".join(c.cmd) for c in CHECKS} == set(HEALTHY)


def test_healthy_toolchain_has_no_failures() -> None:
    results = run_checks(prober())

    assert [r.name for r in results if r.status is Status.FAIL] == []


@pytest.mark.parametrize(
    ("command", "probe", "name", "detail"),
    [
        ("git --version", Probe(None), "Git", "not installed"),
        ("git --version", Probe(0, "git version 2.30.9"), "Git", "2.30.9 (need ≥ 2.31)"),
        ("git --version", Probe(0, "garbage"), "Git", "could not read version"),
        ("docker --version", Probe(None), "Docker", "not installed"),
        (
            "docker --version",
            Probe(0, "Docker version 19.03.12"),
            "Docker",
            "19.3.12 (need ≥ 20.10)",
        ),
        (
            "docker info --format {{.ServerVersion}}",
            Probe(1, "error"),
            "Docker daemon",
            "not reachable",
        ),
        (
            "docker info --format {{.ServerVersion}}",
            Probe(None),
            "Docker daemon",
            "docker not installed",
        ),
        (
            "docker compose version --short",
            Probe(1, "unknown command"),
            "Docker Compose",
            "could not read version",
        ),
        (
            "docker compose version --short",
            Probe(0, "1.29.2"),
            "Docker Compose",
            "1.29.2 (need ≥ 2.20)",
        ),
        ("uv --version", Probe(0, "uv 0.11.9"), "uv", "0.11.9 (need ≥ 0.12)"),
        ("uv python find 3.14", Probe(2, "not found"), "Python 3.14", "not found by uv"),
        ("uv python find 3.14", Probe(None), "Python 3.14", "uv not installed"),
        ("node --version", Probe(0, "v20.11.0"), "Node", "20.11.0 (need 22.x, ≥ 22.18)"),
        ("node --version", Probe(0, "v24.1.0"), "Node", "24.1.0 (need 22.x, ≥ 22.18)"),
        ("node --version", Probe(0, "v22.17.1"), "Node", "22.17.1 (need 22.x, ≥ 22.18)"),
        ("node --version", Probe(None), "Node", "not installed"),
        ("node --version", Probe(0, "???"), "Node", "could not read version"),
        ("npm --version", Probe(None), "npm", "not installed"),
        (
            "npm --version",
            Probe(1, "Error: Cannot find module"),
            "npm",
            "installed but not working",
        ),
    ],
)
def test_problem_is_reported_as_failure_with_a_hint(
    command: str, probe: Probe, name: str, detail: str
) -> None:
    result = by_name(run_checks(prober({command: probe})))[name]

    assert (result.status, result.detail) == (Status.FAIL, detail)
    assert result.hint


def test_oldest_supported_node_passes() -> None:
    result = by_name(run_checks(prober({"node --version": Probe(0, "v22.18.0\n")})))["Node"]

    assert (result.status, result.detail) == (Status.OK, "22.18.0")


def hooks_result(probe: Probe) -> Result:
    return by_name(run_checks(prober({HOOKS_CMD: probe})))["pre-commit hooks"]


def test_missing_hooks_is_a_warning_not_a_failure(tmp_path: Path) -> None:
    result = hooks_result(Probe(0, str(tmp_path / "hooks" / "pre-commit")))

    assert (result.status, result.detail) == (Status.WARN, "not installed")
    assert result.hint == "uv run pre-commit install"


@pytest.mark.parametrize(
    ("probe", "detail"),
    [
        (
            Probe(128, "fatal: not a git repository\n"),
            "could not locate hooks: fatal: not a git repository",
        ),
        (Probe(-1, "timed out"), "could not locate hooks: timed out"),
        (Probe(None), "git not installed"),
    ],
)
def test_hooks_that_cannot_be_located_are_a_warning(probe: Probe, detail: str) -> None:
    result = hooks_result(probe)

    assert (result.status, result.detail) == (Status.WARN, detail)


def test_unreadable_hook_is_a_warning_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = tmp_path / "pre-commit"
    hook.write_text("# File generated by pre-commit\n")

    def deny(self: Path, *args: object, **kwargs: object) -> str:
        raise PermissionError(self)

    monkeypatch.setattr(Path, "read_text", deny)

    result = hooks_result(Probe(0, str(hook)))

    assert (result.status, result.detail) == (Status.WARN, "not installed")


def test_installed_hooks_are_ok_wherever_git_keeps_them(tmp_path: Path) -> None:
    hook = tmp_path / "custom-hooks-path" / "pre-commit"
    hook.parent.mkdir()
    hook.write_text("#!/usr/bin/env bash\n# File generated by pre-commit\n")

    assert hooks_result(Probe(0, f"{hook}\n")).status is Status.OK


def test_hook_path_probe_resolves_in_a_real_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Isolate from the developer's git config and any GIT_DIR set by a calling hook.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for var in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_COMMON_DIR",
        "GIT_CONFIG_PARAMETERS",
        "GIT_CONFIG_COUNT",
    ):
        monkeypatch.delenv(var, raising=False)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)  # noqa: S603, S607 -- fixed git command, no shell
    monkeypatch.chdir(tmp_path)

    probe = doctor.run_probe(tuple(HOOKS_CMD.split()))

    assert probe.returncode == 0
    assert Path(probe.output.strip()) == tmp_path.resolve() / ".git" / "hooks" / "pre-commit"


def test_run_probe_reports_missing_executable() -> None:
    assert doctor.run_probe(("waterline-no-such-tool",)) == Probe(returncode=None)


def test_run_probe_captures_output() -> None:
    probe = doctor.run_probe(("uv", "--version"))

    assert probe.returncode == 0
    assert probe.output.startswith("uv ")


def test_run_probe_reports_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def hang(cmd: tuple[str, ...], **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd, 30)

    monkeypatch.setattr(doctor.subprocess, "run", hang)

    assert doctor.run_probe(("git", "--version")) == Probe(returncode=-1, output="timed out")


def test_run_probe_reports_unrunnable_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(cmd: tuple[str, ...], **kwargs: object) -> None:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(doctor.subprocess, "run", refuse)

    probe = doctor.run_probe(("git", "--version"))

    assert probe.returncode == -1
    assert probe.output.startswith("could not run:")


@pytest.mark.parametrize(
    ("results", "exit_code", "summary"),
    [
        ([Result("Git", Status.OK, "2.53.0")], 0, "Toolchain OK."),
        ([Result("Hooks", Status.WARN, "not installed", "fix")], 0, "Toolchain OK."),
        ([Result("Node", Status.FAIL, "20.1.0", "fix")], 1, "1 check(s) failed."),
    ],
)
def test_doctor_exit_code_reflects_failures(
    monkeypatch: pytest.MonkeyPatch, results: list[Result], exit_code: int, summary: str
) -> None:
    def fake_run_checks() -> list[Result]:
        return results

    monkeypatch.setattr(main, "run_checks", fake_run_checks)

    outcome = CliRunner().invoke(main.app, ["doctor"])

    assert outcome.exit_code == exit_code
    assert summary in outcome.output
