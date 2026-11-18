# The outside review's handoff (2026-11-18)

The owner's decisions after an outside review of branch `s3` at `d2a5e32`, handed off from a
chat session as written below, all approved. Their place in Slice 3's order: Packages 1 to 3
before S3-C0p, Packages 4 and 5 as rows after it (S3-C0q onward), ahead of S3-C1 (DL-390). Each
package is applied one at a time, each with its own decision-log entry, and stops for the owner.

---

You are applying a set of decisions the owner (Nick) made after an outside review of this repository. The review read branch `s3` at commit `d2a5e32`. Every decision below is already approved. Your job is to carry them out exactly, one work package at a time.

## Ground rules

1. **Verify before you change.** File paths and line numbers are from `d2a5e32`. Find each target by the quoted text, not the line number. If a quoted text is not there, or the code already does what a step asks, stop and tell the owner instead of improvising.
2. **One work package at a time, in the order given.** Finish a package, report, and wait for the owner before starting the next. Do not combine packages.
3. **Follow the repository's own process as it stands when you start each package.** Changes to docs, `.claude/`, `tools/` and CI go through the `design-change` skill. Changes to `backend/app/` and `frontend/src/` are checkpoints: propose each as an inserted row in `docs/build-plan.md` using the letter-suffix convention, and get the owner's approval of the row before building it.
4. **Record one decision-log entry per work package**, naming every earlier decision it supersedes. Do not write one entry per bullet.
5. **The current git guard stays in force until Package 1 lands.** Work within it until then.
6. **Smallest complete change.** No package adds anything not listed in it. If you find something else worth changing, add it to `docs/tech-debt.md` or raise it.
7. **Owner-only steps** are marked. Do not attempt them; list them in your report.

## Package 1: replace the git guard with a small allow-list

**Now:** `.claude/hooks/guard_git.py` is 1,298 lines, with a hand-written shell tokenizer, flag-level allow-lists for read-only commands, and a block on any Bash call whose text mentions git. `tools/cli/tests/hooks/test_guard_git.py` is 1,377 lines. The trial log (`docs/spikes/S3-C0b-guard-trial/friction-log.md`) has 37 blocks, none of which stopped a forbidden outcome.

**Change to:** a new `guard_git.py` of roughly 150 lines or fewer, using `shlex` from the standard library and no tokenizer of its own. Its docstring states its scope in these words: "Stops the direct form of a forbidden git or gh command and keeps git usage to one plain command per call. Evasion (scripts, `bash -c`, redirects) is out of scope: GitHub's rulesets (DL-27), CI, and the `wl check` repository-state step cover it."

Behaviour:

1. **Trigger only when git or gh is the program being run.** If the first word of the command is not `git` or `gh`, and neither appears as a command word after `&&`, `||`, `;`, `|`, `$(`, a backtick, `bash -c`, `sh -c`, `eval`, `xargs` or `env`, exit 0. Text that merely contains "git" (paths, heredoc bodies, `diff -x .git`, doc edits) is not inspected.
2. **One git command per call.** If git or gh appears after any of those operators or wrappers, or a direct git/gh command contains an operator, a substitution or a redirect, block with the existing `ONE_COMMAND` message. The single exception stays: a quoted heredoc for `git commit -F - <<'EOF'`.
3. **Allow by subcommand, not by flag.**
   - Read-only, any flags: `status`, `log`, `diff`, `show`, `blame`, `reflog`, `ls-files`, `ls-tree`, `rev-parse`, `rev-list`, `describe`, `grep`, `cat-file`, `shortlog`, `merge-base`, `for-each-ref`, `show-ref`, `check-ignore`, `fetch`, `remote` (with no arguments or `-v`), `branch` in its listing forms, `stash list`, `stash show`, `config --get` and `config --list`.
   - Everyday writes: `add`, `rm`, `mv`, `restore`, `commit`, `switch`, `checkout <one-branch-name>` with no flags, `branch <new-name>`, `stash push`, `stash pop`, `stash apply`, `push`, `pull` (plain or `--ff-only`).
   - Refused inside those writes: `commit --no-verify` or `-n`; any commit while the current branch is `main`; `commit --amend` when `HEAD` is already on a remote branch; `push` with `--force`, `-f`, `--force-with-lease`, `--force-if-includes`, `--delete`, `-d`, `--mirror`, `--no-verify`, a refspec containing `:` or `+`, or `main` as the target; any `config` write; `branch -d`, `-D`, `-m`, `-f`.
   - Everything else is blocked with "ask the owner to run it": `reset` in every form, `rebase`, `merge`, `cherry-pick`, `revert`, `am`, `clean`, `filter-branch`, `worktree`, `update-ref`, `tag`, `submodule`, and any subcommand not listed.
   - `gh`: carry over the current `GH_ALLOWED` set unchanged and add `("run", "rerun")`. `gh api` stays read-only. `gh pr merge` and API writes keep today's "ask the owner" decision (`OWNER_DECIDES`).
   - If today's guard allows a git form this list would block, list those forms in your report and ask before dropping them.
