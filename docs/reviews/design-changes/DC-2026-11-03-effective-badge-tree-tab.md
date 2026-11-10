# Review record: DC-2026-11-03 — An item's effective restriction badge; the tree's Tab stops

- **Change:** the owner's answers during S2-C18's review (Nov 3, 2026): a content item's
  restriction badge shows its effective restriction, returned by the item's read, and the
  restriction dialog's None reads as the project's level (DL-265, from checkpoint-reviewer's
  finding 1); the requirement tree's rows keep one Tab stop, plus the focused row's ID link
  (DL-266, from checkpoint-reviewer's finding 2 and ui-reviewer's note). S2-C18 parked for it
  (DL-20). Docs only.
- **Kind:** docs only, plus the `ui-reviewer` agent's checklist line (no tooling code, so no
  `checkpoint-reviewer`, DL-18).
- **Base commit:** `0bfd5cc` (DC-2026-11-02k).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 2 fixes, both fixed; 3 decisions for the owner, all decided.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-265, DL-266.
- **Docs:** design-doc §3.1 (effective restriction); ui-design-guide (UI-STY-3, UI-FBK-6, the
  `RequirementsTree` row); build plan (row 18); `.claude/agents/ui-reviewer.md` (UI-STY-3's
  exception).

## docs-consistency, pass 1 (base `0bfd5cc`)

### Fixes

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | contradiction | ui-design-guide UI-STY-3, `ui-reviewer.md` | "Never hand-roll a roving tabindex" against DL-266's own `tabindex="-1"` on the links | **Fixed:** the exception in both, citing DL-266; DL-266 supersedes UI-STY-3 in part, and names it in "Applies to" |
| 2 | internal | DL-266 | Its title said one Tab stop; the decision adds the link's | **Fixed:** retitled "rows keep one Tab stop, plus the focused row's link"; the spike's one stop was the rows', before the links existed |

### Decisions for the owner

| # | Question | Owner's answer (Nov 3, 2026) |
|---|---|---|
| 1 | Whose link is in the Tab order when focus and selection differ, or nothing is selected? | **The focused row's** (as recommended): DL-266, the ui-design-guide row, and the build plan say "focused" |
| 2 | Where the effective restriction comes from | **An API field** (as recommended): `effective_restriction_level` and `effective_restriction_categories` on `RequirementRead`, from `rules/restriction.py`'s `effective()`; in DL-265, design-doc §3.1, and the build plan's row 18 |
| 3 | The dialog's None when the project has no level | **"Same as the project (no level)"** (as recommended): DL-265 and design-doc §3.1 |

No pass 2: the answers reword the entries the pass reviewed, and add no rule it didn't see
(DL-108).
