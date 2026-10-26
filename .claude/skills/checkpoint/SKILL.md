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
  import-linter contracts, migration checks, generated-client freshness, and mutation testing
  (when anything it depends on changed). The supply-chain audit and the end-to-end tests run in
  CI (`wl check --full`, DL-99), whose green run step 6 waits for.
- Fix failures and rerun until green. Never lower a threshold or skip a test to get green.
- **Last checkpoint of a slice:** search `docs/schema-doc.md` for `Added in Slice <n>.` (this
  slice's number) and confirm each marked column is in its model. The docs consistency tests
  require these columns only once this checkpoint is committed, so `wl check` can't catch a
  miss yet.

## 3. Update the docs

- `docs/developer-guide.md`: anything a developer now needs (setup steps, commands, conventions,
  how-tos, troubleshooting). Its Status stays one line, the checkpoint and the next one; what was
  built goes in the commit and the review record, not there (DL-170).
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
    or cookie code in `backend/app/core/`; the `auth`, `user`, `workspace`, `org`, or `project`
    areas; any router; rendered markdown (`v-html` or a markdown renderer); CORS, CSRF, or
    `Origin` handling; `github` or `webhook` code; on the frontend, the current-user (auth)
    store, route guards (`src/app/guards/`), or the API client (`src/api/client.ts`).
- Also invoke the `ui-reviewer` agent, with the same inputs, whenever the diff touches
  `frontend/src/` or `frontend/e2e/` (DL-62). It is read-only and runs no tests.
- **One reviewer at a time:** when both run, invoke `security-reviewer` first and
  `checkpoint-reviewer` once it has finished, never in parallel (then `ui-reviewer`, when it
  runs). Both can run tests against the shared test databases (`waterline_test` and the per-worker
  copies, DL-100), and two runs at once collide: each run drops and recreates the workers'
  databases at its start, and the concurrency tests truncate tables and then require every table
  to be empty. `checkpoint-reviewer`'s sabotage checks run tests too. Don't run tests yourself
  while a reviewer is running.
- Do not pass any reviewer your reasoning or a summary of the work; they review from the docs
  and the diff (a re-review also gets the previous pass's record, step 5; DL-105).
- **Before the first reviewer** (DL-106): review your own diff against the `CLAUDE.md` files'
  rules (`backend/CLAUDE.md`'s "Rules that are easy to break silently", `frontend/CLAUDE.md`'s
  "Rules" and "UI"); if that changes anything, rerun `uv run wl check`.
- **Every reviewer reviews the same snapshot** (DL-105): before invoking the first one, take
  `uv run wl review-copy <dir>/reviewed-1`, in a new directory (`mktemp -d` in your scratchpad;
  `review-copy` refuses one that isn't empty). Fix nothing until every reviewer that runs has
  reported: at a slice's last checkpoint, the slice-end agents below included, so their
  findings join the one batch (DL-108).
- **Last checkpoint of a slice:** once the reviewers above have finished, run `uv run wl down`
  (so ports are free) and invoke the `fresh-clone-verifier` agent with the repository's
  absolute path and the checkpoint ID. Its findings are fixed in `docs/developer-guide.md` like
  any other finding.
- **Last checkpoint of a slice:** with the dev stack still down, invoke the `user-guide-verifier`
  agent with the repository's absolute path, the checkpoint ID, and the slice whose "Done when"
  list to walk (DL-124). Its findings are fixed in `docs/user-guide.md`, or in the app when the
  app is what's wrong, like any other finding. Run `uv run wl up` again afterwards.
- **Last checkpoint of a slice:** after `checkpoint-reviewer`, invoke the `docs-consistency`
  agent with trigger `slice-end` and, as the base, the previous slice's last checkpoint commit
  (the root commit for Slice 0). It reports **Fixes** and **Decisions**.
- **Last checkpoint of a slice:** after `docs-consistency`, invoke the `repo-auditor` agent with
  the slice ID and the checkpoint ID (DL-41). It audits the whole repository, not this diff, and
  runs no tests.
- **Last checkpoint of a slice** (from S2-C0a, which builds it, DL-138): after `repo-auditor`,
  invoke the `simplicity-auditor` agent. It audits the whole repository for overengineering,
  reports only, and its findings feed the retro; the next slice's C0 applies those the owner
  accepts. The review record gets its own `## simplicity-auditor` section (a docs consistency
  test requires that heading in the slice's last record, DL-165).

## 5. Resolve every finding

For each finding from every reviewer that ran, exactly one of:
- **Fixed:** made in the batch below, with `uv run wl check` once the batch is done.
- **Logged:** add a tech-debt entry (reason and target) — only for minor findings, or others
  the owner has agreed to defer.
- **Rejected:** only when the finding is factually wrong; record the evidence.
- **Proposed to the owner:** (`repo-auditor` only) a major or blocker finding outside the
  slice's scope, put in the report as a proposed design change (DL-41).

`docs-consistency` **Fixes** are resolved the same way. Its **Decisions** are not yours to
resolve: leave them undecided and put them in the report (step 7) for the owner.

`repo-auditor` findings are resolved the same way too, but many fall outside the slice's
scope: fix one only when the fix is within it. Otherwise log it (minor), or put it in the report
for the owner as a proposed design change (major or blocker). Its questions go to the owner,
and its findings feed the slice retro.

`simplicity-auditor` findings (from S2-C0a, DL-138) are never fixed in the checkpoint: each goes
to the owner, who decides it, and feeds the retro; the next slice's C0 applies the accepted ones.

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
`repo-auditor` or `fresh-clone-verifier` is covered by `checkpoint-reviewer`'s re-review, or by
one pass of it if it had none, given those findings and their resolutions too (DL-110). The re-review gets, besides the usual inputs:
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

If a finding shows a rule that would have prevented the mistake, add it to the relevant
`CLAUDE.md`.

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
  the git guard allows no heredoc or `$(...)` with gh (DL-26).
- Push only the finished checkpoint commit, never work in progress. Wait for CI on it
  (`gh pr checks --watch`). Never amend, rebase, or force-push a pushed commit: a red CI is
  fixed with a follow-up commit, `fix(<ID>): <what>` (rerun `wl check`, push), before the
  report. Never report a checkpoint whose CI isn't green.
- Never merge. At the slice's last checkpoint, the owner's approval decides the merge. Any
  changes the owner decides in the slice retro are applied first, on the slice branch, with the
  `design-change` skill and green CI (DL-19). Before asking, check that every commit is linked
  to a GitHub account (`gh api repos/<owner>/<repo>/pulls/<n>/commits --paginate --jq '.[] |
  [.sha[0:7], .author.login] | @tsv'`: no empty login) and, once the PR is marked ready, its
  merge state (`gh pr view <n> --json mergeStateStatus,reviewDecision`), and report a block or
  an unlinked commit: the ruleset then requires an approval the owner can't give on their own
  PR (DL-33). Then, on their say-so, mark the PR ready
  (`gh pr ready`) and merge it with a merge commit (`gh pr merge --merge`; the branch stays,
  since GitHub blocks deleting any branch, DL-27),
  never squash or rebase. The git guard asks the owner to confirm the merge (DL-25).
- Under the git guard (DL-26), run each git or gh command as its own Bash call: `git add …`,
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
  owner's dev stack (its users, `.env`), not only the end-to-end stack (DL-127). Run it once
  yourself to make sure the steps are right;
  the owner's run is the check. A checkpoint with no visible behavior says so instead;
- **last checkpoint of a slice:** the slice retro: what each reviewer caught, what escaped to
  the owner, which skills and agents never triggered, the verdict of any process trial, and the
  `repo-auditor` findings left for the owner (with the design changes they propose), and every
  `simplicity-auditor` finding for the owner to decide.
  The owner decides what changes; each change gets a decision-log entry and is applied on the
  slice branch before the merge (DL-19);
- what the next checkpoint will cover.

Then **stop**. Do not begin the next checkpoint until the owner explicitly approves.
