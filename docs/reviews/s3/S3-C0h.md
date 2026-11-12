# Review record: S3-C0h — Generated documentation screenshots, with full-width pages

- **Checkpoint:** Slice 3, Checkpoint 0h (group `s3-polish`; PR #12)
- **Base commit:** `5b98078` (DC-2026-11-12, DL-360: the last commit before the checkpoint;
  DL-17)
- **Reviewers:** `security-reviewer` (the diff changes rendered markdown's sanitizer options),
  then `checkpoint-reviewer`, then `ui-reviewer`, one at a time on one snapshot (DL-105).
  `ui-reviewer` re-reviewed the fix diff (its major finding was fixed in code); the other majors
  were fixed in tests and docs, or rejected, so no other re-review (DL-105).
- **Totals:** security-reviewer ready, no findings; checkpoint-reviewer ready after fixes, 3
  major, 1 minor, 1 question; ui-reviewer pass with findings, 1 major, 1 minor, 2 notes, 1
  proposed rule. In all: 8 findings and notes, 5 fixed, 1 rejected, 2 left to the owner (notes);
  the re-review below.
- **Gates at close:** `wl check` green; the full e2e suite green locally; CI on the commit.

---

## Before the reviewers

- **Owner decision at the start:** `wl docs-screenshots` seeds with `--manual-pass`, not
  `--demo` (DL-361): the demo has no requirements, approvals, or Trash items to show.
- **Scope bundled in** (DC-2026-11-12, DL-131): DL-360's full-width pages, and the owner's report
  after S3-C0g that callouts were far too large: DOMPurify checks every attribute value against
  docs mode's URL pattern, so the icon lost its `viewBox`, size, and paths and drew at 300 by
  150.
- **Caught on the way:** the docs consistency tests read every file under `docs/` as text, and
  failed on the first screenshots (`UnicodeDecodeError`); `reference_files()` now skips image
  suffixes. Two shots were swapped after looking at them: the project home (nearly empty) for
  its settings, and the org's members (like the workspace's lists) for its overview.
- The implementing session's own sabotage checks (evidence for the reviewers, not verification):
  the icon spec without `viewbox`, and without `d`; the guide spec with a `-dark` file missing,
  and with an unused image; `csp.spec.ts` without the `data-theme='dark'` rules; `shell.spec.ts`
  with an 80rem cap back on `main`. Each failed; each file restored. A first attempt at the CSS
  check found the e2e API container unhealthy at start; the rerun went through.

## security-reviewer, pass 1 (base `5b98078`)

Verdict: ready. No findings, no questions.

Checked and fine (its words, condensed): the added URI-safe attributes apply only to docs mode,
which only `DocsArticleView` uses, for the bundled guide; stored content keeps `sanitizeOptions`
(no `img`, the URL check on), and markdown-it's raw HTML stays off, so only the internal icon
makes an `svg`; the `-dark` sibling is looked up only in the bundled map, URLs and alt escaped;
the shots' `data:` URL is on a blank test page, never in the app; no backend, API, or secrets
change.

## checkpoint-reviewer, pass 1 (base `5b98078`)

Verdict: ready after fixes.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | major | tests | The icon spec asserts `viewBox`, size, and `d`, but not `fill` and `stroke`: with both removed from the safe list, all 166 specs passed, and the icon would draw as a solid shape, the owner's bug again. | **Fixed:** `fill`, `stroke`, `stroke-width`, `stroke-linecap`, and `stroke-linejoin` asserted. Sibling: every attribute in the safe list is now asserted. |
| 2 | major | conventions | DL-361 changes this checkpoint's own row and sits in the checkpoint's changes, not its own `docs:` commit (DL-8). | **Rejected:** the precedent is DL-359, the owner's decision at S3-C0f's start that changed that checkpoint's own row, committed with it (`b22976e`: `docs/decision-log.md`, `docs/build-plan.md`). The question goes to the owner. |
| 3 | major | docs | The developer guide's `wl seed --manual-pass` row still says "Not for the end-to-end stack", which `wl docs-screenshots` now seeds with it. | **Fixed:** "Not for `wl e2e` …; `wl docs-screenshots` seeds its own run of that stack with it (DL-361)". |
| 4 | minor | docs | The `wl docs-screenshots` row says a removed shot's files are refused as unused; `guide.spec.ts` refuses them only once no page shows them. | **Fixed:** reworded. |

**Sabotage checks** (in a temporary copy of the snapshot):

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| Docs mode keeps the icon's fill and stroke | build plan S3-C0h (DL-131) | `'fill'` and `'stroke'` removed from the safe list | `MarkdownView.spec.ts` | **none** (finding 1, fixed) |
| An image with no `-dark` sibling shows in both themes | DL-343 | the lone image given `theme-light` | `MarkdownView.spec.ts` | "renders an image with no -dark sibling once, in both themes" |
| `wl docs-screenshots` seeds the manual pass's data | DL-361 | `seed="--demo"` | `tools/cli/tests/test_commands.py` | `test_dry_run_prints_underlying_commands[docs-screenshots]` |

**Question:** does DL-8 apply when the owner changes the current checkpoint's row at its start,
or is that a drift fix within scope? To the owner (finding 2).

## ui-reviewer, pass 1 (base `5b98078`)

Verdict: pass with findings.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | major | UI-SHL-7 | With `main` uncapped, three forms that relied on its old cap span the screen: `CreateRequirementForm`, `EditRequirementForm`, and `DecidePanel`'s decision form. | **Fixed:** each form sets `max-w-(--content-narrow)`; `shell.spec.ts` checks New requirement's title field at 2400px; a `frontend/CLAUDE.md` rule (a page's form caps itself). Siblings: every `<form>` in `src/` checked: the rest are in dialogs or the auth card, or already capped (Account, project settings, `NameSlugSettings`, Status). |
| 2 | minor | UI-STY-2, UI-TOK-1 | The theme-switching rules sat in an unscoped `<style>` in `MarkdownView`, a copy of the theme logic outside the global styles. | **Fixed:** moved to `base.css` as app-wide `.theme-light` and `.theme-dark`. |
| 3 | note | — | A 1440px screenshot is drawn at prose width, its text small, with no link to the full size. | **Left to the owner** with the proposed rule below. |
| 4 | note | — | The project settings shot cuts off the Lead select's value ("…@harbor.exam"), from `SelectField`'s existing `max-w-80`. | **Left to the owner** (not this change; a native select shows it all when opened). |

**Proposed rule (to the owner):** UI-MD-1: a guide screenshot drawn smaller than its natural
size links to the full-size image, named by its alt text.

**Gaps it listed:** the form-cap check only on Account (fixed: New requirement added); the prose
bound is a number, not the token's value (low priority, not acted on). **Needs the manual
pass:** the requirement forms and an approval at 1920px and wider; list pages and their header
actions at full width; guide images at 400% zoom and 320px; forced colors and a screen reader on
a guide page with an image pair.

## ui-reviewer, pass 2 (the fix diff)

Verdict: pass. No findings. Both resolutions confirmed: the three forms capped (the dialog that
reuses `CreateRequirementForm` was already capped by `ModalDialog`); the theme rules in
`base.css`'s base layer still win over preflight's `img` display, and `csp.spec.ts` checks the
swap. **Gap it listed, not acted on:** only New requirement's cap is tested end to end (the same
one-class pattern on the other two, and the `frontend/CLAUDE.md` rule covers it).

## Owner decisions and open questions

Made during the checkpoint: DL-361 (the screenshots seed `--manual-pass`).

Open for the owner:
1. checkpoint-reviewer's question: does DL-8 (design changes in their own `docs:` commits) cover
   an owner decision that changes the current checkpoint's row at its start (DL-359, DL-361)?
2. ui-reviewer's proposed UI-MD-1 rule: a screenshot drawn smaller than its size links to the
   full-size file.
3. The Lead select cut off in the project settings shot (`SelectField`'s `max-w-80`).
4. Still open from S3-C0g: NOTE's callout tone, page length, `assetsInlineLimit` once a
   production CSP is sent (every screenshot is well over 4 KB, so none is inlined today), the
   two proposed UI-MD-1 rules, and the tone sample.
