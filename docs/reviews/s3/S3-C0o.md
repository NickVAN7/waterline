# Review record: S3-C0o — The design trial's outcome

- **Checkpoint:** Slice 3, Checkpoint 0o (group `s3-polish`)
- **Base commit:** `4c4bd3a` (DC-2026-11-17b, the last commit before the checkpoint; DL-17)
- **Reviewers:** Impeccable's `critique` and `audit` first (`vue-screen` step 6, DL-381), then
  `security-reviewer` (the build plan names this row: a third-party plugin and its settings),
  `checkpoint-reviewer`, and `ui-reviewer`, one at a time on one snapshot (DL-105);
  `checkpoint-reviewer` re-reviewed the fix diff, its major finding fixed.
- **Totals:** Impeccable critique 27/40, 5 priority issues and 1 detector rule; audit 18/20, 1
  P2 and 3 P3; security-reviewer ready after fixes, 1 minor, 2 questions; checkpoint-reviewer
  pass 1 ready after fixes, 1 major, 1 minor; pass 2 ready, no findings; ui-reviewer pass with
  findings, 2 minor, 2 notes. Reviewers' findings and notes in all: 7, 5 fixed, 2 notes kept with
  reasons; Impeccable's 11: 6 fixed, 3 logged (TD-117 to TD-119), 2 to S3-C0p, 1 rejected.
- **Gates at close:** `wl check` green; `wl e2e` 114 passed locally; CI on the commit.

---

## Before the reviewers

- **Owner decisions during the checkpoint:**
  - Impeccable stays at **local** scope (Nov 18), and the reason goes in the developer guide: a
    committed `enabledPlugins` names only the marketplace, not the pinned commit, and would
    enable a third-party plugin for every clone. The owner's `/plugin install … --scope local`
    in a session installed it at project scope, then at user scope; the shell CLI installed it at
    local scope (`installed_plugins.json`: `scope: local`, `gitCommitSha` `414603bf…`). The
    leftover `enabledPlugins` was removed from `.claude/settings.json`; the guide says to use the
    shell CLI.
  - **DL-389** (Nov 18): `IMPECCABLE_HOME` isn't set (the engine cache is `~/.impeccable`). The
    relative `.impeccable/home` put a second engine in `backend/.impeccable/` when the shell was
    in `backend/`, since the launcher starts on every edit with the hook off. The row's "its cache
    in the repository" is changed in this commit (DL-362).
  - The critique's findings 2, 3, and 5 logged (TD-117 to TD-119); finding 1b goes to S3-C0p by
    `design-change`, after this commit (DL-8).
- **`PRODUCT.md` against the guide** (`vue-screen` step 6.1): current. This checkpoint changes
  UI-SHL-11's breakpoint, which `PRODUCT.md` names only as "decided", with no value.
