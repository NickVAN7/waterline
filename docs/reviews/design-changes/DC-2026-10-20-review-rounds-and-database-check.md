# Review record: DC-2026-10-20 — review rounds (DL-105, DL-106) and the database check (DL-107)

- **Change:** DL-105 to DL-107, applied mid-group (after S1-C15a, before S1-C16) at the
  owner's request; docs and code in one commit, at the owner's request (recorded in DL-107)
- **Base commit:** `cd712fe` (the S1-C15a checkpoint commit)
- **Reviewers:** `checkpoint-reviewer` (the tooling code, DL-18), then `docs-consistency`
  (trigger `design-change`), both on the same snapshot, the first change reviewed under DL-105
- **Totals:** 7 findings (all minor): 6 fixed, 1 rejected; 4 decisions for the owner and 1
  question, 1 decision settled by the review itself. No re-review: no finding was major
  (DL-105).
- **Gates at close:** `uv run wl check` green (mutation testing ran: all 413 mutants killed);
  CI on the commit.

---

## Tests added (sabotage-checked)

| Behavior | Source | Sabotage | Caught by |
|---|---|---|---|
| A distributed run without Postgres stops with the database message, no INTERNALERROR | DL-107 | the check returns at once | `test_a_distributed_run_without_postgres_stops_with_the_database_message` |
| A `-n 0` run of tests that need no database runs without Postgres | DL-107 | the check on every run | `test_a_serial_run_of_tests_that_need_no_database_still_runs_without_postgres` |
| `--collect-only` works without Postgres | review finding 1 | the collect-only skip dropped | `test_collecting_tests_still_works_without_postgres` |

The worker half of the condition (`workerinput`) can't change an outcome: workers start only
after the controller's check has passed. It saves their probes.

## checkpoint-reviewer, pass 1 (base `cd712fe`) — verdict: ready after fixes

| # | Severity | Area | Location | Finding | Resolution |
|---|---|---|---|---|---|
| 1 | minor | correctness | `backend/tests/conftest.py` | **What:** `--collect-only` counts as distributed (`-n auto` in addopts), but xdist starts no workers for it. **Problem:** with Postgres down, test discovery fails with the database message (reproduced). **Fix:** skip on `collectonly`. **If skipped:** an editor's test discovery breaks with the stack down. | **Fixed:** skipped; a test. |
| 2 | minor | lean | `backend/tests/conftest.py` | **What:** the controller condition copies `xdist.is_xdist_controller`. **Fix:** import it. | **Rejected:** `xdist` ships no type stubs, so the import fails pyright (`reportMissingTypeStubs`, seen in this change's first `wl check`); the comment now says why it's inlined. |
| 3 | minor | correctness | `.claude/skills/checkpoint/SKILL.md` | **What:** each review copy is a clone with its own `.git`, so `diff -ruN` shows git's files; `review-copy` refuses a non-empty directory, so fixed paths fail a second time in a session. **Fix:** `-x .git`; a new directory each time. | **Fixed:** `-x .git` in the skill, DL-105, and the three agents; copies in a new `mktemp -d` directory. |
| 4 | minor | docs | `.claude/skills/checkpoint/SKILL.md` | **What:** a full `wl check` before the first reviewer, right after step 2's, which DL-106 doesn't record. | **Fixed:** rerun only if the self-review changed anything. |

**Sabotage checks:** the exit replaced with `pass` → caught; the check run serially too →
caught.

**Question:** does "fix nothing until every reviewer has reported" include the slice-end agents
(`fresh-clone-verifier`, `docs-consistency`, `repo-auditor`)? *For the owner, below.*

## docs-consistency (trigger `design-change`, base `cd712fe`)

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| F1 | gap | `.claude/skills/design-change/SKILL.md`, step 7 | The tooling review never takes the snapshot DL-105's re-review needs. | **Fixed:** step 7 takes it as the `checkpoint` skill's step 4 says. |
| F2 | broken-ref | `.claude/skills/checkpoint/SKILL.md` | "the frontend's and backend's 'easy to break' lists": `frontend/CLAUDE.md` has no such list. | **Fixed:** the real sections named. |
| F3 | broken-ref | root `CLAUDE.md` | "(the `checkpoint` skill, step 5)": the snapshot and self-review are in step 4. | **Fixed:** "steps 4 and 5". |

**Decisions** (for the owner, undecided except D1):

| # | Question | Options |
|---|---|---|
| D1 | Does the `conftest.py` change need a tooling review? | Settled by (a): `checkpoint-reviewer` reviewed it under this ID (above). |
| D2 | Which reviewers can be re-reviewed, and how? `repo-auditor` and `fresh-clone-verifier` have no re-review section; `docs-consistency` reports no severities. | (a) only the three code reviewers; (b) add sections to the other two; (c) another trigger for agents without severities |
| D3 | Does a `checkpoint-reviewer` re-review still sabotage-check? | (a) one behavior the fix changed; (b) none; (c) only when the fixed finding was a test that couldn't fail |
| D4 | The fix diff includes each clone's `.git`. | Settled with finding 3 (option a, `-x .git`). |

## Open questions for the owner

- D2 and D3 above, and the reviewer's question on the slice-end agents; they matter from the
  first re-review (S1-C16 at the earliest) and at S1-C17.
- Not checked by either reviewer: a database host that drops connections silently rather than
  refusing them; the probe has no connect timeout (nor had the fixture before it).

## Owner decisions made during review

- None during review. Before it: the decisions themselves (DL-105 to DL-107, Oct 20, 2026), and
  one commit for docs and code.
