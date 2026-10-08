"""`wl audit` (DL-13): the allowlist, the npm gate, and the network check."""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from waterline_cli import audit, main, steps

runner = CliRunner()

ENTRY = 'id = "GHSA-aaaa-bbbb-cccc"\nreason = "no fix yet"\ntech_debt = "TD-7"\n'


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "audit-allowlist.toml"
    path.write_text(text, encoding="utf-8")
    return path


# --- The allowlist ------------------------------------------------------------------------------


def test_allowlist_entries_are_read_per_ecosystem(tmp_path: Path) -> None:
    text = f"[[python]]\n{ENTRY}\n[[npm]]\n{ENTRY.replace('aaaa', 'dddd')}"

    allowlist = audit.load_allowlist(write(tmp_path, text))

    assert allowlist == audit.Allowlist(
        python=("GHSA-aaaa-bbbb-cccc",), npm=("GHSA-dddd-bbbb-cccc",)
    )


def test_an_allowlist_with_only_comments_ignores_nothing(tmp_path: Path) -> None:
    assert audit.load_allowlist(write(tmp_path, "# nothing\n")) == audit.Allowlist()


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('[[python]]\nid = "X"\nreason = "r"\n', "needs exactly id, reason, and tech_debt"),
        (f'[[python]]\n{ENTRY}extra = "x"\n', "needs exactly id, reason, and tech_debt"),
        ('[[npm]]\nid = "X"\nreason = " "\ntech_debt = "TD-1"\n', "must be non-empty text"),
        ('[[npm]]\nid = "X"\nreason = "r"\ntech_debt = 7\n', "must be non-empty text"),
        ('[[npm]]\nid = "X"\nreason = "r"\ntech_debt = "TD-x"\n', "must be a tech-debt ID"),
        ('[[npm]]\nid = "X"\nreason = "r"\ntech_debt = "see TD-1"\n', "must be a tech-debt ID"),
        (f"[[pip]]\n{ENTRY}", "unknown sections ['pip']"),
        ('python = "GHSA-x"\n', "[python] must be a list"),
        ("python = [1]\n", "needs exactly id, reason, and tech_debt"),
        ("[[python]\n", "audit-allowlist.toml: "),
    ],
)
def test_a_malformed_allowlist_is_an_error(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(audit.AllowlistError) as error:
        audit.load_allowlist(write(tmp_path, text))

    assert message in str(error.value)


def test_a_missing_allowlist_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(audit.AllowlistError, match=r"audit-allowlist\.toml"):
        audit.load_allowlist(tmp_path / "audit-allowlist.toml")


def test_python_advisories_are_ignored_in_both_uv_audits() -> None:
    ignores = audit.uv_ignores(audit.Allowlist(python=("GHSA-1", "PYSEC-2"), npm=("GHSA-3",)))

    assert [s.render() for s in steps.audit(ignores)][1:3] == [
        "uv audit --frozen --preview-features audit-command --ignore GHSA-1 --ignore PYSEC-2",
        "(cd backend && uv audit --frozen --preview-features audit-command --ignore GHSA-1 "
        "--ignore PYSEC-2)",
    ]


def test_wl_audit_stops_on_a_malformed_allowlist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write(tmp_path, '[[npm]]\nid = "X"\n')
    monkeypatch.setattr(main, "find_repo_root", lambda: tmp_path)

    result = runner.invoke(main.app, ["audit", "--dry-run"])

    assert result.exit_code == 1
    assert "needs exactly id, reason, and tech_debt" in result.output


# --- The npm gate -------------------------------------------------------------------------------


def advisory(ghsa: str, title: str = "bad", severity: str = "high") -> dict[str, Any]:
    return {
        "source": 1,
        "url": f"https://github.com/advisories/{ghsa}",
        "title": title,
        "severity": severity,
    }


REPORT: dict[str, Any] = {
    "vulnerabilities": {
        "braces": {"severity": "high", "via": [advisory("GHSA-b", "stack exhaustion")]},
        "micromatch": {"severity": "high", "via": ["braces"]},
        "source-map-js": {
            "severity": "moderate",
            "via": [advisory("GHSA-s", "event loop", "moderate")],
        },
    }
}


def test_every_advisory_outside_the_allowlist_is_reported() -> None:
    assert audit.npm_problems(REPORT, ()) == [
        "GHSA-b (high) in braces: stack exhaustion",
        "GHSA-s (moderate) in source-map-js: event loop",
    ]


def test_an_allowlisted_advisory_is_not_reported() -> None:
    assert audit.npm_problems(REPORT, ("GHSA-b",)) == [
        "GHSA-s (moderate) in source-map-js: event loop"
    ]


def test_a_clean_report_has_no_problems() -> None:
    assert audit.npm_problems({"vulnerabilities": {}}, ()) == []


def test_an_advisory_without_a_url_is_named_by_its_source() -> None:
    report = {"vulnerabilities": {"x": {"severity": "low", "via": [{"source": 42}]}}}

    assert audit.npm_problems(report, ()) == ["42 (low) in x: "]


def fake_npm(
    monkeypatch: pytest.MonkeyPatch, stdout: str, returncode: int = 0, stderr: str = ""
) -> list[list[str]]:
    calls: list[list[str]] = []

    def run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)

    monkeypatch.setattr(audit.subprocess, "run", run)
    return calls


