"""The mutation-testing gate (testing-strategy.md, "Mutation testing"): no surviving mutants in
`app/rules/` and `app/authz/`. mutmut itself exits 0 whatever survives, so `wl backend mutate`
runs this after it:

    python -m tests.support.mutation_gate clean   # before `mutmut run`: no stale results
    python -m tests.support.mutation_gate check   # after `mutmut export-cicd-stats`
"""

import json
import shutil
import sys
from pathlib import Path

MUTANTS = Path("mutants")
STATS = MUTANTS / "mutmut-cicd-stats.json"

# Every outcome except "killed" fails the gate: a survivor, a mutant no test ran, a timeout, a
# crash, or an interrupted run all mean a change to the code could go unnoticed.
NOT_KILLED = (
    "survived",
    "no_tests",
    "timeout",
    "suspicious",
    "skipped",
    "segfault",
    "check_was_interrupted_by_user",
)


def problems(stats: dict[str, int]) -> list[str]:
    """What fails the gate in mutmut's exported counts; empty only when every mutant was killed.

    Fails closed: the gate requires `killed == total`, so an outcome the export doesn't list
    (mutmut 3.8 leaves out `not_checked` and `caught_by_type_check` but counts them in `total`)
    fails too, reported as unaccounted for."""
    total = stats.get("total", 0)
    if total == 0:
        return ["no mutants were generated (is the mutmut configuration right?)"]
    found = [f"{stats[outcome]} {outcome}" for outcome in NOT_KILLED if stats.get(outcome, 0)]
    listed = sum(stats.get(outcome, 0) for outcome in NOT_KILLED)
    unaccounted = total - stats.get("killed", 0) - listed
    if unaccounted:
        found.append(f"{unaccounted} not killed and not reported by outcome")
    return found


def main(argv: list[str]) -> int:
    match argv:
        case ["clean"]:
            shutil.rmtree(MUTANTS, ignore_errors=True)
            return 0
        case ["check"]:
            stats: dict[str, int] = json.loads(STATS.read_text())
            found = problems(stats)
            if found:
                sys.stderr.write(
                    f"Mutation testing failed: {', '.join(found)} of {stats['total']} mutants.\n"
                    "List them with `uv run mutmut results`, inspect one with "
                    "`uv run mutmut show <name>`, and kill each with a new or sharper test "
                    '(testing-strategy.md, "Mutation testing").\n'
                )
                return 1
            sys.stdout.write(f"Mutation testing: all {stats['total']} mutants killed.\n")
            return 0
        case _:
            sys.stderr.write("usage: python -m tests.support.mutation_gate clean|check\n")
            return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