- **The hook** (the row's check): silent all session, no message. It wrote no
  `hook.cache.json`, nothing in `.git/info/exclude`, no `frontend/.gitignore`, no
  `/tmp/impeccable-pre-*`. Its launcher did download the engine (0.1.18, SHA-256 `736ed785…f648`,
  the plugin's) on its first run, into the relative cache: `.impeccable/home`,
  `backend/.impeccable/home`, and later `frontend/.impeccable/home` (DL-389). Each removed;
  `git status --ignored` otherwise matched the baseline before and after each Impeccable run.
- **The trial's code** re-applied hunk by hunk from `results/trial.diff` (never merged or
  cherry-picked): F1, F2, F3, F4, F6, F8, F9 with F29's placement, and `frontend/CLAUDE.md`'s two
  rules; not F28.
- The implementing session's own checks (evidence, not verification): `wl e2e` failed once
  before any test (the e2e stack's migrate container exited 139; the rerun started), then on the
  keyboard step's 576 (the new default width at 1280 is 512, so 528), fixed. `wl
  docs-screenshots` retook eight shots; the My work and Trash shots differed only in the seed's
  date and were restored.

## Impeccable critique (dual-agent: A design review, B detector and CDP browser scans)

Score 27/40. Snapshot: `.impeccable/critique/` (not tracked). The live-server overlay was not
used (DL-381); B scanned the signed-in pages through the DevTools port instead.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1a | P1 | Approve by hand's confirmation put the no-criteria warning (this checkpoint's) above "The pending request is cancelled". | **Fixed:** the warning after the text. |
| 1b | P1 | Approve by hand over a pending request confirms in primary while Cancel request is danger, and doesn't name the approvers bypassed. | **To S3-C0p** (owner, Nov 18), with F14, by `design-change` after this commit. |
| 2 | P2 | A `?open=` link to a requirement under collapsed parents shows no row in the tree. | **Logged:** TD-117 (owner). |
| 3 | P2 | The full page has no line-length cap at 1920. | **Logged:** TD-118 (owner). |
| 4 | P3 | The blocked Request approval leads the pending action row, its reason last. | **To S3-C0p** with F14 (the section's next step). |
| 5 | P3 | The panel title's programmatic focus ring reads as an editable field. | **Logged:** TD-119 (owner). |
| D1 | advisory | Detector: `straggler` on 2 elements (a one-word last line). | **Rejected:** no UI rule; it moves with the width and the data. |

Also raised again, already S3-C0p's: F13, F14, F15, F16, F21.

## Impeccable audit

Score 18/20 (Accessibility 3, Performance 4, Theming 4, Responsive 3, Integrity 4).

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | P2 | ConfirmDialog's Cancel was described by the warning only, so a screen reader heard it and not the consequence. | **Fixed:** Cancel is described by the text, then the warning. |
| 2 | P3 | The default width was computed only at open: opened as the overlay, then widened, the pane kept the overlay's fit. | **Fixed:** recomputed when the window crosses into wide while nothing is stored; a spec. |
| 3 | P3 | The room was measured in px, the width drawn in rem: at a 20px text size the list kept 27rem. | **Fixed:** measured in rem; a spec. |
| 4 | P3 | On an empty description the dialogs' warning still said "its description has no heading". | **Fixed:** `noCriteriaWarning()` worded for an empty description, as F11's note. |

## security-reviewer, pass 1 (base `4c4bd3a`)

Verdict: ready after fixes.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | minor | config | The guide said the engine is checked against the plugin's SHA-256; the launcher checks only a download and its version's cache, and runs `$IMPECCABLE_BIN`, a binary beside it, or an `impeccable` on `PATH` without it. A developer with one of those would run unreviewed native code on every edit, believing the hash protects them. | **Fixed:** the guide says what the check covers, and the install checks `IMPECCABLE_BIN` is unset, no `~/.impeccable/bin/impeccable`, and `command -v impeccable` empty. Siblings: none (the only statement of the check). |

**Questions** (for the owner, in the report):
- The telemetry and update-check variable names come from S3-C0n's README (read from the
  engine's source), not the plugin's own files; the trial also set `"telemetry": false` in
  `.impeccable/config.json`, which S3-C0o's install doesn't.
- Every edit starts the launcher and the native engine with the session's environment, hook off
  or not (DL-389 records it): accepted knowingly?

## checkpoint-reviewer, pass 1 (base `4c4bd3a`)

Verdict: ready after fixes.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | major | tests | The two acceptance-criteria warning tables branched per case (`warned ? … : …`), and with criteria present `toContain('')` always passed: an Approve by hand that always showed an empty warning box would pass. | **Fixed:** each table split into the two warned cases and a plain test asserting no warning Alert at all, and Cancel (or the list) described only by the text. Siblings: `ConfirmDialog.spec.ts` gets the same no-warning case. |
| 2 | minor | docs | Four comments and a test title in `RequirementsView` still said 64rem. | **Fixed:** 80rem (DL-383). Siblings: the 64rem in `DocsArticleView` and UI-SHL's page nav is a different breakpoint, kept. |

**Sabotage checks** (in a temporary copy, its table):

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| Headings capped at h6 | UI-MD-1, DL-382 | `Math.min(6, …)` removed | `MarkdownView.spec.ts` | `shifts "## A\n###### B" at level 3 to ["H4","H6"]` |
| Guide pages keep their headings | DL-310 | the `env.level &&` guard dropped | `src/components`, `src/views/docs` | 24 tests, e.g. `MarkdownView docs mode … ids each heading` |
| Only the drag's own pointer moves it | F4 | `!owns(event)` removed from `dragMove` | `ItemPanel.spec.ts` | `… a second one's move is ignored` |
| The room measured in rem | DL-385 | `/ rem` removed | `ItemPanel.spec.ts` | `measures the room in rem, …` |
| No warning with criteria | DL-384 | the warning passed always | `ApprovalSection.spec.ts` | the criteria case, by `aria-describedby` (finding 1 covers the rest) |

## ui-reviewer, pass 1 (base `4c4bd3a`)

Verdict: pass with findings.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | minor | UI-FRM-5, UI-FRM-6 | Submitting Request approval with no approver read the no-criteria warning ("You can still go ahead") before "Choose at least one approver."; the spec accepted any order. | **Fixed:** the error first in the list's `aria-describedby`; the spec asserts it's the first. |
| 2 | minor | guide §8 | ConfirmDialog's `warning` and Cancel's description, now on every confirmation, were tested only through ApprovalSection. | **Fixed:** `ConfirmDialog.spec.ts` covers both, with and without a warning, the order on screen, and axe. |
| N1 | note | UI-SHL-7, DL-266 | The tree's scroll region is always a Tab stop, before the rows' one, both named "Requirements". | **Kept:** UI-TBL-1's scroll-region pattern, from the trial (F8's region); in S3-C33's manual pass. |
| N2 | note | §9 | Approve by hand's warning is never drawn in a browser (only jsdom). | **Kept:** the warning tone's pair is in `check_contrast.py`, and the same Alert is checked in the Request approval e2e. |

Its coverage gap "the rem spec resets the root font size after mounting" is **fixed**: reset in
`afterEach`. **For the manual pass** (S3-C33's sheet): the separator by mouse, touch, pen, and
two fingers at 1280 and 1920; the region's Tab stop; both warnings in NVDA and VoiceOver; 200%
zoom at 1280; text spacing on the Approval details and the tree's badges; forced colors on the
warnings and the transparent tabs and tree.

## checkpoint-reviewer, pass 2 (the fix diff)

Verdict: ready. No findings. It checked each resolution above (its own two, ui-reviewer's 1 and
coverage gap, security-reviewer's 1) against the fix diff.

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| The approver error read before the warning | UI-FRM-6 | the error id moved back to the end of the list's `aria-describedby` | `ApprovalSection.spec.ts` | `asks for an approver before sending, at the list` |

## Open questions for the owner

- security-reviewer's two questions above.
