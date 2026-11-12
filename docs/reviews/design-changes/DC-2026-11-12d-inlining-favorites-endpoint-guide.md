# Review record: DC-2026-11-12d — No asset inlining; the favorites endpoint; the guide to the sample

- **Change:** the owner's answers on Nov 12, 2026. DL-370: the build never inlines an asset
  (`assetsInlineLimit: 0`), the CSP unchanged (chosen over allowing `data:` images). DL-371:
  `GET /api/me/work/favorites` goes, the favorites section's `total` its count (option a). Both
  built in S3-C0j. And the guide brought to the style sample (DC-2026-11-12c's comparison, the
  owner approving its proposed changes): the Requirements page rewritten in the sample's
  sections, and field and status names bolded as the screen shows them across the guide; the
  two specs that use the page's section ids (`DocsArticleView.spec.ts`, `e2e/shell.spec.ts`)
  follow. Docs, and those specs.
- **Kind:** docs (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `8dcd1e9` (DC-2026-11-12c).
- **Reviewers:** `docs-consistency` (trigger `design-change`, asked to check the guide against
  the behavior reference too), on one snapshot (DL-105).
- **Totals:** 10 fixes, all applied; no decisions.
- **Gates at close:** `uv run wl check` green; `wl e2e` on the shell and CSP specs (36 passed);
  CI on the commit.

---

## docs-consistency, pass 1 (base `8dcd1e9`)

| # | Kind | Finding | Resolution |
|---|---|---|---|
| 1 | contradiction | The API table's My work row still lists the favorites endpoint and first-10 limits. | **Fixed:** named in the S3-C0j row, rewritten with the code (the polish rows' rule; the reviewer's alternative). |
| 2 | contradiction | Design-doc §11 still says 10 per org, and nothing on Favorites in full. | **Fixed:** the same. |
| 3 | contradiction | The screen inventory's My work rows say first 10. | **Fixed:** the same. |
| 4 | stale | TD-37 and its line in the slice's tech-debt table still name favorites' "see all". | **Fixed:** the same. |
| 5 | superseded | DL-302 specifies the favorites endpoint but isn't marked superseded by DL-371. | **Fixed:** both ways. |
| 6 | broken-ref | DL-370 cites "TD-111's note", which says nothing of inlining. | **Fixed:** cites S3-C0g's question, its finding 1 logged as TD-111. |
| 7 | gap | §4's CSP bullet and UI-MD-1 don't say the build never inlines. | **Fixed:** UI-MD-1 added to DL-370's Applies to; both named in the S3-C0j row. |
| 8 | gap | The `security-reviewer` line for S3-C0j omits DL-370 and DL-371. | **Fixed:** both named. |
| 9 | stale | S3-C0g's items 1 to 4 and S3-C0h's items 1, 2, and 4 read as open, though decided. | **Fixed:** each struck and closed with its DL. |
| 10 | contradiction | The rewritten page says you keep working in the tree with the panel open; on a narrow window the panel covers it. | **Fixed:** "On a wide window you can keep working in the tree". |

Checked fine (its words, condensed): every bolded label matches the frontend's labels, and the
status names match `labels.ts`; the rewritten page matches the behavior reference and the
sample; no reference to the page's old anchors is left.