4. **Tests:** replace the test file with a table of `(command, expected verdict)` cases plus a temporary-repository fixture for the three state-dependent rules (commit on `main`, amend of a pushed commit, push to `main`). Include each of the 37 friction-log commands whose shape is recorded, with the verdict the new rules give.

Add a **repository-state step to `wl check`** (extend the existing hook check in `tools/cli/src/waterline_cli/doctor.py`, `_hooks`): fail when `core.hooksPath` is set, when the pre-commit hook file is missing or is not pre-commit's, or when the current branch is `main` (skip the branch test when `CI` is set). This replaces the guard's evasion coverage by checking the result.

Update every reference: root `CLAUDE.md` (the "Hooks block edits…" paragraph, including the sentence that requires logging every block in the friction log, which is removed); developer guide section 11; build plan ("Claude configuration"); the `checkpoint` skill; `checkpoint-reviewer` and `fresh-clone-verifier`; the docstring of `tools/cli/src/waterline_cli/review_copy.py`; and TD-20 ("What the git guard can't see"), which is resolved as accepted by the guard's stated scope. Close the trial in the friction log with the verdict "replaced by the small allow-list". The new decision supersedes DL-26.

**Done when:** `uv run wl check` is green, the guard is under 150 lines, and a Bash call that only mentions git in text runs without a block.

## Package 2: faster verification

### 2a. Reviewers run in parallel

**Now:** `backend/app/core/settings.py` has `TEST_DATABASE_NAME = "waterline_test"`, and `backend/tests/conftest.py` asserts tests only run against that name. The `checkpoint` skill, step 4, has a bullet beginning "**One reviewer at a time:**" because two runs collide on the shared test databases.

**Change to:**
- The test database base name comes from an environment variable, `WATERLINE_TEST_DATABASE`, defaulting to `waterline_test`. It must match `^waterline_test(_[a-z0-9]+)?$`; the conftest assertion becomes that check. The conftest creates the base database when it is not the default one, the same way it already recreates the per-worker copies.
- `wl review-copy <dest> --with-env` writes a unique `WATERLINE_TEST_DATABASE=waterline_test_<8 hex chars>` into the copy's `.env`. Add a way to drop a copy's databases (base and per-worker) when the copy is discarded.
- Replace the "One reviewer at a time" bullet with: every reviewer that runs tests does so only inside its own review copy; the applicable reviewers are invoked in parallel in one step; the author may run tests in the working tree while they run. Apply the same to the slice-end agents.
- Update root `CLAUDE.md` ("Skills, agents, and hooks": the `checkpoint` bullet says "then … then … then") and the agents' own instructions to match.

**Done when:** two review copies run the backend suite at the same time and both pass.

### 2b. CI in parallel jobs

**Now:** `.github/workflows/ci.yml` has one job, `check`, named `wl check`, with `timeout-minutes: 30`, that runs `uv run wl check --full`.

