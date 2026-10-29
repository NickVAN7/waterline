# Review record: DC-2026-10-28e — every requirement parent change, and tasks' ranks

- **Change:** the owner's answers to S2-C7's two open questions (chat, Oct 28, 2026): a delete's
  promote and a restore at the top level follow the move's lock and rules (DL-215), and tasks'
  rank rewrites and move lock are decided in Slice 3 planning (DL-216). Docs only; S2-C8 builds
  DL-215.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `bd58fe4` (S2-C7).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 4 fixes (fixed) and 1 decision for the owner.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-215, DL-216.
- **Docs:** design-doc §6 "Manual ordering" (the move lock bullet, "Ties"), §9 "Trash"; build
  plan (S2-C8); developer guide ("Direct updates"); `backend/CLAUDE.md`; `new-area` skill;
  `docs/reviews/s2/S2-C7.md` ("Owner decisions").

## docs-consistency, pass 1 (base `bd58fe4`)

### Fixes

| # | Kind | Where | Resolution |
|---|---|---|---|
| 1 | superseded | build plan, the direct-update helper bullet, left out the parent change (DL-214, DL-215) | Fixed: in both lists |
| 2 | superseded | design-doc §3 "Optimistic locking" left out the parent change from what doesn't bump `version` | Fixed |
| 3 | contradiction | design-doc §3 "Manual ordering": "Moving an item rewrites only that row", against DL-204 and DL-213 | Fixed: the two rewrites named, tasks pointed at DL-216 |
| 4 | gap | build plan "Later slices" didn't carry DL-216 to Slice 3 planning | Fixed: a Slice 3 bullet; DL-216's "Applies to" names it |

### Decisions for the owner

| # | Question | Options |
|---|---|---|
| 1 | What rank does a promoted child get, and a requirement restored at the top level? DL-215 says they change parent as a move does, but a move takes its rank from neighbors the client sends | (a) keep the stored rank, change only the parent; (b) the bottom of the new siblings, keeping their order, with fresh ranks; (c) promoted children where the deleted parent was, keeping their order |

Due before S2-C8.

## Owner decisions after the change

- Decision 1 (Oct 28, 2026): option (c) for promoted children, (b) for a restore at the top
  level (DL-217). Recorded in DC-2026-10-28f.
