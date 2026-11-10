# Review record: DC-2026-10-26 — the owner's answers to S2-C0h's open questions

- **Change:** the owner's answers to `docs/reviews/s2/S2-C0h.md`'s four open questions, each the
  recommended option: step 2's changed email is checked on Create account, only if it changed
  since the last check (DL-185, as built); project settings' spacing is done as is (no rule
  changes, so no entry); an archived project's Unarchive stays in the Danger zone (DL-186, as
  built); a system admin with no workspace role shows the "System admin" badge alone, and "User"
  in the users list and "None" in the access review both stay (DL-187, amending DL-183; from
  `DC-2026-10-25-c0g-review-answers.md`'s Decisions 1 and 2). DL-187 changes code built in
  S2-C0h, so it's bundled into the next planned checkpoint, S2-C0i (DL-131). Docs only.
- **Base commit:** `44859d0`
- **Files:** `docs/decision-log.md` (DL-185 to DL-187; DL-183's "Superseded by"),
  `docs/ui-design-guide.md` UI-FRM-13, UI-FRM-14, UI-FBK-6, `docs/build-plan.md` (the account
  bullet, the S2-C0h and S2-C0i rows), `docs/developer-guide.md` (Status)
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 2 fixes, applied; no decisions for the owner.
- **Gates:** `uv run wl check` green.

---

## docs-consistency (base `44859d0`)

| # | Kind | Finding | Resolution |
|---|---|---|---|
| 1 | superseded | The build plan's S2-C0h row said step 2's email is "re-checked on change", UI-FRM-13's old wording, readable as checked as it's typed. | **Fixed:** "checked again on Create account if it changed (DL-185)". |
| 2 | superseded | The developer guide's Status said "checked again when changed", likewise. | **Fixed:** "checked again on Create account if changed (DL-185)". |

**Decisions:** none.