**Change to:** separate jobs for the backend (`uv run wl backend check`, with mutation testing forced as `--full` does today), the frontend (`uv run wl frontend check`), the developer CLI's own checks, the supply-chain audit, and the end-to-end tests. Each job sets up only what it needs. Add a final job named exactly `wl check` that `needs` all of them, runs with `if: always()`, and fails unless every one succeeded, so the ruleset's required status check (DL-27) keeps working with no change on GitHub. Add CLI subcommands for any group that has none. `uv run wl check --full` remains the local definition; add a CLI test asserting that the commands the CI jobs run cover exactly the step groups of `wl check --full`, so DL-99 stays mechanically true.

### 2c. Test timeout

**Now:** no per-test or per-query timeout. A planted cycle bug made `tests/api/test_requirement_move.py::test_a_move_under_itself_or_a_descendant_is_a_cycle[itself]` hang for 20 minutes instead of failing.

**Change to:** add `pytest-timeout` (MIT; confirm and record the license as root `CLAUDE.md` requires) to the backend dev dependencies and set `timeout = 120` under `[tool.pytest.ini_options]` in `backend/pyproject.toml`. Confirm the mutation run still passes with it.

## Package 3: process rules

Each item names the text to change and what it becomes.

1. **Concurrency policy.** Add a section "Concurrency policy" to `backend/CLAUDE.md`:
   "Locks are for data invariants only: numbering, rank, revision numbers, tree cycles, the last owner of a roster, and one pending approval request per item. Authorization uses the context loaded at the start of the request. A permission that changes while a request is in flight does not stop that request; the next request is denied. Do not add a lock or a hold to close an authorization-freshness window. Existing holds stay until a checkpoint touches that code."
   Add to `checkpoint-reviewer` (beside its "Scale" item) and to `security-reviewer`: "Not a finding: an authorization-freshness race the concurrency policy in `backend/CLAUDE.md` accepts." Mark TD-31 as accepted by this policy.
