# Review record: S2-C0a — Simplicity audit

- **Checkpoint:** Slice 2, Checkpoint 0a (group `s2-prep`; PR #11)
- **Base commit:** `a2f4b6f` (DC-2026-10-22c's commit)
- **Reviewers:** `checkpoint-reviewer`, on one snapshot (DL-105). `security-reviewer` didn't run
  (the build plan doesn't name S2-C0a, and the diff touches no security-relevant code);
  `ui-reviewer` didn't run (no `frontend/` change).
- **Totals:** `checkpoint-reviewer`: 3 findings (2 major, 1 minor), all fixed; 1 question,
  answered by a fix. No re-review (the fixes are tests, docs, and one minor finding, DL-105).
  `simplicity-auditor`: 11 findings, every one for the owner to decide (DL-138).
- **Gates at close:** `uv run wl check` green; CI on the checkpoint commit.

---

## Spec tests

No `app/rules/` or `app/authz/` change, so `spec-test-writer` didn't run.

## Outside the row's scope, and why

- None. The `checkpoint` skill's slice-end step was already in place from the Slice 2 plan's
  design change; this checkpoint only names its heading (finding 1's question).

## The audit's first run

Run on `main` as of `e999564` (Slice 1 complete), from a snapshot of the slice branch: the app
code (`backend/app`, `frontend/src`, `tools/`, `.claude/hooks/`) is identical to `e999564`
(`git diff --stat e999564` lists only docs, `.claude/` agents and skills, and the docs
consistency tests). The session's agent list loads at its start, so the new agent type wasn't
available yet: its definition, `.claude/agents/simplicity-auditor.md`, was run by a
general-purpose agent told to follow it exactly and stay read-only.

---

## checkpoint-reviewer, pass 1 (base `a2f4b6f`) — verdict: ready after fixes

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | major | **Nothing tests that the audit must be its own heading** (`test_docs_consistency.py`, `docs.py`). The slice-end check needs a line starting `## simplicity-auditor`, but the failing case's text never contains the word, so loosening the pattern to a plain mention still passed all 38 tests. A real S2-C22 record whose `## repo-auditor` section mentions `simplicity-auditor` would then pass without the audit. Fix: put the word in the failing case's text. | **Fixed:** the failing case's `## repo-auditor` section now says "No overlap with simplicity-auditor." Siblings: the passing case already uses the heading; no other test builds record text. |
| 2 | major | **Two docs that list every docs consistency check don't mention the new one** (developer guide section 9's table, testing strategy). A developer whose `wl check` fails on a missing C0a record finds no row explaining it. Fix: add the row and the clause. | **Fixed:** a "Review records" row in section 9 and the clause in the testing strategy. Siblings: the build plan's summary was already updated. |
| 3 | minor | **The check passes when the record is missing or misnamed** (`docs.py`). Only files named exactly by a checkpoint ID are read, so a missing slice-end record, or one named `S2-C22-verification.md`, passes the gate. Fix: require a record for the latest checkpoint commit from Slice 2 on. | **Fixed:** `review_record_problems` takes the latest checkpoint and reports its missing record (two tests: missing in Slice 2, not required in Slice 1). |

**Sabotage checks** (in a throwaway copy of the snapshot):

| Behavior | Source | Change made | Caught by |
|---|---|---|---|
| A C0 record (not only C0a) satisfies the rule before C1 | DL-165 | Checked only `S<n>-C0a` | `test_a_c0_or_c0a_record_satisfies_the_pre_checkpoint_rule[S2-C0]` |
| The slice-end record needs a `## simplicity-auditor` heading | DL-138 | The pattern loosened to a plain mention | **none** (finding 1, fixed) |
| The rules apply only from Slice 2 | DL-138 | Dropped the Slice 2 condition from the C1 rule | `test_slice_1_needs_no_pre_checkpoint_record`, `test_slice_1_end_record_needs_no_simplicity_audit`, `test_review_records_include_the_simplicity_audit` |

The reviewer also downloaded the seven vendored files at the pinned commits: all byte-identical,
both licenses MIT, every section the agent names present.

**Question:** the `checkpoint` skill said "its own `simplicity-auditor` section" without the
heading level the test needs. **Answered:** the skill now says `## simplicity-auditor`.

## simplicity-auditor (S2-C0a, `e999564`)

Lean: about -2,840 lines possible (about -440 without finding 1), no dependencies. Not checked
in depth: the backend and frontend tests, the end-to-end suite, the CLI tests, `authz/actions.py`
(TD-64), `rules/`, the models, `demo.py`, `cli.py`, the migrations, the project settings and
members views (S2-C0h), the CI workflow, Docker Compose, and the skills other than `checkpoint`.
Two smaller findings left out (an unused `Role` export in `fakeRoster.ts`; the `ListSpec`
pyright ignores, unproven).

Every finding is the owner's to decide (DL-138); the recommendation is the implementing
session's.

| # | Category | Finding | Recommendation |
|---|---|---|---|
| 1 | conflicts with DL-26, DL-12 | **The git guard repeats what GitHub's rulesets already enforce** (`.claude/hooks/guard_git.py`, its tests; about -2,400 lines). The rulesets (DL-27) already refuse pushes to `main`, force-pushes, and branch deletion, and CI catches skipped hooks. Only a local commit on `main` and the merge and `gh api` prompts are the guard's alone, and its one-command rule costs every session and shaped `wl review-copy`. Smaller: Claude Code permission rules (`ask` for `gh pr merge` and `gh api`, `deny` for `--no-verify` and force-push), plus an optional 30-line hook refusing commits on `main`. The auditor didn't confirm the rules cover every form the guard handles. | Decide at the Slice 2 retro, after a short trial of the permission rules in a scratch session; no change in Slice 2's rows. |
| 2 | process / delete | **The developer guide's Status line has become a 96-line changelog** (`docs/developer-guide.md:7-102`; about -93 lines). Its test reads only the first checkpoint ID; the rest repeats the history and the records, and grows every checkpoint. Smaller: one line. | Accept, in S2-C0i (tooling). |
| 3 | merge duplicates / process | **The agent, skill, and hook list is written out in three docs, and two tests enforce the copies** (build plan "Claude configuration", developer guide section 11, `CLAUDE.md`; about -120 lines). The copies drift (S1-C17 fixed three). Smaller: one list in section 11; the build plan points to it and keeps only the reviewer order; drop the build-plan test; `frontend/CLAUDE.md`'s layout keeps folder purposes, not file names. | Accept, in S2-C0i, before `user-guide-verifier` adds a fifth copy. |
| 4 | merge duplicates | **Org settings and workspace settings are near-copies** (`OrgSettingsView.vue`, `WorkspaceSettingsView.vue`; about -90 lines). Templates differ in four lines; TD-43 already fixed their save handling twice. Smaller: one `NameSlugSettings.vue` taking the load, save, and check functions and the texts. | Accept, in S2-C0h with TD-56, which changes both. |
| 5 | merge duplicates | **The add-person and create-org dialogs repeat the new-account fields** (`AddPersonDialog.vue:363-410`, `CreateOrgDialog.vue:344-385`; about -40 lines). TD-59 moves only the suggestion timer. Smaller: a `NewAccountFields.vue` on TD-59's composable. | Accept, in S2-C0h, so its add-person changes land once. |
| 6 | process | **`fresh-clone-verifier` re-runs `wl check --full`, which CI already runs on a clean checkout** (`.claude/agents/fresh-clone-verifier.md`, step 5). Both runs so far were green; all 7 findings were setup wording. Smaller: step 5 runs the guide's quick checks only (`wl doctor`, `wl up`, the health check, plain `wl check`). | Accept, in S2-C0i. |
| 7 | simplify | **Two places decide whether a stale row is a 404 or a 409, and no model uses versioning yet** (`core/errors.py:136-177`, `core/db.py:51-120`; about -35 lines). Smaller: decide once in `get_session`; delete `stale_data_handler` and `is_version_conflict`. Rests on FastAPI passing endpoint exceptions through yield dependencies, not run. | Accept, in S2-C1, when `requirement` makes versioning real and its tests exercise it. |
| 8 | merge duplicates | **The "apply changes, flush, then log" block is copied in four services, and TD-57's lock goes into three** (`services/workspace.py`, `org.py`, `user.py`, `project.py`; about -15 lines). Smaller: one `apply_changes` beside `changed_fields` that locks, compares, sets, and flushes; share org's `_name_and_slug_errors` with workspace. | Accept, in S2-C0c, which owns TD-57: the lock and its race test written once. |
| 9 | merge duplicates | **One-field-error helpers copied three times** (`services/project.py:137`, `roster.py:400-405`, `auth.py:355`; about -10 lines). Smaller: `ValidationFailedError.on(loc, message, type)`. | Accept, in S2-C0c beside TD-53. |
| 10 | merge duplicates | **The org's project list builds `include_archived` by hand, although `ListSpec.archived_column` does it** (`services/project.py:74-78`, `repositories/project.py:49-57`; about -8 lines). Smaller: an `ORG_PROJECTS` spec with `archived_column`, then `wl gen-client`. | Accept, in S2-C0g, which changes the project list. |
| 11 | conflicts with DL-125 | **The build plan still describes the review-tier trial in full** (`docs/build-plan.md:116-142`; about -25 lines), though its verdict was "not exercised". Smaller: one line naming the trial and DL-10, DL-125. | Accept, as a docs-only design change before S2-C0b. |

## Open questions for the owner

- Each `simplicity-auditor` finding above: accept (and the row it goes to), reject, or defer.
