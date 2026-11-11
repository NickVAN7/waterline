# Review record: S3-C0d — The item side panel as a split pane

- **Checkpoint:** Slice 3, Checkpoint 0d (group `s3-polish`; PR #12)
- **Base commit:** `0ef3270` (S3-C0c, the last commit before the checkpoint; DL-17)
- **Reviewers:** `checkpoint-reviewer`, then `ui-reviewer` (the diff touches `frontend/src/` and
  `frontend/e2e/`), on one snapshot (DL-105); each re-reviewed the fix diff once, since fixes
  resolved a blocker and major findings and added a behavior (DL-355). `security-reviewer` not
  required: the build plan's Slice 3 list doesn't name S3-C0d, and the diff touches no router,
  auth store, route guard, API client, or rendered markdown. No spec tests: nothing in
  `app/rules/` or `app/authz/` changed.
- **Totals:** pass 1: checkpoint-reviewer 5 findings (1 blocker, 2 major, 2 minor) and 1
  question; ui-reviewer 7 findings (4 major, 3 minor) and 4 notes, overlapping on the blocker.
  10 fixed, 2 logged (TD-107, TD-108), 0 rejected. Pass 2: checkpoint-reviewer ready, 1 minor;
  ui-reviewer pass with findings, 3 minor (one shared with checkpoint-reviewer's): 2 fixed, 1
  logged (TD-109). No third pass (DL-105).
- **Gates at close:** `wl check` green; the requirements and Trash e2e specs green locally; CI on
  the commit.

---

## What was built

`ItemPanel` (`frontend/src/components/ItemPanel.vue`), shared by every item that opens from a
list: at 64rem and wider a split pane beside the list (an `<aside>` named "Requirement
PORTAL-RQ-3", sticky under the header), below 64rem a modal overlay (its `<dialog>`); one
teleport moves the content between them, so crossing the width keeps an open edit and its focus.
A separator resizes it (560px, 400 to 800px; drag, a click that steps 400 → 560 → 800, the arrow
keys; kept in `localStorage`). Its header: the ID and status (`meta`), Open full page, Copy link,
and Close as icon buttons, then the title, which takes focus on opening and on a swap. Close and
Esc emit `dismiss`; the list page changes the URL, so Close, Esc, Back, another ID, and Open full
page all go through its route guards, which ask **Discard your changes?** (`ConfirmDialog`, its
new `navigates` option) while the edit form is `dirty`. The tree marks the open row (the
selected background, a bold title, "Open" with a panel icon, `aria-current` on its link).

`RequirementDetail`'s header (DL-325, DL-326): Edit, Change status, and `MoreActionsMenu` (⋯:
Change restriction…, then Delete… after a separator, hidden when empty), and Priority, Reporter,
and Restriction ("None" when nothing applies) as a two-column definition list; on the page the
ID and status sit under the `h1`. Y6: `RequirementFields.vue` holds Title, Description, and
Priority for the create and edit forms, with `focus(field)` for the 422 focus. `ModalDialog`'s
`panel` option is gone.

Owner decisions: the Parent row waits for S3-C0e's `ancestors` (TD-106); at the review, a click
on the separator steps its width (DL-355), and the tight widths just above 64rem stay as decided
until the manual pass (TD-108).

## Behaviors and their proof

| Behavior | Source | Test | Proof it fails |
|---|---|---|---|
| A split pane at 64rem+, a named region, not a dialog; an overlay below | DL-321, DL-324 | `ItemPanel.spec` "is a complementary region…", "is a modal dialog…"; `RequirementsView.spec` "opens beside the tree…"; e2e side panel at 1280 and 900px | e2e checks both modes in a real browser |
| Close and Esc ask the page, never close it themselves | DL-323 | `ItemPanel.spec` "asks its page to close it on Esc…" (both modes) | sabotage: `@cancel` without `.prevent` |
| Esc that something inside used, or from a dialog opened from the panel, leaves the panel | UI-SHL-11, review finding | `ItemPanel.spec` "leaves an Esc…" (two); e2e Esc in Change restriction… | sabotage: the `defaultPrevented` check removed; the `closest('dialog')` check removed (e2e failed at the panel's visibility) |
| Close returns focus to the ID that opened it, or falls back; a swap moves it to the new ID | DL-324 | `ItemPanel.spec` "returns focus…", "falls back…", "after a swap…"; `RequirementsView.spec` "Close after a swap…" | sabotage: `swapped()` not called |
| Crossing the width keeps the content and the focus | UI-SHL-11, review finding | `ItemPanel.spec` "keeps its content…", "keeps focus where it was when the window…" (both ways); e2e narrowing with focus in Title | the focus cases failed before the fix |
| The separator: 560, 400 to 800, keys, clamped, remembered, blocked storage, drag, click steps | DL-322, DL-355 | `ItemPanel.spec` separator block | sabotage: the clamp removed; `keepWidth()` dropped |
| Swapping updates `?open` and the panel | DL-323 | `RequirementsView.spec` "another ID swaps…"; e2e | e2e |
| The open row: background, bold, "Open", `aria-current` | DL-324 | `RequirementsView.spec` "marks the open requirement's row…"; e2e | sabotage: the row class removed |
| Discard your changes?: wording, Keep editing first, Discard danger, each way out, each field | DL-323, TD-92 | `RequirementsView.spec` the unsaved-edits block (Close, swap, Open full page, Back; title, description, priority, change note); e2e swap with Keep editing then Discard | sabotage: the guard removed (5 failed); `dirty` always false (6 failed); per-field cases added after review finding 2 |
| A confirmation that navigates doesn't return focus late | frontend/CLAUDE.md (S1-C16 rule) | `ConfirmDialog.spec` "confirmed with navigates…"; e2e swap focus | sabotage: `navigates` ignored; found by the e2e first |
| ⋯ More actions: named, hidden when empty, separator before danger, focus back, Esc cancelled | DL-325 | `MoreActionsMenu.spec`; `RequirementView.spec` restriction and delete cases; e2e ⋯ from the keyboard | sabotage: Delete shown without `requirement.delete` |
| The header and definition list on the page | DL-326 | `RequirementView.spec` "shows the requirement…" (`definition()`), "marks a deactivated reporter" | assertions on each term's value |

## checkpoint-reviewer, pass 1 (base `0ef3270`)

**Verdict:** ready after fixes.

| # | Severity | Area | Finding | Resolution |
|---|---|---|---|---|
| 1 | blocker | correctness | At 64rem+, Esc in a dialog opened from the panel (Change restriction…, Delete…, Request approval) bubbles to the `<aside>`'s handler, which emits `dismiss`: the dialog and the panel both close (or Discard your changes? appears over the dialog). Confirmed by a probe spec. | **Fixed:** `escape()` ignores an Esc whose target is inside a `<dialog>`; an `ItemPanel.spec` case and an e2e step (Esc in Change restriction… in the split pane: the panel stays, focus on ⋯), the e2e shown to fail without the fix. Siblings: the overlay below 64rem is itself a modal, so only the topmost dialog gets `cancel`; no other container handles Esc itself. Rule added to `frontend/CLAUDE.md` |
| 2 | major | tests | `dirty` compares four fields, but only a title change was tested: cut to the title alone, all 241 requirement specs passed. | **Fixed:** an `it.each` over the title, description, priority, and change note, each alone asking before Close |
| 3 | major | docs | The developer guide still said `ItemPanel` is `ModalDialog` with `panel`, with one `close` event; none of the split pane, `label`, `swapped()`, the guards, `navigates`, `stubWidth`, `MoreActionsMenu`, or `RequirementFields`. | **Fixed:** the Side panels and Dialogs bullets rewritten, the components and test-helper lists updated |
| 4 | minor | lean | `ModalDialog`'s `panel` option has no user left. | **Fixed:** the prop, its classes, the heading's `tabindex`, and `focusTitle` removed; its side-panel spec case removed, the fallback case kept without it |
| 5 | minor | docs | The root `CLAUDE.md` Status still named S3-C0d next. | **Fixed:** S3-C0d done, next S3-C0e |

**Sabotage checks** (in a throwaway copy of the snapshot):

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| Swap, Close, and Back with unsaved edits ask first | DL-323 | `onBeforeRouteUpdate(keepEdits)` removed | `RequirementsView.spec.ts` | 5 tests ("Close with unsaved edits asks first…", "Keep editing…", "Discard changes…", "another ID…", "Back…") |
| Unsaved changes in any field are dirty | DL-323 | `dirty` compares the title only | `src/views/requirement` (241) | none: finding 2 |
| The width stays 400 to 800px | DL-322 | the clamp's upper bound 9999 | `ItemPanel.spec.ts` | "stops at its limit: ArrowLeft from 800 stays 800", "opens at the remembered width, kept within its limits" |

**Questions:** TD-92's resolution and UI-SHL-11 list Esc among the ways that ask, while DL-323
says Esc doesn't close the panel while editing; the code does both (Esc in the form does nothing;
Esc on the panel's own controls, with changes, asks). **Resolved:** that reading is the intended
one; UI-SHL-11 now says "Esc from outside the edit form (in it, Esc does nothing)".

## ui-reviewer, pass 1 (base `0ef3270`)

**Verdict:** pass with findings.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | major | UI-SHL-11, UI-FRM-14 | Esc in a modal dialog inside the wide panel also closes the panel (as checkpoint-reviewer 1). | **Fixed** with checkpoint-reviewer 1 |
| 2 | major | UI-SHL-11, UI-SHL-7 | From 64rem to about 75rem the 560px panel leaves the tree about 150px, and a stored 800px leaves none (a sideways scroll). | **Logged (TD-108), the owner's decision** (2026-11-11): kept as DL-321 and DL-322 decide until the slice's manual pass judges 1024 to 1280px and zoom |
| 3 | major | UI-SHL-11, WCAG 2.4.3 | Crossing 64rem with the panel open moves or drops focus: the teleport blurs the focused node, and `showModal()` or `close()` moves it again. | **Fixed:** the panel notes what had focus inside it before the move and focuses it again (or the title); `ItemPanel.spec` both ways, and an e2e step narrowing with focus in Title. Rule added to `frontend/CLAUDE.md` |
| 4 | major | UI-TBL-5, WCAG 2.5.7 | The drag resize has no single-pointer alternative (arrow keys aren't one). | **Fixed, the owner's decision (DL-355):** a click without a drag steps 400 → 560 → 800 → 400, kept as a drag is; `ItemPanel.spec` four steps; UI-SHL-11 and the user guide say so |
| 5 | minor | UI-FRM-17 | The icon buttons' tooltips are `title` only, never shown on keyboard focus (the `RowActions` pattern, now spreading). | **Logged (TD-107):** a focus-showing hint is its own component; S3-C33's tech-debt review |
| 6 | minor | UI-SHL-3 | The split pane is a new sticky layer UI-SHL-3 doesn't list. | **Fixed:** UI-SHL-3 lists it; a taller header than `--header-height` goes to the manual pass |
| 7 | minor | guide §8 | `MoreActionsMenu` has no spec of its own, no axe or token audit with it open, no e2e inside the panel. | **Fixed:** `MoreActionsMenu.spec.ts` (named, hidden when empty, the separator before danger only when not first, the danger color, focus back, Esc cancelled, axe open); an e2e step opening ⋯ from the keyboard in the split pane (position, axe, token audit) |

**Notes:** the separator's bare number (**fixed:** `aria-valuetext`, "560 pixels wide"); the
open row's state not on its link (**fixed:** `aria-current="true"`); an `aside` inside `main`
(a best-practice rule the project doesn't run; no change); a repeated Esc in the overlay under
Chrome's close-watcher rule (to the manual pass).

**Needs the manual pass** (carried to S3-C33's sheet): the requirements page at 1024 to 1200px
and at 1280px zoomed 125% and 150% (TD-108); zooming across 64rem with focus in the edit form;
Esc in every dialog opened from the wide pane, and in the Revisions compare's pickers; the
separator with NVDA and VoiceOver; forced colors on the separator, the open row, and the focus
ring; text spacing in a 400px panel; the header icon buttons from the keyboard (TD-107).

**Proposed rules:** both added to `frontend/CLAUDE.md` (Esc from a nested dialog; focus after
moved content).

## checkpoint-reviewer, pass 2 (the fix diff, reviewed-1 → reviewed-2)

**Verdict:** ready.

| # | Severity | Area | Finding | Resolution |
|---|---|---|---|---|
| 1 | minor | correctness | `dragStart` takes any button and `pointercancel` runs `dragEnd`, so a right-click or a cancelled press counts as a click and steps (and saves) the width. | **Fixed:** the primary button only; `pointercancel` puts the width back and saves nothing; three `ItemPanel.spec` cases (right-click, a cancelled press, a cancelled drag), each shown to fail against the old handlers. Siblings: no other pointer handler in `src/` |

**Resolutions checked:** blocker 1, majors 2 and 3, minors 4 and 5, and ui-reviewer's fixes, as
recorded above.

**Sabotage checks** (in a throwaway copy of reviewed-2):

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| Crossing the breakpoint keeps focus where it was | UI-SHL-11, ui-reviewer 3 | the refocus after the move removed | `ItemPanel.spec.ts` | "keeps focus where it was when the window narrows" and "…widens" |

**Questions:** none. Its note on `MoreActionsMenu.spec`'s "focus back on its button first" (an
assertion inside the action's callback, which might not fail the test): **fixed:** the callback
records where focus was, and the test asserts it after the call; sabotage-checked (the focus
line removed from `MoreActionsMenu`'s command: the case fails).

## ui-reviewer, pass 2 (the fix diff)

**Verdict:** pass with findings. Pass-1 majors 1, 3, and 4 and minors 6 and 7, and both notes,
checked fixed.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | minor | UI-SHL-11, DL-355 | A cancelled pointer or a right-click steps the width (as checkpoint-reviewer pass 2, 1). | **Fixed** with it |
| 2 | minor | UI-SHL-11, UI-FRM-14 | Crossing 64rem with a dialog from the panel open moves it out of the top layer: it may stay open but not modal, its Esc reaching the panel (unsure; needs a browser). | **Logged (TD-109):** the manual pass checks it at 1024px; fixed in the slice if it shows |
| 3 | minor | UI-SHL-3, UI-FBK-10 | UI-SHL-3 now lists the split pane, but no e2e runs `expectFocusNotObscured` in it. | **Fixed:** one ran already with focus on the separator (the pane open); a second now runs with focus back on a tree row beside it |

**Gaps noted:** the title fallback when the focused node is gone after a move, and widening with
focus kept end to end (jsdom only); the cancelled-pointer cases (now covered).

**Needs the manual pass** (added to S3-C33's sheet): crossing 64rem at 1024px with Change
restriction… open (TD-109); clicking the separator with NVDA and VoiceOver ("N pixels wide");
the separator's 1px line and its focus in forced colors.

## Owner decisions during review

- **TD-108** (ui-reviewer 2): keep the 64rem breakpoint and 400 to 800px as decided; judge at
  the manual pass.
- **DL-355** (ui-reviewer 4): a click on the separator steps its width.
- Before review, during the build: the Parent row goes to S3-C0e (TD-106).

## After the commit: found by the owner

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | major | UI-SHL-7, UI-SHL-11 | On a screen wider than the sidebar and 80rem, the split pane and the tree share `main`'s 80rem column, the rest of the screen empty. Escaped review: the e2e ran at 1280px, where the cap doesn't show. | **Fixed** in `fix(S3-C0d)`: owner decision DL-356, a split-pane list takes the whole width (route meta `fullWidth`); the e2e checks the panel's right edge at 1920px, failing without the meta (sabotage-checked by the implementing session: evidence, not verification; CI runs it). Siblings: the requirements page is the only split-pane list so far; later ones set the meta (UI-SHL-7). |
| 2 | major | UI-SHL-11 | Still not it, after #1: the panel sat inside `main`, under the page header, so it neither ran from the app header to the window's foot nor let the page header (New requirement) narrow beside it. | **Fixed** in a second `fix(S3-C0d)`: the `<aside>` is teleported to `AppLayout`'s column after `main` (`#side-pane`), DL-356 restated; the separator's line is now the panel's border (it drew a second line beside it). The e2e checks the panel's top against the header, its foot and right edge against the window, and `main` ending where it starts, at 1920px. Checked in a screenshot at 1920px by the implementing session (evidence, not verification). |
