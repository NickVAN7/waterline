# S3-C0n trial: results

The trial's recorded results, written by the trial session from its own runs (2026-11-16 and
17) and accepted by the owner on 2026-11-17; the outcome is DL-381 to DL-385. The owner's
decisions are listed as decisions; the trial's code went to S3-C0o, and the findings marked "recorded only" (F13 to F18, F21) to
S3-C0p (DC-2026-11-17b). Each claim says who verified it. "Session" means the session that did the work: under
the root `CLAUDE.md`, that alone doesn't count as verified.

Clone: `~/scratch/impeccable-trial/waterline`, branch `trial`, at `aca8710` plus uncommitted
changes in 16 files. Impeccable 4.8.0 (`414603b`), engine 0.1.18.

**For the Results header:** Claude Code 2.1.326 · permission mode: auto · dates: 2026-11-13 to
2026-11-17.

## Results (rows 1 to 10)

| # | Result | Matches expected? | Notes |
|---|---|---|---|
| 1 | Baseline shots in `trial-shots/baseline/`: the panel open on PORTAL-RQ-2 at 375, 1280, and 1920, light and dark. | Yes | The guide's shots were retaken too (`approval*.webp`, `trash*.webp`, since restored to `HEAD`, with the four `my-work*` and `requirement-panel*` shots the after run retook. The list of past findings is in "Past findings on the panel" below, and the findings table's "found before?" column is checked against it. |
| 2 | `PRODUCT.md` written (untracked, 109 lines, Nov 13). It defers to the docs: `ui-design-guide.md` is the authority for every UI rule, and Principle 4, "The docs decide", sends differences to the owner. WCAG 2.2 AA, with the main rules. | Partly | **It doesn't say "system fonts only"**, and Impeccable's craft floor pushes a self-hosted display face (row 9). It doesn't name `docs/ui/tokens.css`: only the brand accents from guide §3.1. The mode ("Operate") isn't in it, by Impeccable's design, but every command used Operate. Beyond the guide, it adds users, purpose and positioning (cited from the design doc and screen inventory), four principles (Principle 2 restates the design doc), and "Evidence on hand", which forbids invented customers or metrics. Read by the session on 2026-11-16. |
| 3 | `DESIGN.md` written (untracked, 447 lines, Nov 13; sidecar `.impeccable/design.json`). Compared by script with `frontend/src/app/styles/tokens.css` on 2026-11-16. **Every token value matches:** all 37 colours (light and dark), both font stacks, the type sizes, the three radii and both shadows. No token is missing. It names the guide as the authority. It also states "system fonts, no web font" (UI-STY-4), which covers what `PRODUCT.md` leaves out. | Yes | Values that aren't tokens are all accounted for: Tailwind's spacing scale (`0.5rem`, `0.75rem`, `9.5rem` = `min-w-38` in `Button.vue`), 1px and 3px borders, the decided widths and breakpoints (`64rem`, `40rem`, `320px`, `400`/`560`/`800px`, DL-321, DL-322), and the logo's `#197bb0`, named as never an interface colour (guide §3.1). **Two small errors:** the panel's Description is described as an `h3`, but it's an `h2`, at the `h3` size. Once decisions 2 and 5 land, its `64rem` and `560px` go stale: refresh it then, if it's kept. |
| 4 | Critique ×3: 24/40 (Nov 14), 24/40 (Nov 15), 27/40 (Nov 16, after the fixes). Audit ×2: 15/20, then 18/20. | Yes | Findings below. Snapshots in `.impeccable/critique/` (not tracked by git). |
| 5 | The accepted findings fixed (F1 to F6, F8, F9 below). `ui-reviewer` on the diff: PASS WITH FINDINGS, its findings fixed in one batch. After shots in `trial-shots/after/` (2026-11-16), beside the baseline. **Better than the baseline:** the baseline's page ran past the window into blank space (the 1280 shots are 1252px tall for an 800px window, and the 375 shots show the list below the overlay); after, every shot is exactly the window's height (F1). The tree and tabs lost the raised fill in dark (F3). **Worse at a glance:** at 1280 the tree's status badges are now whole but cut off at the region's edge ("Awaiting approval", "Approved · modifi…") until scrolled, where the baseline wrapped them into two-line boxes. Decision 5 fixes this; it isn't built. | Partly | The fixes were made through Impeccable's commands (`adapt`, `polish`, `harden`); the `vue-screen` skill wasn't invoked. That's a gap against the row as written. `ui-reviewer`'s re-review of that batch (2026-11-17): PASS WITH FINDINGS, all six fixes resolved; one major on the compact Edit (F28) and one minor (F29). The `vue-screen` gap stays as a deviation: running it afterwards wouldn't show how the fixes were made. |
| 6 | Live mode ran on 2026-11-16 at <http://localhost:5183>, with the copy-edit agent off (`IMPECCABLE_LIVE_COPY_AGENT=off`). It needed a one-time config, which it put in `frontend/.impeccable/live/`; the CSP allowance from the setup already covered `script-src` and `connect-src`. Three picks. **(1) The panel's Edit button:** 3 variants (primary, ghost, compact 32px), and the owner accepted the compact one. **(2) The requirements page header:** cancelled, because it's shared by every page and outside the trial screen. **(3) The whole panel body:** cancelled, because it holds the requirement, which would mount 4 times. Ended with the helper stopped, the injected `<script>` gone from `frontend/index.html`, no variant markers left in `frontend/src`, and the session journals moved to `.impeccable/live-trial-row6/`. | Partly | Works under the CSP allowance. The injected tag was found and removed. Live mode's own findings are F23 to F28. The accepted compact Edit (32px beside 36px controls, and on the full page too, DL-326) is a proposal, not a change to bring to `s3`. |
| 7 | The design hook ran after every UI edit: at least 7 times on Edit and Write calls this session (ApprovalSection ×2, Badge, RequirementsTree, RequirementDetail ×2, and more). Each time it said "No deterministic design-quality issues found", so it flagged nothing, and none of its messages was useful. It cost one red `wl check` (C2). | — | Time per edit and at the end of a turn weren't measured, and can't be now that rows 5 and 6 are over; the session noticed no delay. |
| 8 | Source scan (`detect --json frontend/src`): `[]` in every run. URL scan signed out: sees only sign-in. In-browser scan through the DevTools port, signed in: `skipped-heading` ×1 (true, F7), `straggler` ×2 per state (advisory, rejected), `cramped-padding` ×1 in the Nov 15 run (likely false positive). The overlay never ran (C1). | Partly | The Nov 15 critique notes that the CLI scans `.vue` regex-only (its element rules don't run), so `[]` is not a real all-clear for Vue files. |
| 9 | No edit went against a UI rule or a decision. Recommendations that would have done so were turned into proposals: the header badge and Approve by hand's place (DL-325, DL-161; recorded as findings), the panel width (DL-322; decision 5), and the breakpoint (DL-321; decision 2). Impeccable's craft floor tells it to self-host a display face instead of a system font, against our system-fonts rule. It wasn't acted on, because the panel is Operate mode. | Yes | |
| 10 | After live mode, with its tag removed: `uv run wl check` green, and `uv run wl e2e` 114 passed (2.8 min), light and dark. Both from the gates, 2026-11-16. | Yes | The end state includes the accepted compact Edit button. |

## Critique and audit findings (row 4)

Sources:
- **A1:** the first audit (15/20).
- **A2:** the second audit (18/20).
- **CR1, CR2, CR3:** the critiques of Nov 14, Nov 15 and Nov 16.
- **UR:** `ui-reviewer` on the trial's diff.

The "found before?" column is checked against row 1's list of past findings ("Past findings on the
panel", below), by the session on 2026-11-17.

| # | Finding | Source | Accept / reject / rule | Found by our process before? | What happened |
|---|---|---|---|---|---|
| F1 | With the split pane open, the page scrolls into blank space below the layout. A visually hidden note escaped the pane's unpositioned scroll container. | A1 | Accept (UI-SHL-7) | No | Fixed: `relative` on the pane's scroll div. The `frontend/CLAUDE.md` rule now covers every scroll container. The e2e checks that the page is the window's height. Sabotage-checked by the session. |
| F2 | The tree's expand toggle shrinks to about 10–14px beside a long title. | A1 | Accept (UI-TOK-6) | No | Fixed: `shrink-0`. The e2e measures 24×24 at 320px. Sabotage-checked by the session. |
| F3 | The tabs and the tree use Aura's raised fill (`surface-raised`): white blocks on the pane in light, raised cards in dark. | A1, CR1, CR2 | Accept (UI-STY-6) | No | Fixed in `preset.ts` (transparent). The e2e checks the computed fills. Sabotage-checked by the session. This also changes MarkdownEditor's Write and Preview tabs everywhere (UR note). |
| F4 | The separator drag. **(a)** A fast mouse drag level with the panel's Parent link starts a native drag of that link, Chromium cancels the pointer, and the resize is lost. **(b)** A second pointer could take over the drag. **(c)** A lost capture left the drag running. | A1 (via `harden`) | Accept | No (a was there before the trial) | Fixed: the press's default is prevented and the separator focused explicitly; a drag belongs to one pointer; a lost capture reverts. The specs cover each guard separately, and an e2e drives the real pointer. Sabotage-checked by the session: each guard, plus the e2e failing at 560 against 660. |
| F5 | The tree is squeezed at 1024px (about 176px for the list). | A1, CR2 | Accept | **Yes:** S3-C0d's `ui-reviewer` finding 2 (TD-108); the owner kept 64rem then | **Decision 2** (breakpoint to 80rem). |
| F6 | Two label/value styles in one panel (Approval's inline "Label:" against the details list). | CR1, CR2, polish | Accept (DL-325 pattern) | No | Fixed: ApprovalSection uses the details list's pattern. The specs' text updated. |
| F7 | The description's headings skip a level (h2 → h4) under the panel. | A1, CR2, CR3, detector | Accept | **Partly:** heading order was fixed twice (S2-C18b UR 4, S2-C20a UR 2); this skip is what that fix's absolute shift leaves | **Decision 1** (relative shift). |
| F8 | No wrapping on every Badge, an earlier trial change: a long restriction badge overflows at 320px. | UR, CR3 | Accept (UI-SHL-7) | n/a (caused by the trial) | Fixed: no-wrap only in the tree's status cell. The e2e checks that the panel's badge wraps. Sabotage-checked by the session. |
| F9 | The second-pointer spec couldn't fail. No end-to-end check of the fast-drag fix. | UR | Accept | n/a | Fixed: four cases and a real-pointer e2e (see F4). Two rules added to `frontend/CLAUDE.md`. |
| F10 | The tree is 40–50px wider than its room at 1280 with the pane open (Status cut off until scrolled). | A2, CR3 | Accept | **Partly:** TD-108 covers 64 to about 75rem; 1280 wasn't covered | **Decision 5** (the default width fits the list). |
| F11 | Empty description: the acceptance-criteria note sits above "No description." | polish | Accept | No | **Decision 3** (one note). |
| F12 | Requesting approval without acceptance criteria gives no warning. | Owner, during the trial | Owner's addition | — | **Decision 4** (warn, never block). |
| F13 | The panel header shows "Draft" while the tree shows "Awaiting approval". The waiting state has three names. | CR1, CR2, CR3 (P1 each time) | Accept as a finding, undecided | **Partly:** the tree's badge came from the owner's feedback (S3-C0l, DL-376); the header wasn't raised | Recorded only (owner). It would change DL-325 and DL-376. |
| F14 | Approve by hand has the same weight as the normal flow, and nothing marks the next step. | CR1, CR2, CR3 (P1 each time) | Accept as a finding, undecided | No: the owner's feedback was about Delete's weight (S3-C0d, DL-325) | Recorded only (owner). It would change DL-325 and DL-161/212. |
| F15 | Flat hierarchy (title `text-xl`, sections `text-lg`). The acceptance-criteria alert is the loudest element. | CR1, CR2, CR3 | Finding | **Yes:** the owner's "wall of text" feedback (full page), addressed in S3-C0l; CR3 still raises it after that | Recorded only (owner). |
| F16 | The header's icon buttons come before the focused title: reachable only with Shift+Tab. | CR1, CR2, CR3 | Finding | **Listed, not checked:** the panel's Tab order is on the S2-C22 manual-pass sheet, which has no item ticked yet | Recorded only (owner). DL-324 sets focus-on-title, not the DOM order. |
| F17 | Edit mode is ragged: a lone ⋯, the title repeats the field, the details reshuffle. CR2: a dirty Cancel is unguarded. | CR1, CR2, CR3 | Finding | **Partly:** unsaved edits on the ways out were TD-92 (S2-C18b), resolved by DL-323; edit mode's focus order is on the manual-pass sheet | Recorded only (owner). CR2's unguarded Cancel is accurate and by design: DL-323 asks only on Close, Esc, Back, another ID and Open full page, not Cancel (behavior reference). |
| F18 | The empty live region under the title still takes up space. | CR3, A2 | Finding (P3) | No | Recorded only. |
| F19 | A single word alone on a description's last line (`straggler`). | Detector | Reject | — | User-written markdown, and it changes with the width. No UI rule covers it. |
| F20 | `cramped-padding` on the tab panels. | Detector (Nov 15) | Reject (likely false positive, UI-SHL-7) | — | |
| F21 | History omits approval events. The status menu doesn't mark the current status, or say why Approved is missing. | CR1, CR2, CR3 | Finding | No: the owner's feedback was History's spacing (S3-C0l) | Recorded only. |
| F22 | The guide's reference `docs/ui/tokens.css` lacks two tokens the app's copy has: `--docs-card-min` (DL-339) and `--split-pane-height` (DL-356). The developer guide says the app's file is "a copy of" it. | Row 3's comparison (by the session, not Impeccable) | Accept (drift, not caused by the trial) | No: the docs consistency test checks only the contrast pairs | Recorded. A `docs:` fix for the design change, or a check that the two files match. |
| F23 | Live mode wrapped the wrong element: the Edit button's classes appear 13 times on the page, and it matched the header's **Menu** button in `AppLayout.vue`. | Live mode | Cost | — | The session wrapped the real button by hand. |
| F24 | Live mode's preview CSS (`<style>` in the wrapper) can't work in a Vue template: Vue drops it. | Live mode | Cost | — | The variants used token classes only. |
| F25 | **The accept merged the chosen variant without the original's `v-if` and `ref`, and reported "nothing to clean up".** Edit then showed to people who can't edit, and focus couldn't return to it. | Live mode | Cost (a real bug, until fixed) | — | Fixed by the session. Our specs catch each loss (3 failures each, sabotage-checked by the session), so `wl check` would have gone red. Partly the session's doing: it put the `v-if` on the wrapper. |
| F26 | Live mode couldn't find the shared page header in `PageHeader.vue` ("could not locate element"). | Live mode | Cost | — | Cancelled (and outside the trial screen). |
| F27 | Live mode will preview any picked element by copying it whole: in a Vue app, one that holds a slot or child components (the panel body) would mount them once per variant. | Live mode | Cost | — | Cancelled. Only small, mostly static elements preview safely. |
| F28 | The accepted compact Edit (32px) sits beside 36px controls, against `DESIGN.md` ("controls 2.25rem; 2rem for icon buttons and dense rows"), and changes the full page's action row (DL-326). | Live mode (owner's pick) | Proposal | — | In the trial only; not for `s3` without a decision. `ui-reviewer`'s re-review: **major**, against UI-TOK-6 (buttons are `--control-height`). The classes also fight Button's own (`min-h-(--control-height)`, `px-4`), so which wins depends on CSS order. If adopted: a `size` prop on Button and a UI-TOK-6 exception, for the whole action row. |
| F29 | The new fast-drag e2e sits between the 320px test and that test's leading comment (`requirements.spec.ts`). | UR (re-review) | Accept (minor) | n/a (caused by the trial) | Not fixed in the clone: place it correctly when the panel fixes are re-applied on `s3`. |

### Past findings on the panel (row 1)

From `docs/reviews/s2/S2-ui-feedback.md` (Requirements) and the panel's review records, collected by
the session on 2026-11-17:

| Source | Finding | Outcome |
|---|---|---|
| Owner feedback | The pop-out panel blocks the page | S3-C0d: the split pane (DL-321) |
| Owner feedback | Open full page highlighted; the link and close buttons should be icons; Delete the only solid button | S3-C0d (DL-325) |
| Owner feedback | Move the actions to the bottom | Kept in the header (DL-325) |
| Owner feedback | History and Revisions spacing; revisit Compare | S3-C0l (Compare kept, restyled) |
| Owner feedback | Full page is a wall of text: no distinction between title and content | S3-C0l |
| Owner feedback | A way to see which requirements await approval | S3-C0l: the tree's badge (DL-376); the filter is S3-C26 |
| Owner feedback | Description checkboxes can't be ticked | No change (read-only in v1) |
| S2-C18b | Esc in the status menu closed the panel; Try again sent focus behind the modal | Fixed |
| S2-C18b UR 4 | Heading order in the panel | Fixed: Description an `h2` |
| S2-C18b | Closing the panel drops an open edit (TD-92) | Resolved in S3-C0d (DL-323) |
| S2-C20 | The Approval section didn't follow the requirement; a 403's focus; the failure alert's focus | Fixed |
| S2-C20a UR 2 | The bound revision's headings broke the heading order | Fixed: `MarkdownView`'s `level` (DL-310) |
| S3-C0d | Esc in a dialog from the panel closed the panel too; `dirty` tested on one field; focus moved crossing 64rem | Fixed |
| S3-C0d UR 2 | Just above 64rem the panel leaves the tree about 150px (TD-108) | Logged; the owner kept DL-321 and DL-322 |
| S3-C0d | A dialog from the panel may stop being modal crossing 64rem (TD-109) | Logged, for the manual pass |
| S3-C0l 3 | The tree's reflow at 320px untested | Fixed: an e2e |
| S2-C22 sheet | The panel's Tab order, its title's ring, edit mode's focus order, headings in a screen reader | Listed for the manual pass (now S3-C33's sheet); no item ticked |

