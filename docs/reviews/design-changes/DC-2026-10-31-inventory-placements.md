# Review record: DC-2026-10-31 — The inventory's unplaced items

- **Change:** TD-62's check at the start of `s2-web` (DL-157, DL-203): step 6's table against
  the docs and the built screens. Its Built rows match `frontend/src/app/router.ts`; nine v1
  items had no slice, each left to the owner (DL-197, DL-200, DL-201). The owner's placements
  (chat, Oct 31, 2026): "Show deactivated" on the built lists, the session list, and favorite
  projects join Slice 2, and the Documentation page goes at its end (DL-238; S2-C21a to
  S2-C21d, provisional); saved filters, CSV export, the turned-off module page, the Get started
  checklist, and the audit log page go in later slices (DL-239). Docs only.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `658e50b` (the `chore(deps)` fix before S2-C15).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 4 fixes, all fixed; 3 decisions for the owner, open.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-238, DL-239.
- **Docs:** build plan (slice overview, Slice 2 "Before starting", rows 21a to 21d, groups,
  reviewer lists, "Web screens", "Done when", "Later slices"); design-doc §1.1, §3, §4, §11;
  schema-doc (deferred tables); ui-design-guide UI-SHL-4, UI-SHL-8, §6; screen-inventory
  (introduction, step 6); tech debt (TD-62 resolved).

## docs-consistency, pass 1 (base `658e50b`)

### Fixes

| # | Kind | Where | Resolution |
|---|---|---|---|
| 1 | stale | screen-inventory's introduction: "the list S2-C15's check runs against", "S2-C15 to S2-C21" | **Fixed:** the check done in DC-2026-10-31 (TD-62, DL-238, DL-239); the range S2-C15 to S2-C21d |
| 2 | stale | schema-doc's deferred tables: `session.user_agent`, `ip_address` "its slice to be placed" | **Fixed:** S2-C21b (DL-238, specified at its re-cut); schema-doc added to DL-238's "Applies to" |
| 3 | stale | ui-design-guide UI-SHL-8 ("if a help link is ever added") and UI-SHL-4 (the user menu's items) | **Fixed:** the Documentation item is that help link, and joins the user menu from S2-C21d; §4 added to DL-238's "Applies to" |
| 4 | broken-ref | DL-239's "Applies to" left out design-doc §1.1, which the change edited | **Fixed:** §1.1 added (UI-SHL-13, also proposed, left out: the change doesn't edit it) |

### Decisions for the owner

| # | Question | Options |
|---|---|---|
| 1 | Where are S2-C21a to S2-C21d's actions and threat-model entries recorded? The build plan says each row's actions and threat-model pass are in `S2-plan.md`, which has none for them. | (a) each re-cut adds its rows to `S2-plan.md`'s two tables, in its `docs:` commit; (b) each checkpoint's review record holds them, and the build plan says so; (c) nothing extra |
| 2 | Which of the new rows get `spec-test-writer` and `security-reviewer`? Now 21d for the first, 21a and 21b for the second; 21a to 21c leave their actions to the re-cut. | (a) as listed, each row confirming at its start; (b) 21a to 21c on the `spec-test-writer` list too; (c) also 21c and 21d on the `security-reviewer` list |
| 3 | Which client IP does S2-C21b record in `session.ip_address` behind a proxy? | (a) the socket peer only; (b) a forwarded header from a configured trusted proxy; (c) decided at the S2-C21b re-cut, recorded in design-doc §4 |

## Owner decisions

None yet: the three decisions above are open.
