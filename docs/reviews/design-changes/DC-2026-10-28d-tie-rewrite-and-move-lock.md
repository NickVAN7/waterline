# Review record: DC-2026-10-28d — the tie rewrite and the move lock

- **Change:** two owner answers in chat during S2-C7 (Oct 28, 2026), where the move endpoint
  had to differ from design-doc §6's "Ties" bullet: a drop between tied ranks rewrites the gap's
  siblings (DL-213), and moves run one at a time per project (DL-214). Docs only; S2-C7 (parked
  for this change) builds both.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `d79ab9c` (S2-C6).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 2 fixes (fixed) and 2 decisions for the owner.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-213, DL-214.
- **Docs:** design-doc §6 "Manual ordering" (the out-of-order neighbors rule, "Ties", a new
  bullet on moves); build plan (S2-C7); TD-67's Fix by.

## docs-consistency, pass 1 (base `d79ab9c`)

### Fixes

| # | Kind | Where | Resolution |
|---|---|---|---|
| 1 | superseded | `backend/CLAUDE.md`, the developer guide's "Direct updates", and the `new-area` skill list what skips `version` and which `updated_at` each passes, without a move's parent change (DL-214) | Fixed: each list names it (`touch_updated_at=True`); DL-214's "Applies to" lists the three |
| 2 | contradiction | design-doc §6's new bullet read as every ranked move taking the project lock, while DL-214 says a requirement move | Fixed: "Requirement moves run one at a time per project" |

### Decisions for the owner

| # | Question | Options |
|---|---|---|
| 1 | Do S2-C8's other parent-changing writes (a delete promoting children, a restore to the top level) take the tree lock and follow DL-214's `updated_at` and `version` rule? | (a) yes, one lock order and one rule for every tree write; (b) only moves lock, promote and restore are versioned ORM updates; (c) decide when S2-C8 starts |
| 2 | For tasks (Slice 3), which siblings does the tie rewrite (DL-213) and the cap's (DL-204) rewrite, and do task moves run one at a time? | (a) the project's tasks in rank order, with the same lock; (b) the same set, no lock; (c) decide in Slice 3 planning, §6 marked "requirements" meanwhile |

Neither blocks S2-C7; both go to the owner with the S2-C7 report.
