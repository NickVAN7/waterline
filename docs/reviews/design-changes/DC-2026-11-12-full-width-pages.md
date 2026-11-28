# Review record: DC-2026-11-12 — Full-width pages

- **Change:** the owner's feedback after S3-C0g (Nov 12, 2026): pages are capped and
  left-aligned beside the sidebar, which "looks off"; the owner chose full width over centering,
  for the whole app (DL-360). With it, the owner's second note, that the guide's callouts are far
  too large, which is a bug in S3-C0g's docs mode, not a design change: both are bundled into the
  next planned checkpoint, S3-C0h (DL-131). Docs only.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `8156bce` (S3-C0g).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 4 fixes, all applied; 0 decisions for the owner.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-360; DL-356's "Superseded by" filled in (its `fullWidth`).
- **Docs:** build plan (the S3-C0h row, the Slice 3 checkpoints note, "Done when"); the root
  `CLAUDE.md`'s Status; the ui-design-guide's token table and `docs/ui/tokens.css` gain
  `--content-prose` (S3-C0g's token, missing there). UI-SHL-7, UI-SHL-11, the shell diagram, the
  token table's `--content-wide`, and the developer guide's Side panels change with the code in
  S3-C0h, as the polish rows do ("each updates the rules it changes when it's built").
- **Checked against the repository:** the cap is one class on `main` (`AppLayout.vue`), lifted
  only by route meta `fullWidth`, set on the requirements page alone (`router.ts`); forms,
  settings, and the error pages cap themselves at `--content-narrow`, and a guide article's text
  at `--content-prose`, so they keep their widths without it.
- **Not a new checkpoint:** a row `0ga` or `0n` after 0g is refused by the build plan's checks
  (one letter after the number; rows in order), and S3-C0h, next, already changes docs mode.
- **The callout bug** (found while checking the owner's note): DOMPurify checks every attribute
  value against the URL pattern, so the callout icon's `viewBox`, `width`, `height`, and path
  data were stripped and the `svg` drew at its default 300 by 150. Its fix, and a spec asserting
  the attributes, are parked for S3-C0h.

## docs-consistency, pass 1 (base `8156bce`)

| # | Kind | Finding | Resolution |
|---|---|---|---|
| 1 | stale | The Slice 3 checkpoints note says S3-C0a to S3-C0h are as decided by DL-312 to DL-343; S3-C0h now also has DL-360. | **Fixed:** "S3-C0h also DL-360". |
| 2 | gap | "Done when" has no item for full-width pages. | **Fixed:** an item added. |
| 3 | gap | The S3-C0h row names only UI-SHL-7, UI-SHL-11, and the token table; the shell diagram ("up to 80rem") and the developer guide's Side panels (`meta.fullWidth`) state the cap too. | **Fixed:** the row says every statement of the cap is rewritten and names all five. |
| 4 | contradiction (from S3-C0g) | The token table lacks `--content-prose`, which DL-360 keeps. | **Fixed:** added to the guide's table and `docs/ui/tokens.css`. |

Decisions for the owner: none.

## Owner decisions and open questions

Made: full width, not centered (DL-360). Open: S3-C0g's five questions (its review record).
