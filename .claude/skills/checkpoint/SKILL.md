---
name: checkpoint
description: Close out a Waterline checkpoint — run the gates, update docs and the tech-debt log, get an independent review, resolve findings, commit, report to the owner, and stop for approval. Use at the end of every checkpoint.
---

# Close out a checkpoint

Run these steps in order at the end of every checkpoint. Do not skip steps, and do not start
the next checkpoint: this skill ends by stopping for the owner's approval.

## 1. Confirm scope

- Identify the checkpoint ID (e.g. `S0-C2`) and read its row in `docs/build-plan.md`.
- List each scope item and confirm it is done. Anything unfinished is either finished now or
  logged in `docs/tech-debt.md` with a reason and target.
- List anything done that is **outside** the scope; justify it or remove it.

## 2. Run the gates

- Run `uv run wl check`. Everything must pass: lint, types, tests, coverage thresholds,
  import-linter contracts, migration checks, generated-client freshness, mutation testing, and
  the supply-chain audit (`wl audit`, which needs the network).
- Fix failures and rerun until green. Never lower a threshold or skip a test to get green.
- **Last checkpoint of a slice:** search `docs/schema-doc.md` for `Added in Slice <n>.` (this
  slice's number) and confirm each marked column is in its model. The docs consistency tests
  require these columns only once this checkpoint is committed, so `wl check` can't catch a
  miss yet.

## 3. Update the docs

- `docs/developer-guide.md`: anything a developer now needs (setup steps, commands, conventions,
  how-tos, troubleshooting).
- `docs/user-guide.md`: any user-visible behavior.
- `docs/design-doc.md`, `docs/schema-doc.md`, `docs/build-plan.md`: any drift between the docs
  and what was built (approved changes only; unapproved divergence goes back to the owner).
- `docs/tech-debt.md`: add entries for any shortcut, using this format:

  ```
  ### TD-<n>: <short title>
  - **Added:** <checkpoint ID>
  - **What:** <the shortcut or gap>
  - **Why:** <reason it was accepted>
  - **Fix by:** <checkpoint or slice>
  - **Status:** open | resolved in <checkpoint ID>
  ```

  Mark resolved entries as resolved rather than deleting them.

## 4. Independent review

- **Spec tests first:** if the checkpoint adds or changes `app/rules/` or `app/authz/`, start
  `docs/reviews/<ID>.md` now with a "Spec tests" section: `spec-test-writer`'s output (its
  behavior table and its files table, with each file's `git hash-object`), plus any change to
  those files the owner approved (what and why). `checkpoint-reviewer` compares the files with
  the recorded hashes.
- Invoke the `checkpoint-reviewer` agent with the checkpoint ID and the base commit (the
  previous checkpoint's commit, or the root commit for the first).
- Also invoke the `security-reviewer` agent, with the same inputs, when **either** holds:
  - the build plan's section for the slice says the checkpoint gets the security reviewer
    (e.g. Slice 1: "every checkpoint from 1 to 16"); or
  - the diff touches any of: `backend/app/authz/`; `backend/app/rules/account_rank.py`,
    `password_policy.py`, `identifiers.py`, or `classification.py`; session, token, password,
    or cookie code in `backend/app/core/`; the `auth`, `user`, `workspace`, `org`, or `project`
    areas; any router; rendered markdown (`v-html` or a markdown renderer); CORS, CSRF, or
    `Origin` handling; `github` or `webhook` code; on the frontend, the current-user (auth)
    store, route guards (`src/app/guards/`), or the API client (`src/api/client.ts`).
- **One reviewer at a time:** when both run, invoke `security-reviewer` first and
  `checkpoint-reviewer` once it has finished, never in parallel. Both can run tests against the
  shared test database (`waterline_test`), and two runs at once collide: the concurrency tests
  truncate tables and then require every table to be empty, and each run migrates the test
  database at its start. `checkpoint-reviewer`'s sabotage checks run tests too. Don't run tests
  yourself while a reviewer is running.
- Do not pass either reviewer your reasoning or a summary of the work; they review from the docs
  and the diff.
- **Last checkpoint of a slice:** once the reviewers above have finished, run `uv run wl down`
  (so ports are free) and invoke the `fresh-clone-verifier` agent with the repository's
  absolute path and the checkpoint ID. Its findings are fixed in `docs/developer-guide.md` like
  any other finding. Run `uv run wl up` again afterwards.
- **Last checkpoint of a slice:** after `checkpoint-reviewer`, invoke the `docs-consistency`
  agent with trigger `slice-end` and, as the base, the previous slice's last checkpoint commit
  (the root commit for Slice 0). It reports **Fixes** and **Decisions**.

## 5. Resolve every finding

For each finding from every reviewer that ran, exactly one of:
- **Fixed:** make the fix, then rerun `uv run wl check`.
- **Logged:** add a tech-debt entry (reason and target) — only for minor findings, or others
  the owner has agreed to defer.
- **Rejected:** only when the finding is factually wrong; record the evidence.

`docs-consistency` **Fixes** are resolved the same way. Its **Decisions** are not yours to
resolve: leave them undecided and put them in the report (step 7) for the owner.

If fixes changed behavior (not just docs or tests), run the reviewer again on the fixes.
If a finding shows a rule that would have prevented the mistake, add it to the relevant
`CLAUDE.md`.

**Record every pass** of every reviewer that ran (checkpoint, security, fresh-clone,
docs-consistency) in `docs/reviews/<ID>.md` (format: `docs/reviews/S0-C1.md`). Include the base
commit, the totals, the "Spec tests" section (when the checkpoint has one), and for each pass
its verdict, its findings table with each resolution (fixed / logged with TD number / rejected
with evidence), `checkpoint-reviewer`'s "Sabotage checks" table, and the questions it raised.
End with the questions still open for the owner and any owner decisions made during review.
The record goes in the checkpoint's commit.

**Tech debt due now:** before committing, list every open `docs/tech-debt.md` entry whose
Fix by is this checkpoint (or this slice, at its last checkpoint). Each is resolved in this
checkpoint, or re-targeted with the owner's approval (record the new Fix by and why). None
may be left open past its Fix by: the docs consistency tests fail on it after the commit.

## 6. Commit and push

Work on the slice's branch, `s<n>` (`docs/build-plan.md`, "Pull requests"), never on `main`.
One commit for the whole checkpoint, with this message:

```
checkpoint(<ID>): <checkpoint name>

Built:
- ...

Tests:
- ...

Decisions / deviations:
- ... (or "None")

Review: <n> findings — <x> fixed, <y> logged (TD-…), <z> rejected (docs/reviews/<ID>.md)
Security review: <n> findings — … (or "not required")
Fresh-clone verification: <result> (last checkpoint of a slice only)
Docs consistency: <n> fixes — …; <m> decisions for the owner (last checkpoint of a slice only)
Tech debt: <added / resolved entries, or "no change">
Next: <next checkpoint ID and name>
```

Then:
- Push the branch. At the branch's first push, open the slice's PR as a draft
  (`gh pr create --draft`, titled with the slice, listing its groups).
- Push only the finished checkpoint commit, never work in progress. Wait for CI on it
  (`gh pr checks --watch`). Never amend, rebase, or force-push a pushed commit: a red CI is
  fixed with a follow-up commit, `fix(<ID>): <what>` (rerun `wl check`, push), before the
  report. Never report a checkpoint whose CI isn't green.
- Never merge. At the slice's last checkpoint, the owner's approval decides the merge: on their
  say-so, mark the PR ready and merge it with a merge commit
  (`gh pr merge --merge --delete-branch`), never squash or rebase. The git guard hook asks the
  owner to confirm the merge command; it also blocks commits on `main`, pushes to `main`, force
  pushes, rebases, and skipped hooks. When it blocks a command, do what its message says.

## 7. Report and stop

Nothing counts as verified because you say so. Label every verification claim in the report
with who verified it: a gate (`wl check`, CI), an agent (e.g. "sabotage-checked by
checkpoint-reviewer"), or the owner. Your own sabotage checks and runs are evidence for the
reviewers, not verification.

Send the owner:
- the review note (the commit message body);
- each reviewer's findings table (checkpoint, security, fresh-clone, docs-consistency) with
  the resolution of each finding (as recorded in `docs/reviews/<ID>.md`);
- the `docs-consistency` Decisions, unresolved, with their options;
- any open questions from the review;
- the PR link and its CI result, and whether this checkpoint ends its group (a review point)
  or the slice (so the PR is ready to merge on approval);
- **a try-it-yourself script**, for any checkpoint with behavior visible through the API or
  the UI: 3–6 numbered steps against the running dev stack (`curl` with a cookie jar and an
  `Origin` header before S1-C14, screens after), each with its expected result, including at
  least one step that should be denied. Run it once yourself to make sure the steps are right;
  the owner's run is the check. A checkpoint with no visible behavior says so instead;
- **last checkpoint of a slice:** the slice retro: what each reviewer caught, what escaped to
  the owner, which skills and agents never triggered, and the verdict of any process trial.
  The owner decides what changes; each change gets a decision-log entry;
- what the next checkpoint will cover.

Then **stop**. Do not begin the next checkpoint until the owner explicitly approves.

**Review-tier trial** (`docs/build-plan.md`, "Verification"; S1-C8 to S1-C10 only):
- **S1-C8 and S1-C9:** after sending the report, go straight on to the next checkpoint without
  stopping, only if **all** of these hold: `wl check` and CI are green; every reviewer that ran
  returned no findings, or only findings that were **fixed** (none logged, none rejected); and
  there are no open questions, no `docs-consistency` Decisions, and no deviations from the docs
  in the review note. Say in the report that it auto-continued and why. If any condition
  fails, stop as usual.
- **S1-C10:** a full stop for the whole group. The report covers S1-C8 to S1-C10, with links to
  the three review records and the group's diff range (`<S1-C7 commit>..<S1-C10 commit>`).
