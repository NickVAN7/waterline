# Review record: DC-2026-11-18b — The git guard as a small allow-list (Package 1)

- **Change:** the outside review's Package 1
  (`docs/reviews/design-changes/2026-11-18-outside-review-handoff.md`), recorded as **DL-391**.
  Tooling and docs.
  - `.claude/hooks/guard_git.py` rewritten in 148 lines (from 1,298) on `shlex`, scoped to the
    direct form of a forbidden git or gh command; its tests rewritten as a table, every command
    shape the trial's friction log recorded, and real git for the three rules that read the
    repository.
  - A repository-state step first in `wl check`'s CLI checks (`doctor.repo_state`).
  - Every doc that states the guard's rules; TD-20 resolved; the guard trial closed.
- **Owner decisions during the change** (Nov 18, 2026): the forms today's guard allowed that the
  handoff's list would block, kept: `merge`/`rebase`/`cherry-pick`/`revert`/`am --abort`,
  `stash drop`, `config get`/`list`; let go: path and soft resets, `checkout -- <paths>`. After
  review: `hash-object <file>` with no options kept (DL-29); `switch -C`/`--force-create` refused;
  a `SKIP=` prefix accepted as out of scope, root `CLAUDE.md` saying `--no-verify` is blocked.
- **Deviations from the handoff, named for the owner:**
  - In CI the repository-state step checks only `core.hooksPath`: CI installs no pre-commit hook
    (its workflow skips it), so the hook check would always fail there; the handoff named only
    the branch check.
  - The block message (`ONE_COMMAND`) no longer lists `cd`, variables, and environment prefixes,
    which the new guard doesn't refuse (checkpoint-reviewer finding 4, docs-consistency fix 5).
  - The friction log had 51 entries, not the handoff's 37 (all recorded after `d2a5e32`); all 51
    are in the table.
  - `checkpoint-reviewer`, `fresh-clone-verifier`, and `review_copy.py`'s docstring are unchanged:
    their sentence ("one plain git command per call, so these steps live in `wl`") is still true.
- **Kind:** tooling (`chore:`), with `checkpoint-reviewer` (DL-18).
- **Base commit:** `1138729` (DC-2026-11-18).
- **Reviewers:** `checkpoint-reviewer`, then `docs-consistency` (trigger `design-change`), on one
  snapshot (DL-105); `checkpoint-reviewer` re-reviewed the fix diff (a blocker fixed).
- **Totals:** checkpoint-reviewer pass 1 ready after fixes, 1 blocker, 2 major, 1 minor, 3
  questions; pass 2 ready after fixes, 1 major (fixed), 1 minor (documented), 1 question;
  docs-consistency 6 fixes (5 applied, 1 moot), 2 decisions (answered).
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## checkpoint-reviewer, pass 1 (base `1138729`)

