# Review record: DC-2026-11-12c — Favorites uncapped; the style sample committed

- **Change:** two parts, both from the owner on Nov 12, 2026. DL-369: My work's Favorites have
  no cap (only each organization's section is, at 5, DL-368; approvals keep 10), built in
  S3-C0j. And a reference fix, not a new decision: the "Requirements sample" DL-342 names as the
  guide's tone, never committed, is added verbatim as the appendix of
  `DC-2026-11-09-s2-retro-and-ui-polish.md`; DL-342 points there (its wording changed at the
  owner's request); S3-C0g's open item 5 is closed. Docs only.
- **Kind:** docs only (no `checkpoint-reviewer`, DL-18).
- **Base commit:** `f5c1516` (DC-2026-11-12b).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 2 fixes, both applied; 1 decision for the owner.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## docs-consistency, pass 1 (base `f5c1516`)

| # | Kind | Finding | Resolution |
|---|---|---|---|
| 1 | broken-ref | Two docs cite `DC-2026-11-12c`, which had no record yet. | **Fixed:** this record. |
| 2 | gap | S3-C0g's item 5 says "the guide was compared with it" without saying who, or where the result is. | **Fixed:** the comparison is below, by the implementing session, a judgment for the owner (not a verification). |

**Decision for the owner** (left undecided): with Favorites uncapped, what becomes of
`GET /api/me/work/favorites` (paging) and the section's `total`? (a) remove the endpoint, keep
`{available, items, total}` with `total` the count; (b) keep the endpoint; (c) remove it and drop
`total`. Recommended: (a).

## The guide compared with the style sample

By the implementing session, on Nov 12, 2026: a judgment for the owner, who decides what
changes. The sample guides tone and depth, not a template.

**Where the guide matches it:** second person, short task sections, the screen's words in bold
for what you select, a sentence of why where it helps, no route paths or exact messages. Every
page but Requirements is close in tone and depth.

**Where Requirements differs** (the sample is that page, so these are clear):
1. The opening says less: the sample says what a requirement has (an ID like `PORTAL-RQ-7`, a
   status, a priority, a description with acceptance criteria) and why it's a tree.
2. No "Browse the tree" section: opening a branch with its arrow, **Expand requirement**, and the
   ++→++ / ++←++ keys (Expand requirement sits under "Open a requirement" today).
3. Open and edit are two sections; the sample has one, with the panel screenshot in it.
4. No word on a requirement's restriction ("Change its status or restriction").
5. Getting it approved is a clause in Edit; the sample gives it a short section linking to
   Approvals.
6. Move and delete are apart (delete only as the Trash link); the sample has "Move or delete a
   requirement".
7. The "Who can do this" table has no heading of its own (it sits under History) and lacks the
   sample's restriction and approval rows.

**Across pages, smaller:** the sample bolds field names as the screen shows them (**Title**,
**Priority**, **Parent**) and status names ("start as Draft"); the guide writes "a title", "a
draft". **Not proposed:** the sample's "Choose" where the guide says "Select" (the guide is
consistent), its run-in bold headings (the guide's `##` sections feed On this page), and its
inline (1) (2) steps (the guide's numbered lists read the same).

**Proposed changes, for the owner before any rewrite:** Requirements rewritten along items 1 to
7; field and status names bolded on every page.
