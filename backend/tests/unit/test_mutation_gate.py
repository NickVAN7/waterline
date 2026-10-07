"""The mutation-testing gate (tests/support/mutation_gate.py): mutmut exits 0 whatever
survives, so this is what makes a surviving mutant fail `wl check`."""

import json
from pathlib import Path

import pytest

from tests.support.mutation_gate import main, problems

ALL_KILLED = {
    "killed": 84,
    "survived": 0,
    "total": 84,
    "no_tests": 0,
    "skipped": 0,
    "suspicious": 0,
    "timeout": 0,
    "check_was_interrupted_by_user": 0,
    "segfault": 0,
}


def test_every_mutant_killed_passes() -> None:
    assert problems(ALL_KILLED) == []


@pytest.mark.parametrize(
    "outcome",
    [
        "survived",
        "no_tests",
        "timeout",
        "suspicious",
        "skipped",
        "segfault",
        "check_was_interrupted_by_user",
    ],
)
def test_any_reported_mutant_not_killed_fails(outcome: str) -> None:
    assert problems({**ALL_KILLED, "killed": 83, outcome: 1}) == [f"1 {outcome}"]


def test_a_mutant_counted_in_the_total_but_not_reported_fails() -> None:
    # mutmut 3.8 exports no count for not_checked or caught_by_type_check, but totals them.
    assert problems({**ALL_KILLED, "killed": 83}) == ["1 not killed and not reported by outcome"]


def test_a_run_with_no_mutants_fails() -> None:
    assert problems({"killed": 0, "total": 0}) == [
        "no mutants were generated (is the mutmut configuration right?)"
    ]


@pytest.fixture
def in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def write_stats(stats: dict[str, int]) -> None:
    Path("mutants").mkdir(exist_ok=True)
    Path("mutants/mutmut-cicd-stats.json").write_text(json.dumps(stats))


def test_check_exits_0_when_all_killed(in_tmp: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_stats(ALL_KILLED)

    assert main(["check"]) == 0
    assert "all 84 mutants killed" in capsys.readouterr().out


def test_check_exits_1_on_a_survivor(in_tmp: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_stats({**ALL_KILLED, "killed": 83, "survived": 1})

    assert main(["check"]) == 1
    assert "1 survived of 84 mutants" in capsys.readouterr().err


def test_clean_removes_previous_results(in_tmp: Path) -> None:
    write_stats(ALL_KILLED)

    assert main(["clean"]) == 0
    assert not (in_tmp / "mutants").exists()


def test_clean_with_nothing_to_remove_succeeds(in_tmp: Path) -> None:
    assert main(["clean"]) == 0


def test_unknown_arguments_are_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run"]) == 2
    assert "usage" in capsys.readouterr().err
