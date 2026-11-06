# Review record: DC-2026-11-02c — `security-reviewer` runs on S2-C18

- **Change:** the owner's answer to DC-2026-11-02b's decision 1 (chat, Nov 2, 2026): option
  (a), `security-reviewer` runs on S2-C18, which holds the stored-XSS end-to-end test (DL-245).
  DL-247. Docs only.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `ec75138`.
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 0 fixes; 0 decisions for the owner.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-247.
- **Docs:** build plan (Slice 2, the `security-reviewer` list); DC-2026-11-02b's record (its
  decision 1 marked decided).

## docs-consistency, pass 1 (base `ec75138`)

### Fixes

None. The build plan's Slice 2 sentence is the only place that lists the checkpoints by
number; the checkpoint skill and `security-reviewer` point to it.

### Decisions for the owner

None.
