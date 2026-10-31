# Review record: DC-2026-10-31c — The tree's move menu, and where its specs run

- **Change:** the owner's answers at the start of S2-C15 (chat, Oct 31, 2026): S2-C15's move
  menu has Move up and Move down, and the tree's theme audit moves to S2-C17, the first page
  that renders the tree; then the answers to docs-consistency's three decisions: the menu is
  `MoveToMenu`, built now and reused by the board; the tree's keyboard and move specs stay
  component specs; S2-C17's menu gains Move to bottom, and design-doc §6 stops calling the tree
  draggable. All in DL-243. Docs only.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `e0715ab` (DC-2026-10-31b).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 0 fixes; 3 decisions for the owner, all decided before the commit and folded into
  DL-243 (not yet committed when they were raised).
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-243.
- **Docs:** build plan (S2-C15, S2-C17); design-doc §6 ("Manual ordering"); ui-design-guide §9
  (the keyboard and move/cancel row); testing strategy (the wrapper specs).

## docs-consistency, pass 1 (base `e0715ab`)

### Fixes

None.

### Decisions for the owner

| # | Question | Options |
|---|---|---|
| 1 | Is the tree's menu `MoveToMenu`? The ui-design-guide §8 list says the tree comes with it; the first draft of DL-243 built it with the board. | (a) the tree's own menu, `MoveToMenu` pulled out in Slice 3; (b) `MoveToMenu` built now for the tree and reused by the board; (c) two menus for good |
| 2 | Do the tree's keyboard and move/cancel specs also run end to end, as §9 says for a wrapper? | (a) component specs are enough, the exception written into §9 and the testing strategy; (b) S2-C17 adds an end-to-end keyboard and move spec |
| 3 | Does the tree's menu include Move to bottom? Design-doc §6 gives every draggable list the full set and calls the tree draggable. | (a) add Move to bottom to S2-C17; (b) record that the tree has no drag and keep the set |

## Owner decisions

1. Decision 1: option (b), `MoveToMenu` built in S2-C15 (DL-243).
2. Decision 2: option (a), component specs are enough (DL-243; §9 and the testing strategy say
   so).
3. Decision 3: option (a), Move to bottom in S2-C17, and design-doc §6's tree has no drag
   (DL-174, DL-243).