Verdict: ready after fixes.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | blocker | correctness | Line breaks became ` ; ` before `shlex`, whose `#` comment then ran to the end of the call: `"# push it\ngit push --force origin s3"` and `"ls # note\n…"` were allowed, and so were `--no-verify` and a commit on `main` after a comment. | **Fixed:** a line break becomes `\n; `, so a comment ends at its line; both cases are table rows (BLOCK), and `git status  # a note` (ALLOW). |
| 2 | major | correctness | Push and commit refusals matched whole words: `--force-with-lease=s3`, `-uf`, `--forc`, `--no-verif`, and `refs/heads/main` passed. | **Fixed:** one `refuses` rule for push, commit, and `switch -C`: a flag with `=value`, abbreviated (git takes a prefix), longer than a refused one (`--force-with-lease`), or a short flag among others; a target ending `/main` is `main`. A row for each. |
| 3 | major | docs | `hash-object` went to the owner, but the spec-test hashes need it (DL-29, the agents, the guide, the testing strategy). | **Fixed** (owner's choice): `hash-object <file>` with no options allowed again; `-w` goes to the owner. DL-391 says so; DL-29 stands. |
| 4 | minor | docs | The block message named `cd`, variables, and environment prefixes, which the guard no longer refuses. | **Fixed:** the message names operators, `$(...)`, and redirects, as root `CLAUDE.md` does. |

**Questions**, answered by the owner (Nov 18): `hash-object` (above); `switch -C` refused;
`SKIP=` accepted as out of scope.

**Sabotage checks** (in a temporary copy, its table):

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| The repository-state step fails on `main` | DL-391 | `== "main"` to `== "mainx"` in `doctor.py` | `tests/test_doctor.py` | `test_each_unsound_repository_state_is_a_problem[on main]`, `test_the_step_exits_1_and_says_why` |
| An amend of a pushed HEAD is blocked | DL-23, DL-391 | the `not` dropped | `tests/hooks/test_guard_git.py` | `test_an_amend_is_blocked_once_head_is_pushed_in_real_git` and the table's amend row |
| A substitution in a git command blocks | handoff rule 2 | `"$" in w` removed | `tests/hooks/test_guard_git.py` | the table's `git log $REV` and `ma$'in'` rows |

## docs-consistency, pass 1 (base `1138729`)

| # | Kind | Finding | Resolution |
|---|---|---|---|
| 1 | superseded | DL-29 still allowed `hash-object`, which DL-391 blocked. | **Moot:** `hash-object` is allowed again (checkpoint-reviewer 3); DL-29 stands. |
| 2 | superseded | DL-30 said the guard blocks a redirect naming `.pre-commit-config.yaml`. | **Fixed:** DL-30 superseded in part by DL-391 (the protected-files hook still blocks the file tools); DL-391 names it. |
| 3 | stale | The guide's `wl doctor` row: hooks "so worktrees and `core.hooksPath` work". | **Fixed:** `wl check` fails when `core.hooksPath` is set. |
| 4 | gap | The guide's `wl check` row, its section 1 doctor sentence, and root `CLAUDE.md`'s `wl check` bullet didn't name the new step. | **Fixed:** all three. |
| 5 | contradiction | The block message (as checkpoint-reviewer 4), and root `CLAUDE.md`'s "skipped hooks are blocked". | **Fixed:** the message; `CLAUDE.md` says `--no-verify` is blocked (owner, on `SKIP=`). |
| 6 | broken-ref | DL-391 applied to build plan ("Process"), a section that doesn't exist. | **Fixed:** "Pull requests". |

**Decisions for the owner:** both answered by the checkpoint-reviewer questions above
(`hash-object` kept; a variable prefix out of scope, recorded in DL-391 and the guide).

## checkpoint-reviewer, pass 2 (the fix diff)

Verdict: ready after fixes. Every pass-1 resolution and docs-consistency fix checked against the
fix diff; the guard's 264 tests pass in a copy of reviewed-2.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | major | correctness | `git push origin @` from `main` was allowed: git reads `@` as `HEAD` (it pushed `HEAD:refs/heads/main` in a dry run), but only `HEAD` sent the guard to the current branch. | **Fixed** (no third pass, DL-105): `HEAD` or `@`; rows in the table and the real-git push test. Siblings: no other rule reads a ref name. |
| 2 | minor | correctness | `git switch --force <branch>` is blocked (it reads as a prefix of `--force-create`), while the same `-f` is allowed. Fails closed. | **Kept, documented:** the guide's `switch` bullet says to use `-f`. |

**Sabotage check:** the line break back to ` ; ` failed the two comment-line rows.

**Question:** `branch --verbose` went from allowed to blocked. **Answer:** a side effect of
trimming the guard under 150 lines (`-v` is the same option, and the guide lists only `-v` and
`-vv`); not one of the owner's decisions, so it's named for them in the report.

Noted by the reviewer, not raised: forms reviewed-1 already over-blocked, failing closed
(`git commit -uno`, `git commit -m"done"` read as `-n`). Left as they are: a commit message goes
`-m "<text>"`, as every skill writes it.
