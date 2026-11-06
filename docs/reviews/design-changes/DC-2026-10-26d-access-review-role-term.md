# Review record: DC-2026-10-26d — the access review's role term is "Role"

- **Change:** the owner's answer to S2-C0j's open question 1 (DL-191): the per-person access
  review's "Workspace role" term is renamed "Role", the users list's column name. It changes code
  built in S2-C0j, so it's bundled into S2-C1 (DL-131). Docs only.
- **Base commit:** `2370c0b`
- **Files:** `docs/decision-log.md` (DL-191), `docs/build-plan.md` (the S2-C1 row)
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** no fixes; no decisions for the owner.
- **Gates:** `uv run wl check` green.

---

## docs-consistency (base `2370c0b`)

No fixes, no decisions. "Workspace role" as the access review's term is only in
`AccessReviewView.vue` and its Vitest spec, both now in S2-C1's scope; the user guide doesn't
quote the label; the design doc's "Workspace roles" heading is a different concept.

Its note that renaming the term in `AccessReviewView.spec.ts` changes a spec test: that file is
a Vitest spec, not a `spec-test-writer` test of `app/rules/` or `app/authz/`, so the owner's
approval rule for spec tests doesn't apply; S2-C1 updates it with the rename.
