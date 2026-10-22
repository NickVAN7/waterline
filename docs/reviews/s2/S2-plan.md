# Review record: Slice 2 plan (Oct 21–22, 2026)

The owner's Slice 2 planning decisions (chat session, Oct 21, 2026), applied to the repository
docs as a design change outside a checkpoint (`design-change` skill; its review record is
`docs/reviews/design-changes/DC-2026-10-22-slice-2-plan.md`). The plan is the build plan's
"Slice 2 — Requirements & approvals" section; this record holds the fixes, decisions,
conventions, threat-model pass, and open questions behind it (DL-139).

## Fixes (gaps found while writing the plan)

| # | Fix |
|---|---|
| F1 | The docs consistency tests required every slice's checkpoint table to start at row 1, so rows S2-C0a to S2-C0i would have failed `wl check`. The owner chose to let a table start at 0 or 0a (DL-156), a `chore:` change in this design change |
| F2 | DL-134's rename also covers the two restriction actions (`project.raise_classification` and `project.lower_classification` → `project.raise_restriction` and `project.lower_restriction`), which the decision's list didn't name; "full rename" includes them |
| F3 | The schema doc is checked against the models, so it keeps the built names (`classification_*`, `restricted`) until S2-C0d's migration, with a note naming the rename; the developer and user guides, and the `.claude/` lines that name built code, change with the code in S2-C0d to S2-C0h too. The rule docs (design doc, UI design guide, testing strategy, screen inventory, the plan) state the decided rules now |
| F4 | With Restricted gone, Confidential's examples take in all PII (the design doc's levels table); existing `restricted` rows become `confidential` (DL-134) |
| F5 | Design-doc §1.1 and §10 said the project activity feed shows status and lead changes from Slice 2; the logging stays in Slice 2 and the feed moves to Slice 3 (DL-147) |
| F6 | Design-doc §16 already listed @mentions under v1.5, so DL-144 records the placement without a change there |
| F7 | The UI design guide had no rule IDs for rendered markdown; DL-140, DL-141, and DL-145's UI rules are UI-MD-1 to UI-MD-3 (§7.3), with a matching section in the `ui-reviewer` checklist |
| F8 | The owner's UI feedback moved to `docs/reviews/s1/S1-ui-feedback.md` (DL-158); each item carries its S2-C0 row |

## Decisions

| # | Decision | DL |
|---|---|---|
| D1 | Export control hidden in the UI; the API and Slice 2's gate stay | DL-133 |
| D2 | "Classification" becomes "Restriction"; the Restricted level removed | DL-134 |
| D3 | PrimeVue 5 stays, with the owner's license key | DL-135 |
| D4 | An unshipped module can't be enabled | DL-136 |
| D5 | The owner's Slice 1 UI feedback, mapped to S2-C0's rows, with its rule changes | DL-137 |
| D6 | The simplicity audit (`simplicity-auditor`), built in S2-C0a | DL-138 |
| D7 | Planning a slice, and sizing its checkpoints | DL-139 |
| D8 | Markdown rendered in the browser (`markdown-it`, DOMPurify) | DL-140 |
| D9 | The markdown editor: a textarea with Write and Preview tabs | DL-141 |
| D10 | A Content-Security-Policy from Slice 2 | DL-142 |
| D11 | Length limits | DL-143 |
| D12 | Item-ID auto-links in Slice 3; @mentions in v1.5 | DL-144 |
| D13 | Revision compare in the browser, on the raw markdown | DL-145 |
| D14 | Trash in Slice 2; restoring a tree | DL-146 |
| D15 | Item history in Slice 2; the project activity feed in Slice 3 | DL-147 |
| D16 | Requirement status: no transition table | DL-148 |
| D17 | Acceptance-criteria templates, one per project type | DL-149 |
| D18 | The tree widget decided by a spike, S2-C0b | DL-150 |
| D19 | TD-60: the docs describe the one registry | DL-151 |
| D20 | TD-44: a first-admin candidates endpoint | DL-152 |
| D21 | My work's project fields | DL-153 |
| D22 | The ranked-view cap, proposed at 2,000 (open question Q1) | DL-154 |
| D23 | Slice 3, 4, 7, and v1.5 placements | DL-155 |
| D24 | S2-C0 becomes rows S2-C0a to S2-C0i | DL-156 |
| D25 | Two screen-inventory dependencies | DL-157 |

