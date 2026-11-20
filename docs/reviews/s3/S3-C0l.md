# Review record: S3-C0l — Project & requirements feedback

- **Checkpoint:** Slice 3, Checkpoint 0l (group `s3-polish`; PR #12)
- **Base commit:** `cdb1c61` (S3-C0k, the last commit before the checkpoint; DL-17)
- **Reviewers:** `security-reviewer` (the diff touches the project area), then
  `checkpoint-reviewer` and `ui-reviewer`, one at a time on one snapshot (DL-105). No finding was
  major or a blocker, so none was re-reviewed (DL-105).
- **Totals:** security-reviewer ready, no findings; checkpoint-reviewer ready after fixes, 2
  minor; ui-reviewer pass with findings, 3 minor, 2 notes, 4 coverage gaps. In all: 5 findings
  fixed, 2 notes to the owner, 0 logged, 0 rejected; 3 of the gaps closed.
- **Gates at close:** `wl check` green; the full e2e suite green locally (110); CI on the commit.

---

## Before the reviewers

- **Owner decisions at the start** (Nov 13, 2026), each recorded: the tree's badge reads
  "Awaiting approval" (DL-376, settling the plan review's item 8); one shared hint line before the
  right-aligned Expand requirement and Move; both project add paths start at Member (DL-378);
  UI-FRM-15 is one primary button per form (DL-377). The build plan's S3-C0l row says so
  (DL-362).
- **Tech debt due now:** TD-105 (a project key's API messages in the slug's words), targeted at
  S3-C0l: resolved, with `PROJECT_KEY_MESSAGES` and an API test.
- The implementing session's own sabotage checks (evidence for the reviewers, not verification):
  each of `pending_entity_ids`' three filters removed (project, status, type), the key's own
  messages dropped, and, after review, the Trash announcement reverted and the tree forced wider
  than 320 px. Each failed its test; each was restored.

## security-reviewer, pass 1 (base `cdb1c61`)

Verdict: ready. No findings, no questions.

Checked and fine (its words, condensed): `awaiting_approval` comes from a query scoped to the
authorized project, pending requests, and the requirement type, set only on rows the caller
already sees, and reveals nothing beyond what `…/approval-requests` already shows them; the key
messages are fixed text; no new endpoints, actions, or request fields; the Trash filter goes
through the typed client and the list spec; the default role changes nothing the server allows.

## checkpoint-reviewer, pass 1 (base `cdb1c61`)

Verdict: ready after fixes.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | minor | lean (DL-40) | `MoveToMenu` kept its own reason (`blockedReason` and its span) beside the new `reasonShownAt`, with no product caller left. | **Fixed:** `reasonShownAt` is the one way, required; the prop, span, and spec went. Siblings: `MoveToMenu` has one caller (the tree); the backlog (S3-C20) shows its own hint the same way. |
| 2 | minor | docs | design-doc §9 still called Trash the last item of the project's navigation, with a "from S3-C0l" note after it. | **Fixed:** reworded as the screen inventory now reads (not in the navigation, DL-350; last there from DL-202). Siblings: the inventory, UI-SHL-6, and the behavior reference were already reworded. |

**Sabotage checks** (in a temporary copy, its table):

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| "Awaiting approval" counts only requirement requests | DL-376, Q12b; schema-doc `approval_request` | removed `entity_type == entity_type` in `pending_entity_ids` | `test_requirements.py -k pending` | `test_the_tree_marks_only_requirements_with_a_pending_request` |
| A panel that finds no request clears the row's badge | behavior reference | `ApprovalSection` no longer emits `awaiting` for no request | `ApprovalSection.spec.ts`, `RequirementsView.spec.ts` | `tells the tree whether it awaits approval, with no request`; `a request no longer pending … leaves the row's "Awaiting approval"` |
| Trash ignores a type the API doesn't know | DL-350 | returned the raw URL value | `TrashView.spec.ts` | `ignores a type it does not know` |

Questions: none.

## ui-reviewer, pass 1 (base `cdb1c61`)

Verdict: pass with findings.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | minor | UI-TBL-3, UI-FBK-8 | Changing or clearing the Trash Type filter was often not announced: the live text said "Loading…" only with no data yet, and the count didn't change (one type). | **Fixed:** "Loading the trash…" on every load, as `OrgProjectsView`; a spec whose second load never ends asserts it (it fails against the old condition). Siblings: the other filtered list, `OrgProjectsView`, already does this. |
| 2 | minor | UI-FRM-5, UI-FRM-6 | A Modules error could sit inside the closed `<details>` when focus went to an earlier invalid field. | **Fixed:** a watch opens Modules whenever it holds an error; a spec with two invalid fields. Siblings: no other disclosure holds a field. |
| 3 | minor | UI-SHL-7 | With `whitespace-nowrap` IDs and two badges, nothing showed the tree reflows at 320 px. | **Fixed (measured):** an e2e at 320 px with a nested branch, in PORTAL with its awaiting requirement, asserts no sideways scroll; it fails with the tree forced wider. The IDs stay unwrapped. |
| 4 | note | UI-FBK-3 | An empty Trash opened from Requirements reads "No deleted items match Type: Requirement … Try another type", while only one type exists. | **To the owner** (below). |
| 5 | note | DL-350 | The delete status's "Open Trash" link opens Trash unfiltered; the header link filters. | **To the owner** (below); DL-350 keeps that link as it was. |

Coverage gaps it listed, and what was done:
- The panel finding a pending request at the view level (only true to false was tested):
  **closed**, `a pending request the panel finds gives its row "Awaiting approval"`.
- The Trash filter's announcement and the tree at 320 px: **closed** (findings 1 and 3).
- No e2e visits Project settings, so the Modules summary has had no axe run in a browser: left
  for the manual pass (listed in the report), as before this checkpoint.
- The primary tone checked by class, not rendered color: kept; the token pair is checked.

Needs the manual pass (its list): the controls row at 200% and 400% zoom; the add-member
dialog's title focus ring; the Modules summary with the keyboard, a screen reader, and forced
colors; the dividers in forced colors; the Trash breadcrumb under 40rem; the Trash link and the
badge in both themes.

## Owner decisions and open questions

- **Decided at the start:** DL-376, DL-377, DL-378, and the shared hint line (above).
- **Open — the empty Trash from Requirements (ui-reviewer 4):** with one type, the filtered empty
  state offers "Try another type". Options: (a) keep until S3-C20 adds tasks (a second type
  makes the copy true); (b) show "The trash is empty" when the filtered list is empty and no
  other type exists; (c) drop the filter from the link until there's a second type.
  Recommendation: (a), nothing to change now.
- **Open — "Open Trash" after a delete (ui-reviewer 5):** filter it to requirements like the
  header link, or keep it unfiltered as DL-350 says. Recommendation: filter it (one way to arrive),
  a one-line change with a DL entry, if you agree.
