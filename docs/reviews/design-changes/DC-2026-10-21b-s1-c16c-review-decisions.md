# Review record: DC-2026-10-21b — the owner's S1-C16c review decisions

- **Change:** DL-120 to DL-123, from the owner's answers to S1-C16c's open questions (and
  DC-2026-10-21's two docs-consistency questions); docs only (the code follows in S1-C16d,
  inserted before S1-C17)
- **Base commit:** `2f3cef3` (the S1-C16c checkpoint)
- **Reviewers:** `docs-consistency` (trigger `design-change`). No tooling code, so no
  `checkpoint-reviewer`.
- **Totals:** 0 fixes; 1 decision, already answered by the owner and recorded as DL-123.
- **Gates:** `uv run wl check` green.

---

## Decisions applied

- **DL-120:** a classification save refused with `members_changed` reloads the project; UI-FRM-7.
- **DL-121:** the security reviewer's fixed range stays 1 to 16b; S1-C16c and S1-C16d get it only
  when their diff calls for it; the build plan's reviewers paragraph.
- **DL-122:** DL-118 in the create-organization and password-reset dialogs, in S1-C16d (TD-50).
- **DL-123:** these refusals' alerts keep the server's message; UI-FRM-7.
- Inserted: S1-C16d (Review follow-ups (2)), building DL-120 and DL-122.

## docs-consistency, pass 1 (base `2f3cef3`)

No fixes.

| # | Kind | Question | Resolution |
|---|---|---|---|
| 1 | gap | The refusal's copy (S1-C16c's U3) had no recorded answer. | **Recorded:** the owner had answered (keep the server's message); DL-123, and UI-FRM-7 says so. |