def test_the_npm_gate_runs_npm_audit_as_json(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_npm(monkeypatch, json.dumps(REPORT), returncode=1)

    assert audit.run_npm_audit(Path("frontend")) == REPORT
    assert calls == [["npm", "audit", "--json"]]


@pytest.mark.parametrize(
    ("stdout", "returncode", "stderr"),
    [
        (json.dumps({"error": {"code": "ENOAUDIT"}}), 1, ""),
        ("", 1, "npm ERR! network"),
    ],
)
def test_npm_audit_failing_to_run_is_an_error(
    monkeypatch: pytest.MonkeyPatch, stdout: str, returncode: int, stderr: str
) -> None:
    fake_npm(monkeypatch, stdout, returncode, stderr)

    with pytest.raises(audit.AllowlistError, match="npm audit failed"):
        audit.run_npm_audit(Path("frontend"))


def test_npm_audit_with_no_json_and_success_is_a_clean_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_npm(monkeypatch, "", 0)

    assert audit.run_npm_audit(Path("frontend")) == {}


@pytest.mark.parametrize(
    ("allowlist", "code", "stderr"),
    [
        ("", 1, "GHSA-b (high) in braces: stack exhaustion\n"),
        (f"[[npm]]\n{ENTRY.replace('GHSA-aaaa-bbbb-cccc', 'GHSA-b')}", 0, ""),
    ],
)
def test_the_npm_gate_fails_on_advisories_outside_the_allowlist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    allowlist: str,
    code: int,
    stderr: str,
) -> None:
    write(tmp_path, allowlist)
    only_braces = {"vulnerabilities": {"braces": REPORT["vulnerabilities"]["braces"]}}
    fake_npm(monkeypatch, json.dumps(only_braces), returncode=1)

    assert audit.main(["npm"], root=tmp_path) == code
    assert capsys.readouterr().err.startswith(stderr)


def test_the_npm_gate_reports_a_malformed_allowlist(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path, "[[npm]]\n")

    assert audit.main(["npm"], root=tmp_path) == 1
    assert "needs exactly id, reason, and tech_debt" in capsys.readouterr().err


# --- The network check --------------------------------------------------------------------------


class Connection:
    closed = False

    def close(self) -> None:
        self.closed = True


def test_no_network_fails_with_a_clear_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse(_address: tuple[str, int], _timeout: float) -> audit.Closeable:
        raise OSError("Network is unreachable")

    monkeypatch.setattr(audit.socket, "create_connection", refuse)

    assert audit.main(["network"], root=tmp_path) == 1
    assert capsys.readouterr().err.startswith(
        "wl audit needs the network: can't reach api.osv.dev (Network is unreachable)."
    )


def test_the_network_check_reaches_every_service_and_closes_each_connection() -> None:
    reached: list[tuple[str, int]] = []
    connections: list[Connection] = []

    def connect(address: tuple[str, int], _timeout: float) -> audit.Closeable:
        reached.append(address)
        connections.append(Connection())
        return connections[-1]

    assert audit.network_problem(connect) is None
    assert reached == [("api.osv.dev", 443), ("registry.npmjs.org", 443), ("github.com", 443)]
    assert [c.closed for c in connections] == [True, True, True]


def test_the_network_subcommand_passes_when_online(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(audit, "network_problem", lambda: None)

    assert audit.main(["network"], root=tmp_path) == 0


def test_an_unknown_subcommand_prints_usage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert audit.main(["nope"], root=tmp_path) == 2
    assert "usage: python -m waterline_cli.audit network|npm" in capsys.readouterr().err
