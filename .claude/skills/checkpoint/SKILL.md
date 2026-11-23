---
name: checkpoint
description: Close out a Waterline checkpoint — run the gates, update docs and the tech-debt log, get an independent review, resolve findings, commit, report to the owner, and stop for approval. Use at the end of every checkpoint.
---

# Close out a checkpoint

Run these steps in order at the end of every checkpoint. Do not skip steps, and do not start
the next checkpoint except as step 7 allows: this skill ends by stopping for the owner's approval,
unless the checkpoint is marked auto-continue (DL-393).

**Last checkpoint of a slice:** also follow the `slice-end` skill, whose steps join steps 2, 4,
5, 6, and 7 here.

## 1. Confirm scope

- Identify the checkpoint ID (e.g. `S0-C2`) and read its row in `docs/build-plan.md`.
- List each scope item and confirm it is done. Anything unfinished is either finished now or
  logged in `docs/tech-debt.md` with a reason and target.
- List anything done that is **outside** the scope; justify it or remove it.

## 2. Run the gates

- Run `uv run wl check`. Everything must pass: lint, types, tests, coverage thresholds,
  import-linter contracts, migration checks, generated-client freshness, and mutation testing
  (when anything it depends on changed). The supply-chain audit and the end-to-end tests run in
  CI (`wl check --full`, DL-99), whose green run step 6 waits for.
- Fix failures and rerun until green. Never lower a threshold or skip a test to get green.

## 3. Update the docs

- The root `CLAUDE.md`'s **Status**: one line, this checkpoint and the next one; what was built
  goes in the commit and the review record, not there (DL-315).
- `docs/developer-guide.md`: anything a developer now needs (setup steps, commands, conventions,
  how-tos, troubleshooting).
- `docs/behavior-reference.md`: only behaviour no test asserts: flows that cross screens, the
  reason behind a behaviour, and anything a user must know that no screen states (DL-393). The guide (`docs/user-guide/`, one page per topic) only when something a user does or sees
  changes or is added: the reference changes with behavior; the guide only when what a user does
  or sees changes (DL-335). The guide leaves out route paths, exact messages, and numeric limits
  (DL-342).
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

  New entries go at the end of the open entries, before **Resolved**. A resolved entry moves
  under **Resolved**, in number order, shrunk to its heading, Added, and Status (`resolved in
  <checkpoint ID>` and how); its full text stays in git history and this review record
  (DL-313).

## 4. Independent review

- **Spec tests first:** if the checkpoint adds or changes `app/rules/` or `app/authz/`, start
  `docs/reviews/s<n>/<ID>.md` now with a "Spec tests" section: `spec-test-writer`'s output (its
  behavior table and its files table, with each file's `git hash-object`), plus any change to
  those files the owner approved (what and why). `checkpoint-reviewer` compares the files with
  the recorded hashes.
- Invoke the `checkpoint-reviewer` agent with the checkpoint ID and the base commit: the last
  commit before this checkpoint's work started (DL-17), so design-change commits between
  checkpoints stay out of its review. For a checkpoint parked for a design change, that's the
  design change's last commit.
- Also invoke the `security-reviewer` agent, with the same inputs, when **either** holds:
  - the build plan's section for the slice says the checkpoint gets the security reviewer
    (e.g. Slice 1: "every checkpoint from 1 to 16b"); or
  - the diff touches any of: `backend/app/authz/`; `backend/app/rules/account_rank.py`,
    `password_policy.py`, `identifiers.py`, or `restriction.py`; session, token, password,
    or cookie code in `backend/app/core/`; the `auth` area; rendered markdown (`v-html` or a
    markdown renderer); CORS, CSRF, or `Origin` handling; `github` or `webhook` code; on the frontend, the current-user (auth)
    store, route guards (`src/app/guards/`), or the API client (`src/api/client.ts`).
- Also invoke the `ui-reviewer` agent, with the same inputs, whenever the diff touches
  `frontend/src/` or `frontend/e2e/` (DL-62). It is read-only and runs no tests.
- **In parallel, in one step** (DL-392): invoke every reviewer that applies at once. A
  reviewer that runs tests does so only inside its own review copy (`wl review-copy <dir>
  --with-env`, which gives the copy a test database of its own), and discards it with `wl
  discard-copy <dir>` (its databases dropped too); so you may run tests in the working tree
  while they run.
