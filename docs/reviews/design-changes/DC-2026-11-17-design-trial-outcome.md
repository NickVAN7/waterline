# Review record: DC-2026-11-17 — The design skill trial's outcome

- **Change:** S3-C0n's outcome (`docs/spikes/S3-C0n-impeccable/results.md`). Impeccable is kept
  for critique and audit inside `vue-screen`, with its hook off and live mode unused (DL-381).
  The owner's trial decisions are recorded: relative heading shift (DL-382), the split pane from
  80rem (DL-383), a warning without acceptance criteria (DL-384), and a default width that
  leaves the list 30rem (DL-385). One note on an empty description is detail for S3-C0o (DL-312).
  A new checkpoint, S3-C0o, carries the code (DL-131): the decisions, the trial's kept fixes, and
  its open findings. The trial's results and evidence are in the spike folder. Docs only.
- **Kind:** docs only (no `checkpoint-reviewer`, DL-18).
- **Base commit:** `d2a5e32` (S3-C0n).
- **Owner answers** (Nov 17, 2026):
  - Keep critique and audit only (recommended).
  - Discard F28, the compact Edit button (recommended).
  - Fix the trial's open findings in S3-C0o (F13 to F18, F21; not the recommended tech-debt
    entries).
  - Live mode's page text in the session's context: accepted in practice (it ran, on seed data).
- **Also in this change:**
  - F22's drift fix: `--split-pane-height` and `--docs-card-min` added to `docs/ui/tokens.css`
    and the guide's inline copy.
  - TD-108 re-targeted to S3-C0o.
  - The polish group extended to S3-C0o.
  - The root `CLAUDE.md` Status.
  - Guard friction-log rows 38 to 42.
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 6 fixes, all applied; 1 decision for the owner.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## docs-consistency, pass 1 (base `d2a5e32`)

| # | Kind | Finding | Resolution |
|---|---|---|---|
| 1 | broken-ref | DL-382 and the S3-C0o row cite design-doc §4 for the heading shift. The rule is in §3. | **Fixed:** §3 in both places. |
| 2 | gap | S3-C0o's list of docs that change with the code leaves out `frontend/CLAUDE.md`'s `MarkdownView` level rule. | **Fixed:** added to the row. |
| 3 | contradiction | `results.md` still calls itself a draft, to be copied into the README's tables. | **Fixed:** retitled as the recorded results, accepted by the owner. |
| 4 | contradiction | `results.md` decision 4 cites design-doc §5. The rule is in §6. | **Fixed:** §6. |
| 5 | stale | `results.md` C5 says only #38 is logged, while the log now has #38 to #42. | **Fixed:** #39 to #42 relabelled as the outcome session's own blocks; C5 says so. |
| 6 | stale | The README and the trial's empty `friction-log.md` say friction goes in that log. It was recorded in `results.md`'s Costs. | **Fixed:** both point to `results.md` ("Costs"). |

**Decisions for the owner** (left undecided):
1. Do Impeccable's `PRODUCT.md` and `DESIGN.md` (and its `.impeccable/` state) live in the
   repository after S3-C0o?
   - (a) Commit both, with `ui-design-guide.md` the authority and a refresh at each UI rule
     change. Critiques are repeatable for everyone, but this is a second copy that can drift
     (F22).
   - (b) Generated per developer and gitignored. Nothing duplicated, but each developer's
     critique context differs and is unreviewed.
   - (c) Commit `PRODUCT.md` only, since it defers to the guide. Shared context with no second
     token list, though the critique may work less well without `DESIGN.md`.

   Copies from the trial are in `docs/spikes/S3-C0n-impeccable/results/`. Due before S3-C0o is
   built.

Not checked by the reviewer: `results/trial.diff`, the critiques, and the shots (evidence). Also
not checked: whether S3-C0o should name `security-reviewer` for the third-party plugin's setup
(the build plan's call).
