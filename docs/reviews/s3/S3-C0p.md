# Review record: S3-C0p — The design trial's open findings: the panel

- **Checkpoint:** Slice 3, Checkpoint 0p (group `s3-polish`)
- **Base commit:** `b07a442` (DL-395, the last commit before the checkpoint; DL-17)
- **Reviewers:** Impeccable's `critique` (two isolated sub-agents: A, the design review; B, the
  detector) and `audit` first (`vue-screen` step 6, DL-381), then `checkpoint-reviewer` and
  `ui-reviewer` in parallel on one snapshot (DL-105, DL-392). `security-reviewer` didn't apply:
  the diff touches no trigger, and History's read moved to S3-C0q (DL-395). No re-review: the two
  majors were an e2e test and a docs line (the `checkpoint` skill, step 5).
- **Totals:** Impeccable critique 27/40 (as S3-C0o's), 5 priority issues, 7 minor notes,
  detector 0 findings; audit 17/20, 2 P2. checkpoint-reviewer ready after fixes, 1 major, 1
  minor; ui-reviewer pass with findings, 1 major, 4 minor, 2 notes. Reviewers' findings: 7, all
  fixed (one in part, the rest logged as TD-124); notes kept with reasons.
- **Gates at close:** `wl check` green; `wl e2e e2e/requirements.spec.ts e2e/approvals.spec.ts`
  14 passed locally; the frontend's 1,496 specs green; CI on the commit.

---

## Before the reviewers

- **`PRODUCT.md` against the guide** (`vue-screen` step 6.1): current. Its "one primary button
  per form or section" already covers F14's rule.
- **Impeccable's plugin:** the local install is the pinned commit (`gitCommitSha`
  `414603bf…`); `IMPECCABLE_BIN` unset, no `~/.impeccable/bin/impeccable`, none on `PATH`.
  Afterwards `git status --ignored` showed nothing new outside `.impeccable/`.
- **Screenshots:** `wl docs-screenshots` regenerated `approval` and `requirement-panel` (light
  and dark), viewed after each run. `my-work` and `trash` came out changed only in their dates
  (the demo data's "today") and were restored, so the commit holds only shots this checkpoint
  changes.
- **The session's self-review** (DL-106): one change named for the reviewers: Request approval is
  now two elements (the next step, and the blocked one at the end of the row), so after a request
  the opener is gone and the dialog's fallback focus takes over. ui-reviewer raised it (finding
  2), fixed below.

## Impeccable critique

Method: dual-agent (A: design review · B: detector), no browser: A reviewed from source, and B's
detector ran its regex rules only on `.vue` files (contrast and text-size rules need a rendered
page). Snapshot: `.impeccable/critique/2026-11-20T01-17-28Z__…requirementdetail-vue….md`
(ignored by git).

| # | Heuristic | Score |
|---|---|---|
| 1 | Visibility of system status | 3 |
| 2 | Match system / real world | 3 |
| 3 | User control and freedom | 3 |
| 4 | Consistency and standards | 3 |
| 5 | Error prevention | 3 |
| 6 | Recognition rather than recall | 3 |
| 7 | Flexibility and efficiency | 2 |
| 8 | Aesthetic and minimalist design | 2 |
| 9 | Error recovery | 3 |
| 10 | Help and documentation | 2 |
| | **Total** | **27/40** |

| # | Finding | Resolution |
|---|---|---|
| P1-1 | The ID and status come before the title that takes focus: a screen reader opening the panel doesn't hear them. | **Fixed:** the title's `aria-describedby` names the meta row (`ItemPanel`); spec. |
| P1-2 | The panel's title at `text-2xl` (32px) wraps a long title to four or five lines in a 400–560px pane. | **Owner decision, DL-396:** `text-xl` in the panel, `text-2xl` on the page. UI-SHL-11 and the row updated (DL-362). |
| P2-3 | The two-column grids switch on the window's width, not the panel's. | **Logged:** TD-121 (owner, Nov 19). |
| P2-4 | Heading sizes don't follow the tokens' h1/h2/h3 roles. | **Logged:** TD-122 (owner, Nov 19). |
| P2-5 | An approver who is also an admin sees five actions, two meaning "approve". | **Declined by the owner** (DL-396): F14 stands. |
| minor | "Link copied." stays under the title for good, even after a swap. | **Fixed:** cleared on `swapped()`; spec. |
| minor | One 409 message says "approve it again" for every Approval action. | **Logged:** TD-123 (built before this row). |
| minor | The `external` icon for a same-tab link; Awaiting approval shown three times; "Editing <ID>" repeats the ID above it; the Change note's help always shown; no link from "Last approved" to its revision. | **Noted, no change:** none is one of the row's findings, and the owner took the critique's questions above. |

