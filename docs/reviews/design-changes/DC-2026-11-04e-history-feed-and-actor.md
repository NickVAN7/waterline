# Review record: DC-2026-11-04e — History's paging and an app command's actor

- **Change:** the owner's answers to DC-2026-11-04's two decisions (chat, Nov 4, 2026): a
  cursor-paged feed shows more with "Show more", kept in the page, not the URL (DL-273, UI-TBL-9);
  a History entry an app CLI command made names its actor "System" (DL-274). Docs and one
  reviewer checklist question.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `dac9b8a` (DC-2026-11-04d).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 3 fixes, all fixed; 1 decision for the owner.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-273, DL-274.
- **Docs:** ui-design-guide (UI-TBL-9; UI-TBL-2 and UI-TBL-3 scoped to offset-paged tables; §2's
  WCAG map); `ui-reviewer` (UI-TBL-9's question); design-doc §6.1; build plan (rows 19 and 19a);
  DC-2026-11-04's record (its decisions answered).

## docs-consistency, pass 1 (base `dac9b8a`)

### Fixes

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | contradiction | ui-design-guide UI-TBL-2, UI-TBL-3 | Still read as covering every paged list, a cursor feed included | **Fixed:** both scoped to offset-paged tables, UI-TBL-2 pointing to UI-TBL-9 |
| 2 | internal | ui-design-guide §7 | UI-TBL-9 sat between UI-TBL-3 and UI-TBL-4, inside ranges cited as "UI-TBL-1 to 4" | **Fixed:** moved after UI-TBL-8 |
| 3 | gap | ui-design-guide §2, WCAG map rows 2.4.2/2.4.3 and 4.1.2/4.1.3 | Didn't list UI-TBL-9's focus move and announcement | **Fixed:** UI-TBL-9 added to both |

### Decisions for the owner

| # | Kind | Question | Options | Resolution |
|---|---|---|---|---|
| 1 | gap | Does "System" for a missing actor reach beyond History: the Slice 3 project activity feed (`activity_log`) and the admin audit screen (`audit_event`, design-doc §10.1, "none for app CLI commands")? | (a) widen DL-274 to every screen with an actorless entry, in design-doc §10 and §10.1; (b) keep it to History, noting in §10.1 and the Slice 3 list that their label is decided when planned; (c) leave it | **Open:** to the owner, before Slice 3's planning |
