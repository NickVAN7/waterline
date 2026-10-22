# Review record: DC-2026-10-22b — answers to the Slice 2 plan's questions

- **Change:** the owner's Oct 22 answers to the Slice 2 plan's open questions (Q1 to Q5,
  `docs/reviews/s2/S2-plan.md`) and to the five decisions left by
  `DC-2026-10-22-slice-2-plan.md`, recorded as DL-159 to DL-167. Docs only.
- **Base commit:** `9d567ef`
- **Files:** `docs/decision-log.md`, `docs/build-plan.md`, `docs/design-doc.md`,
  `docs/ui-design-guide.md`, `docs/reviews/s2/S2-plan.md`, `docs/reviews/s1/S1-ui-feedback.md`,
  `docs/reviews/design-changes/DC-2026-10-22-slice-2-plan.md`, `.claude/agents/ui-reviewer.md`
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 4 fixes, all applied; 2 decisions for the owner.
- **Gates:** `uv run wl check` green.

---

## docs-consistency (base `9d567ef`)

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | superseded | ui-design-guide UI-SHL-4 | From S2-C0e the user menu held "Administration" only, so the theme choice would go in S2-C0e. | **Fixed:** the theme choice stays until S2-C0g (DL-164); UI-SHL-4 added to DL-164's "Applies to". |
| 2 | superseded | `.claude/agents/ui-reviewer.md`, the org menu check | The same, in the reviewer's checklist. | **Fixed:** as #1; the file added to DL-164's "Applies to". |
| 3 | stale | S2-plan, threat-model row "An oversized tree" | Cited DL-154. | **Fixed:** cites DL-159. |
| 4 | gap | DL-167's "Applies to" | SVAR's scope is also stated in design-doc §2, the build plan's tooling line, the screen inventory, the testing strategy, `frontend/CLAUDE.md`, and `ui-reviewer`. | **Fixed:** DL-167 and the S2-C0b row name every statement of SVAR's scope. |

**Decisions for the owner** (left undecided):

1. **Does a requirement's restriction `PUT` bump the requirement's `version`?** DL-162 takes no
   `version` "as a project's doesn't", but `project` has no `version` column and `requirement`
   does (design-doc §2, "Optimistic locking"). Options: (a) the write bumps `version`, so an open
   edit form gets a 409 after a restriction change; (b) a direct update that doesn't bump it,
   like rank, adding a second exception to design-doc §2.
2. **Does `POST …/requirements/{number}/approve` take a `version`?** Options: (a) no: it
   approves whatever revision is current; (b) the client sends the `version` it showed (409 when
   stale), so the revision approved is the one on screen.
