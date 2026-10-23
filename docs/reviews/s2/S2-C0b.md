# Review record: S2-C0b — Tree spike

- **Checkpoint:** Slice 2, Checkpoint 0b (group `s2-prep`; PR #11)
- **Base commit:** `5df47df` (DC-2026-10-22e's commit)
- **Reviewers:** `checkpoint-reviewer`, on one snapshot (DL-105). `security-reviewer` didn't run
  (the build plan doesn't name S2-C0b, and the diff touches no security-relevant code);
  `ui-reviewer` didn't run (no `frontend/src/` or `frontend/e2e/` change; the spike only imports
  `frontend/src`).
- **Totals:** `checkpoint-reviewer`: 3 findings (all minor), all fixed; 2 questions, one answered
  by a fix, one for the owner. No re-review (minor findings and docs only, DL-105).
- **Gates at close:** `uv run wl check` green; CI on the checkpoint commit.

---

## Spec tests

No `app/rules/` or `app/authz/` change, so `spec-test-writer` didn't run.

## Outside the row's scope, and why

- None. The docs that named the tree's widget as undecided (UI-SVR-2, UI-SVR-4, the component
  list, §10 item 5(g), the S2-C15 row, "Web screens", the testing strategy, `ui-reviewer`) now
  state DL-174's result, which the row asks for ("decides S2-C15").

## The spike

`docs/spikes/S2-C0b-tree/`: a scratch Vite app on the app's own tokens, styles, and PrimeVue
preset, its measurement script, and both runs' results (`results.json`, dev server;
`results-build.json`, production build). The result, `results.md`, is DL-174.

---

## checkpoint-reviewer, pass 1 (base `5df47df`) — verdict: ready after fixes

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | minor | **`npm run measure` runs the wrong thing** (`package.json`). It runs `playwright test`, with no config or tests; the measurement is `node measure.mjs`. Fix: point it there. | **Fixed:** `"measure": "node measure.mjs"`. Siblings: `results.md` and `measure.mjs`'s header already said `node measure.mjs`. |
| 2 | minor | **One number in `results.md` had no recorded measurement** (the 0.94 s rebuild-every-node move). Neither JSON held it, and no variant reproduced it, but S2-C15's "splicing the node objects in place" rests on it. Fix: record it or say it wasn't kept. | **Fixed:** a `&rebuild=1` variant in `PrimeTree.vue` and `moveMsAtCapRebuilt` in `measure.mjs`; both runs re-measured (0.92 s rebuilt, 0.06 s spliced, production build) and `results.md` and DL-174 updated to the new run. Siblings: every other timing in `results.md` now names its JSON key. |
| 3 | minor | **The testing strategy limited theme audits and keyboard and move specs to SVAR wrappers** (`testing-strategy.md:145`), while S2-C15 asks them of the TreeTable wrapper. Fix: widen it and add it to DL-174's "Applies to". | **Fixed:** both. Siblings: `frontend/CLAUDE.md` and design-doc §2 describe SVAR's scope only, which DL-174 doesn't change. |

**Sabotage checks** (in a throwaway copy of the snapshot; the evidence tool, since there's no
product code):

| Behavior | Source | Change made | Caught by |
|---|---|---|---|
| The fixed TreeTable passes axe because its expand button is hidden | `results.md`; S2-C15 row | `togglePt` set to `{}` in fix mode | `measure.mjs`: `prime_fixed.axe` reported `button-name (critical, 100 nodes)` |
| The dark header border uses our token | `results.md`; S2-C15 row | The preset's `treetable` mapping removed | `measure.mjs`: `prime_fixed.theme_dark.unmapped` reported `border-bottom-color: rgb(39, 39, 42)` |

The reviewer also read grid-store 2.7.4's source and confirmed `e.tree&&(e.undo=!1,e.reorder=!1)`
and the skipped `moveItem` in tree mode, and checked the results table against
`results-build.json`.

**Questions:**
1. *Which UI-SVR rules govern `RequirementsTree`, and is its menu the shared `MoveToMenu`?*
   **Answered by a fix:** UI-SVR-2 now says the tree still follows UI-SVR-5 (the server decides
   each move) and UI-SVR-6 (the menu outside the widget), and the component list gives
   `RequirementsTree` the shared `MoveToMenu`. The arrow-key claim it didn't verify now cites
   grid-store's `arrowleft`/`arrowright` handlers in `results.md`.
2. *Does the tree open with its branches closed?* Open, below.

## Open questions for the owner

- **Approve DL-174** (the requirement tree is PrimeVue TreeTable), the spike's result.
- **How does the requirement tree open?** With every branch open, TreeTable's first render is
  2.1 s at the 2,000-row cap (0.6 s at 500 rows); with branches closed, 0.2 s. Options: (a) open
  the top level only, with "Expand all"; (b) everything open; (c) remember each user's choice.
  Needed by S2-C17 (the requirements page).
