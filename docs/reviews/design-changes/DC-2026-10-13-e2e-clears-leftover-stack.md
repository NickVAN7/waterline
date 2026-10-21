# Review record: DC-2026-10-13 — `wl e2e` clears a leftover stack before starting

- **Change:** `wl e2e` (and so `wl check`) runs `down --volumes` on the `waterline-e2e` project
  before `up`, reusing `e2e_down()`. A stack an earlier run left behind (its teardown
  interrupted, or a manual demo run) kept a database that made `seed --demo` refuse with "A
  workspace already exists". The teardown after the run is unchanged (DL-65). Owner request
  (Oct 13, 2026); no recorded rule changes, so no decision-log entry. The developer guide's
  `wl e2e` row says so.
- **Base commit:** `70cf484` (`s1`); the pass reviewed the uncommitted changes.
- **Reviewers:** `checkpoint-reviewer`. `security-reviewer` wasn't run: CLI tooling with nothing
  security-relevant.

Severity: **blocker**: wrong behavior, security, data integrity, or a failing gate. **major**:
missing tests, a convention violation, or doc drift. **minor**: small issues worth fixing or
logging.

**Author's checks** (evidence, not verification): the leading `*e2e_down(),` removed from
`steps.e2e()`; four tests failed (`test_dry_run_prints_underlying_commands[check]`, `[e2e]`,
`[e2e-pass-through]`, `test_e2e_tears_the_stack_down_when_a_step_fails`); restored.

## checkpoint-reviewer, pass 1 (base `70cf484`) — verdict: ready after fixes

| # | Severity | Area | Location | Finding | Resolution |
|---|---|---|---|---|---|
| 1 | minor | docs | `docs/developer-guide.md` (the `wl e2e` row) | **What:** the row said a second run "shares the project and the first to finish tears it down". **Problem:** the second run's first step now removes the first run's stack at once, so the first fails partway. **Fix:** say so. **If skipped:** confusing failures when two runs overlap. | **Fixed:** "a second run shares the project, and its first step clears the first run's stack". (docs-consistency raised the same fix.) |

**Sabotage checks** (reviewer, in a copy):

| Behavior | Change made | Caught by |
|---|---|---|
| A leftover stack is cleared before `up` | the leading `*e2e_down(),` deleted | the three e2e dry-run cases and `test_e2e_tears_the_stack_down_when_a_step_fails` |
| The clear removes the volume too | a leading `down` without `--volumes` (an over-broad edit also broke unrelated tests, so a weak signal; the e2e tests compare exact commands) | the same four tests |

It also checked that `down --volumes` on a project that doesn't exist exits 0 (a clean machine
or CI runner), and that with Docker down the leading step fails and the `finally` teardown fails
the same way, harmlessly.

**Questions raised:** whether a tooling fix that changes no recorded rule needs a decision-log
entry. *Answered: no; DL-65 still holds, and this adds a step before `up`.*
