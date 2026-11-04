# Review record: DC-2026-11-04g — History names a parent and a revision

- **Change:** the owner's decision at S2-C19's start (chat, Nov 4, 2026): a parent change's and an
  approval's entries carry server-resolved values, as user fields' names already are (DL-276);
  the owner's answers to this review's two decisions are folded into DL-276 before its commit.
  Docs only.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `546d940` (DC-2026-11-04f).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 1 fix, fixed; 2 decisions for the owner, both answered (DL-276).
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-276.
- **Docs:** design-doc §6.1 (History); build plan (row 19; the security-reviewer list; the Slice 3
  note).

## docs-consistency, pass 1 (base `546d940`)

### Fixes

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | contradiction | design-doc §6.1, History | Left out DL-276's "no parent is the top level" and that the value is resolved when read | **Fixed:** both said, in §6.1 and in DL-276 |

### Decisions for the owner

| # | Kind | Question | Options | Resolution |
|---|---|---|---|---|
| 1 | gap | In v1 only a deleted parent is unseen by a History reader: what does its entry show? | (a) "another requirement"; (b) its ID to those who'd see it in Trash; (c) as (a), through the view check | **Answered** (the owner's own option): its ID always, with a "Deleted" badge while it's deleted (`*_is_active` false); "another requirement" dropped; v2's per-person visibility revisits it (DL-276) |
| 2 | gap | Does DL-276 reach the Slice 3 project activity feed? | (a) the same rule; (b) decide at Slice 3; (c) History only | **Answered:** (a); the Slice 3 note says so (DL-276) |
