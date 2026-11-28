# Review record: DC-2026-11-12e — The backlog is PrimeVue DataTable

- **Change:** the owner's choice after trying S3-C0i's demo (Nov 12, 2026): the backlog is
  PrimeVue DataTable with row reorder and its virtual scroller, through our own wrapper (DL-372),
  deciding S3-C19 and UI-SVR-2's backlog line (DL-344). Docs only.
- **Kind:** docs only (no `checkpoint-reviewer`, DL-18).
- **Base commit:** `9f1af11` (S3-C0i).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 4 fixes, all applied; 2 decisions for the owner.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## docs-consistency, pass 1 (base `9f1af11`)

| # | Kind | Finding | Resolution |
|---|---|---|---|
| 1 | stale | Root `CLAUDE.md`'s Status still says the choice is the owner's. | **Fixed:** names DL-372. |
| 2 | contradiction | UI-SVR-2's backlog sentence doesn't say the DataTable wrapper follows UI-SVR-5 and UI-SVR-6, which a reader could take as SVAR-only. | **Fixed:** both named, with the scroller's region and the one tab stop. |
| 3 | internal | UI-SVR-2's "The spike did not decide the per-list split" now reads as S3-C0i's. | **Fixed:** "The Oct 10 spike". |
| 4 | superseded | DL-64's Superseded by doesn't name DL-372. | **Fixed.** |

**Decisions for the owner** (left undecided):
1. Is SVAR DataGrid still the default for a list where manual row order is the point? Both
   ordered lists specified so far are exceptions (the tree, DL-174; the backlog, DL-372).
   (a) keep the rule, the backlog a second exception; (b) narrow the DataGrid to inline cell
   editing, ordered lists on DataTable or TreeTable through our wrapper (a new DL entry).
2. The backlog wrapper's name and listing: (a) name it now (e.g. `TaskBacklog`), list it in the
   UI guide's §8 and §9; (b) leave both to S3-C19.
