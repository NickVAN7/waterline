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
  import-linter contracts, migration checks, generated-client freshness.
- Fix failures and rerun until green. Never lower a threshold or skip a test to get green.

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

- Invoke the `checkpoint-reviewer` agent with the checkpoint ID and the base commit (the
  previous checkpoint's commit, or the root commit for the first).
- Also invoke the `security-reviewer` agent, with the same inputs and in parallel, when the diff
  touches any of: `backend/app/authz/`; session, token, password, or cookie code in
  `backend/app/core/`; the `auth`, `user`, `org`, or `project` areas; any router; rendered
  markdown (`v-html` or a markdown renderer); CORS, CSRF, or `Origin` handling; `github` or
  `webhook` code.
- Do not pass either reviewer your reasoning or a summary of the work; they review from the docs
  and the diff.
- **Last checkpoint of a slice:** also run `uv run wl down` (so ports are free) and invoke the
  `fresh-clone-verifier` agent with the repository's absolute path and the checkpoint ID. Its
  findings are fixed in `docs/developer-guide.md` like any other finding.

## 5. Resolve every finding

For each finding from every reviewer that ran, exactly one of:
- **Fixed:** make the fix, then rerun `uv run wl check`.
- **Logged:** add a tech-debt entry (reason and target) — only for minor findings, or others
  the owner has agreed to defer.
- **Rejected:** only when the finding is factually wrong; record the evidence.

If fixes changed behavior (not just docs or tests), run the reviewer again on the fixes.
If a finding shows a rule that would have prevented the mistake, add it to the relevant
`CLAUDE.md`.

**Record every pass** of every reviewer that ran (checkpoint, security, fresh-clone) in
`docs/reviews/<ID>.md` (format: `docs/reviews/S0-C1.md`). Include the base commit, the totals,
and for each pass its verdict, its findings table with each
resolution (fixed / logged with TD number / rejected with evidence), and the questions it
raised. End with the questions still open for the owner and any owner decisions made during
review. The record goes in the checkpoint's commit.

## 6. Commit

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
Tech debt: <added / resolved entries, or "no change">
Next: <next checkpoint ID and name>
```

## 7. Prepare the Project upload

Claude Code can't write to the claude.ai Project, so the owner uploads changed files by hand.

- List every file this commit changed or added that the Project keeps a copy of:
  `git diff --name-only <base>..HEAD -- docs CLAUDE.md backend/CLAUDE.md frontend/CLAUDE.md .claude`.
  Files under `docs/` go to the Project under the same path; `CLAUDE.md` files and `.claude/`
  go under `repo-seed/` (same relative path).
- Copy them into one folder in the scratchpad, laid out as they go in the Project
  (`docs/…`, `repo-seed/…`), so the owner can upload them together.
- Never say the Project was updated: it wasn't.

## 8. Report and stop

Send the owner:
- the review note (the commit message body);
- each reviewer's findings table (checkpoint, security, fresh-clone) with the resolution of
  each finding (as recorded in `docs/reviews/<ID>.md`);
- any open questions from the review;
- the Project upload list from step 7 (each file, whether it's new or changed, and the folder
  it was copied to);
- what the next checkpoint will cover.

Then **stop**. Do not begin the next checkpoint until the owner explicitly approves.