2. **Scope line for protective mechanisms.** Add to root `CLAUDE.md`, "Always": "Every protective mechanism (a hook, a guard, a lock, a validation layer) states in one line what it defends against and what is out of scope. Reviewers judge it against that line and do not raise out-of-scope holes."
3. **Approval at group boundaries (trial for the rest of Slice 3).** Today `docs/build-plan.md` ("Development process") says "The next checkpoint starts only after the current one is approved." Change the build plan, root `CLAUDE.md` ("How work is done: checkpoints") and the `checkpoint` skill ("Report and stop") to: a checkpoint the owner has marked "auto-continue" in the build plan goes on to the next checkpoint after its report when every gate is green, every reviewer finding is fixed, and there are no open questions, deviations or decisions for the owner; the owner reviews the group at its last checkpoint. All other checkpoints stop as now. Add the marking to the build plan and ask the owner which remaining Slice 3 rows get it. The verdict is recorded at the Slice 3 retro. This revives DL-10 and supersedes DL-125 in part.
4. **One home for the process.** The checkpoint steps are written out in root `CLAUDE.md`, the build plan ("Development process" and "Verification"), `docs/testing-strategy.md` ("Workflow and gates"), the developer guide, and the `checkpoint` skill. Keep the full steps only in the skills. Reduce each other passage to at most five lines plus a pointer to the skill.
5. **Lighter docs-only design changes.** The `design-change` skill, steps 7 and 8, says every design change, "docs-only or tooling, gets a record (DL-126)". Change to: a docs-only change needs its decision-log entry, green docs consistency tests and its commit, with no review record file and no `docs-consistency` agent run. Tooling changes keep the full path. Supersedes DL-126 in part.
6. **Visual tuning is not a decision.** Add to the `design-change` skill and `frontend/CLAUDE.md`: spacing, alignment, width and similar look-and-feel adjustments are edited directly in `docs/ui-design-guide.md` and get a decision-log entry only when the owner says the look is settled.
7. **Prune the `CLAUDE.md` files.** The three files total about 50.8 KB. Target 30 KB or less. For each rule: if a lint rule or test can enforce it, add that and delete the prose; if a skill already says it, delete it. Change the "Always" bullet beginning "When a review catches a mistake that a rule would have prevented, add that rule to the relevant `CLAUDE.md`" to: "…add a lint rule or a test if one can enforce it, and prose only if not. Remove a prose rule once a check enforces it." Show the owner the list of removals before committing.
8. **Split the `checkpoint` skill.** Move every slice-end step (`fresh-clone-verifier`, `user-guide-verifier`, `docs-consistency`, `repo-auditor`, `simplicity-auditor`, the slice retro) into a new `slice-end` skill, and leave one line in `checkpoint` that invokes it at a slice's last checkpoint.
9. **Narrow the security reviewer.** In the `checkpoint` skill's trigger list, remove "any router" and the blanket "the `auth`, `user`, `workspace`, `org`, or `project` areas", and keep: `backend/app/authz/`, the named rules files, session, token, password and cookie code in `backend/app/core/`, the `auth` area, rendered markdown, CORS, CSRF and `Origin` handling, `github` and `webhook` code, and on the frontend the auth store, route guards and API client. In `.claude/agents/security-reviewer.md`, replace the literal values copied from design-doc §4 (the lines about the token size, the cookie attributes and the password length) with "as specified in design-doc §4".
10. **Shrink the behaviour reference.** The `checkpoint` skill, step 3, says "`docs/behavior-reference.md`: any change to behavior, exhaustively, in the words on the screen." Change to: "`docs/behavior-reference.md`: only behaviour no test asserts: flows that cross screens, the reason behind a behaviour, and anything a user must know that no screen states." Adjust `user-guide-verifier` to that scope. Do not prune the existing file now; do it once in the Slice 3 slice-end.
11. **Conventions arrive with their first consumer.** Add to root `CLAUDE.md`, "Always": "A shared convention, framework or piece of infrastructure is built in the checkpoint of its first real consumer, not ahead of it."
12. **"Proof it fails" only where it pays.** In the `test-writer` skill (the planning table and its checklist line) and `docs/testing-strategy.md`, require the "Proof it fails" column only for tests of `backend/app/rules/` and `backend/app/authz/`. Mutation testing and the reviewer's sabotage check cover the rest.
13. **Workspace features are frozen.** Add to `docs/design-doc.md` §4, under "One workspace for the foreseeable future", and to root `CLAUDE.md`: "No new workspace-level screens, roles or actions until a second workspace exists. New item types still carry `workspace_id` and use the existing list scoping."
14. **New slice for pre-deployment work.** In the build plan's slice table, move the contents of the current Slice 7 to a new Slice 8, and insert "7: Pre-deployment hardening" between Slices 6 and 8, holding TD-12, the items of TD-14, TD-17 and TD-83, and the nightly session cleanup as the job queue's first real job. Change each of those entries' "Fix by" from "Slice 7" to "Slice 8". Do not define its checkpoints.
15. **Stale statements.**
    - `README.md`: `uv run wl check             # everything CI runs` becomes `uv run wl check             # the pre-commit gate; CI runs wl check --full`.
    - Build plan, "Development process": "and can be reviewed in roughly 15–30 minutes" becomes "and is small enough to review in one sitting".
    - **Owner-only:** `.pre-commit-config.yaml`, line 3, "The full gate is `uv run wl check`, which is also what CI runs." should read "The pre-commit gate is `uv run wl check`; CI runs `uv run wl check --full`."

## Package 4: small code fixes (one checkpoint each unless the owner groups them)

