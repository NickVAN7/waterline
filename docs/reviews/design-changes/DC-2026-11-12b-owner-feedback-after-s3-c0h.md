# Review record: DC-2026-11-12b — The owner's feedback after S3-C0h

- **Change:** the owner's answers after S3-C0h (Nov 12, 2026): DL-362 (an owner decision that
  changes the current checkpoint's own row goes in its commit), DL-363 (a guide screenshot opens
  full size in a new tab and loads lazily), DL-364 (callout tones), DL-365 (no word counts for
  the guide), DL-366 (table header scope; the guide's ids), DL-367 (capped pages centered, guide
  text up to 80ch), DL-368 (My work at 5 projects per organization). The code goes to S3-C0j,
  which the owner chose, and which may change again after their UI review. Docs only.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18). DL-362 is a process
  rule and applies now: root `CLAUDE.md`, the `design-change` skill.
- **Base commit:** `431478b` (S3-C0h).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 8 fixes, all applied; 1 decision, settled by the owner's own words.
- **Gates at close:** `uv run wl check` green; CI on the commit.
- **Left open:** whether to set `assetsInlineLimit: 0` (recommended) or allow `data:` images in
  the CSP's `img-src`, the owner's to answer; the tone sample (DL-342), which the owner will
  send.

---

## docs-consistency, pass 1 (base `431478b`)

| # | Kind | Finding | Resolution |
|---|---|---|---|
| 1 | superseded | Two "Done when" items still say each organization's first 10 projects. | **Fixed:** 5 (DL-368). |
| 2 | superseded | The full-width "Done when" item doesn't say capped pages and guide articles are centered. | **Fixed:** DL-367 added. |
| 3 | stale | The Slice 3 checkpoints note doesn't name S3-C0j's new decisions. | **Fixed:** "S3-C0j also DL-363 to DL-368". |
| 4 | gap | DL-366's id list leaves out ids the shell renders, such as `user-menu`. | **Fixed:** the check compares with the ids a mounted shell and docs page render, the list given as examples. |
| 5 | gap | DL-367's Applies to leaves out `docs/ui/tokens.css` and `frontend/CLAUDE.md`'s form rule. | **Fixed:** both added there and to the S3-C0j row. |
| 6 | gap | The Slice 3 `spec-test-writer` and `security-reviewer` lines don't name S3-C0j. | **Fixed:** both lines name it, with what it changes. |
| 7 | stale | TD-104's reason rests on "about 2,500 words", which DL-365 drops. | **Fixed:** "small enough to browse from its nav". |
| 8 | gap | The reviewer's own two guard blocks aren't logged. | **Fixed:** friction log #25 and #26. |

**Decision:** does DL-368's 5 cover only each organization's projects, or Favorites and
Approvals too? **Settled from the owner's words** ("cap the projects at 5 for each
organization"): organizations only; Favorites and Approvals keep 10, so the organizations' limit
is its own constant (DL-368 says so).

## Owner decisions and open questions

Made: DL-362 to DL-368. Open: the CSP question above; the tone sample.