## Conventions (set in Slice 2, copied by later slices)

| # | Convention |
|---|---|
| C1 | Ranked views return complete lists up to a hard cap, with `truncated: true` above it (proposed 2,000, DL-154) |
| C2 | Markdown is rendered only in the browser, through one sanitizing renderer; the API carries markdown only; a CSP is the second layer (DL-140, DL-142) |
| C3 | An item's restriction is set through its own `PUT …/restriction`, as a project's is |
| C4 | Entities without a number (approval requests) are addressed by UUID, at `/api/approval-requests/{id}` |
| C5 | Append-only item feeds (activity, revisions) use cursor paging |

## Actions per row (DL-139)

Proposed names, each registered in `authz/actions.py` (DL-151) and confirmed by its row's spec
tests. Content actions are denied by the export-control gate to anyone without an explicit
membership (design-doc §3.1); the org overview's action is open question Q5.

| Row | Endpoints | Action | Allowed to | Kind |
|---|---|---|---|---|
| S2-C0c | `GET /api/orgs/{org_id}/first-admin-candidates` | `project.assign_first_admin` (exists) | org owners/admins, workspace admins, system admins | management |
| S2-C0f | the org overview page (an org read and its project list) | Q5 | — | management |
| S2-C3 | `GET …/requirements/{number}/activity` | `requirement.view` | project viewers and up, inherited admins | content |
| S2-C5 | `POST …/requirements` | `requirement.create` | project members and up | content |
| S2-C5 | `GET …/requirements`, `GET …/requirements/{number}` | `requirement.view` (the list scoped by content access) | project viewers and up, inherited admins | content |
| S2-C6 | `PATCH …/requirements/{number}` | `requirement.update` (title, description, status except `approved`, priority) | project members and up | content |
| S2-C6 | `PATCH …` changing `reporter_id` | `requirement.reassign_reporter` | project admins | content |
| S2-C6 | `PUT …/requirements/{number}/restriction` | `requirement.raise_restriction`; `requirement.lower_restriction` | members and up; project admins | content |
| S2-C7 | `POST …/requirements/{number}/move` | `requirement.update` | project members and up | content |
| S2-C8 | `DELETE …/requirements/{number}`, `POST …/restore` | `requirement.delete` (whoever may delete may restore, design-doc §9) | the reporter while never approved; project admins | content |
| S2-C8 | `GET /api/projects/{key}/trash` | `requirement.view` (each row with its `allowed_actions`) | project viewers and up, inherited admins | content |
| S2-C9 | `GET …/revisions`, `GET …/revisions/{revision_number}` | `requirement.view` | project viewers and up, inherited admins | content |
| S2-C10 | `POST …/approval-requests` | `approval_request.create` (named in design-doc §6.2) | project admins | content |
| S2-C10 | `GET …/approval-requests`, `GET /api/approval-requests/{id}` | `requirement.view` on the approved entity (approval requests inherit, design-doc §3.1) | project viewers and up, inherited admins | content |
| S2-C10 | `POST /api/approval-requests/{id}/cancel` | `approval_request.cancel` | project admins | content |
| S2-C11 | `POST /api/approval-requests/{id}/decision` | `approval.decide` (personal) | the named approver, with content access | content |
| S2-C11 | `POST …/requirements/{number}/approve` | `requirement.approve_manually` | project admins | content |
| S2-C14 | `GET /api/me/work/approvals` | signed in (scoped to the user's pending rows and content access) | — | — |

## Threat-model pass

| Threat | Control | Row |
|---|---|---|
| Stored XSS through markdown | Raw HTML off, DOMPurify, links limited by scheme, no remote images, the CSP; an XSS-corpus component test and an end-to-end payload test | S2-C16 |
| A parent, a move target, or an approver from another project, or someone without access | Scoped lookups (a 404 for anything outside the project or the user's access); same-project and cycle checks | S2-C5, S2-C7, S2-C10 |
| Deciding someone else's approval | `approval.decide` is a personal action no admin level grants | S2-C11 |
| Export-controlled content leaking through a list, feed, revision, the trash, or My work | Content scoping in every list query, the gate on every content action, a test per list | S2-C4 onward |
| Storage growth from huge descriptions times revisions | Length limits (DL-143); a revision only on a real change | S2-C5, S2-C6 |
| An oversized tree | The ranked-view cap (DL-154) | S2-C5 |
| Races: a replacement against a decision; a delete against a restore | Row locks in a fixed order, a race test each | S2-C8, S2-C11 to S2-C13 |
| Names of former members in history | The server resolves names at read time; see Q2 | S2-C3 |
| A remote image revealing that a Confidential item was opened | Image syntax renders as a link (DL-140) | S2-C16 |

## Open questions for the owner (answered before S2-C0a starts)

**Q1. The ranked-view cap (DL-154).** The requirement tree is returned whole (drag needs the full
list), so a cap stops one huge project from making the page slow or the response unbounded.
Options: 2,000 per project, `truncated: true` above it, and a tech-debt entry to page the tree if
a project nears it; or a lower cap (1,000) with the same handling; or no cap until a project
needs one. **Recommendation: 2,000**, which is far beyond any v1 project and cheap to raise.

**Q2. Names of former members in history.** The History tab shows who changed what. Once someone
leaves the project (or is deactivated), their name still shows on their old entries to anyone who
can read the requirement. Options: accept it (the entries were visible to the same people
before); or show "Former member" for anyone no longer on the project. **Recommendation: accept
it**, with the "Deactivated" badge for a deactivated account as elsewhere: the history is the
record of who did what, and hiding names would make it useless for sign-off.

**Q3. Approving by hand: one path or two.** S2-C11 adds
`POST …/requirements/{number}/approve` (`requirement.approve_manually`), since approving records
the revision and cancels a pending request. A `PATCH` setting `status` to `approved` then needs a
defined answer. Options: the `PATCH` refuses `approved` for everyone (422 `validation_error` on
`status`, type `use_approve`), so there is one path; or the `PATCH` accepts it from those with
`requirement.approve_manually` and does the same work, with no separate endpoint. Design-doc §5
says members get a 403 for the transition, which either option keeps for members.
**Recommendation: one path, the `approve` endpoint**; the `PATCH` answers 403 to members (as §5
says) and 422 `use_approve` to admins.

**Q4. A requirement's restriction and `version`.** `PUT …/requirements/{number}/restriction`
mirrors the project's, which takes no `version`. Options: no `version` (last write wins; each
change is logged); or `version` with a 409, like content edits. **Recommendation: no `version`**,
as for projects: a restriction change isn't a content edit, and raising can't lose anything.

**Q5. The org overview page's gate.** UI-SHL-10 says anyone who opens org admin pages holds
inherited project admin, so every project's settings link works. `org.view` admits plain org
members, so it can't be the gate. Options: `org_member.manage` (org owners/admins, workspace
admins, system admins: the people who already see Members), `org.update` (adds nothing for org
admins, who can't rename the org), or a new `org.overview` action with the same holders as
`org_member.manage`. **Recommendation: `org_member.manage`**, since the overview sits beside
Members and has the same audience; no new action.

Anything the design change's `docs-consistency` pass leaves for the owner is in its record
(`DC-2026-10-22-slice-2-plan.md`).
