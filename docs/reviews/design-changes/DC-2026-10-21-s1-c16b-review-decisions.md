# Review record: DC-2026-10-21 — the owner's S1-C16b review decisions

- **Change:** DL-116 to DL-119, from the owner's answers to S1-C16b's open questions; docs only
  (the code follows in S1-C16c, inserted before S1-C17)
- **Base commit:** `dec09e4` (the S1-C16b checkpoint)
- **Reviewers:** `docs-consistency` (trigger `design-change`). No tooling code, so no
  `checkpoint-reviewer`.
- **Totals:** 3 fixes, all applied; 2 decisions for the owner.
- **Gates:** `uv run wl check` green.

---

## Decisions applied

- **DL-116:** an add, or project settings' classification save, refused with
  `confirmation_required` or `confirmation_not_needed` reloads the project (TD-48, now Fix by
  S1-C16c); UI-FRM-7.
- **DL-117:** a confirmation step inside a dialog starts on Back; UI-FRM-13, UI-FRM-14, the
  `ui-reviewer` agent.
- **DL-118:** a new step's text is in the focused control's `aria-describedby`; UI-FRM-14, the
  `ui-reviewer` agent.
- **DL-119:** the per-project access review is its own page; two add buttons; UI-SHL-6, the
  `ui-reviewer` agent.
- Not a rule change: the project page actions' layout (UI-SHL-8) stays as is for now, logged as
  TD-49 for Slice 2.
- Inserted: S1-C16c (Review follow-ups), building DL-116 to DL-118.

## docs-consistency, pass 1 (base `dec09e4`)

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | gap | `ui-design-guide.md` UI-FRM-13 | DL-117 names UI-FRM-13, which said nothing of the confirm step's focus. | **Fixed:** the confirm and `join_org` steps start on Back (DL-117). |
| 2 | stale | `tech-debt.md` TD-48 | Why still said the reload was the owner's to decide. | **Fixed:** the owner chose it (DL-116). |
| 3 | gap | `ui-reviewer.md` (UI-SHL-6 check) | Didn't say the access review isn't a pages item. | **Fixed:** DL-119 added there, and the agent to DL-119's Applies to. |

### Decisions for the owner (undecided)

1. **`members_changed` on project settings' classification save:** a member added or removed
   after the page loaded gives a 422 `members_changed` on `confirmed_member_ids`. Options: (a) add
   it to DL-116's reload in S1-C16c; (b) keep the server's message in the form's alert, recorded
   as intended; (c) log it for Slice 2.
2. **`security-reviewer` on S1-C16c:** the build plan names checkpoints 1 to 16b. Options: (a)
   extend the range to 16c (the build plan and the `checkpoint` skill's example); (b) leave it,
   relying on the diff-path trigger, which doesn't cover views.
