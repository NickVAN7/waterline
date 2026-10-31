# Review record: S2-C0e — Shell

- **Checkpoint:** Slice 2, Checkpoint 0e (group `s2-prep`; PR #11)
- **Base commit:** `4f31b2b` (S2-C0d's commit)
- **Reviewers:** `security-reviewer`, then `checkpoint-reviewer`, then `ui-reviewer`, on one
  snapshot (DL-105).
- **Totals:** `security-reviewer`: no findings. `checkpoint-reviewer`: 3 findings (2 major,
  1 minor), fixed. `ui-reviewer`: 2 findings (minor), fixed, and 2 notes, no change; 2 coverage
  gaps left for the manual pass. `checkpoint-reviewer` pass 2 (the fix diff): no findings.
- **Gates at close:** `uv run wl check` green; `uv run wl e2e` green (76 tests, both themes) with
  the owner's key in `.env`; CI on the checkpoint commit, with the owner's
  `VITE_PRIMEUI_LICENSE` secret.

---

## Spec tests

No `app/rules/` or `app/authz/` change, so `spec-test-writer` didn't run.

## Outside the row's scope, and why

- `ChangePasswordView` (the forced change, on the same card as sign-in) gets the same smaller
  `h1` as sign-in: the card's sizes are one rule, the app's name the largest text on it.
- `docs/ui/check_contrast.py` gains danger text on the hover and selected surfaces (Sign out's
  tone on a focused menu item): frontend `CLAUDE.md`, a new color pair is added in the same change.

## Evidence the new end-to-end checks can fail (main session's, not verification)

- With no key in `.env`, `wl e2e sign-in projects` failed the license check in both themes
  (`#p-license-host` rendered); with the owner's key, all 76 tests passed.
- With `m-auto` removed from `ModalDialog`, the centering check failed
  (`projects.spec.ts`, the create dialog).

---

## security-reviewer, pass 1 (base `4f31b2b`) — verdict: ready

No findings, no questions. It searched every file in the snapshot, dot folders included, for the
real `.env`'s key (printing file names only): it's in none. CI runs on `pull_request` with
`contents: read`, so a fork's PR never gets the secret.

## checkpoint-reviewer, pass 1 (base `4f31b2b`) — verdict: ready after fixes

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | major | **No test notices if the org name moves back to the far end of the header** (`AppLayout.vue`): moved back after the `flex-1` spacer, all 411 tests in `src/app` and `src/views` passed. Fix: assert the order in the shell test. | **Fixed:** the order in the DOM stays the same with the spacer between, so the end-to-end flow (`projects.spec.ts`) now checks the org name sits within 40 px of "Waterline"; `router.spec.ts` also checks the text order. Sabotage check (main session's): the reviewer's change fails the e2e check. Siblings: no other header item's position is a rule. |
| 2 | major | **Sign-in and the forced change drop `PageHeader`, but UI-SHL-8 and the developer guide say every page's `h1` is in one.** Fix: write the exception down. | **Fixed:** UI-SHL-8 names the auth card's pages as the one exception (a plain `h1`, `text-xl`, below the app's name; DL-137), and the developer guide's "Adding a screen" says so. Siblings: `ProjectHeader`'s own `h1` is already recorded (TD-49). |
| 3 | minor | **The license-key test cleaned up in a `try/finally` inside the test.** Fix: `vi.unstubAllEnvs()` in a hook. | **Fixed:** in the spec's `afterEach`. Siblings: no other test stubs the environment. |

**Sabotage checks** (in a throwaway copy of the snapshot):

| Behavior | Source | Change made | Caught by |
|---|---|---|---|
| Header reads "Waterline", then the org's name | UI-SHL-4, DL-137 | `<OrgSwitcher>` back after the `flex-1` spacer | **none** (finding 1, fixed) |
| PrimeVue gets the license key | DL-135 | `license: undefined` in `createApp.ts` | `gives PrimeVue the license key from the build-time setting (DL-135)` |
| Sign out has the danger tone and an icon | UI-SHL-4, DL-137 | `danger: true` removed | `sets Sign out apart with an icon and the danger tone` |

## ui-reviewer, pass 1 (base `4f31b2b`) — verdict: pass with findings

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | minor | **The org name heading the project popover is visual only** (`ProjectSelector.vue`, `LinkPopover.vue`): focus goes straight to a link and the dialog is named "Projects", so a screen reader never reads whose projects they are (WCAG 1.3.1, 2.4.6). Fix: the heading in the popover's description. | **Fixed:** `LinkPopover` wraps its `header` slot in an element whose id is the popover's `aria-describedby`; the e2e flow asserts the description is "Acme Manufacturing". Siblings: `OrgSwitcher` has no header. |
| 2 | minor | **The new selector specs asserted CSS classes, not what the user sees**: a `pl-4` wrapper or a dropped `underline` would pass. Fix: check the layout in the e2e run. | **Fixed:** the e2e flow checks "All projects" is underlined and a project row isn't, and that "New project" starts at a row's left edge with the same inset; the class-asserting unit test is gone. Sabotage check (main session's): "New project" at `px-4` fails the inset check. |
| 3 | note | The auth pages hand-write a `text-xl` `h1`. | Recorded in UI-SHL-8 (checkpoint-reviewer finding 2). |
| 4 | note | Sign out's tone comes from our slot content, not the preset; contrast worked out by hand above 4.5:1. | No change. |

**Out of scope, fixed:** two comment lines past the line width (`AppLayout.vue`, `UserMenu.vue`);
§9 of the guide said 136 contrast checks (now 140).

**Coverage gaps it named:** no e2e axe run with the selector or user menu open (left: their
token pairs are in `check_contrast.py`); no test of a dialog taller than the viewport (left, for
the manual pass).

**Needs the manual pass** (S2-C22): the selector with a screen reader (the org name now in its
description, All projects a link, New project a button, the focus order); Sign out's red in both
themes at rest, hover, and focus; the header at 320 px and 400% zoom; a dialog taller than the
viewport; the auth card at 320 px with a text-spacing override; forced colors.

## checkpoint-reviewer, pass 2 (the fix diff, `reviewed-1` to `reviewed-2`) — verdict: ready

No findings. Every pass-1 resolution checked, its and `ui-reviewer`'s. It noted the text-order
assertion in `router.spec.ts` doesn't catch a spacer (the e2e check does, as the record says), and
that the e2e flow's exact left-edge comparison is the one assertion to watch for flakiness in CI.

| Behavior | Source | Change made | Caught by |
|---|---|---|---|
| The project popover is described by its org-name heading | ui-reviewer 1; WCAG 1.3.1, 2.4.6 | `:aria-describedby` removed from `<Popover>` in `LinkPopover.vue` | `projects.spec.ts`, "a project is created from the project selector, and opens", both themes |

---

## Open questions for the owner

None from this checkpoint. S2-C0d's three (`docs/reviews/s2/S2-C0d.md`) are still open.
