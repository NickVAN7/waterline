# Review record: Slice 3 plan (Nov 10, 2026)

The owner's Slice 3 planning decisions (chat session, Nov 10, 2026), applied to the repository
docs as a design change outside a checkpoint (`design-change` skill; its review record is
`docs/reviews/design-changes/DC-2026-11-10-slice-3-plan.md`, which also holds the plan's readiness
review and lists which decisions got decision-log entries, DL-344 to DL-354). Part 1 is the build
plan's "Slice 3 — Tasks" section as approved; the build plan holds the current version. The plan
as approved follows.

**Status:** every open question answered by the owner on Nov 10, 2026 (Q6 withdrawn). Ready
for the `design-change` that writes it into the repo.

Draft for the owner's review, verified against `main` after the Slice 2 merge (`664eb92`, PR #11;
its tree is `s2`'s `6b422ab`, which draft 1 used): the Slice 3 stub (S3-C0a to S3-C0h, DL-312 to
DL-343), "Planning a slice" (DL-139), the slice overview, "Later slices — placements decided so
far", the design, schema, and screen-inventory docs, the open tech-debt log, S2-C22's audit
findings, and the code itself. Once decided, it becomes the build plan's Slice 3 section and
`docs/reviews/s3/S3-plan.md` through the `design-change` skill (DL-139).

Part 1 is the proposed build-plan section. Part 2 is the plan record (fixes, decisions,
conventions, actions per row, threat model, open questions). Part 3 maps every
`S2-ui-feedback.md` item to its row, as the Slice 3 section requires.

**Changed from draft 1, after checking it against the code:**
- **Q6 dropped.** The docs tests only check that every built table is documented, never that a
  documented table is built (`model_tables_missing_from_schema_doc`), so nothing forces
  `task_dependency` in Slice 3. It becomes fix F1: the feature map's Owns cell notes "(from Slice
  6)".
- **Trash across two tables** (fix F6 rewritten): `TRASH` is a `ListSpec` over `Requirement`
  only (with its `type` filter already declared for more types), so tasks joining it needs a
  union query; S3-C9 says so.
- **The requirement tree takes no filters today** (`GET …/requirements` has no query model), so
  the filter bar on the tree, the "awaiting approval" filter, and the requirements CSV need a
  decision: new Q13.
- **Task types per project type** are undecided (`task.type` holds seven values, ERP's included):
  new Q14.
- **The questions are due before S3-C0a**, not S3-C0i: "Planning a slice" says before the
  slice's first checkpoint.
- **TD placements corrected:** TD-64 is 387 lines of 600, so the new actions don't trigger it
  (slice-end review only); TD-100 moves to the slice-end review (no Slice 3 row touches approval
  reads); TD-73 is due Slice 7, pulled into S3-C7 only if Q3 is accepted.
- **My work's sections are separate routes** (`/api/me/work/approvals`, …, no `{section}`
  parameter), so the task sections are `/api/me/work/tasks` and `/api/me/work/reviews`.
- **Restore is its own action** (`requirement.restore`), so tasks get `task.restore`.
- **Activity endpoints live in the `activity` router**; the task's History goes there too.
- **The project home shows the current phase** (screen inventory, "Project home"), added to
  S3-C30.
- **S3-C33's reviewers** follow the `checkpoint` skill's list (`repo-auditor`, `simplicity-auditor`
  included).
- **Feedback items already answered:** "Show deactivated" moves into the filter bar (TD-97, so
  not to the bottom of the list); the panel's buttons stay in its header (DL-325); the org on
  project pages and the link back to members come with the breadcrumbs (S3-C0e). Part 3 maps all
  50 items.
