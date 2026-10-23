# S2-C0b tree spike: SVAR DataGrid tree mode against PrimeVue TreeTable

Evidence for DL-174 (DL-150's checklist). Throwaway code: not part of the app, not linted or
tested, and not maintained as the app changes. It imports the app's own tokens, styles, and
PrimeVue preset from `frontend/src` and SVAR's mapping from `docs/ui/svar-theme.css`, so the
theme audit measures the real theme.

**Rerun** (from this folder): `npm ci`, then `npm run dev` (port 5199) and `node measure.mjs`
for `results.json`; for the production build, `npx vite build && npx vite preview --port 5198`
and `BASE=http://localhost:5198/ OUT=results-build.json node measure.mjs`. Page options:
`?w=svar|prime`, `&theme=dark`, `&deny=1` (the mock server refuses every move), `&fix=1` (the
TreeTable wrapper fixes below), `&rows=2000`, `&open=none`, `&rebuild=1` (TreeTable rebuilds every node on a move).

**Versions:** `@svar-ui/vue-grid` 2.7.5 (grid-store 2.7.4), `@svar-ui/vue-core` 2.6.1, PrimeVue
5.0.2, `@primeuix/themes` 3.0.1, Vue 3.5.43; Chromium from Playwright 1.64.0, on WSL2. Data:
one checklist of 500 requirements, three levels (20 × 4 × 5), every branch open, unless noted.

## Results

Times are from the production build (`results-build.json`), one run; the dev server's
(`results.json`) are slower for both but in the same order.

| Check | SVAR DataGrid, `tree` | PrimeVue TreeTable | TreeTable with the wrapper fixes |
|---|---|---|---|
| Tree mode in the free package | Yes (MIT) | Yes (already installed) | — |
| Roles | `treegrid`, `row`, `gridcell` | `treegrid`, `row`, `cell` | same |
| `aria-level`, `aria-expanded` (parents only) | Yes | Yes | same |
| `aria-setsize`, `aria-posinset` | No | Yes | same |
| `aria-rowindex` | From **0** on body rows, none on the header: axe `aria-valid-attr-value` (critical), as in the Oct 10 spike | None (every row is in the DOM, so none is needed) | same |
| Accessible name on the grid | None (the wrapper's job) | None: `aria-label` lands on the outer `div` | "Requirements", through `pt.table` |
| axe (WCAG 2.2 AA and best practice), light and dark, a row selected | 1 violation: `aria-valid-attr-value` | 1 violation: `button-name` on the 100 expand buttons (critical) | **0** (the button is `aria-hidden`: it's `tabindex="-1"`, and the row carries `aria-expanded`) |
| Tab stops in the widget | 1 | 1 | 1 |
| Up and Down | Move between rows (and select them) | Move between rows | same |
| Left on an open parent | Moves to the previous column (grid-store's `arrowleft` and `arrowright` handlers call `focus-cell` on the next column); **doesn't collapse** | Collapses | same |
| Right on a closed parent | Moves to the next column; **doesn't expand** | Expands, **then moves focus to the next row** | Expands, focus stays (WAI treegrid) |
| Enter | Opens or closes a branch, only from the tree column | Selects the row | same |
| Tab out | Leaves the widget | Leaves the widget | same |
| Menu move (outside the widget), server allows | Works only by re-rendering from our data: **`move-item` does nothing in tree mode** (grid-store 2.7.4 skips the move when `tree` is set). Screen equals data; focus returned to the moved row by the wrapper | Works: our data drives the widget. Screen equals data; focus returned to the moved row by the wrapper | same |
| Menu move, server denies | Nothing moves; screen equals data; the message shows | Nothing moves; screen equals data; the message shows | same |
| Pointer drag | **Not available in tree mode**: the store forces `reorder` (and undo) off when `tree` is set (`e.tree&&(e.undo=!1,e.reorder=!1)`), so no drag handle renders | Not available (TreeTable has no row drag) | — |
| Theme audit (colors outside our tokens), light | 0 | 0 | 0 |
| Theme audit, dark | 0 | 1: the header cell's bottom border, Aura's `{surface.800}` | 0 (`treetable.root.borderColor` mapped to `--color-border-subtle`) |
| License notice | None | None | None |
| First render, 500 rows | 0.18 s | 0.63 s | 0.66 s |
| First render, 2,000 rows (the cap, DL-159), all open (`renderMsAtCap`, the median of three) | 0.29 s | **2.1 s** | — |
| First render, 2,000 rows, all closed (`renderMsAtCapClosed`) | 0.10 s | 0.22 s | — |
| Menu move at 2,000 rows, all open (30 ms mock server included; `moveMsAtCap`) | 0.12 s (a full re-render) | 0.06 s, the node objects spliced in place; 0.92 s with every node rebuilt (`moveMsAtCapRebuilt`, `&rebuild=1`) | — |

## What it means

- SVAR's two reasons to be chosen for the tree, row drag and its own move action, are both
  switched off in the free package's tree mode. Its tree is a read-only view that re-renders on
  every move, with column-style arrow keys and a critical axe defect.
- TreeTable follows the WAI treegrid keyboard pattern, adds `aria-setsize` and `aria-posinset`,
  and passes axe with three small wrapper fixes (the table's name, the hidden expand button, the
  Right arrow) and one preset entry. It's already a dependency.
- TreeTable's cost is the first render with every branch open: 2.1 s at the 2,000-row cap, 0.2 s
  with branches closed. Moves are fast as long as the wrapper splices nodes in place instead of
  rebuilding them.
