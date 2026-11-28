# Review record: S3-C0s — Backend robustness

- **Checkpoint:** Slice 3, Checkpoint 0s (group `s3-polish`; the handoff's Package 4 items 2, 3
  and 4, DL-400)
- **Base commit:** `05bb688` (the design change regrouping Package 4, the last commit before this
  one; DL-17)
- **Reviewers:** `checkpoint-reviewer` and `security-reviewer` (the build plan names S3-C0s: the
  error handlers' new 503), in parallel on one snapshot (DL-105, DL-392). No `ui-reviewer`: the
  diff doesn't touch `frontend/`. No re-review: both major findings' fixes are tests only (the
  `checkpoint` skill, step 5).
- **Totals:** checkpoint-reviewer ready after fixes, 2 major, 1 minor, all fixed;
  security-reviewer ready, no findings.
- **Gates at close:** `wl check` green, mutation testing included; CI's `wl check --full` on the
  pushed commit.

---

## Before the reviewers

- **Item 3, the untested lock: removed, with a test that fails with it.** The first attempt
  sought an interleaving that leaves no owner without the guard's second `lock_owners`: two
  demotions waiting on Ann's lock while she hands over, then a second owner made. It can't
  happen: Postgres keeps a `FOR UPDATE` lock on a row it re-checked and found no longer matching
  (the trace: the second demotion timed out "while locking updated version of tuple" behind the
  first), so `_member`'s first lock already queues every owner change, and every path that
  changes or counts owners takes it (change, removal, add, deactivation). The second lock instead
  deadlocks: Dee's demotion waits on the owners while Ann hands over to Bob, then Bob steps down,
  locking his row and waiting on Dee's, and the guard's second lock waits on Bob's
  (`DeadlockDetected`, observed). Without it, Dee's demotion commits and Bob's is refused as the
  last owner. The handoff's other outcome (keep the lock, with a test failing without it) had no
  interleaving to test; the line and its comment are removed, as the commit message says.
- **Drift fix (DL-362):** the row said TD-83 "kept open for Slice 6a", from the handoff; no
  Slice 6a exists, and TD-83's Fix by is Slice 7. The row now says so.
- **The session's self-review** (DL-106) against `backend/CLAUDE.md`'s rules and concurrency
  policy: no change. The race test pauses a repository read by patching it, the "steps by hand"
  form a test of lock order takes.

## checkpoint-reviewer, pass 1

**Verdict:** ready after fixes.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | major · tests | `test_wiring.py` imports only `app.services.wiring`; nothing checks an entry point loads it. With the import removed from each, `app.main` and `app.cli` still had all five handlers (their routers and services reach every area), but `app.jobs.worker` had four of five empty: the one process the change fixes is the one no test covers. | **Fixed:** the test is parametrized over `app.services.wiring`, `app.jobs.worker`, `app.cli`, and `app.main`, the same five-registry assertion. Sabotage: the worker's import removed fails `[app.jobs.worker]`. Siblings: no other entry point imports services (`app/demo.py` runs only through the CLI). |
| 2 | major · tests | The new race test had a `for` loop (its setup), an `if` in the patched read, an `if pause:`, and an `if … commit` in its transaction. | **Fixed:** the setup is three explicit factory calls; the pause is `PausedMembershipLocks` and "commit unless refused" is `attempt`, both in `tests/support/concurrency.py` beside `refusal` and `failure`; the test has two transaction functions, `demote_dee` (paused) and `demote_bob`. Siblings: no other test in the concurrency files branches. |
| 3 | minor · docs | The file's docstring says every test is sabotage-checked without its row locks; the new one fails with a lock restored. | **Fixed:** the docstring names the last test's check, the guard's second lock restored. |

### Sabotage checks

| Behavior | Change made (in its copy) | Caught by |
|---|---|---|
| The guard doesn't lock the owners again, so the race doesn't deadlock | The second `lock_owners` restored | `test_a_demotion_racing_a_new_owners_step_down_neither_deadlocks_nor_leaves_none` (Bob's outcome a deadlock, not `last_owner`) |
| Only `40P01` is a retryable 503; any other database error stays a 500 | The condition made `sqlstate is None` | `test_another_database_error_is_still_a_500` |
| Importing the wiring alone fills every registry | `requirement` removed from `wiring.py` | `test_importing_the_wiring_alone_fills_every_handler_registry` |

The session repeated the first after the fix batch (the rewritten test fails with the lock
restored) and the wiring's for the worker (finding 1).

**Question raised:** the handoff asks that the removal be said in the commit message: it is.

## security-reviewer, pass 1

**Verdict:** ready. No findings, no questions. Traced every path that lowers the owner count
(`change_role` and `remove` through `_member`'s lock; deactivation, `auth.py`; adding an owner,
`roster.py:232`) and found no interleaving in which two changes pass the guard and leave no
active owner. The wiring guarantees `auth`'s `on_email_changed` handler in every process (an
email change ends the user's sessions, also in a job). The deadlock handler maps only `40P01`,
its body generic, its log line the method and path only; any other error the standard 500.

It couldn't run tests: its review copy stopped at startup on a missing `postgres_db`. The session
checked `wl review-copy --with-env`: its copy has the `.env` and runs the tests, so the copy was
most likely made without `--with-env`, which the prompt to this reviewer didn't name (the
checkpoint reviewer's did). Its review rests on reading; the tests are verified by `wl check` and
the checkpoint reviewer's runs.

## Open questions for the owner

None.