- **The Trash feedback item is cut off** mid-sentence ("…accessible from the Requirements page,
  but"): completed by the owner (Nov 10) — "…and any other pages that will allow the user to
  'Trash' an item"; Q12a now holds only the details.

---

# Part 1 — Build plan: Slice 3 — Tasks

**Goal:** tasks can be created, triaged, ordered, worked on a board and a backlog, broken into
subtasks, moved through the transition rules, deleted and restored; requirements show their
tasks; phases and workstreams exist; every list has the filter bar and CSV export where
decided (saved filters last, as a nice-to-have); My work shows the user's tasks and reviews; the project activity feed
exists; and the owner's Slice 2 feedback is in. After this slice Waterline can track its own
build (build plan, slice overview).

**Before starting:** the open questions below answered before S3-C0a (build plan, "Planning a
slice"); `uv run wl audit` green; the web rows (S3-C16 onward) provisional, re-cut before each
starts (DL-139). The slice-boundary audit findings are all placed already: Y4 in S3-C0a, Y6 in
S3-C0d, A2 and A3 as TD-100 and TD-101; Y1, Y2, Y3, Y5 were applied by the retro.

**Carry-in tech debt** (Fix by: Slice 3 or an S3 row):

| TD | Row |
|---|---|
| TD-103 | S3-C0a |
| TD-92 | S3-C0d |
| TD-101 | S3-C6 (assignee and reviewer would be a third and fourth copy of the check: one shared helper) |
| TD-38, TD-41, TD-96 | S3-C13 (server search) and S3-C17 (the pickers) |
| TD-97, TD-102 | S3-C16 (the filter bar) |
| TD-37 | S3-C29 (My work's "see all": the per-section routes exist, so frontend only) |
| TD-19, TD-31, TD-42, TD-64, TD-68, TD-86, TD-100 | S3-C33 (the tech-debt review; TD-64 is 387 of 600 lines, and Slice 3's ~16 actions shouldn't cross it; TD-100 only if no row touches approval reads first) |
| TD-73 | S3-C7 (Q3 decided: the one-statement rewrite, shared with the tree; it was due Slice 7) |

### Checkpoints

S3-C0a to S3-C0h are as decided (DL-312 to DL-343), unchanged here. S3-C0i to S3-C0m are new:
a spike, and the Slice 2 feedback the handoff didn't cover (each `S2-ui-feedback.md` item
marked with its row, as Slice 2 did, DL-137, DL-158).

| # | Checkpoint | Includes |
|---|---|---|
| 0a–0e, 0g–0h | *(as decided)* | Project pages' shared setup; the git guard's trial; the manual-pass seed; the split pane; breadcrumbs; Documentation as a guide and a reference; generated screenshots |
| 0f | My work grouped by organization *(amended, Q9)* | As decided (DL-329, DL-330, DL-332, DL-334; past decisions removed, DL-333), with three changes: the order is Favorites, then each organization, then Approvals waiting for you (below the projects, superseding DL-333's approvals-first); each organization's section shows its first **10** projects (active first) with "Showing 10 of N", its count, and **All N projects**, and the hidden-projects toggle (superseding DL-331's "every project"); so `GET /api/me/work` returns each org's first 10 and its total, which settles the row's open question (DC-2026-11-09, decision B) |
| 0i | Backlog widget spike | Q1: SVAR DataGrid (row drag, never exercised in the Oct 10 spike, UI-SVR open item 5c) against PrimeVue DataTable's row reorder, on one checklist: pointer drag, the move menu outside the widget, a server-denied move snapping back, keyboard, axe, the token theme audit, ~2,000 rows. Evidence in `docs/spikes/`; the result is a decision-log entry deciding S3-C19 and UI-SVR-2's backlog line. The owner sees a working example of each option (a runnable demo in the spike folder, and screenshots or a short recording in the results) before deciding; no product code |
| 0j | Shell feedback | The sidebar stays put while the page scrolls; browser tab titles (one short pattern, e.g. `WTL-RQ-12 · Waterline`, as a UI-SHL rule); the sidebar says whose items it shows (org vs project, a heading or label); project selector (arrow right-aligned, "All projects" styled apart without the link look, the filter behind a search button); Account's "Change password" a button; the frontend design skill's trial per Q12i |
| 0k | Admin pages feedback | Org overview ("Archived projects" heading; an archived project shown as Archived, not its old status; the "Name" line removed; the slug in the title); the deactivated marker on people lists reworked, with fixed column widths when shown; workspace users' Role column gains the user's orgs and projects (backend: a memberships summary on the user row, API tests, `wl gen-client`); workspace orgs table gains project and member counts and owners (backend, same); access review ("Why they reach it" renamed; an inherited admin's project role shown as "Admin (inherited)", per Q12h). The org-member add's project step is its own row, S3-C0m (Q12g) |
| 0l | Project & requirements feedback | Project settings (Save restriction in the primary tone; Modules per Q12c); add-member dialog (focus on the dialog's title, the list not opening on its own; the email path defaults to Member); requirements page (the selection hints, the toolbar right-aligned to the table, the title-to-table spacing); "Awaiting approval" on the tree per Q12b (backend: a field on `RequirementItem`, which has none today); History and Revisions spacing with a rule between entries; the full page's spacing (title vs description); compare revisions per Q12e; Trash per Q12a, its explanation text removed, the nav link replaced by a Trash link in the Requirements header |
| 0m | Add an org member to projects too | Q12g: the org's add-person form gains an optional last step, a multi-select of the org's projects the actor may add members to, each with a role (Member by default); backend: the add takes the projects, adds each membership through the project service in the same request (each its own audit event; the export-control confirmation where it applies), all or nothing; API and race tests; `wl gen-client` |
| 1 | Models & migration | `phase`, `workstream`, `task`, `subtask` (schema-doc), one migration; `requirement.workstream_id` (marked Slice 3); `task`'s `(project_id, status, rank)`, `ix_task_assignee_id_status`, `ix_task_reviewer_id_status`; `RestrictionMixin` on `task`; not built: `task.sprint_id`, `milestone_id` (Slice 4), `search_vector` (Slice 6), `task_dependency` (Slice 6, F1); constraint tests; factories |
| 2 | Task rules & actions | `rules/task_transitions.py` (design-doc §5's table: who may make each transition, `allowed_transitions` computed from it), `rules/branch_name.py` (the lowercase ID plus a title slug, design-doc §6; non-ASCII and length handled), the task types allowed per project type (Q14), all test-first by `spec-test-writer` and mutation-tested; the `task.*`, `subtask.*`, `phase.*`, `workstream.*` actions in the registry, each marked content or management; their matrix rows (export control included) |
| 3 | Phases | `GET/POST /api/projects/{key}/phases`, `GET/PATCH/DELETE …/phases/{id}`, `POST …/phases/{id}/move` (rank among the project's phases); hard delete only while no task references it (422 `in_use`); `status`, dates, and baselines logged (`entity_type = phase`); members and up |
| 4 | Workstreams | `GET/POST /api/projects/{key}/workstreams` (`include_archived`), `GET/PATCH …/workstreams/{id}`, `POST …/move`, `…/archive`, `…/unarchive`; the lead a project member (the project lead's rule); archived hidden from pickers, still shown on items; `workstream_id` on a requirement's `PATCH`, logged, same project |
| 5 | Tasks: create, read, list | `POST /api/projects/{key}/tasks` (the `TA` number, `todo`, reporter = creator, priority `medium`, rank at the bottom, restriction at creation, requirement/phase/workstream in the same project and visible, title and description limits, DL-143); `GET …/tasks` per Q2 (the ranked view, declared filters, display sorts, the 2,000 cap with `truncated`); `GET …/tasks/{number}` with `allowed_actions` and `allowed_transitions` |
| 6 | Tasks: update | `PATCH …/tasks/{number}` (`version`, 409 when stale; every field in design-doc §6; status through `rules/task_transitions.py`, a denied transition 403; assignee and reviewer per Q5, through one shared person check replacing `_check_reporter`/`_check_approver`'s copies, TD-101; reporter reassignment admins only, as requirements, DL-211; every logged field through `log_change()`, §10); `PUT …/tasks/{number}/restriction` (no `version`, as requirements, DL-162) |
| 7 | Task order | `POST …/tasks/{number}/move` (`after_id` or `before_id`, optional `status` for a cross-column drop: status and rank in one request, the transition checked first, nothing saved if denied); rank from `rules/rank.py`; the whole project's task order rewritten in one statement on a tie or past the cap, moves one at a time under the tree's project-row lock (Q3, closing DL-216), with race tests; TD-73 (the tree's rewrite becomes the same one statement) |
| 8 | Subtasks | `GET/POST …/tasks/{number}/subtasks`, `PATCH/DELETE …/subtasks/{n}`, `POST …/subtasks/{n}/move`; numbers from `task.next_subtask_number` (`allocate_subtask_number`, a direct `UPDATE … RETURNING`, concurrency-tested like `project_counter`); hard delete; members and up; the task read's `subtasks_done` / `subtasks_total` |
| 9 | Delete, restore & trash | `DELETE …/tasks/{number}` (`task.delete`: reporter as member, or admin, design-doc §5), `POST …/restore` (`task.restore`, as `requirement.restore`); subtasks hidden and restored with the task (§9); `GET /api/projects/{key}/trash` across both tables: `TRASH` becomes a union of deleted requirements and tasks (its `type` filter, declared already, gains `task`), newest first, each row's `allowed_actions`; the requirement delete's linked-tasks choice beside `children` (`tasks=detach\|delete`; delete only when the user could delete each task directly, `can_delete_tasks` on the read; each unlink logged `unlinked`; restore re-links nothing) |
| 10 | Requirement ↔ task reads | `GET …/requirements/{number}/tasks` (the requirement's tasks, for its page and the approver's review panel, DL-196); the tree items' coverage fields (`task_count`, `tasks_done`, DL-199); the tree's filters per Q13 |
| 11 | My work: tasks | `GET /api/me/work/tasks` (assigned to the user, any status but `done`/`cancelled`) and `GET /api/me/work/reviews` (`in_review`, the user reviewer), each also a section of `GET /api/me/work` with its total, on the two indexes; the summary's `due_soon` count (the user's open assigned tasks with `due_date` before today plus 7 days, overdue included, and the overdue part); export-controlled content and archived projects left out (design-doc §11) |
| 12 | Activity | In the `activity` router: `GET /api/projects/{key}/activity` (cursor-paged, declared filters: entity type, actor, field, date; names resolved server-side, "System" for actorless entries, parents and revisions named as on History, DL-275, DL-276; scoping per Q10); `GET …/tasks/{number}/activity` (the task's History, as the requirement's) |
| 13 | Server-side pickers | `?q=` search on the people candidates the pickers need: task assignee/reviewer candidates (Q5), approver candidates for everyone §6.2 allows (TD-96), and the existing pickers' sources (TD-41); the project selector's `?q=` (TD-38); offset-paged, scoped as their lists |
| 14 | CSV export | `GET …/requirements/export.csv` and `GET …/tasks/export.csv`: the list's filters (the tree's per Q13) and the visible columns (`columns=`), same scoping and cap as the list, formula-injection escaping, a `Content-Disposition` filename with the project key and date |
| 15 | Get started & home numbers | The checklist (design-doc §11, DL-201) computed on the project home read (member besides the creator; a dated phase; a requirement and a task); the per-project hide flag (a column, its migration, `PUT/DELETE …/get-started/hidden`, project admins); headline numbers per Q11 |
| 16 | Filter bar *(provisional)* | The shared `FilterBar` (chips for any number of declared filters, operators per type, `me`, Clear, the URL through `useListQuery`, UI-TBL-2/3), first used on the four people lists with "Show deactivated" moved into it (TD-97, TD-102); a UI-TBL rule |
| 17 | Searchable pickers *(provisional)* | One searchable person picker on S3-C13's endpoints, replacing the 200-row pickers (TD-41) and the approver picker (TD-96); the project selector's search (TD-38) |
| 18 | Board widget *(provisional)* | The `TaskBoard` wrapper on SVAR Kanban (DL-64; UI-SVR-1 to 7): pinned packages and their licenses, `svar-theme.css`, accessible name, visible and announced selection, server-decided moves (`api.intercept`), the move menu and status control outside the widget, `e2e/svar-known-issues.ts`; component specs on a fixture; task status, priority, and severity tones (UI guide open item 8) |
| 19 | Backlog widget *(provisional)* | Per S3-C0i's result: a `TaskGrid` wrapper on SVAR DataGrid, or the DataTable reorder through our own component; its component specs |
| 20 | Backlog page *(provisional)* | Tasks in the project nav with Board and Backlog tabs (`…/:key/tasks/backlog`); the ranked list per Q4, the move menu (top, up, down, bottom, after…), manual vs display sort, the filter bar; opening a task in the split pane; the Trash link in the Tasks header (Q12a); Export CSV (S3-C14) |
| 21 | Board page *(provisional)* | `…/:key/tasks/board`: columns per Q4, a cross-column drop through S3-C7 (a denial snaps back with its message), the card's status control, the filter bar (assignee, workstream, type, priority) |
| 22 | Create task *(provisional)* | The create dialog (title, type per Q14, description with `MarkdownEditor`, priority, requirement, assignee), expandable to `…/:key/tasks/new`, landing on the new task; "Add task" on a requirement (its requirement pre-filled); ERP type labels (`bug` → Defect, design-doc §1.1) |
| 23 | Task detail *(provisional)* | The task in `ItemPanel` and at `…/:key/tasks/:number` (S3-C0d's header): fields, status menu from `allowed_transitions`, assignee and reviewer, phase and workstream, dates, estimate and time taken, the requirement link or the "No requirement" flag, Copy branch name, restriction |
| 23a | Edit task *(provisional)* | Edit mode as the requirement's (DL-263): title, description, priority, severity (bugs), type; 409 handling; unsaved-edits prompt (S3-C0d) |
| 24 | Subtasks & History *(provisional)* | The subtask checklist on the task (add, check off, rename, reorder menu, delete with confirm; "3 of 5 done"); the task's History tab on S3-C12's endpoint, reusing the requirement's |
| 25 | Requirement ↔ tasks *(provisional)* | The requirement's Tasks section (list, "Add task"); the tree's coverage columns; the approver's review panel gains the tasks and subtasks (DL-196); the delete dialog's linked-tasks choice; tasks in Trash; the end-to-end "deleting a requirement with tasks" |
| 26 | Requirement tree filters & CSV *(provisional)* | The filter bar on the requirement tree per Q13 (matches with their ancestors as context, drag and the move menu off while filtered, a polite note saying so), including the "Awaiting approval" filter (Q12b); Export CSV of the matches (S3-C14) |
| 27 | Timeline & workstreams *(provisional)* | `…/:key/timeline`, the basic Timeline: a dated table of phases (create, edit dates and baselines, status, reorder, delete while unreferenced; DL-199); the Workstreams page (`…/:key/workstreams`, after Timeline in the nav; Q7); the Get started item "Compile your plan" now live |
| 28 | Activity page *(provisional)* | `…/:key/activity`: the feed with the filter bar over a cursor feed (UI-TBL-9), plain-language entries as on History |
| 29 | My work: tasks and summary *(provisional)* | The summary tiles at the top (Q9): Approvals waiting, Assigned to you, Waiting for your review, Overdue or due this week, each a link to its section with its full text ("2 approvals waiting"), never color alone, a zero shown as such; the two task sections below Approvals, each opening the task; "see all" for every section (TD-37); design-doc §11 and the user guide updated |
| 30 | Project home *(provisional)* | The Get started checklist (ticks, links, hide); the current phase (screen inventory, "Project home"); the headline numbers per Q11; the status control per Q12f |
| 31 | Item-ID auto-links *(provisional)* | `{KEY}-RQ-n`, `{KEY}-TA-n(.m)` (and `TC` from Slice 5) linked in `MarkdownView` (DL-144), routed by key; never inside code spans or existing links; XSS-corpus cases added |
| 32 | Saved filters *(nice-to-have; last feature row; the web half provisional)* | Backend: the `saved_filter` table (Q8: per list, per project; `UNIQUE(user_id, project_id, list, name)`), its migration and constraint tests; `GET/POST /api/me/saved-filters`, `PATCH/DELETE …/{id}` (the user's own only); a saved query validated against its list's spec when applied, not when saved. Web: the filter bar's saved-filter menu (save, apply, rename, delete) and Account settings' Saved filters section. If the slice runs long, it moves to a later slice through `design-change` rather than being split |
| 33 | Slice verification | As S2-C22, with the `checkpoint` skill's slice-end reviewers (`fresh-clone-verifier`, `user-guide-verifier` in both parts, DL-336, `docs-consistency`, `repo-auditor`, then `simplicity-auditor`); `wl docs-screenshots` (DL-343); "Done when" walked through; the owner's manual pass on the DL-320 sheet; the tech-debt review (TD-19, TD-31, TD-42, TD-64, TD-68, TD-86, TD-100); every `S2-ui-feedback.md` item done or logged; the retro |

**Groups** ("Pull requests"), on `s3` with one PR:

| Group | Name | Checkpoints |
|---|---|---|
| 1 | `s3-polish` | 0a–0m (Slice 2 polish, the retro's changes, the spike, the rest of the feedback) |
| 2 | `s3-foundations` | 1–4 (models, rules and actions, phases, workstreams) |
| 3 | `s3-tasks` | 5–10 (tasks, order, subtasks, delete and trash, requirement links) |
| 4 | `s3-views` | 11–15 (My work, activity, pickers, CSV, project home) |
| 5 | `s3-web` | 16–33 (saved filters, 32, last) |

**`spec-test-writer`:** S3-C2, and each row that adds an action or changes `app/rules/` (S3-C3,
C4, C7 if the rank rule changes, C12 for `project.view_activity`, C15, C32); each row confirms
it when it starts.
**`security-reviewer`:** every row from S3-C1 to S3-C15 (routers, authorization, scoping), S3-C0e (the
requirement read's `ancestors`), S3-C0f (My work's cross-project read), S3-C0g (rendered
markdown's docs mode and the CSP's `img-src`), S3-C0k
and S3-C0l (new backend fields), S3-C0m (membership adds), S3-C31 (rendered markdown), S3-C32 (saved filters' backend),
and each web row that adds a route. **`ui-reviewer`:** whenever the diff touches `frontend/` (DL-62).

### Done when
- [ ] (The polish group, as already written.)
- [ ] Every item in `S2-ui-feedback.md` is done or logged.
- [ ] A member creates a task with and without a requirement (the latter flagged), triages it,
      and orders the backlog by drag and by the move menu; a server-denied move snaps back.
- [ ] On the board, a drop into another column changes status and rank in one request; a
      transition the rules deny is refused and the card returns; the status control does the same
      without a drag.
- [ ] The transition table holds for assignee, reviewer, both, neither, and project admin.
- [ ] Subtasks number as `TA-n.m`, never reused after a delete, concurrency-tested.
- [ ] Deleting a requirement offers detach or delete for its tasks, delete only where allowed;
      tasks appear in Trash and restore with their subtasks.
- [ ] Copy branch name gives `wtl-ta-45-sign-in-throttling`.
- [ ] Phases are created, dated, reordered, and deleted only while unreferenced; workstreams
      archived and unarchived; date, status, and workstream changes are logged.
- [ ] My work shows the summary tiles, Favorites, each organization's first 10 projects, then
      approvals, tasks assigned to me, and tasks waiting for my review, with "see all".
- [ ] The project activity feed shows every logged change with filters (scoped by the
      export-control gate like all content; export control itself is on hold, Q10).
- [ ] Every list has the filter bar (the requirement tree showing matches with their
      ancestors); CSV export holds the list's rows as filtered (a filtered tree's matches, without
      their context ancestors) and escapes formula cells.
- [ ] A saved filter reapplies (S3-C32, unless moved to a later slice).
- [ ] A new project's home shows the Get started checklist to its admins, ticking itself.
- [ ] Item IDs in markdown link to their items.
- [ ] Accessibility: axe passes in component and end-to-end tests (SVAR's known issues listed,
      not hidden); the manual pass finds no unresolved problem.
- [ ] CI is green.

---

# Part 2 — Plan record (`docs/reviews/s3/S3-plan.md`)

## Fixes (gaps found while drafting)

| # | Fix |
|---|---|
| F1 | The feature map lists `task_dependency` under `task`, Slice 3, but dependencies are Slice 6. No test forces the table (the docs tests check built tables only), so the fix is a note in the Owns cell: "task_dependency (from Slice 6)" |
| F2 | The screen inventory puts Workstreams in "a section of Settings (or its own tab)", and Settings is a project-admin page; design-doc §5 lets members manage workstreams (Q7) |
| F3 | "Backlog = ranked tasks not in a sprint" has no meaning before sprints exist (Slice 4); its contents and the board's columns need defining for Slice 3 (Q4) |
| F4 | The API conventions say ranked views return complete lists, but CSV export and the filter bar also need the task list; one endpoint or two is undecided (Q2) |
| F5 | Design-doc §5 names no rule for who may be an assignee or reviewer (Q5) |
| F6 | Trash is `ListSpec` `TRASH` over `Requirement` alone, in the `requirement` area (layer 6). With tasks it becomes a union query (its `type` filter already anticipates more types), reads the task repository (allowed), and restores through the task service (layer 4, allowed): no layer change, but `ListSpec` over a union is new and gets its own tests |
| F7 | The project home's headline numbers and current phase ("fill in with their slices") have no row in any slice so far (Q11) |
| F8 | Several `S2-ui-feedback.md` items need a decision before they can be built (Q12) |
| F9 | The requirement tree endpoint takes no query parameters, yet the filter bar is for "any list" and the requirements CSV is "the list's filters as shown" (Q13) |
| F10 | `task.type` has seven values, ERP's `config`, `data`, and `training` among them, with no rule for which a project type offers (Q14) |
| F11 | `S2-ui-feedback.md`'s items need marking with their rows (the Slice 3 section's rule), done in this change's `docs:` commit (Part 3) |

## Decisions (entries per DL-312: only those that change or supersede a rule, or set a process)

| # | Decision |
|---|---|
| D1 | S3-C0i: a backlog widget spike, as S2-C0b was for the tree (Q1) |
| D2 | S3-C0j to S3-C0m carry the Slice 2 feedback the handoff didn't cover |
| D3 | Tasks use one ranked list endpoint (Q2) and one move endpoint that also changes status (design-doc §6, "Cross-column drop") |
| D4 | Task rank rewrites and the move lock (Q3; closes DL-216) |
| D5 | Assignable people (Q5) |
| D6 | Saved filters' scope and table (Q8) |
| D7 | My work: summary tiles, Favorites, each org (first 10), Approvals, Assigned to you, Waiting for your review (Q9; supersedes DL-331 and DL-333 in part) |
| D8 | The activity feed's export-control scoping (Q10) |
| D9 | The project home's numbers and status control (Q11, Q12f) |

## Conventions (set in Slice 3, copied by later slices)

| # | Convention |
|---|---|
| C1 | One shared `FilterBar` per list, built from the list's declared `ListSpec` filters; no hand-built filter controls |
| C2 | CSV export is a sibling endpoint, `…/export.csv`, taking the list's own query parameters plus `columns=`; every cell formula-escaped |
| C3 | Pickers search on the server (`?q=`), never a client-filtered first page |
| C4 | A move that also changes a field (status on the board, sprint in Slice 4) is one request through the move endpoint, the field's rules checked first |
| C5 | One shared person check for every "who may be named" field (reporter, approver, assignee, reviewer), differing only in its action and error (TD-101) |

## Actions per row (DL-139)

Proposed names, registered in `authz/actions.py` and confirmed by each row's spec tests. Content
actions are denied by the export-control gate to anyone without an explicit membership.

| Row | Endpoints | Action | Allowed to | Kind |
|---|---|---|---|---|
| S3-C3 | phases list, read | `phase.view` | viewers and up, inherited admins | content |
| S3-C3 | phase create, update, move, delete | `phase.manage` | members and up | content |
| S3-C4 | workstreams list, read | `workstream.view` | viewers and up, inherited admins | content |
| S3-C4 | workstream create, update, move, archive, unarchive | `workstream.manage` | members and up | content |
| S3-C5 | `POST …/tasks` | `task.create` | members and up | content |
| S3-C5 | `GET …/tasks`, `…/tasks/{number}` | `task.view` | viewers and up, inherited admins | content |
| S3-C6 | `PATCH …/tasks/{number}` | `task.update` (status also through the transition rule) | members and up | content |
| S3-C6 | `PATCH` changing `reporter_id` | `task.reassign_reporter` | project admins | content |
| S3-C6 | `PUT …/tasks/{number}/restriction` | `task.raise_restriction`; `task.lower_restriction` | members and up; project admins | content |
| S3-C7 | `POST …/tasks/{number}/move` | `task.update` (+ the transition rule when `status` is sent) | members and up | content |
| S3-C8 | subtasks | `task.view` to read; `subtask.manage` to change | viewers / members and up | content |
| S3-C9 | `DELETE …/tasks/{number}` | `task.delete` | the reporter as a member, project admins | content |
| S3-C9 | `POST …/tasks/{number}/restore` | `task.restore` | as `requirement.restore` | content |
| S3-C9 | `GET …/trash` (now with tasks) | unchanged (project content view); rows by `requirement.restore` / `task.restore` | as today | content |
| S3-C0k | workspace users and orgs lists (new fields only) | unchanged (each list's current scoping) | as today | management |
| S3-C0l | tree item's pending-approval field | unchanged (`requirement.view`) | as today | content |
| S3-C10 | `GET …/requirements/{number}/tasks` | `requirement.view`, tasks scoped by `task.view` | viewers and up | content |
| S3-C11 | `GET /api/me/work/tasks`, `/reviews` | signed in (scoped like approvals) | — | — |
| S3-C12 | `GET …/activity`, `…/tasks/{number}/activity` | `project.view_activity` (Q10); `task.view` | viewers and up | content |
| S3-C13 | candidates endpoints | the action of the field they fill (`task.update`, `approval_request.create`, …) | as that action | as that action |
| S3-C14 | `…/requirements/export.csv`, `…/tasks/export.csv` | `requirement.view`, `task.view` | viewers and up | content |
| S3-C15 | `PUT/DELETE …/get-started/hidden` | `project.update` | project admins | management |
| S3-C32 | `/api/me/saved-filters` | signed in (the user's own rows) | — | — |

## Threat-model pass

| Threat | Control | Row |
|---|---|---|
| A requirement, phase, workstream, assignee, or reviewer from another project or outside access | Scoped lookups (404), same-project checks, the shared person check | S3-C4 to S3-C6 |
| A transition the rules forbid, via `PATCH` or a board drop | One rule in `rules/`, checked on both paths; `allowed_transitions` only a hint | S3-C2, S3-C6, S3-C7 |
| Export-controlled tasks leaking through the board, My work, activity, Trash, CSV, or a requirement's task list | Content scoping in every query, a test per path | S3-C5 onward |
| CSV formula injection (`=`, `+`, `-`, `@`, tab, CR) | Every cell escaped; a test per prefix | S3-C14 |
| Oversized exports or ranked lists | The 2,000 cap with `truncated` | S3-C5, S3-C14 |
| Indirect delete through the requirement dialog | "Delete them too" only where each task's own delete passes; 403 and nothing deleted otherwise | S3-C9 |
| Subtask number collisions under concurrency | Direct `UPDATE … RETURNING` on the task row; concurrency test | S3-C8 |
| Concurrent moves producing ties or out-of-order ranks | The Q3 lock; `(rank, id)` ordering; rewrite on tie or cap | S3-C7 |
| Saved filters reading or changing another user's rows | Every query scoped to the caller's `user_id`; 404 otherwise | S3-C32 |
| A saved filter smuggling an undeclared or restricted filter | Validated against the list's spec when applied (unknown → 422, restricted → `not_permitted`) | S3-C32 |
| Item-ID auto-links as an XSS or open-redirect vector | Links built only from the matched pattern to an in-app route; DOMPurify after; corpus cases | S3-C31 |
| Picker search revealing people outside scope | Candidates scoped like their lists; `q` length-limited (200) | S3-C13 |

## Owner questions (all answered Nov 10, 2026, before S3-C0a)

Settled by Q9: how My work returns its projects (DC-2026-11-09, decision B): each org's first
10 and its total. Decided as each first appears: the tone
and icon for task status, priority, and severity (UI guide open item 8), at S3-C18.

**Q1. The backlog's widget.** UI-SVR-2 and DL-64 put lists "where manual row order is the point"
on SVAR DataGrid, but its row drag was never exercised (UI guide open item 5c), it has known
ARIA defects, and PrimeVue's DataTable (already used) has a row reorder of its own. Options: SVAR
DataGrid as decided; PrimeVue DataTable with reorder; or a spike first. **Recommendation: a
spike (S3-C0i)**, as the tree's (S2-C0b) settled the same question cheaply.
**Decided** (owner, Nov 10, 2026): the spike, S3-C0i. The owner wants to see a working example of each option before choosing.

**Q2. The task list endpoint.** Options: one `GET …/tasks` ranked view (complete up to 2,000,
declared filters, display sorts) serving the backlog, board, and CSV; or a ranked view plus a
separate offset-paged list. **Recommendation: one endpoint**, following the requirement tree's
convention (C1 of Slice 2); a project near 2,000 tasks gets a tech-debt entry, as TD-70.
**Decided** (owner, Nov 10, 2026): as recommended.

**Q3. Task rank rewrites and moves (DL-216).** Schema-doc says tasks have one global order per
project. Options for the rewrite on a tie or past the cap: (a) the project's whole task order;
(b) only the run around the gap. For concurrency: (i) task moves one at a time per project,
sharing the tree's project-row lock; (ii) a separate task-order lock; (iii) no lock (ties are
handled by `(rank, id)` and repaired by the next rewrite). **Recommendation: (a) + (i)**, with
the rewrite as one statement (TD-73, fixing the tree's too): simplest, matches the requirement
tree, and a task move waiting milliseconds on a requirement move doesn't matter at v1's scale.
**Decided** (owner, Nov 10, 2026): as recommended, (a) + (i); TD-73 comes into S3-C7.

**Q4. Backlog and board contents before sprints.** **Recommendation:** the backlog lists every
task not `done` or `cancelled` (the filter bar shows the rest); the board has five columns, To
do, In progress, Blocked, In review, Done, with Cancelled left off (filterable in the backlog).
Slice 4 narrows the backlog to tasks without a sprint.
**Decided** (owner, Nov 10, 2026): as recommended; the backlog and board are built before sprints exist.

**Q5. Who may be an assignee or reviewer.** Options: anyone who may update tasks (members and up
with content access, inherited admins on a non-export-controlled project), as the reporter rule
(DL-211); explicit project members only; or any project member including viewers.
**Recommendation: anyone who may update tasks**, active, through the shared check (C5); a
deactivated assignee stays on existing tasks with the badge.
**Decided** (owner, Nov 10, 2026): as recommended.

*(Q6, `task_dependency`, is withdrawn: no test forces the table, so it's fix F1.)*

**Q7. Where workstreams are managed.** Members manage them, but Settings is an admin page.
Options: a section of Settings, visible read-only to members; its own page in the project nav;
or a tab on the Timeline page. **Recommendation: its own small page** (`…/:key/workstreams`),
after Timeline in the nav.
**Decided** (owner, Nov 10, 2026): its own Workstreams page, `…/:key/workstreams`, after Timeline in the project nav.

**Q8. Saved filters' scope.** Options: per list per project; or per list type across projects
(portable filters like "assigned to me", but project-specific values like a workstream stop
matching). **Recommendation: per list per project**; the table `saved_filter (user_id,
project_id, list, name, query)`, `UNIQUE(user_id, project_id, list, name)`.
**Decided** (owner, Nov 10, 2026): as recommended. Saved filters are a nice-to-have, so they move to the end of the slice (S3-C32, backend and web in one row).

**Q9. My work's order once tasks join.** **Recommendation:** Approvals, Assigned to you,
Waiting for your review, Favorites, then each organization (DL-329 to DL-333 keep their order
around them).
**Owner (Nov 10, 2026):** Favorites and each organization's projects stay at the top; the rest follows. My work becomes a dashboard summarizing everything for the user across Waterline later (noted for v1.5/v2, design-doc §16). **To confirm:** DL-333 (Nov 9, S3-C0f) put Approvals first, above Favorites; this moves Approvals below the projects too, superseding DL-333 in part, with S3-C0f's row and design-doc §11 changed to match. Proposed order: Favorites, each organization, Approvals waiting for you, Assigned to you, Waiting for your review.
**Decided** (owner, Nov 10, 2026): a lite dashboard now. Summary tiles at the top (Approvals waiting, Assigned to you, Waiting for your review, Overdue or due this week), then Favorites, each organization capped at its first 10 projects, then Approvals, Assigned to you, and Waiting for your review. Built in S3-C0f (order and cap), S3-C11 (`due_soon`), and S3-C29 (tiles and task sections). The fuller dashboard is v1.5/v2.

**Q10. The activity feed and export control.** Options: the whole feed is content (hidden from
inherited admins without an explicit membership on an export-controlled project); or project
entries (status, lead) shown to them and item entries hidden. **Recommendation: the whole feed is
content** (one rule, nothing to split), through a `project.view_activity` content action.
**Decided** (owner, Nov 10, 2026): as recommended. Export control is on hold indefinitely (hidden from the UI since DL-133, Oct 21), so this costs nothing now: the gate already scopes every content action.

**Q11. Project home numbers in Slice 3.** Options: none yet; blocked tasks and pending approvals
(the two whose data exists after this slice); or wait for all three (untested requirements need
Slice 5). **Recommendation: blocked tasks and pending approvals now**, untested requirements in
Slice 5.
**Decided** (owner, Nov 10, 2026): as recommended.

**Q12. The Slice 2 feedback that needs a decision.** Recommendations in brackets. **(b) to (i) decided** (owner, Nov 10, 2026): as recommended; (a) as recorded below.
- (a) **Trash location** — *the owner's intent, completed Nov 10:* off the sidebar, "accessible
  from the Requirements page, and any other pages that will allow the user to 'Trash' an item".
  **Decided** (owner, Nov 10, 2026), with these details: [a **Trash** link in the header of every list page whose items
  can be deleted (Requirements in S3-C0l, Tasks in S3-C20, Test cases in Slice 5), shown under
  the same check as today's nav link (DL-291); it opens the one Trash page pre-filtered to that
  page's type (`?type=task`, the filter `TRASH` already declares), with the filter removable to
  see everything; the route `…/:key/trash` stays, and the breadcrumb leads back to the list.
  Supersedes DL-291's link in the project navigation. The S2-C21 delete status's "Trash" link
  (DL-287) stays.]
- (b) **Awaiting approval on the tree**: a filter, a column, or a status label. [A badge beside
  the status ("Approval pending"), from a field on the tree row, plus a filter-bar filter; no new
  status.]
- (c) **Modules section in project settings**: collapsible, or a compact list. [Collapsed to a
  one-line summary with Edit, expanded on demand.]
- (d) **Task-list checkboxes in descriptions**: they render read-only. [Keep read-only in v1:
  ticking them would be an edit, a new revision per tick; subtasks are the checklist for tasks.]
- (e) **Compare revisions**: keep or revisit. [Keep, it's built and tested; restyle with 0l.]
- (f) **Changing project status outside Settings**: [a status menu on the project home for its
  admins, S3-C30.]
- (g) **Adding an org member: offer their projects too**: [yes, an optional project multi-select
  on the add-person form's last step; v1.5 if S3 runs long.]
- (h) **Inherited admins in the project's member list**: [leave them out of Members; the access
  review shows them, labelled "Admin (inherited)".]
- (i) **A frontend design skill** (Impeccable, Addy Osmani's agent skills, Anthropic's
  frontend-design): [trial one with `vue-screen` on S3-C0j, as the git guard's trial, through
  `design-change`.]

**Q13. Filtering the requirement tree.** `GET …/requirements` takes no filters today, and a
filtered tree is harder than a filtered list (a match's ancestors, and what a drag means while
filtered). Options: (a) the tree takes declared filters and returns the matches plus their
ancestors (ancestors marked as context), with drag and the move menu off while filtered; (b) the
tree stays unfiltered in v1, and the filter bar, "awaiting approval", and the CSV use a flat
"List" view of requirements beside the tree; (c) no requirement filters in v1. **Recommendation:
(a)**, which keeps one view and makes Q12b's filter possible; the CSV exports the matches only.
**Decided** (owner, Nov 10, 2026): as recommended, (a); built in S3-C10 (backend) and S3-C26 (web).

**Q14. Task types per project type.** `task.type` holds feature, bug, chore, spike, config, data,
and training. Options: (a) every type on every project, labels per project type; (b) software
projects offer feature, bug, chore, spike, and ERP and general projects all seven; (c) a
per-project setting (v2-shaped). **Recommendation: (b)**, as a rule in `rules/` beside the
labels, with an existing task's type always shown even if its project type changes later.
**Decided** (owner, Nov 10, 2026): as recommended, (b).

---

# Part 3 — `S2-ui-feedback.md`, item by item

All 50 items (the four "None" lines aside). The `docs:` commit marks each item in the file with
its row (F11).

| Section | Item (shortened) | Row |
|---|---|---|
| Overall | Sidebar scrolls away with the page | S3-C0j |
| Overall | Breadcrumbs unintuitive, need a sleeker look | S3-C0e |
| Overall | Explore a frontend/UI design skill | S3-C0j (Q12i) |
| Overall | Browser tab text jumbled and long | S3-C0j |
| Overall | Tell org items from project items in the sidebar | S3-C0j |
| My work | Favorite star on the left | S3-C0f |
| My work | Rows cluttered; remove the access | S3-C0f (DL-334) |
| My work | Group by organization; show every project | S3-C0f (DL-329 to DL-331) |
| My work | No "My past decisions" | S3-C0f (DL-333) |
| Account settings | "Change password" a button | S3-C0j |
| Documentation | Needs serious work | S3-C0g, S3-C0h |
| Org overview | "Archived" → "Archived projects" | S3-C0k |
| Org overview | An archived project shown in Planning | S3-C0k |
| Org overview | Remove the "Name" line | S3-C0k |
| Org overview | Slug in the title | S3-C0k |
| Org members | Rework the "deactivated" label | S3-C0k |
| Org members | Show deactivated changes column widths | S3-C0k |
| Org members | Offer to add a new member to the org's projects | S3-C0m (Q12g) |
| Projects list | Show a project's organization, here and on its pages | S3-C0e (the trail starts at the org) |
| Project dropdown | Arrow right-aligned | S3-C0j |
| Project dropdown | "All projects" not blue and underlined | S3-C0j |
| Project dropdown | Filter behind a button | S3-C0j |
| Project settings | Minimize the Modules section | S3-C0l (Q12c) |
| Project settings | Change status outside Settings | S3-C30 (Q12f) |
| Project settings | Save Restriction in the primary color | S3-C0l |
| Project members | "Show deactivated" at the bottom | S3-C16: into the filter bar (TD-97) |
| Add member (project) | The list opens on its own; focus the title | S3-C0l |
| Add member (project) | Add by email defaults to Member | S3-C0l |
| Access review | Rename "Why they reach it" | S3-C0k |
| Access review | "none" for inherited admins; list them at all? | S3-C0k (Q12h) |
| Access review | A way back to Members | S3-C0e (breadcrumbs) |
| Requirements | The selection hints | S3-C0l |
| Requirements | Expand and Move right-aligned | S3-C0l |
| Requirements | Space between title and table | S3-C0l |
| Requirements | Awaiting-approval filter, column, or label | S3-C0l (Q12b badge), S3-C26 (filter) |
| Panel | Can't use the page with it open | S3-C0d (DL-321) |
| Panel | "Open full page" highlighted | S3-C0d (DL-325) |
| Panel | Icon buttons for copy and close | S3-C0d (DL-325) |
| Panel | Other buttons to the bottom | S3-C0d (DL-325 keeps them in the header) |
| Panel | Delete the only solid button | S3-C0d (DL-325) |
| Panel | History spacing, a line between entries | S3-C0l |
| Panel | Revisions spacing | S3-C0l |
| Panel | Revisit compare revisions | S3-C0l (Q12e) |
| Full page | The panel's items apply here too | S3-C0d (DL-326) |
| Full page | Wall of text; title vs description | S3-C0l |
| Full page | Description checkboxes not checkable | Q12d (no change recommended) |
| Trash | Not its own sidebar item; reached from every page that can trash an item | S3-C0l (Requirements), S3-C20 (Tasks), Slice 5 (Test cases); Q12a |
| Trash | Remove the explanation text | S3-C0l |
| Workspace users | Org/project column, maybe with Role | S3-C0k |
| Workspace orgs | More information in the table | S3-C0k |
