# S3-C0i backlog spike: SVAR DataGrid against PrimeVue DataTable's row reorder

Evidence for the backlog's widget (DL-344's checklist), deciding S3-C19 and UI-SVR-2's backlog
line once the owner chooses. Throwaway code: not part of the app, not linted or tested, and not
maintained as the app changes. It imports the app's own tokens, styles, and PrimeVue preset from
`frontend/src`, SVAR's mapping from `docs/ui/svar-theme.css`, and the owner's PrimeUI license
key from the repository's `.env` (DL-135), so the theme audit measures the real theme.

**See it yourself** (from this folder, with the repository's `.env` in place): `npm ci`, then
`npm run dev`, and open:

| Address | Shows |
|---|---|
| <http://localhost:5197/?w=svar&fix=1> | SVAR DataGrid, with the handle the wrapper would draw |
| <http://localhost:5197/?w=svar> | SVAR as installed: the handle is there but blank (see "What it means") |
| <http://localhost:5197/?w=prime&fix=1&virtual=1> | PrimeVue DataTable as recommended: the virtual scroller and the two fixes below |
| <http://localhost:5197/?w=prime> | PrimeVue as installed, every row drawn |

Add `&deny=1` to have the mock server refuse every move, `&rows=2000` for the big backlog, and
`&theme=dark` for the dark theme. Drag a row by its handle (SVAR's six dots in the Title cell,
PrimeVue's three bars in the first column), or select a row and use the move buttons above the
list. Screenshots, a row selected: `screenshot-svar-light.png`, `screenshot-svar-dark.png`,
`screenshot-prime-light.png`, `screenshot-prime-dark.png`.

**Rerun the measurements** (dev server up): `node measure.mjs` writes `results.json`.

**Versions:** `@svar-ui/vue-grid` 2.7.5, `@svar-ui/vue-core` 2.6.1, PrimeVue 5.0.2,
`@primeuix/themes` 3.0.1, Vue 3.5.43, Chromium from Playwright 1.64.0, on WSL2; the dev server
(the S2-C0b spike found the production build faster for both, in the same order). Data: a flat
backlog of 500 tasks, or 2,000 with `&rows=2000`; a mock server answering every move in 30 ms.

## Results

| Check | SVAR DataGrid | PrimeVue DataTable | DataTable with the fixes and virtual scroller |
|---|---|---|---|
| Free package | Yes (MIT) | Yes (already installed) | — |
| Pointer drag, server allows | Works by its handle; screen equals data after the server answers | Works by its handle; screen equals data | same |
| Pointer drag, server refuses | Snaps back; the message shows | Snaps back; the message shows | same |
| Drag handle as installed | **Blank:** Willow's icons are an icon font from SVAR's CDN, which `:fonts="false"` (UI-SVR-3) leaves out and UI-STY-4 rules out; the wrapper draws its own (`fix=1`: a sized handle with our SVG) | PrimeVue's own SVG icon (three bars) | same |
| The drop's event | `move-item` on the drop carries **no `mode`** (before or after); only the previews do, so the wrapper keeps the last preview's | `row-reorder` with the drag and drop indexes | same |
| Move menu outside the widget, allowed and refused | Works; screen equals data; focus on the moved row | Works; screen equals data; focus on the moved row | same |
| Keyboard reorder of its own | None (Alt, Ctrl, or Shift with an arrow; Space; Enter) | None | None: the move menu is the way (UI-SVR-6) |
| Up and Down | Move between rows | Move between rows | same |
| Tab stops in the widget | 1 | 1 | 2: the virtual scroller's container (unnamed), then a second Tab reaches the rows; Shift+Tab from the third row went to the first, which kept its tab stop (checked by hand, not by `measure.mjs`) |
| Space on a row | **Drops focus to the page's `<body>`** | Selects the row | same |
| Roles | `grid`, `row`, `gridcell` | `table`, `row`, `cell` | same |
| Accessible name | None (the wrapper's job) | "Backlog", through `pt.table` | same |
| Selected row announced (`aria-selected`) | No | Yes | Yes |
| `aria-rowindex` | From **0**: axe `aria-valid-attr-value` (critical), as in the Oct 10 and S2-C0b spikes | None | None |
| axe (WCAG 2.2 AA and best practice), light and dark, a row selected | 1 violation: `aria-valid-attr-value` (critical) | 1: `empty-table-header` (minor), the handle column's header | **0** (the header named "Reorder", visually hidden) |
| Theme audit (colors outside our tokens), light | 0 | 0 | 0 |
| Theme audit, dark | 0 | 1: the header cell's border, Aura's `{surface.800}` | 0 (`datatable.root.borderColor` mapped to `--color-border-subtle`) |
| License notice | None | None (with the key) | None |
| First render, 500 rows | 0.15 s (19 rows drawn: it virtualizes) | 1.1 s (500 drawn) | 0.20 s (32 drawn) |
| First render, 2,000 rows (the median of three) | 0.14 s | **3.5 s** | 0.21 s |
| Menu move at 2,000 rows (the mock server's 30 ms included) | 0.05 s | 0.07 s | 0.06 s |

## What it means

- Both meet the checklist's core: pointer drag, a refused move snapping back, the menu outside
  the widget, the screen always equal to our data, and focus following the moved row.
- **PrimeVue DataTable** passes axe and the theme audit with two small fixes (a name for the
  handle column's header, one preset entry, as TreeTable needed in S2-C0b), and stays fast at
  2,000 rows with its virtual scroller, under which drag still works. Its wrapper's other work:
  name the scroller as the table's scroll region (UI-TBL-1) and keep one tab stop in the rows.
  It's the component every other list uses, so the backlog would look and behave like them.
- **SVAR DataGrid** is fast without configuration, but the wrapper has more to make right: draw
  the drag handle (its icons need an icon font from a CDN), keep the drop's missing `mode`, keep
  focus when Space is pressed, name the grid, announce the selected row, and patch or report the
  critical `aria-rowindex="0"` defect (UI-SVR-7), unchanged since the Oct 10 spike.
- **Recommendation:** PrimeVue DataTable with row reorder and its virtual scroller, through our
  own wrapper (S3-C19). The decision is the owner's, after seeing both (DL-344).

## Found on the way

- SVAR's own stylesheet (`@svar-ui/vue-grid/all.css`) has to be imported: without it the grid
  draws unstyled, its cells stacked, and the drag lands off target. The S2-C0b tree spike didn't
  import it either, so its SVAR numbers (the theme audit, the timings, the keyboard) were taken on the
  unstyled grid. Its decision, TreeTable, rested on SVAR's tree
  mode switching drag and moves off in code, which styling doesn't change.
