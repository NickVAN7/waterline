# Review record: DC-2026-10-14 — faster checks (DL-99, DL-100)

- **Change:** `wl check` becomes the gate before every commit: lockfiles, client freshness, lint,
  types, import rules, tests, and coverage gates, plus mutation testing only when the backend's
  `app/`, `tests/`, `pyproject.toml`, or `uv.lock` changed since its last green run (a hash in
  `backend/mutants/inputs.sha256`). `wl check --full` adds mutation testing whatever changed,
  `wl audit`, and `wl e2e`; CI runs it, and `--skip-e2e` is gone (DL-99). The backend suite runs
  under pytest-xdist, `-n auto --maxprocesses 8`, each worker on its own database
  `waterline_test_gw<n>`; filtered runs and mutmut use `-n 0`; the 100% gate checks the
  controller's combined coverage (DL-100). Owner decisions, Oct 14, 2026.
- **Base commit:** `b71a73f` (`s1`, the S1-C14a checkpoint); the passes reviewed the uncommitted
  changes.
- **Reviewers:** `checkpoint-reviewer` (tooling code), then `docs-consistency` (trigger
  `design-change`). `security-reviewer` wasn't run: test and CLI tooling with nothing
  security-relevant (the worker database name comes from xdist's worker id, not input).
- **Timings** (local, 32 cores): backend tests 208 s serially; 84 s with 4 workers, 61 s with 8,
  64 s with 12. `wl check` 361 s before; `wl check` 101 s after (mutation testing skipped);
  `wl check --full` 219 s.

Severity: **blocker**: wrong behavior, security, data integrity, or a failing gate. **major**:
missing tests, a convention violation, or doc drift. **minor**: small issues worth fixing or
logging.

**Author's checks** (evidence, not verification), each in the working tree and restored:

| Behavior | Sabotage | Caught by |
|---|---|---|
| The hash is recorded only after a green run | the record moved before `run_steps` | `test_check_records_mutation_testing_as_green_only_when_it_passes[True-False]` |
| An unchanged hash skips mutation testing | the condition made `full or True` | `test_check_skips_mutation_testing_when_nothing_it_depends_on_changed` |
| The hash covers file contents | the content update removed | `test_a_change_to_any_input_makes_mutation_testing_run_again` (4 cases) |
| The controller checks combined coverage | the strict gate skipped when `PYTEST_XDIST_WORKER` is set | `test_a_run_below_100_percent_on_rules_fails`, `test_under_xdist_the_controller_checks_the_combined_data` |

The last one is how the first parallel run failed: a worker's `PYTEST_XDIST_WORKER` reaches a
pytest started in a subprocess, so a "skip on workers" check turned the gate off there. No
worker check was needed (a worker's failure count and output never reach the controller), so
the hook has none; the two-worker test proves the controller's check.

## checkpoint-reviewer, pass 1 (base `b71a73f`) — verdict: ready after fixes

| # | Severity | Area | Location | Finding | Resolution |
|---|---|---|---|---|---|
| 1 | major | correctness | `tools/cli/src/waterline_cli/mutation.py` | **What:** the skip's inputs left out `tests/factories/`, which the authz unit tests import (through `tests/support/authz.py`). **Problem:** a changed factory default could let a mutant survive while `wl check` skips the run. **Fix:** add it, or hash all of `tests/`. **If skipped:** a survivor found only by CI, after the push. | **Fixed:** the inputs are `app`, `tests`, `pyproject.toml`, `uv.lock`; the test edits a factory; DL-99, the testing strategy, and the developer guide list the same inputs. |
| 2 | minor | docs | `.claude/skills/checkpoint/SKILL.md` | **What:** one line of the "One reviewer at a time" bullet ran to about 140 characters. **Fix:** rewrap. | **Fixed.** |

**Sabotage checks** (reviewer, in a copy):

| Behavior | Source | Change made | Caught by |
|---|---|---|---|
| A failed mutation run is never recorded green | DL-99 | `_mutate_steps` records whatever `run_steps` does | `test_check_records_mutation_testing_as_green_only_when_it_passes[True-False]` |
| Each worker uses its own database | DL-100 | `test_database_url` always returns `waterline_test` | `test_tests_run_against_the_test_database` (under `-n 2`) |

**Questions raised:** none.

## checkpoint-reviewer, pass 2 (base `b71a73f`; the fixes) — verdict: ready

No findings. No copy this pass: the only new behavior is the input list, covered by the
`tests/factories/user.py` case.

| # | Severity | Area | Location | Finding | Resolution |
|---|---|---|---|---|---|
| 2.1 | note | correctness | `mutation.py` | The hash read only `.py` files, so a data file a test reads wouldn't trigger a re-run (none found). | **Fixed** by the author after the pass: every file except `__pycache__`, with `test_a_data_file_counts_but_python_bytecode_does_not`. A widening of the inputs, covered by its test, so no further pass. |

## docs-consistency (trigger `design-change`, base `b71a73f`)

| # | Kind | Where | Fix | Resolution |
|---|---|---|---|---|
| 1 | gap | root `CLAUDE.md`, "How work is done" | Nothing said to run `wl audit` before a checkpoint now that `wl check` leaves it out (DL-99). | **Fixed:** "run `uv run wl audit` before starting a checkpoint". |
| 2 | internal | `docs/developer-guide.md` §9 | "migrates the test database, `waterline_test`" beside the per-worker databases. | **Fixed:** each worker migrates its own; `waterline_test` under `-n 0`. |
| 3 | superseded | `docs/testing-strategy.md`, "Database isolation" | "The test database is migrated once per session". | **Fixed:** each test database (one per worker). |
| 4 | stale | `backend/CLAUDE.md`; `docs/build-plan.md` (Slice 1 notes) | Mutation testing "in `wl check`" unconditionally. | **Fixed** in both; the S1-C3 checkpoint row is history and stays. |
| 5 | stale | `.claude/agents/fresh-clone-verifier.md` | Its example setup check was `wl check`; the guide's is `wl check --full`. | **Fixed.** |

**Decision for the owner (open):** which `wl check` level a *future* gate joins (e.g. the token
contrast check once ported, ui-design-guide §9). (a) Every gate goes in `wl check` unless it
needs the network or a running stack: one rule, but `wl check` grows. (b) Decided per gate:
each needs its own doc line, and drift is likelier.

## Open questions for the owner

- The docs-consistency decision above.
