# Review record: DC-2026-11-10 — the Slice 3 plan

- **Change:** the owner's Slice 3 planning decisions (chat session, Nov 10, 2026: every question
  answered, Q6 withdrawn), written into the repository docs. The plan is the build plan's
  "Slice 3 — Tasks" section; the plan as approved, with its fixes, decisions, conventions,
  actions per row, threat-model pass, questions, and the feedback map, is
  `docs/reviews/s3/S3-plan.md` (copied from the owner's `S3-plan-approved.md`, whose root copy
  is deleted). Docs only: no tooling code.
- **Base commit:** `664eb92` (main after the Slice 2 merge, PR #11), on the new branch `s3`.
- **Files:** `docs/build-plan.md`, `docs/decision-log.md`, `docs/design-doc.md`,
  `docs/schema-doc.md`, `docs/screen-inventory.md`, `docs/ui-design-guide.md`,
  `docs/tech-debt.md`, `docs/reviews/s2/S2-ui-feedback.md`, `docs/reviews/s3/S3-plan.md` (new),
  this record (new), `CLAUDE.md` (Status)
- **Reviewers:** the plan's readiness review (an independent read-only agent, DL-353) and
  `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** readiness review: 20 findings, 7 fixed (1 in part), 13 open for the owner (R1 to
  R4). `docs-consistency`: 4 fixes, all applied; 8 decisions, 4 answered by the owner (DL-354
  and three refinements), 1 fixed as a clear-cut correction, 3 open.
- **Gates:** `uv run wl audit` green before starting; `uv run wl check` green before the commit.

---

## Decisions and their entries (DL-312)

Every decision's source is the owner, Nov 10, 2026 (chat session, Slice 3 planning); `Qn` is the
plan record's question.

**Entries** (each changes or supersedes a written rule, or sets a process):

| Decision | Entry | Why it gets one |
|---|---|---|
| Q1, the backlog widget spike | DL-344 | Puts DL-64's and UI-SVR-2's "DataGrid for manual-order lists" to a spike for the backlog |
| Q3, task rank rewrites and the move lock | DL-345 | Closes DL-216 (superseded) |
| Q4, the backlog and board before sprints | DL-346 | Changes the screen inventory's backlog ("not in a sprint") until Slice 4 |
| Q5, who may be assignee or reviewer | DL-347 | A new authorization rule in design-doc §5 that later slices keep, as Q14 (the owner named Q14 "a new rule") |
| Q7, Workstreams on its own page | DL-348 | Changes the inventory's "Workstreams in Settings"; DL-202's nav order in part |
| Q9, My work's tiles, order, and cap of 10 | DL-349 | Supersedes DL-331, and DL-333 in part |
| Q12a, Trash from the list pages | DL-350 | Supersedes DL-291's nav link, and DL-202's "Trash last" in part |
| Q13, filters on ranked views | DL-351 | Changes the ranked-view convention (build plan, API conventions) |
| Q14, task types per project type | DL-352 | A new rule (the owner) |
| The readiness review's procedure (owner, this session) | DL-353 | Sets a process ("Planning a slice") |
| "Compile your plan" live from Slice 3 (owner, this session; `docs-consistency` decision 1) | DL-354 | Supersedes DL-201 in part |

**No entry** (detail for unbuilt rows, written into the docs where named, under DL-312):

| Decision | Where it went | Why no entry |
|---|---|---|
| Q2, one task list endpoint | build plan S3-C5 | Follows the existing ranked-view convention (DL-159) |
| Q8, saved filters per list per project | build plan S3-C32; design-doc §11; schema-doc `saved_filter` | Design-doc §11 left the table to be "designed there" (DL-239); this fills that in |
| Q10, the activity feed is content | build plan S3-C12; design-doc §5 | Design-doc §3.1 already counts the activity feed as content; the action name is row detail |
| Q11, the home's numbers | build plan S3-C15, S3-C30; design-doc §11; screen inventory | The inventory already said "numbers fill in with their slices" |
| Q12b to Q12i (the feedback's details) | build plan S3-C0j to S3-C0m, S3-C26, S3-C30; `S2-ui-feedback.md` | UI detail for unbuilt rows; Q12d changes nothing; Q12i's trial outcome goes through `design-change` when decided, as the git guard's (DL-316) |
| The plan record's conventions C1 to C5 | build plan, API conventions (C2, C3; C1 and C4 were already there; C5 is S3-C6's) | Detail of the list conventions for unbuilt rows, as Slice 2's C3 to C5 were |

## How Part 1 was written into the build plan

Part 1 is copied word for word, except:
- each `Qn` with an entry became its `DL-n` (Q1, Q3, Q4, Q5, Q7, Q9, Q12a, Q13, Q14); the other
  `Qn` stay, pointing to the plan record, which "Before starting" now names;
- "the open questions below answered" became the plan record's questions, answered Nov 10, 2026
  (there's no "below" in the build plan);
- the table's first row, "0a–0e, 0g–0h *(as decided)*", became the stub's rows, word for word;
  S3-C0f is the amended row, its title without "*(amended, Q9)*";
- the checkpoints' opening paragraph keeps the stub's order and review rules, and says S3-C0i to
  **S3-C0m** (Part 1 said 0l, but its table and groups have 0m) and "each row but 0b and 0i" (0i
  is a spike, no product code);
- "Done when"'s "(The polish group, as already written.)" became the stub's polish items, with
  the My work item changed to DL-349's order (it still said approvals first) and the duplicate
  feedback item dropped;
- the stub's "Slice verification, from Slice 3" paragraph is kept, and a pointer to the plan
  record added.

## Proposals the owner asked for

- **`saved_filter.list`'s values:** `requirements`, `tasks` (the backlog and board share one task
  list), `activity`, `trash`, `project_members` (the project lists with a filter bar). **Index:**
  none beyond `UNIQUE(user_id, project_id, list, name)`, which leads with `user_id` and serves
  every lookup (as `project_favorite`'s). `name` at most 100 characters, `query` text at most
  2,000.
- **`saved_filter`'s area:** its own, `saved_filter`, in service layer 1, calling nothing: the
  list endpoint checks a query when it's applied, so the service never needs another area's
  `ListSpec`.
- **The Get started hide flag:** `project.get_started_hidden`, boolean, NOT NULL, default false,
  `Added in Slice 3.`
- **The task indexes:** S3-C1 names `(project_id, status, rank)`, `ix_task_assignee_id_status`,
  and `ix_task_reviewer_id_status`; the schema doc has the same three. No conflict.

## Tech-debt retargets

TD-37 → S3-C29; TD-73 → S3-C7; TD-97, TD-102 → S3-C16; TD-101 → S3-C6; TD-100 → Slice 3's
tech-debt review (S3-C33). TD-38, TD-41, and TD-96 → **S3-C17**, naming S3-C13's search in the
text: the docs tests read a Fix by's first checkpoint as its deadline, so "S3-C13 and S3-C17"
would turn `wl check` red at S3-C13's commit while the pickers wait for S3-C17.

---

## Readiness review (base `664eb92`; an independent read-only agent, DL-353)

20 findings against "Planning a slice"; size findings are judgments against the rule text, not
line counts. Rows that passed every rule: S3-C0a, C0b, C0c, C0d, C0h, C0i, C1, C2, C3, C4, C6, C7,
C8, C11, C14, C15, C16, C17, C18, C19, C21, C23a, C24, C26, C28, C31, C33.

| # | Row | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | S3-C12 | 2 | `project.view_activity` is a new action, but S3-C12 isn't in the `spec-test-writer` list; the list's reasons are also uneven (C3 and C4 listed though C2 registers their actions; C5, C6, C8, C9's targeted rules not listed) | **Fixed:** S3-C12 added (build plan, plan record). The uneven reasons: **open**, decision R1 below |
| 2 | S3-C0m | 2 | No endpoint or actions named for the add's project step | **Open**, R2 |
| 3 | S3-C13 | 2 | The candidates endpoints' paths and actions aren't named | **Open**, R2 |
| 4 | S3-C5, S3-C10 | 2 | The task list's and the tree's declared filters and sorts aren't named | **Open**, R2 |
| 5 | S3-C10 | 1 | Two units: the requirement ↔ task reads, and the filtered tree | **Open**, R3 |
| 6 | S3-C9 | 1 | Likely past the size target: task delete and restore, the union Trash, and the requirement delete's linked tasks | **Open**, R3 |
| 7 | S3-C27 | 1 | Two pages (Timeline, Workstreams) | **Open**, R3 (a provisional row, re-cut before it starts) |
| 8 | S3-C29 | 1, 3 | "See all" lists add screens the inventory doesn't have | **Open**, R3 |
| 9 | S3-C32 | 1, 3 | Backend and web in one row; not marked provisional | **Fixed:** "the web half provisional". Its size: the owner chose a move to a later slice over a split (Q8), recorded here |
| 10 | S3-C0g *(kept)* | 1 | Several units in one row | **Open**, R3 (decided word for word, DL-335 to DL-342) |
| 11 | S3-C0k | 1 | Web edits plus two backend fields | **Open**, R3 |
| 12 | S3-C0l | 1 | About 13 edits plus a backend field and the Trash change | **Open**, R3 |
| 13 | S3-C0j | 1 | The design-skill trial (a tooling trial, like 0b) inside a shell row | **Open**, R3 |
| 14 | S3-C22 | 4 | The first requirement picker (and its source) sits in a feature row | **Open**, R4 |
| 15 | S3-C23 | 4 | The first date field sits in a feature row | **Open**, R4 |
| 16 | S3-C20 | 4 | The first Export CSV control sits in the Backlog page | **Open**, R4 |
| 17 | S3-C25, S3-C30 | 3 | The inventory doesn't cover the requirement's Tasks section, or the home's current phase and status menu | **Fixed:** both inventory rows (Step 6) |
| 18 | S3-C0f *(kept)* | security | Changes My work's cross-project read, but has no `security-reviewer` | **Fixed:** added to the list |
| 19 | S3-C0g *(kept)* | security | Changes rendered markdown and the CSP | **Fixed:** added to the list |
| 20 | S3-C0e *(kept)* | security, 2 | Adds the requirement read's `ancestors` | **Fixed:** added to the `security-reviewer` list; its actions line is **open**, R2 |

## docs-consistency (base `664eb92`, trigger `design-change`)

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | internal | build plan, `spec-test-writer` list | S3-C12 missing | **Fixed** (readiness 1) |
| 2 | superseded | ui-design-guide §1, "SVAR for what PrimeVue does not have" | "orderable lists use DataGrid" | **Fixed:** an orderable list's widget is decided per list (DL-344) |
| 3 | stale | screen inventory, Step 6: Trash and the Requirements and approvals rows | Status "—" for built screens | **Fixed:** "Built", with the checkpoint and the Slice 3 parts to come |
| 4 | contradiction | build plan "Done when", CSV | "as shown" vs a filtered tree's matches only (DL-351) | **Fixed:** the list's rows as filtered, a tree's matches without their ancestors |

**Decisions, and the owner's answers** (Nov 10, 2026, this session):
1. "Compile your plan" before milestones: **live from S3-C27**, ticked by a dated phase (DL-354,
   superseding DL-201 in part; design-doc §11, screen inventory Step 5).
2. Drag on a filtered ranked view: **the tree only** turns its move menu off; a filtered task
   view keeps drag (DL-351 and the API convention reworded before commit).
3. Saved filters outside projects: **project lists only** (S3-C32, design-doc §11).
4. Task types and labels: **the rule on the server, the labels in the client** (DL-352 and
   design-doc §6 reworded; the allowed types on the project read, S3-C5).
5. The readiness review in the `design-change` skill (or an agent file): **open**.
6. The plan record's "S3-C0i to S3-C0l" and "S3-C0j to S3-C0l": **fixed** in the record to 0m, as
   its own table and groups say (owner: fix what the reviews find).
7. A fallback for S3-C0m ("v1.5 if S3 runs long", Q12g): **open**.
8. The tree's indicator: "Approval pending" (Q12b, the badge) vs "Awaiting approval" (S3-C0l,
   S3-C26, the filter): **open**.

The plan record keeps Q13's and Q14's text as approved; answers 2 and 4 refine them, and the
docs state the refined rules.

## Open decisions for the owner (from the readiness review)

- **R1.** Which rows get `spec-test-writer`: every row whose code changes `app/rules/` or
  `app/authz/` (adding C5, C6, C8, C9 for their targeted rules), or only rows that add an action
  or rule (dropping C3 and C4, whose actions C2 registers)?
- **R2.** Name the missing endpoints, actions, and filters before the rows start: S3-C0e's
  `ancestors` scoping; S3-C0m's endpoint and per-project actions; S3-C13's candidates endpoints;
  S3-C5's and S3-C10's declared filters and sorts.
- **R3.** Splits: S3-C10 (the tree's filters as S3-C10a), S3-C9 (the requirement delete's linked
  tasks), S3-C27 (Timeline and Workstreams), S3-C29 (the "see all" screens), S3-C0g, S3-C0j (the
  design-skill trial), S3-C0k (the backend fields), S3-C0l.
- **R4.** Shared pieces' first use: a requirement picker (S3-C22), a date field (S3-C23), the
  Export CSV control (S3-C20): into S3-C16 or S3-C17, or rows of their own.
