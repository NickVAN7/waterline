# Review record: DC-2026-11-18c — Parallel reviewers, parallel CI, a test timeout (Package 2)

- **Change:** the outside review's Package 2
  (`docs/reviews/design-changes/2026-11-18-outside-review-handoff.md`), recorded as **DL-392**.
  Tooling, test code, and docs; no app code.
  - **2a:** the tests' own settings read `WATERLINE_TEST_DATABASE` (default `waterline_test`,
    nothing else allowed); `wl review-copy --with-env` gives a copy `waterline_test_<8 hex>`;
    `wl discard-copy` drops the copy's databases (`backend/tests/support/review_databases.py`)
    and deletes it; reviewers run in one parallel step.
  - **2b:** CI as five parallel jobs and a last `wl check` job; `wl cli check` added; a CLI test
    keeps the jobs equal to `wl check --full`.
  - **2c:** `pytest-timeout` (MIT, 2.4.0), `timeout = 120`; `wl check`'s mutation run passed with
    it (all 658 mutants killed).
- **Owner decision during the change** (Nov 18, 2026): the test database's name is read by the
  tests, not by `backend/app/core/settings.py`, so 2a needs no checkpoint row.
- **Deviations from the handoff, named for the owner:**
  - `docker-compose.yml`'s Postgres allows 300 connections (default 100): two full suites at once
    ran out ("too many clients already"); without it the "Done when" fails.
  - `fresh-clone-verifier` and `user-guide-verifier` still follow the other reviewers, with the
    dev stack down: they start stacks of their own. The other slice-end agents join the
    parallel step.
  - Two test fixes the parallel runs needed: a copy's own base database is created (if missing)
    and migrated by the run's controller, so tests that read it directly and runs started from
    tests (pytester) find it ready; `test_health`'s connection kill is limited to its own
    database, as another copy's run uses the same application name.
- **Done when** (two review copies running the backend suite at the same time, both passing):
  met on the author's run (7,578 passed each, after the fixes above), and verified by
  `checkpoint-reviewer` on two copies of its own (7,578 passed each, 3 m 11 s).
- **Kind:** tooling (`chore:`/`ci:`), with `checkpoint-reviewer` (DL-18).
- **Base commit:** `06f39b4` (DC-2026-11-18b).
- **Reviewers:** `checkpoint-reviewer` and `docs-consistency` (trigger `design-change`), in
  parallel on one snapshot (DL-105, DL-392); `checkpoint-reviewer` re-reviewed the fix diff (a
  blocker fixed).
- **Totals:** checkpoint-reviewer pass 1 ready after fixes, 1 blocker, 1 major, 1 minor;
  pass 2 ready, 1 minor (fixed); docs-consistency 12 fixes, all applied, no decisions.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## checkpoint-reviewer, pass 1 (base `06f39b4`)

Verdict: ready after fixes.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | blocker | correctness | CI's `e2e` job had no `POSTGRES_*` settings (they sat on the `backend` job only), and `docker-compose.yml` requires them: `docker compose … config` with an empty environment exits 1, so `wl e2e` and the required check would fail on the first push. | **Fixed:** the `env:` block moved to the workflow level, for every job. Siblings: no other job runs Compose. |
| 2 | major | tests | Nothing tested that the last `wl check` job fails when another does: deleting `if: always()` passed all 105 command tests, and a job dropped from `needs:` would too. | **Fixed:** `test_the_required_ci_check_fails_when_any_job_does` asserts the job's name, its full `needs:`, `if: always()`, and the all-success test. |
| 3 | minor | correctness | `drop` removed `<name>` and `<name>_gw%` only, so a scratch database a killed `-n 0` run left (`<name>_scratch_<hex>`) survived `wl discard-copy`. | **Fixed:** everything named `<name>_…` (still bounded by the copy's unique name); the test's copies include a scratch one. |

**Sabotage checks** (in copies of its own, its table):

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| Only `waterline_test` or `waterline_test_<suffix>` | 2a, DL-392 | `re.fullmatch` to `re.match` | `tests/unit/test_test_database_name.py` | `test_any_other_name_is_refused[waterline_test_]`, `[waterline_test_A1]` |
| `drop` touches only a copy's name | 2a | the `{8}` in `COPY` to `*` | `tests/integration/test_review_databases.py` | `test_only_a_copys_name_is_dropped[waterline_test_ab]` |
| `wl check` fails when a job fails | 2b | `if: always()` deleted | `tools/cli/tests/test_commands.py` | nothing (finding 2, fixed) |

## docs-consistency, pass 1 (base `06f39b4`)

| # | Kind | Finding | Resolution |
|---|---|---|---|
| 1 | superseded | `security-reviewer` ran tests in the working tree. | **Fixed:** only in a `--with-env` copy of its own, discarded after. |
| 2 | superseded | `repo-auditor`: "after docs-consistency", and "the test database" as its reason to run no tests. | **Fixed:** in the same step; a read-only audit (DL-41). |
| 3 | superseded | `simplicity-auditor`: "after repo-auditor". | **Fixed:** in the same step. |
| 4 | internal | The guide's §11 still listed the slice-end agents as one sequence. | **Fixed:** the three beside the reviewers, then the two verifiers with the stack down. |
| 5 | internal | The `checkpoint` skill's slice-end bullets said "as the reviewers above", which took in the two verifiers. | **Fixed:** "in the parallel step with the reviewers (not after the two verifiers)". |
| 6 | superseded | The build plan's "End of each slice" put them in sequence. | **Fixed:** in parallel; the verifiers after, with the stack down. |
| 7 | stale | The guide's §9: "one full `pytest` at a time against a stack". | **Fixed:** per test database; a copy's own, dropped by `wl discard-copy`. |
| 8 | stale | The guide's §10 described CI as one job. | **Fixed:** the five jobs, the last `wl check`, the CLI test. |
| 9 | stale | Testing strategy and build plan: "CI calls `wl check --full`". | **Fixed:** its parts as parallel jobs, kept equal by a CLI test. |
| 10 | gap | The build plan's CLI table lacked `wl discard-copy` and `wl cli check`. | **Fixed.** |
| 11 | gap | DL-392 and the build plan's Compose section didn't name `max_connections`. | **Fixed:** both; named to the owner as beyond the handoff. |
| 12 | stale | `backend/CLAUDE.md`'s allowed test databases. | **Fixed:** `WATERLINE_TEST_DATABASE` added. |

## checkpoint-reviewer, pass 2 (the fix diff)

Verdict: ready. Every pass-1 resolution and docs-consistency fix checked against the fix diff;
the workflow-level `env:` changes no other job (the backend container sets its own host).

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | minor | docs | `wl discard-copy`'s message and the guide's §9 named only the workers' copies, though `drop` now removes every database named after the copy. | **Fixed** (no third pass, DL-105): "every database named after it" in both. |

**Sabotage checks:** `\_%` back to `\_gw%` failed both drop tests; `audit` removed from
`needs:` failed `test_the_required_ci_check_fails_when_any_job_does`. The reviewer dropped the
two scratch databases its failing run left, then discarded its copy.
