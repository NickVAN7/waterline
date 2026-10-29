# Review record: DC-2026-10-28f — where promoted children and a top-level restore are ranked

- **Change:** the owner's answer to DC-2026-10-28e's docs-consistency decision 1 (chat, Oct 28,
  2026): promoted children take the deleted requirement's place, in their order; a restore at
  the top level goes to the bottom (DL-217). Docs only; S2-C8 builds it.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `2b5a8f2` (DC-2026-10-28e).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** no fixes; 1 decision for the owner, decided before the commit (DL-218).
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-217, DL-218.
- **Docs:** design-doc §3 "Manual ordering", §6 "Manual ordering", §9 "Trash"; build plan (S2-C8); DC-2026-10-28e's record ("Owner
  decisions after the change").

## docs-consistency, pass 1 (base `2b5a8f2`)

### Fixes

None.

### Decisions for the owner

| # | Question | Options |
|---|---|---|
| 1 | When promoted children or a top-level restore can't get ranks where DL-217 puts them (a tie, DL-213; past the 255-character cap, DL-204), may the delete or restore rewrite ranks? §3 and §6 name only a drop's rewrites | (a) rewrite the new parent's children in order, as a drop does; (b) no rewrite, fall back to the bottom of the new siblings; (c) leave it to S2-C8 |

## Owner decisions

- Decision 1 (chat, Oct 28, 2026): option (a) (DL-218), applied in this change: §3, §6, §9, and
  the build plan's S2-C8 row.
