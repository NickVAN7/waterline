# Review record: DC-2026-10-22c — version checks on restriction and approve

- **Change:** the owner's answers to `DC-2026-10-22b-slice-2-plan-answers.md`'s two decisions,
  recorded as DL-168 (a restriction change is a direct update that doesn't bump `version`) and
  DL-169 (approving by hand takes the `version` the admin saw). Docs only.
- **Base commit:** `0d6de34`
- **Files:** `docs/decision-log.md`, `docs/design-doc.md`, `docs/build-plan.md`,
  `backend/CLAUDE.md`, `.claude/skills/new-area/SKILL.md`,
  `docs/reviews/design-changes/DC-2026-10-22b-slice-2-plan-answers.md`
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 5 fixes: 4 applied, 1 deferred to S2-C6; 1 decision for the owner.
- **Gates:** `uv run wl check` green.

---

## docs-consistency (base `0d6de34`)

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | internal | design-doc §2, "Optimistic locking" | "Two writes" left out the subtask counter (§3). | **Fixed:** names rank, the subtask counter, and the restriction. |
| 2 | contradiction | build plan, "Backend architecture", direct-update helper | Listed rank and the counter only. | **Fixed:** adds the restriction (DL-168); its `updated_at` behavior is the open decision below. |
| 3 | contradiction | `backend/CLAUDE.md`, the optimistic-locking rule and `check_version` | Would have had S2-C6's restriction `PUT` call `check_version`. | **Fixed:** the restriction is an explicit exception in both. |
| 4 | contradiction | developer guide, "Direct updates" | Lists rank and counters. | **Deferred to S2-C6:** the developer guide describes built code and changes with it (S2-plan F3); S2-C6's row names the paragraph. |
| 5 | contradiction | `new-area` skill; DL-168's "Applies to"; both entries' Source | The skill listed rank and counters; "Applies to" was incomplete; each Source cited both decisions. | **Fixed:** all three. |

**Decisions for the owner** (left undecided):

1. **Does a restriction change move `updated_at`?** `direct_update` needs `touch_updated_at` on
   every call. Options: (a) `True`, like the counter: the change shows as an update, matching its
   activity-log entry; (b) `False`, like rank: `updated_at` stays content-only. Needed before
   S2-C6.