- Do not pass any reviewer your reasoning or a summary of the work; they review from the docs
  and the diff (a re-review also gets the previous pass's record, step 5; DL-105).
- **Before the first reviewer** (DL-106): review your own diff against the `CLAUDE.md` files'
  rules (`backend/CLAUDE.md`'s "Rules that are easy to break silently" and "Concurrency policy",
  `frontend/CLAUDE.md`'s "Rules" and "UI", and `.claude/skills/vue-screen/traps.md` for a
  frontend diff); if that changes anything, rerun `uv run wl check`.
- **Every reviewer reviews the same snapshot** (DL-105): before invoking the first one, take
  `uv run wl review-copy <dir>/reviewed-1`, in a new directory (`mktemp -d` in your scratchpad;
  `review-copy` refuses one that isn't empty). Fix nothing until every reviewer that runs has
  reported: at a slice's last checkpoint, the `slice-end` skill's agents included, so their
  findings join the one batch (DL-108).

## 5. Resolve every finding

For each finding from every reviewer that ran, exactly one of:
- **Fixed:** made in the batch below, with `uv run wl check` once the batch is done.
- **Logged:** add a tech-debt entry (reason and target) — only for minor findings, or others
  the owner has agreed to defer.
- **Rejected:** only when the finding is factually wrong; record the evidence.
- **Proposed to the owner:** (`repo-auditor` only) a major or blocker finding outside the
  slice's scope, put in the report as a proposed design change (DL-41).

The `slice-end` agents' findings are resolved as that skill says.

**Fix in one batch** (DL-105, DL-106), once every reviewer has reported:
- Fix every finding together. Before each fix, grep for the same pattern elsewhere in the diff
  and the code it touches, and fix every instance at once.
- Fix code from an earlier checkpoint only when the finding or this checkpoint's scope needs
  it; otherwise log it in `docs/tech-debt.md`.
- While fixing, run only the affected tests (`wl frontend test <spec>`, `wl backend test -k …`);
  run `uv run wl check` once the batch is done.

**Re-review, at most once** (DL-105): a reviewer runs again only when a fix resolved one of its
**major or blocker** findings, or added behavior its finding didn't ask for; fixes to minor
findings, tests, or docs alone don't trigger one. Only `checkpoint-reviewer`,
`security-reviewer`, and `ui-reviewer` are re-reviewed; the other agents' findings are fixed
without another pass (DL-108), except that a code fix for a major or blocker finding from
`repo-auditor`, `fresh-clone-verifier`, or `user-guide-verifier` is covered by `checkpoint-reviewer`'s re-review, or by
one pass of it if it had none, given those findings and their resolutions too (DL-110, DL-190). The re-review gets, besides the usual inputs:
- the fix diff: take `uv run wl review-copy <dir>/reviewed-2` and pass the reviewer
  `diff -ruN -x .git <dir>/reviewed-1 <dir>/reviewed-2`, saved to a file, as what to review
  (each copy is a clone, with its own `.git`; the rest of the diff was reviewed in pass 1);
- its previous pass's findings and their resolutions, as recorded in the review record.

**List the siblings** (DL-128): for each fix, the review record says where else the pattern
lives and what was done there. Before a re-review, run `uv run wl fmt`, and grep the docs for
the behavior the fix removed.

Two passes per reviewer at most. Findings from the second pass are fixed without another
pass, logged, or, when a fix would change behavior beyond the finding, put to the owner in the
report.

If a finding shows a rule that would have prevented the mistake, add a lint rule or a test if
one can enforce it, and prose in the relevant `CLAUDE.md` only if not (DL-393).

**Record every pass** of every reviewer that ran (checkpoint, security, UI, fresh-clone,
docs-consistency, repo-auditor, simplicity-auditor) in `docs/reviews/s<n>/<ID>.md` (format: `docs/reviews/s0/S0-C1.md`).
Include the base commit, the totals, the "Spec tests" section (when the checkpoint has one), and
for each pass its verdict, its findings table in the `S0-C1.md` columns, one row per finding with
its resolution (fixed / logged with TD number / rejected with evidence / proposed to the owner;
for `checkpoint-reviewer`, `security-reviewer`, `ui-reviewer`, and `repo-auditor`, the four parts condensed
into the Finding cell, DL-42), `checkpoint-reviewer`'s "Sabotage checks" table, and the
questions it raised. End with the questions still open for the owner and any owner decisions made during review.
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

Review: <n> findings — <x> fixed, <y> logged (TD-…), <z> rejected (docs/reviews/s<n>/<ID>.md)
Security review: <n> findings — … (or "not required")
Fresh-clone verification: <result> (last checkpoint of a slice only)
Docs consistency: <n> fixes — …; <m> decisions for the owner (last checkpoint of a slice only)
Repository audit: <n> findings — <x> fixed, <y> logged (TD-…), <z> proposed to the owner (last checkpoint of a slice only)
Tech debt: <added / resolved entries, or "no change">
Next: <next checkpoint ID and name>
```

Then:
- Push the branch: `git push -u origin s<n>` at its first push, `git push` after. At the
  first push, open the slice's PR as a draft (`gh pr create --draft`, titled with the slice,
  listing its groups), with a literal `--title '…'` and `--body '…'` or `--body-file <file>`:
  the git guard allows no heredoc or `$(...)` with gh (DL-391).
- Push only the finished checkpoint commit, never work in progress. Wait for CI on it
  (`gh pr checks --watch --required`: the `wl check` job; the `timing test (not gating)` job's
  result is read from its log, never fixed to get a green run, DL-403). Never amend, rebase, or force-push a pushed commit: a red CI is
  fixed with a follow-up commit, `fix(<ID>): <what>` (rerun `wl check`, push), before the
  report. Never report a checkpoint whose CI isn't green.
- Never merge: the PR is merged at the slice's end, as the `slice-end` skill says.
- Under the git guard (DL-391), run each git or gh command as its own Bash call: `git add …`,
  then `git commit -F - <<'EOF'` with the message, then the push above. When it blocks a command,
  do what its message says.

## 7. Report and stop

Nothing counts as verified because you say so. Label every verification claim in the report
with who verified it: a gate (`wl check`, CI), an agent (e.g. "sabotage-checked by
checkpoint-reviewer"), or the owner. Your own sabotage checks and runs are evidence for the
reviewers, not verification.

Send the owner:
- the review note (the commit message body);
- each reviewer's findings table (checkpoint, security, UI, fresh-clone, docs-consistency,
  repo-auditor, simplicity-auditor) with
  the resolution of each finding (as recorded in `docs/reviews/s<n>/<ID>.md`);
- the `docs-consistency` Decisions, unresolved, with their options;
- any open questions from the review. Each decision or question says what it is, why it
  matters, the options, and a recommendation (DL-130); every open question in the review record
  is in the report;
- the PR link and its CI result, and whether this checkpoint ends its group (a review point)
  or the slice (so the PR is ready to merge on approval);
- **a try-it-yourself script**, for any checkpoint with behavior visible through the API or
  the UI: 3–6 numbered steps against the running dev stack (`curl` with a cookie jar and an
  `Origin` header before S1-C14, screens after), each with its expected result, including at
  least one step that should be denied. Its first step sets up or names the state it needs
  (e.g. `uv run wl seed --demo` on an empty database), and before handing it over, check the
  owner's dev stack (its users, `.env`), not only the end-to-end stack (DL-127). When the
  checkpoint added or changed a dependency, restart the owner's stack with `wl up` first, and
  tell them to hard-reload any open tab (DL-260). Run it once yourself to make sure the steps
  are right;
  the owner's run is the check. A checkpoint with no visible behavior says so instead;
- **last checkpoint of a slice:** the slice retro (the `slice-end` skill);
- what the next checkpoint will cover.

Then **stop**. Do not begin the next checkpoint until the owner explicitly approves, with one
exception (DL-393; trial for the rest of Slice 3, its verdict at the Slice 3 retro): a
checkpoint the owner has marked **auto-continue** in its build-plan row goes on to the next
checkpoint after its report when every gate is green, every reviewer finding is fixed, and there
are no open questions, deviations, or decisions for the owner. The owner reviews the group at its
last checkpoint, which always stops.
