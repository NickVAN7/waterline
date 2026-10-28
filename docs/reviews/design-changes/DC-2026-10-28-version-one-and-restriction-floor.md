# Review record: DC-2026-10-28 — a new item at version 1, and the restriction floor

- **Change:** the owner's answers to S2-C5's two open questions (chat, Oct 28, 2026): a new
  item starts at `version` 1 (DL-207), and an item's stored level is never below the project's
  (DL-208). Both change code S2-C5 built, so the code is bundled into S2-C6, the next planned
  checkpoint (DL-131); this change records it in the build plan and doesn't touch the code.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `81ec572` (S2-C5).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 3 fixes (3 fixed) and 2 decisions for the owner.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-207 (create sets `current_revision_id` with `direct_update`, so a
  new item starts at `version` 1), DL-208 (an item's stored level is null or at least the
  project's: a lower one is a 422 `validation_error` of type `below_project`, and raising a
  project's level raises its items stored below it, each logged).
- **Docs:** design-doc §3 "Optimistic locking" and §3.1 "What's restricted"; schema-doc
  `requirement` (`restriction_level`, `current_revision_id`); build plan (the direct-update
  helper, S2-C6's row); `backend/CLAUDE.md` (optimistic-locking bypasses); `new-area` skill;
  `docs/reviews/s2/S2-C5.md` ("Owner decisions during review").

## docs-consistency, pass 1 (base `81ec572`)

### Fixes

| # | Kind | Where | Resolution |
|---|---|---|---|
| 1 | contradiction | design-doc §3.1, the `new-area` skill: "a 422 `below_project`" reads as a new error code, while a 422 is `validation_error` with a field type (build plan "API conventions"; DL-161's `use_approve`) | Fixed: "a 422 `validation_error` of type `below_project` on the level field" in both; the build-plan row keeps the short form, as it does for `use_approve` |
| 2 | gap | `new-area` skill carried only the 422 half of DL-208, so a new item type (task, test case) would miss the project-raise cascade | Fixed: the skill's bullet adds raising the item type's rows when the project is raised |
| 3 | gap | build plan S2-C6 tied the developer guide's "Direct updates" paragraph to the restriction PUT alone | Fixed: the row says the paragraph covers restriction writes and the first revision pointer (DL-207) |

### Decisions for the owner

| # | Question | Options |
|---|---|---|
| 1 | Does the project-raise cascade also raise soft-deleted items (in Trash)? | (a) the cascade opts in to deleted rows (a second non-trash `include_deleted` query, and history on items no one can view, DL-206); (b) the cascade skips them and restore (S2-C8) raises a restored item to the project's level, logged; (c) a restored item may sit below the floor (the effective level is still right) |
| 2 | Does the cascade move each item's `updated_at`, and how is it written? | (a) like the restriction PUT, decided once before S2-C6 (already open in `backend/CLAUDE.md`); (b) never moves it (the user didn't edit the items); (c) always moves it |

Both are left for the owner, undecided; neither blocks this change, since S2-C6 builds the
cascade.

## Open questions for the owner

- The two decisions above, due before S2-C6.