## Impeccable audit

17/20 (Accessibility 3, Performance 4, Theming 4, Responsive 3, Integrity 3).

| # | Finding | Resolution |
|---|---|---|
| P2 | Edit mode's `<dl class="contents">`: `display: contents` has dropped list semantics in older Safari and VoiceOver. | **Kept, for the manual pass** (VoiceOver), as ui-reviewer's note too: Chromium keeps it, and the e2e runs Chromium only (TD-13). |
| P2 | Grid columns follow the window (as critique P2-3). | TD-121. |

## checkpoint-reviewer, pass 1

**Verdict:** ready after fixes.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | major · docs | The root `CLAUDE.md`'s Status still named S3-C0p as next (DL-315). The next session would read the row as still to do. | **Fixed:** S3-C0p done; next S3-C0q, then Packages 4 and 5 from S3-C0r. |
| 2 | minor · lean | Three checks that can no longer change anything: `moreActions`' `!editing.value` (the menu is hidden while editing), the blocked button's `@click` (a blocked `Button` drops it), and `v-if="$slots.details"` in the edit form (its one caller always fills it). | **Fixed:** all three removed. Siblings: no other blocked `Button` in the diff has a click handler. |

### Sabotage checks

| Behavior | Change made (in its copy) | Caught by |
|---|---|---|
| Approve by hand's confirmation in the danger tone while a request is pending | `variant: 'primary'` always | "approves by hand once confirmed, with the version, saying a pending request is cancelled" |
| The header's Awaiting approval while a request is pending (DL-386) | `awaitingChanged` sets `false` | RequirementView "shows Awaiting approval … : true"; RequirementsView "a pending request the panel finds…" |
| Edit mode keeps the details grid, Priority first (F17) | the details slot moved before `PriorityField` | "hides the actions, heads the page 'Editing <ID>', and keeps the details grid in place" |

## ui-reviewer, pass 1

**Verdict:** pass with findings.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | major · UI-SHL-11 | `e2e/requirements.spec.ts`'s narrowing step looks for the overlay by "Stored payload", but while editing its name is "Editing <ID>": CI would go red. | **Fixed:** the step finds the overlay by its editing name, then by its title after Cancel; `wl e2e` on both changed files, 14 passed. Siblings: no other e2e finds the panel by name while editing. |
| 2 | minor · UI-FRM-14 | After a request, the opener is gone and focus falls to the Approval heading; nothing tests it. | **Fixed:** the dialog's fallback and `keepFocus` focus the blocked Request approval when it's there (its reason read with it), else the heading; spec, shown to fail without the fix. |
| 3 | minor · UI-FRM-6 | Edit mode's 422 focus and announcement follow the old field order (Description before Priority). | **Fixed:** the edit form's labels in screen order (the create form's unchanged: its Priority is still last); spec, shown to fail with the old order. |
| 4 | minor · traps (a confirmation naming people) | The by-hand confirmation names approvers without email or a Deactivated marker. | **Fixed in part:** a deactivated approver reads "(deactivated)"; spec. The email needs the API (`ApprovalRead` has none): **logged** TD-124, for S3-C0q, which changes that API. |
| 5 | minor · UI-SHL-11 | An empty `<header>` stays in the panel while editing, a gap above the form. | **Fixed:** the header itself is `v-if="!inPanel \|\| !editing"`. |
| note | `<dl class="contents">` | As the audit's P2: for the manual pass (VoiceOver). |
| note | The Awaiting approval badge arrives after the title has taken focus, so the title's description may be read without it. | **Kept:** it's visible text, read on browsing; the request loads after the panel opens. |

**For the manual pass** (ui-reviewer's list): the panel's title read with its ID and status; Tab
from the title to the icon buttons; "Link copied." announced, then cleared on a swap; edit
mode's "Editing <ID>" and its details grid under VoiceOver; the Approval section's Tab order
in each state; the divider and ghost button in forced colors; the action row at 320px and in a
400px pane; a long `text-xl` title beside the icon buttons at 200% and 400% zoom.

## Owner decisions during the checkpoint

- **DL-396** (Nov 19): the panel's title `text-xl`; an approver-admin keeps all five actions;
  the grids and heading sizes are tech debt (TD-121, TD-122).

## Open questions for the owner

None.
