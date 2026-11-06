# Review record: DC-2026-10-23 — the owner's answers to S2-C0d to S2-C0f's open questions

- **Change:** the owner's answers to the open questions in `docs/reviews/s2/S2-C0d.md`,
  `S2-C0e.md` (UI-SHL-8's exception, confirmed), and `S2-C0f.md`, recorded as DL-176 to DL-180.
  DL-176 and DL-178 change no code; DL-177, DL-179, and DL-180 are built in S2-C0g (review
  answers bundled into the next planned checkpoint, DL-131), whose row now lists them. The user
  guide describes the app as built, so S2-C0g updates it with that code. Docs only.
- **Base commit:** `104f383`
- **Files:** `docs/decision-log.md` (DL-176 to DL-180; DL-136's "Superseded by"),
  `docs/design-doc.md` (§1.1, §5 "Access review"), `docs/ui-design-guide.md` (UI-SHL-8, UI-FBK-6,
  UI-SHL-10), `docs/build-plan.md` (the projects API's unshipped modules, the per-person access
  API, S2-C0g), `docs/developer-guide.md` (the S2-C0d status line), `.claude/agents/ui-reviewer.md`
  (UI-SHL-8's exception)
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 4 fixes, applied; 1 decision for the owner.
- **Gates:** `uv run wl check` green.

---

## docs-consistency (base `104f383`)

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | internal | design-doc §1.1 | The paragraph's later sentence still gave every unshipped module `module_unavailable`, against DL-178's new sentence before it. | **Fixed:** the later sentence refers back ("as above"). |
| 2 | superseded | DL-136 | "Superseded by: none", though DL-178 supersedes its wording in part. | **Fixed:** "DL-178, in part (a v2 module is a 422 `enum`)". |
| 3 | contradiction | build plan (the projects API, "Unshipped modules"); developer guide (S2-C0d's status line) | Both said the API refuses every unshipped module with `module_unavailable`. | **Fixed:** `module_unavailable` for `sprints` and `github`, `enum` for a v2 module (DL-178). Siblings: frontend `CLAUDE.md` names only `sprints` and `github` (correct). |
| 4 | superseded | `.claude/agents/ui-reviewer.md`'s UI-SHL-8 check | No exception, so the reviewer would flag the auth card's pages again (S2-C0e's finding 2). | **Fixed:** the check names DL-176's exception. |

**Decisions for the owner** (left undecided):

1. **How the org overview fetches only its archived projects** (DL-180). The only archived filter
   the docs define, `?include_archived=true` (build plan, "Hidden rows"; `ListSpec.archived_column`),
   returns live and archived projects together, and the overview pages its list. Options: (a) an
   archived-only filter on `ListSpec`'s archived handling (e.g. `?archived=only`), named in "Hidden
   rows" and the org projects API, with API tests and `wl gen-client` in S2-C0g: a small backend
   change any list with `archived_column` can reuse; (b) `include_archived=true` split into the two
   sections in the browser: no API change, but a page mixes both kinds, so both sections page
   wrongly or the overview stops paging; (c) a second, unpaged request: an unbounded list and a
   filter `ORG_PROJECTS` may not have. Needed before S2-C0g; the S2-C0g row's "on that spec's
   archived filter" is then reworded to name it.
