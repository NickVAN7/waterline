# Review record: DC-2026-10-28c — who may be a reporter, and `requirement.approve_manually`

- **Change:** two owner answers in chat before S2-C6 starts (Oct 28, 2026): who a requirement's
  reporter may be reassigned to (DL-211), and registering `requirement.approve_manually` in
  S2-C6 for the PATCH's 403/422 split (DL-212). Docs only; S2-C6 builds both.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `c8d7b23` (DC-2026-10-28b).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** no fixes; 1 decision (decided by the owner).
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-211, DL-212.
- **Docs:** design-doc §6 (`reporter_id`); schema-doc `requirement.reporter_id`; build plan
  (S2-C6, S2-C11); `docs/reviews/s2/S2-plan.md` (actions table).

## docs-consistency, pass 1 (base `c8d7b23`)

### Fixes

None.

### Decisions for the owner

| # | Question | Options |
|---|---|---|
| 1 | DL-211 made a deactivated reporter a `not_member`, while every other user field (a project's lead, a first admin, an owner's successor) answers `account_inactive` for one and treats an unchanged value as no change | (a) keep DL-211 as written; (b) follow the existing convention |

## Owner decisions

- Oct 28, 2026: decision 1, (b); DL-211 (not yet committed) states it, with design-doc §6 and
  the build plan's S2-C6 row.
