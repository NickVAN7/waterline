# Review record: DC-2026-10-22f — TreeTable approved, and how the tree opens

- **Change:** the owner's answers to `docs/reviews/s2/S2-C0b.md`'s open questions, recorded as
  DL-175: DL-174 approved; the tree opens at the top level, and "Expand all" opens the deeper
  levels in steps, built in S2-C17. Docs only.
- **Base commit:** `269aee1`
- **Files:** `docs/decision-log.md`, `docs/build-plan.md` (S2-C17), `docs/reviews/s2/S2-C0b.md`
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 1 fix, applied; 1 decision for the owner.
- **Gates:** `uv run wl check` green.

---

## docs-consistency (base `269aee1`)

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | internal | DL-175's Decision | "Only the top level open" could read as the top-level branches expanded, showing the second level, against "Expand all opens the second level". | **Fixed:** "only the top-level rows showing (every branch closed)". Siblings: the S2-C17 row said "the top level only"; reworded the same way. |

**Decisions for the owner** (left undecided):

1. **What pass mark does S2-C17 use for "the page never freezes"?** DL-175 and the row name a
   measurement with no criterion. Options: (a) a number now, e.g. no main-thread task over N ms
   during "Expand all" at 2,000 rows, written into the S2-C17 row: checkable and testable, but
   picked before any data; (b) S2-C17 records what it measures and reports it to the owner, with
   no gate: less work now, but "never freezes" then rests on the session's own claim. Needed
   before S2-C17.
