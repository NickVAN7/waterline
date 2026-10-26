# Review record: DC-2026-10-26e — indexes on requirement and approval_request

- **Change:** the owner's answers at the start of S2-C1 (DL-192, under DL-37): an index on
  `requirement.parent_requirement_id`, and one on `approval_request (project_id, status)`. The
  tables aren't built yet; S2-C1's migration adds both. S2-C1 is parked for this change (DL-20).
  Docs only.
- **Base commit:** `378bca8`
- **Files:** `docs/decision-log.md` (DL-192), `docs/schema-doc.md` (`requirement`,
  `approval_request`), `docs/build-plan.md` (the S2-C1 row)
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** no fixes; 1 decision for the owner, decided.
- **Gates:** `uv run wl check` green.

---

## docs-consistency (base `378bca8`)

No fixes.

**Decisions:**

1. **`approval_request.project_id` without an index.** The first draft of DL-192 left it out,
   saying nothing in Slice 2 looks rows up by it; but S2-C12's approver replacement on marking a
   project export-controlled finds the project's pending requests, and the schema doc gives the
   column that purpose. Options: keep it out and find the requests another way; index
   `(project_id, status)` in S2-C1's migration; or decide in S2-C12. **Owner, Oct 26, 2026:
   index `(project_id, status)` in S2-C1** (DL-192 amended before its commit; the schema doc
   and the S2-C1 row say so).