1. **Database session time zone.** `backend/app/core/db.py`: `connect_args={"connect_timeout": 5}` becomes `connect_args={"connect_timeout": 5, "options": "-c timezone=UTC"}`. Add a test that an application connection reports `UTC` for `SHOW timezone`. Reason: with Postgres set to another zone, `tests/api/test_my_work_approvals.py::test_an_item_shows_the_revision_under_approval_and_where_it_is` fails because timestamps come back in the server's zone.
2. **Explicit handler registration.** Five registries are filled by module-level calls: `backend/app/services/auth.py` (`register_on_email_changed(_end_sessions)`), `project.py` (`register_on_member_removed(_remove_with_projects)`), and `requirement.py` (`register_on_restriction_changed`, `register_on_approved`, `register_on_rejected`). Add `backend/app/services/wiring.py` that imports every service module, import it from `app/main.py`, `app/cli.py` and `app/jobs/worker.py`, and add a test that importing only `app.services.wiring` leaves all five registries non-empty. Adjust the import-linter contract if it needs a place for the module.
3. **The untested lock.** `backend/app/services/roster.py`, `_guard_last_owner`, takes `lock_owners` a second time (the comment begins "Locked again, not the list `_member` locked"). All 7,299 tests pass without it. Try to write a concurrency test that fails without that line. If you can, keep the lock and the test. If no interleaving fails, remove the line and its comment and say so in the commit message.
4. **Deadlocks are retryable.** Map a Postgres deadlock (SQLSTATE `40P01`) in the error handlers to a 503 in the standard error format with `Retry-After: 1`, with a test. This is the interim for TD-83; leave the entry open for Slice 6a.
5. **Hide module choice until a module ships.** `frontend/src/views/project/CreateProjectDialog.vue` and `ProjectSettingsView.vue` render `ModuleFields`. Render it only when at least one module is available. Keep the backend gate. Update the specs and the guide. Supersedes DL-136 in part.
6. **Worker off by default.** In `docker-compose.yml`, put the `worker` service under a Compose profile so `wl up` does not start it, and keep whatever the job tests need. It returns to the default in Slice 6a.
7. **Timing test out of the gate.** Move the 2,000-row tree timing test in `frontend/e2e/requirements.spec.ts` to its own CI job with `continue-on-error: true`, outside `wl e2e`. Remove the special case for it from the `checkpoint` skill. Supersedes DL-257 and the gating parts of DL-253 and DL-254. DL-271 and DL-272 are feature decisions that mention the test: change only what depends on it being a gate.
8. **Inline the audit lens.** `simplicity-auditor` reads sections of the vendored files under `.claude/audit/`. Copy the sections it uses into the agent file with attribution, keep `SOURCES.md` for licenses, and delete the rest.

## Package 5: refactors, before the first task feature checkpoint

No behaviour changes in this package. Existing tests should pass with only import changes.

1. **One restriction-rights rule.** `backend/app/services/project.py` and `requirement.py` both contain `needed = [a for a, does in ((raise_, kind.raises), (lower, kind.lowers)) if does]`. Move it into a pure function in `backend/app/rules/restriction.py`, with tests from `spec-test-writer`, and call it from both.
2. **One person check (TD-101, pulled ahead of S3-C6).** Merge `_check_lead` (`project.py`), `_check_reporter` and `_check_approver` (`requirement.py`) into one helper that takes the action, the field name, and whether a miss is a 404 or a 422. Keep each caller's current locking behaviour. The new assignee and reviewer callers do not add a hold (concurrency policy).
3. **One composable for failed non-form actions.** Forms already share `useFormErrors`; leave them. Add `frontend/src/composables/useActionFailure.ts` for row and menu actions: it maps 403, 404 and 409 to their messages, reloads, and moves focus to the alert when the control has gone. Convert `TrashView.vue` and `RequirementDetail.vue` as the reference, then the remaining views.
4. **Split the two large services.** Move project membership (members, the org-add flow, `_remove_with_projects`) to `backend/app/services/project_members.py`, and the approval-request plumbing in `requirement.py` (with its `register_on_approved` and `register_on_rejected` handlers) to `backend/app/services/requirement_approvals.py`. Move the pure validators and message tables that `services/user.py` holds for other areas (for example `PROJECT_KEY_MESSAGES`) into `backend/app/rules/`. Update the import-linter layers.

## Deferred: do not do now

- **SVAR.** At the board checkpoint, spike the board with SVAR and with PrimeVue as was done for the backlog, and bring the comparison to the owner. No change before then.
- **List filters.** At S3-C16, delete from `backend/app/core/lists.py` any `FilterType` member, `CustomFilter`, or restricted-filter check that the filter bar does not use.
- **The behaviour reference prune** (Package 3, item 10) happens at the Slice 3 slice-end.

## Report format for each package

What changed (files), what you verified and how, anything that did not match this prompt, the owner-only steps outstanding, and the decision-log entry number.