**Against the trial:** of the 17 findings Impeccable or `ui-reviewer` raised on code that was there
before the trial (F1 to F7, F10, F11, F13 to F18, F21, F22), our process had **already found 2**
(F5, F15), **partly found 5** (F7, F10, F13, F17, and F16 listed but not checked), and **missed 10**
(F1 to F4, F6, F11, F14, F18, F21, F22; F22 came from the session's own check, not Impeccable).
F12 is the owner's own addition. F8 and F9 were caused by the trial, and F19, F20 and F23 to F28
are costs or rejections.

## The owner's decisions (for `design-change`, after the trial)

1. **Description headings shift relative to the content's own top heading.** The top heading
   becomes h(level+1). Deeper headings keep their distance from it, capped at h6. An author's own
   skips stay. Docs mode (`level` 0) is unchanged.
   - Changes: UI-MD-1, the MarkdownView rule in `frontend/CLAUDE.md`, a new DL entry (DL-310
     stays).
2. **The split pane starts at 80rem (1280px).** Below it, the panel opens as the overlay.
   - Changes: DL-321, and every doc that says 64rem.
3. **An empty description shows one note:** "No description: the requirement has no acceptance
   criteria." The separate "No description." line goes. A description with text keeps today's
   note.
   - No rule changes. The behavior reference gets the wording.
4. **No acceptance criteria → a warning, never a block,** in the Request approval dialog and in
   Approve by hand.
   - Changes: DL-149 and design-doc §6 ("nothing blocks it" stays, with the warning added).
5. **The split pane's default width fits the list.** 560px, or narrower so the list keeps 30rem
   (480px). Never below 400px. A width the viewer chose is kept.
   - Changes: DL-322's default.

The code goes in S3-C0o (DL-131), the open findings in S3-C0p (DC-2026-11-17b), together with the trial's fixes that are
kept, re-applied by hand on `s3`. `trial` is never merged or cherry-picked.

## Costs

- **C1, the overlay never ran.** Its detector core needs WebAssembly, and our CSP has no
  `'wasm-unsafe-eval'`. The trial's `localhost:8400` allowance isn't enough on its own. This
  happened in all three critiques. The in-browser scan through the DevTools port stood in for it.
- **C2, `frontend/.impeccable/` broke `wl check`.** Twice: the hook's cache, then live mode's config and journals.
  The hook broke it the first time. It created a second cache, `frontend/.impeccable/`,
  when the session worked from `frontend/`, and Prettier's check failed on it. It was removed
  (it held only hook state) and hasn't come back.
- **C3, the hook writes.** It writes `.impeccable/hook.cache.json` and lines in
  `.git/info/exclude`, for the repo root and for `frontend/`. These were accepted for the trial
  (README, "The hook").
  **Live mode also wrote `frontend/.gitignore`,** a new file of 30 Impeccable ignore lines, at boot. The README's list doesn't include it. It was removed when the trial ended.
- **C4, the detector's limits.** It reads `.vue` regex-only. Its element rules need a rendered,
  signed-in page, which only the DevTools-port scan gave. Its advisories (F19, F20) were noise
  here.
- **C5, the git guard.** It blocked about 5 combined calls this session, each re-run as single
  commands. One is logged in the friction log (#38); the others weren't, though logging is
  required until the guard's decision at the end of S3-C0x, and can't be reconstructed now
  (#39 to #42 are the outcome session's own blocks).
- **C6, speculative code once.** Reordering the capture call in `harden` was tried, then reverted
  under DL-40.

## Verification

- **Gates:** `wl check` and `wl e2e` (114) are green on the final state.
- **Independent:** `ui-reviewer` reviewed the diff, then re-reviewed the batch that fixed its
  findings (F8, F9, the two `frontend/CLAUDE.md` rules) on 2026-11-17: all resolved, plus F28
  and F29. The critique's assessments A and B ran as isolated sub-agents.
- **Not verified independently:** every sabotage check, which the session did itself.
- **Not tested:** Safari, Firefox, a physical touch device, real screen readers, and forced colors
  beyond the e2e's checks.
