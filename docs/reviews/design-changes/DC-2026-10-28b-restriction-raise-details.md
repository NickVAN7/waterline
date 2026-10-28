# Review record: DC-2026-10-28b — the restriction raise: trash and `updated_at`

- **Change:** the owner's answers to DC-2026-10-28's two decisions (chat, Oct 28, 2026): a
  project raise skips items in the trash and restore raises them (DL-209); `updated_at` moves on
  an item's own restriction change, not on items lifted by a project raise (DL-210). Docs only;
  the code is built in S2-C6 and S2-C8.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `c4641c0` (DC-2026-10-28).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 1 fix (fixed) and 1 decision (decided by the owner).
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-209, DL-210.
- **Docs:** design-doc §3.1 "What's restricted", §9 "Restore"; build plan (the direct-update
  helper, S2-C6, S2-C8); `backend/CLAUDE.md` (`touch_updated_at` for restriction writes);
  DC-2026-10-28's record ("Owner decisions").

## docs-consistency, pass 1 (base `c4641c0`)

### Fixes

| # | Kind | Where | Resolution |
|---|---|---|---|
| 1 | gap | `new-area` skill: the restriction-floor bullet didn't say the raise lifts live rows only, left out the restore-time raise, and didn't say `touch_updated_at` for the lifted rows; DL-209 and DL-210 didn't list the skill | Fixed: the bullet states all three, and both entries list the skill under "Applies to" |

### Decisions for the owner

| # | Question | Options |
|---|---|---|
| 1 | Does the first revision pointer set at creation (DL-207) move `updated_at`? Each `direct_update` call names it, and the docs didn't say | (a) no, the row was just inserted; (b) yes, as counters; (c) either, the docs saying it makes no difference |

## Owner decisions

- Oct 28, 2026: decision 1, (a) no; recorded in DL-210, the build plan, and `backend/CLAUDE.md`.
