# Review record: DC-2026-11-12f — SVAR DataGrid for inline cell editing only

- **Change:** the owner's answer to DC-2026-11-12e's decision 1 (option b, Nov 12, 2026): the
  SVAR DataGrid is for lists where inline cell editing is the point; a list where manual row
  order is the point is PrimeVue's through our own wrapper (DL-375). Docs only.
- **Kind:** docs only (no `checkpoint-reviewer`, DL-18).
- **Base commit:** `13f3c70` (S3-C0j).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 2 fixes, both applied; 2 decisions for the owner.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## docs-consistency, pass 1 (base `13f3c70`)

| # | Kind | Finding | Resolution |
|---|---|---|---|
| 1 | superseded | UI-SVR-5 still lists `move-item`, the DataGrid's row move, among the actions to intercept. | **Fixed:** removed, citing DL-375; UI-SVR-5 added to DL-375's Applies to. |
| 2 | stale | §10 item 5(c) still describes grid row drag as wrapper work; TD-113's example icon is the grid's drag handle. | **Fixed:** 5(c) closed by DL-375 (the spike link kept); TD-113's example now the board's icons. |

**Decisions for the owner** (left undecided):
1. Does "a list where manual row order is the point is PrimeVue's" cover a list reordered only
   by a menu (the subtask checklist, S3-C24; phases, S3-C27; workstreams)? (a) only drag-ordered
   lists, a menu-only list native or PrimeVue under UI-STY-3; (b) every ordered list; (c) each
   list decided when its screen is specified, DL-375 the default for drag lists.
2. What the DataGrid wrapper sends the server, and whether it turns SVAR's row drag off: (a)
   record now (row reorder off; the cell-edit action intercepted, its name checked against grid
   2.7.5 in the first grid checkpoint); (b) leave it to the first screen that specifies an
   editable grid, with a tech-debt entry.
