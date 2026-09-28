# Waterline — Design Doc (v1, revised)

> Revision notes:
> 1. Folds in a structured review of the original v1 design (nine areas: IDs & placement, status
>    & ordering, test execution, requirement history, deletion, audit & authorization, users &
>    auth, GitHub integration, infrastructure).
> 2. Broadens the tool beyond software projects to ERP implementations run from a
>    finance/operations point of view: project types and modules (§1.1), phases, workstreams,
>    generalized approvals (§6.2), and a 3–6 character project key rule. The ERP-specific modules
>    (RAID, status reports, budget, data migration, cutover) are planned but not yet designed.
> 3. Settles number allocation (`project_counter` table) and switches subtasks to
>    parent-referenced IDs (`PMT-TA-45.2`).
>
> Table-level detail lives in `schema-doc.md`.

## 1. Overview

**Working name: Waterline.** Most of an iceberg sits below the waterline, as does most of a
project: the hidden work, dependencies, and risk. The tool keeps status visible above the line
and the traceability behind it available below. The name ties to the company's iceberg logo. It
is used for the repository (`waterline`), container images, the developer CLI (`waterline`, alias
`wl`), and the app's title; the Python package stays `app`, so a later rename is cheap.

A tool for gathering requirements, planning work scope, executing, testing, and reporting on a
project. It serves two kinds of work from one codebase:

- **Software projects** — requirements, tasks, sprints, test cases, GitHub integration.
- **ERP implementations**, run from a finance/operations point of view — phases and gates,
  functional workstreams, formal sign-offs, UAT cycles, and (as modules land) RAID logs, budget
  vs. actuals, data migration, cutover, and status reporting.

Built for personal use initially, with the data model designed to scale to multiple teams,
projects, and organizations later.

**Product direction:** a traditional PM tool first (v1). AI-assisted features (requirements
drafting, task breakdown, test-case generation, etc.) are a deliberate v2+ addition.

**Guiding principle — workflow over enforcement.** The app supports good process; it does not
force it. Where a rule is really a team's process choice (review before done, requirements on
every test case, reassigning work when someone leaves), the app makes the state *visible*
(flags, warnings, badges) rather than blocking the action. Hard constraints are reserved for
data integrity and security (uniqueness, tenant isolation, lockout prevention).

### 1.1 Project types & modules

One shared core, plus modules switched on per project. There is no separate schema or codebase
per kind of project.

- **Core (always on):** requirements, tasks and subtasks, phases, milestones, workstreams, test
  cases and runs, approvals, comments, tags, links, dependencies, activity log, search.
- **`project.type`** — `software` / `erp` / `general`. It seeds the project's default modules
  when the project is created and selects the display labels the UI uses. Owners/admins can
  change it later; changing it changes labels and recommendations only, never data or enabled
  modules.
- **`project.enabled_modules`** — seeded from the type; org owners/admins can turn modules on
  or off at any time.

| Module | Adds | Default on for | Status |
|---|---|---|---|
| `sprints` | Sprint planning; sprint board | software | v1 |
| `github` | GitHub App, repo mapping, PR/branch links (§12) | software | v1 |
| `raid` | Risks, assumptions, issues, decisions, change requests | erp | planned |
| `status_reports` | Published RAG status snapshots | erp | planned |
| `budget` | Budget lines, actuals, forecast | erp | planned |
| `data_migration` | Data objects, load cycles, reconciliation | erp | planned |
| `cutover` | Cutover runbook and rehearsals | erp | planned |

A module can be enabled only once it has shipped.

- **Disabling a module hides it; it never deletes data.** Re-enabling brings everything back.
  A disabled module's endpoints return 404 for that project.
- **UI guidance on module choice.** Module selection (at project creation and in project
  settings) shows, for the project's type, which modules are recommended and a short
  best-practice note for each. Examples:
  - "ERP implementations: keep a RAID log from day one; steering committees expect one."
  - "Sprints suit an ERP build phase; phases and milestones drive the overall plan."
  - "GitHub linking is only useful when the project's work lands in a repository."

  Turning off a recommended module, or one that already holds data, shows a warning explaining
  what will be hidden. This follows the workflow-over-enforcement principle: guidance, not
  blocking.
- **Display labels.** Stored values stay stable; the UI maps them to labels per project type
  (e.g. `task.type = bug` is shown as "Defect" on ERP projects). The mapping lives in code in
  v1; user-configurable labels are v2+.

## 2. Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Backend | Python + FastAPI | Existing familiarity; first-class Anthropic SDK for v2 AI features |
| ORM / Migrations | SQLAlchemy (or SQLModel) + Alembic | Mature; fits the relational, traceability-heavy model |
| Database | PostgreSQL | Also hosts the job queue and full-text search — no extra services in v1 |
| Background jobs | procrastinate (Postgres-backed queue) | No new infrastructure; jobs enqueue in the same transaction as the data they act on |
| Frontend | Vue 3 + TypeScript | Existing familiarity |
| Local dev | Docker Compose: `api`, `worker`, `postgres` | Worker runs the same image with a different command |
| Deployment | Self-hosted/local initially | Stateless API + externalized DB keeps it cloud-portable |

**Backend language decision:** a Node/TypeScript backend was considered for shared types with
Vue. Python/FastAPI was kept — it removes a variable while product decisions are still being
made, and costs nothing on the AI roadmap.

**Queue decision:** procrastinate + Postgres was chosen over ARQ + Redis and Celery. Expected
volume is a few jobs per minute, orders of magnitude below where a Postgres queue strains.
Redis may be added later for its own strengths (caching, rate limiting, real-time pub/sub)
without moving the queue. See §13 for the conventions that keep a later queue migration cheap.

**Async decision:** the backend is async throughout (SQLAlchemy asyncio + psycopg 3). The app is
database-bound, so async buys little raw throughput; it was chosen for team familiarity and to
avoid a later migration if streaming AI responses (v2) or live updates arrive. Rules that keep
it safe (explicit loading, nothing blocking the event loop) are in `build-plan.md`.

**Application architecture:** a layered backend (routers → services → repositories → models),
organized layer-first with one file name per aggregate repeated across layers, in a monorepo
(`backend/`, `frontend/`, `docs/`). The frontend uses types generated from the backend's OpenAPI
schema (`openapi-typescript` + `openapi-fetch`). Layer responsibilities, area ownership, and
cross-area rules are in `build-plan.md` ("Backend architecture", "Feature map").

## 3. Cross-Cutting Conventions

- **Primary keys:** UUIDv7 (time-ordered, index-friendly). UUIDs are the only internal
  references.
- **Human-readable IDs:** every project has a short `key`; requirements, tasks, and test cases
  get a per-project `number`, and subtasks a number within their parent task, displayed as:

  | Entity | Format | Example |
  |---|---|---|
  | Requirement | `{KEY}-RQ-{n}` | `PMT-RQ-12` |
  | Task | `{KEY}-TA-{n}` | `PMT-TA-45` |
  | Subtask | `{KEY}-TA-{n}.{m}` | `PMT-TA-45.2` |
  | Test case | `{KEY}-TC-{n}` | `PMT-TC-7` |

  Entity prefixes are always two letters. ERP modules will add more (e.g. `RK` risk, `IS` issue,
  `CR` change request), assigned when those modules are designed. Subtasks have no prefix of
  their own: the ID shows which task they belong to. The separator is a dot, not a hyphen, so a
  branch like `pmt-ta-45-2fa-login` can't be misread as a subtask.

  Numbers are **never reused** — a deleted `PMT-TA-45` means the next task is still 46, and a
  deleted `PMT-TA-45.3` means the next subtask of TA-45 is still `.4`, because the old ID may
  already appear in PR titles and notes.
- **Number allocation:**
  - **Project-level numbers** (requirements, tasks, test cases, and future module entities) come
    from a `project_counter` table: one row per project per prefix, holding the next value.
    Allocation is a single `INSERT … ON CONFLICT DO UPDATE SET next_value = next_value + 1
    RETURNING` inside the request's transaction. Rows are created **lazily** on first use, so
    new projects need no setup and new modules need no migration or backfill.
  - **Subtask numbers** come from `task.next_subtask_number`, incremented by a direct
    `UPDATE … RETURNING` that deliberately bypasses the ORM, so adding a subtask does not bump
    the task's optimistic-locking `version` (and cause a 409 for someone editing the task).
  - Both go through one helper module (`allocate_number(project, prefix)`,
    `allocate_subtask_number(task)`); endpoints never compute numbers themselves.
  - Only the one counter row is locked, and only until the request commits: creating a task
    doesn't block creating a test case or editing the project. If the request rolls back, so
    does the increment; the number was never visible, so nothing is lost.
  - Bulk imports can reserve a block of numbers in one statement (`+ n`).
- **No moving items between containers (v1):** `project_id` is immutable on requirements,
  tasks, and test cases, and `task_id` is immutable on subtasks. Moving would change the ID and
  break every existing reference; if moves are ever needed, the old ID is kept as an alias (same
  approach as project key renames, §16).
- **Project key rules:** entered by the user at project creation; **3–6** uppercase
  letters/digits, starting with a letter (`^[A-Z][A-Z0-9]{2,5}$`); unique within the
  organization; **immutable** after creation (renaming would break every external reference).
  Because every entity prefix is two letters, a 3-character minimum means no project key can
  ever collide with a current or future prefix — no reserved-word list is needed.
- **Timestamps:** `timestamptz` everywhere. Every table has `created_at`/`updated_at`, with
  `updated_at` maintained by the ORM, never set by hand.
- **Enums:** stored as `VARCHAR` + `CHECK` constraint (`Enum(..., native_enum=False)`), not
  native Postgres enums — values can be added, renamed, or removed with ordinary migrations,
  which matters for the planned move to configurable workflows. Typos are caught in Python
  (enum members) and at the API boundary (Pydantic returns 422). **Rule:** queries always filter
  with enum members, never string literals — a literal typo silently returns zero rows.
- **Soft delete:** `deleted_at` on requirement, task, test case, and comment; `archived_at` on
  project and workstream. A global SQLAlchemy loader criterion (`with_loader_criteria`) excludes
  deleted rows from every query unless a query explicitly opts in (trash/restore screens).
- **Optimistic locking:** `version` column on requirement, task, and test case
  (`version_id_col`). A save based on a stale version returns **409 Conflict**; the UI prompts a
  reload instead of silently overwriting someone else's edit.
- **Manual ordering:** `rank` (sortable string, fractional indexing) on task, requirement, and
  subtask; phases and workstreams use `rank` for display order. Moving an item rewrites only
  that row. See §6.
- **Markdown:** rendered markdown (descriptions, comments) is sanitized on render to prevent
  stored XSS.

## 4. Tenancy, Users & Authentication

### Tenancy
- `Organization` ↔ `User` is **many-to-many** via `Membership`; `role` lives on the membership
  (`owner` / `admin` / `member` / `viewer`), so one person can hold different roles in
  different orgs.
- `Project` belongs to **exactly one** `Organization`.
- `Project.is_restricted` (default `false`) prepares for project-level access control
  (`ProjectMembership`) without building it yet. In v1, every project is visible to the whole
  org. ERP use (outside consultants on client projects) may pull this forward — see §15.

### Users
- `username` — unique across the app (users can belong to several orgs); lowercase letters,
  digits, hyphens; set at account creation, changeable by the user. Exists now so @mentions can
  be added with notifications (v1.5); mentions will store user IDs, so renames break nothing.
- `is_active` — an inactive user **cannot sign in at all**; deactivation deletes their sessions
  immediately. Their past work (tasks, comments, log entries) still references them and is shown
  with a "deactivated" badge. Their open tasks stay assigned; the UI highlights them for manual
  reassignment.
- `is_system_admin` — may perform any action in any org or project (one exception: deciding
  another person's approval, §6.2). Orgs still have their own owners/admins with full control
  over their org. The first system admin is created by a CLI / seed script. The last active
  system admin cannot be deactivated or demoted (lockout safeguard).
- `must_change_password` — set when an admin creates an account or resets a password; the user
  is prompted to choose their own on next sign-in.

### Account creation (no invitations in v1)
- **System admins** create accounts.
- **Org owners/admins** can also create accounts; doing so creates the user *and* their
  membership in that org in one step. If the email already has an account (the person belongs
  to another org), the existing user is added to the org instead of creating a duplicate.
- **Scope limit for org admins:** they can add/remove members and change roles within their own
  org. Deactivating an account or resetting the password of a user who belongs to **more than
  one** org is system-admin-only — otherwise one org's admin could lock someone out of, or take
  over, their access elsewhere.

### Sign-in
- **Email + password** is primary (`user.hashed_password`, required).
- **GitHub sign-in** is optional: a user links their GitHub account from account settings
  ("Connect GitHub" OAuth flow → `user_identity` row) and can unlink it later. "Sign in with
  GitHub" **only works for accounts that already have GitHub linked** — it never creates
  accounts, keeping admins in control of who gets in. A GitHub account can link to only one
  user. (Account-level; independent of whether any project enables the `github` module.)
- **Change password** from account settings: requires the current password; signs out the
  user's other sessions.
- **Forgot password:** admin reset in v1 (no email infrastructure yet); self-service email reset
  later.

### Sessions
- Server-side sessions in a `session` table, referenced by an httpOnly cookie (not JWTs), so
  deactivation, removal, and password changes take effect immediately by deleting session rows.
- **Slice 1 security checklist** (standard practice, built with auth):
  - Token: 32 random bytes (`secrets.token_urlsafe(32)`); only its SHA-256 hash is stored.
  - Cookie: `__Host-session`, `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`.
  - A fresh token at every sign-in (never reuse an existing session); a password change
    replaces the current session's token and deletes the user's other sessions.
  - CSRF: `SameSite=Lax`, plus an `Origin` check on every mutating request, plus JSON-only
    request bodies.
  - Passwords hashed with Argon2id.
  - Idle timeout and absolute lifetime as configuration (defaults 7 and 30 days);
    `last_seen_at` written at most every 5 minutes.
- **Before the first non-local deployment** (features, not design questions):
  - Sign-in throttling per account and per IP, with progressive delays and no permanent
    lockout (`login_attempt` table).
  - Active-sessions page (adds `user_agent` and `ip_address` to `session`) with per-session
    revoke; admin "sign out everywhere" with the same scope limits as deactivation.
  - Password re-entry for sensitive actions (changing email, linking/unlinking GitHub, admin
    password resets).
  - Nightly worker job deleting expired sessions.
  - Per-org session-length settings, if any org needs shorter limits.
- GitHub OAuth `state` + PKCE are part of the GitHub slice.

## 5. Authorization

### The choke point
- No permission table in v1. Every check goes through one service-layer function,
  `authorize(user, action, entity)`, which **fails closed** (unrecognized action → deny) and has
  one unit test per action/role combination. Its internals can later be swapped for a
  data-driven `Permission`/`RolePermission` table without touching endpoints.
- `authorize()` checks `user.is_system_admin` first; then membership role; then the targeted
  field-based rules below.
- **Reads are authorized too**, not just mutations:
  - Single-entity reads call `authorize(user, "view", entity)`.
  - List endpoints can't check row by row, so their queries are **org-scoped** at the query
    level.
  - Both are enforced through a FastAPI dependency so an endpoint can't obtain an entity without
    the check.
  - Failures on entities the user can't see return **404, not 403**, so existence isn't leaked.
- **Module gating** is a separate dependency: a request to a module that is disabled for the
  project returns 404 before `authorize()` runs.

### Role capabilities (org level)

| Role | Capabilities |
|---|---|
| viewer | View everything in the org; comment on tasks and requirements; edit/delete own comments; decide approvals they are named on |
| member | Viewer + create and edit requirements, tasks, subtasks, test cases; record test results; manage sprints, phases, milestones, workstreams, tags, dependencies, links |
| admin | Member + create and cancel approval requests; create/archive projects; change project type and enabled modules; manage members and roles; create users in the org; every targeted-rule override below |
| owner | Admin + manage the org itself and its owners/admins |
| system admin | Anything, in any org (except deciding someone else's approval) |

### Targeted rules — Task status transitions

| Transition | Allowed |
|---|---|
| `in_review → done` | assignee or reviewer; always owner/admin |
| `in_review →` any other status | reviewer; if no reviewer, the assignee; always owner/admin |
| `→ done` from any other status | assignee; if unassigned, the reviewer; always owner/admin |
| Assignee is also the reviewer | allowed |

Review is therefore *supported but not enforced* (consistent with §1). Enforced review and
blocking self-review are candidates for per-org settings later.

### Other targeted rules
- **Deletion** (soft delete; whoever may delete an item may also restore it):

  | Item | Who can delete |
  |---|---|
  | Task | reporter, or owner/admin |
  | Requirement | reporter while it has never been approved (`approved_revision_id IS NULL`); once approved, owner/admin only |
  | Test case | reporter, or owner/admin |
  | Subtask (hard delete) | any member |
  | Phase, milestone (hard delete) | any member, only while nothing references them |

  An approved requirement is a signed-off artifact, which is why it needs an owner/admin.
- **Approvals (§6.2):** owners/admins create and cancel approval requests. Only the **named
  approver** can decide their own approval row. This is personal: nobody, including owners,
  admins, or system admins, decides on another approver's behalf. An admin can cancel the
  request instead.
- The **last owner** of an org cannot leave or be demoted.

### Request shape
Every protected mutation follows the same order, inside **one database transaction per
request**:

**authenticate → authorize() → apply the change → log_change() → commit**

A failed authorization produces a clean 403/404 with no side effects. Because the change and
its log entry commit together, a change is never saved without its audit record (and vice
versa).

## 6. Core Entities

```
Organization → Project ─┬─ Requirement (self-referencing tree) ─┬─ RequirementRevision
                        │                                        └─ Task (optional link)
                        ├─ Task (always) → Subtask
                        ├─ TestCase (always) ⇄ Requirement (many-to-many)
                        ├─ TestRun → TestResult
                        ├─ Phase ── Milestone (optional phase)
                        ├─ Workstream  (owner of requirements, tasks, test cases)
                        └─ Sprint      (sprints module)

Task → Phase, Sprint, Milestone, Workstream: each optional and independent.
ApprovalRequest → Approval (one per approver), attached to a requirement, gate, or test run.
```

### Requirement
- Self-referencing (`parent_requirement_id`) for arbitrary nesting in one table; a top-level
  requirement stands in for an "epic." On ERP projects the tree naturally holds the
  business-process hierarchy (e.g. Procure-to-Pay → Invoice Processing → 3-way match). A parent
  must be in the same project; parent cycles are prevented by a service-layer check (same
  approach as task dependencies).
- `priority` (critical/high/medium/low), markdown `description_md`, `rank` among siblings.
- `reporter_id` (NOT NULL, set to the creator; owners/admins can reassign it). Drives delete
  permission (§5). Distinct from any ERP "business owner" role, which is covered by approvals
  (§6.2).
- `workstream_id` (nullable). A new child requirement defaults to its parent's workstream in the
  UI.
- **Acceptance criteria live in the description** (no separate field). New requirements are
  pre-filled from a template with a `## Acceptance Criteria` heading, so criteria are
  consistently placed and machine-findable for v2 AI features.
- Revision history and approval tracking — see §6.1 and §6.2.

### 6.1 Requirement revisions
- Every **explicit save** that actually changes `title` or `description_md` creates a
  `requirement_revision` (full snapshot + optional `change_note`). No-op saves and autosaves do
  not create revisions.
- `requirement.current_revision_id` points to the latest revision;
  `requirement.approved_revision_id` (+ `approved_by`, `approved_at`) records exactly which
  revision was approved, set when an approval request completes (§6.2).
- **"Changed since approval"** is *derived*, never stored:
  `approved_revision_id IS NOT NULL AND approved_revision_id <> current_revision_id`.
  The status stays `approved`; the UI shows "Approved · modified" with a diff between the two
  revisions. Re-approval is a new approval request for the current revision.
- Status and priority changes are *not* revisions — they go to `activity_log`.

### 6.2 Approvals
Formal sign-off, generalized beyond requirements. ERP implementations run on sign-offs
(design documents, gate reviews, UAT exit); software projects use the same mechanism for
requirement approval.

- **Approvable entities (v1):** requirements, gates (`milestone.kind = gate`), and test runs
  (e.g. UAT exit sign-off). The reference is polymorphic, so more entity types can be added
  without a migration.
- An **approval request** names one or more approvers; each gets one `approval` row. A
  requirement request is bound to a specific revision. At most one request per entity is
  pending at a time.
- **Policy (v1): every named approver must approve.** Any rejection rejects the whole request;
  a further round is a new request. Other policies (any-one, quorum) are v2+.
- **Who does what:** owners/admins create and cancel requests; each named approver decides only
  their own row (§5). Named approvers may hold any role, including viewer, so business
  stakeholders can sign off without edit rights.
- **Completing a requirement request** sets `approved_revision_id` to the request's revision,
  `approved_at` to the completion time, and `approved_by` to the approver whose decision
  completed it (the full list lives in the `approval` rows). A `draft` requirement moves to
  `approved`.
- **Stale requests:** because a request is bound to its revision, approving it after a newer
  revision was saved still records exactly what was approved; the requirement then shows
  "Approved · modified" (§6.1). The UI warns approvers when a newer revision exists.
- Approval requests are never deleted; they are cancelled.

### Task (the "story")
- Always belongs to a project (`project_id` NOT NULL). `requirement_id` is **optional** — bugs,
  chores, and spikes often have no parent requirement. Tasks without a requirement are flagged
  in the UI, not blocked.
- `type`: feature / bug / chore / spike / config / data / training. (Displayed per project type,
  e.g. `bug` → "Defect" on ERP projects.)
- `severity` (s1 / s2 / s3 / s4, nullable): defect severity, shown for bugs. Separate from
  priority — severity is the impact, priority is the order work is done in.
- Title, markdown description, **manually set** `status` (not derived from subtasks; a
  "3 of 5 subtasks done" indicator may be shown alongside later).
- `priority` (critical/high/medium/low), nullable `start_date` and `due_date`, `rank`.
- People (all single FKs to `user`): `assignee_id` (nullable), `reporter_id` (NOT NULL, set to
  creator), `reviewer_id` (nullable, single reviewer).
- Placement, each optional and independent: `phase_id`, `sprint_id` (one sprint at a time),
  `milestone_id` (independent of requirement), `workstream_id`.
- `time_estimate` / `time_taken`: numeric and unit-agnostic (points or hours by project
  convention).
- Its phase, sprint, milestone, workstream, and requirement must belong to the same project
  (service-layer check).

### Subtask
- Separate table (not self-referencing) — no multi-level nesting to guard against.
- Title, plain-text description, `is_done`, `rank`, and a number within its task, displayed as
  `{KEY}-TA-{n}.{m}` (e.g. `PMT-TA-45.2`). A subtask cannot move to another task.
- No `assignee_id`, phase, or workstream — always resolved through the parent task.
- Hard-deleted (it's a checklist item inside its task).

### Phase
- A span of the project's timeline — e.g. Discover, Design, Build, Test, Deploy, Hypercare on
  an ERP project. Project-scoped, ordered by `rank`, with `start_date`/`end_date` and
  `baseline_start`/`baseline_end`.
- **Phases may overlap** (Build and Test usually do), so several can be `active` at once; unlike
  sprints, there is no one-active rule.
- **Task → Phase:** `task.phase_id` (nullable). A task belongs to at most one phase,
  independently of its sprint and milestone — one task can be in the Build phase, Sprint 4, and
  the Release 1 milestone at once.
- **Milestone → Phase:** `milestone.phase_id` (nullable). A gate usually closes its phase
  ("Design sign-off" belongs to Design); a release milestone that spans phases leaves it null.
- **TestRun → Phase:** `test_run.phase_id` (nullable) places a run such as "UAT cycle 2" in the
  Test phase.
- A mismatch between a task's phase and its milestone's phase is flagged in the UI, not blocked.
- Schedule slippage = current dates vs. baseline dates. Re-baselining is logged (§10).
- Part of the core: available on every project type (a software project can use one phase or
  none).

### Workstream
- A functional area of the project with its own lead — the ownership dimension. ERP examples:
  Finance (GL, AP, AR, fixed assets), Procure-to-Pay, Order-to-Cash, Inventory & Warehouse,
  Manufacturing, Data Migration, Integrations, Reporting, Training & Change Management. On
  software projects the same table serves as components (API, frontend, infrastructure).
- Workstreams cut across phases: each goes through design, build, and test. Phase × workstream
  is the grid status reporting rolls up on.
- **Not the same as the requirement tree:** the tree is the business process (what the business
  does); the workstream is who owns it. They usually line up but don't have to — e.g.
  vendor-master conversion sits under Procure-to-Pay in the tree but belongs to the Data
  Migration workstream.
- Requirements, tasks, and test cases carry a nullable `workstream_id` (one per item); ERP
  module entities will too. Items without one appear as "Unassigned" in rollups.
- `lead_id` (nullable user), `rank` for display order, and `archived_at` instead of deletion.

### Sprint
- Part of the `sprints` module (on by default for software projects).
- Belongs to one project (multi-project sprints are a contained v2 migration).
- `goal` text field. **At most one `active` sprint per project** (partial unique index — a data
  integrity rule, not a workflow rule).

### Milestone
- Flat, separate from the requirement tree; a point in time for cross-cutting groupings.
- `kind`: **milestone** (a general checkpoint), **gate** (a formal checkpoint, usually closing a
  phase and needing sign-off via §6.2), or **release** (a delivery grouping).
- `target_date` and `baseline_date`; slippage is target vs. baseline. Re-baselining is logged.
- Optional `phase_id` (see Phase above).
- Task links to a milestone independently of its requirement. Test runs can reference a
  milestone (§8); test cases do not.

### Manual ordering (rank)
- One rank per task (not per view). The backlog shows tasks in rank order; a board column shows
  its status's tasks in the same relative order. Dragging within a column updates rank;
  dragging to another column changes status and places the card among that column's cards.
- Rank is the default **manual** sort. Users can switch a view to sort by priority, due date,
  etc. (display-only); drag-to-reorder is available only in manual sort.
- New items go to the bottom by default. Requirement and subtask ranks are meaningful among
  siblings only.
- **Mechanics:**
  - **The server computes rank.** The client sends the neighbors ("after X, before Y" as IDs);
    the server derives the new fractional-index value. Clients never write rank strings.
  - **Rank writes bypass optimistic locking.** Rank is updated with a direct `UPDATE` that does
    not bump `version`, so reordering never causes a 409 for someone editing the item's content
    (same approach as the subtask counter, §3).
  - **Ties:** every ordered query sorts by `(rank, id)`, so two items that receive the same rank
    in a simultaneous drop still order deterministically. No locking or periodic rebalancing in
    v1.
  - **Cross-column drop** on a board changes status and rank in one request. The status change
    goes through the transition rules in `authorize()` (§5); if denied, the card snaps back with
    a short message and nothing is saved.
- **Requirement tree:** drag reorders among siblings only. Changing a requirement's parent uses a
  "Move to…" action, which runs the same-project and cycle checks and shows the result clearly.
  Parent changes are logged (§10).
- **Sprint planning** (`sprints` module): the backlog shows sprint sections; dragging a task into
  a section sets its `sprint_id` and rank in one request.
- **Non-drag alternatives:** every draggable list offers "Move to top" / "Move to bottom" menu
  actions, for keyboard users and long lists.

## 7. Status Model

v1 uses **fixed status values per entity** (stored as varchar + CHECK).

| Entity | Values |
|---|---|
| Requirement | `draft` / `approved` / `in_progress` / `done` / `rejected` / `deferred` |
| Task | `todo` / `in_progress` / `blocked` / `in_review` / `done` / `cancelled` |
| Test run | `planned` / `in_progress` / `completed` |
| Test result | `not_run` / `passed` / `failed` / `blocked` / `skipped` |
| Sprint | `planned` / `active` / `completed` |
| Phase | `planned` / `active` / `completed` |
| Milestone | `planned` / `in_progress` / `released` / `cancelled` |
| Approval request | `pending` / `approved` / `rejected` / `cancelled` |
| Approval (per approver) | `pending` / `approved` / `rejected` |

- `blocked` is a real task status, not a flag. "All active work" = `status IN ('in_progress',
  'blocked')`.
- `cancelled` keeps abandoned work out of completion metrics.
- **Priority** (requirement and task): `critical` / `high` / `medium` / `low`.
- **Severity** (task, for defects): `s1` / `s2` / `s3` / `s4`, most to least severe.

> **Flagged for v2+:** configurable per-project workflows (custom statuses and ordering) with a
> generic `category` (todo / in_progress / done) so cross-project logic still works.

## 8. Testing Model

The original single `testcase.status` could not answer "what passed in v1.0?", "when did this
start failing?", or "against which commit?". Definition and execution are now separate:

- **`testcase`** — the definition: title, description (steps folded in), `test_type`,
  `expected_result`, `automation_ref` (e.g. `tests/api/test_auth.py::test_login`, for future CI
  ingestion), optional `workstream_id`, and `reporter_id` (set to the creator; drives delete
  permission, §5). **No status column.**
  `test_type`: unit / integration / e2e / manual / sit / uat / parallel / regression. ERP
  projects mostly use `sit`, `uat`, and `parallel` (running the old and new systems side by side
  and comparing results).
- **`test_run`** — one test cycle ("v1.0 regression", "UAT cycle 2"), optionally tied to a
  phase, milestone, and/or sprint, with optional `environment` and `commit_sha`. Exit sign-off
  for a run uses an approval request (§6.2).
- **`test_result`** — one test case's outcome in one run (`UNIQUE(run, testcase)`): status,
  `actual_result`, notes, executor, time, and an optional `bug_task_id` linking a failure to the
  bug task it produced.

**Every result belongs to a run**, but manual recording stays quick: the "record result" action
on a test case finds or creates an **ad-hoc run** (`is_adhoc = true`) for that project and day
("Ad-hoc — 2026-09-23"). Planned runs remain deliberate and separate. When CI integration
arrives, each workflow run becomes its own run with `commit_sha` set — no schema change.

**Current test status** = the most recent result by `executed_at`, **ignoring `not_run`** (so
adding a case to a new planned run doesn't make it look untested). Computed, not cached; cache
later only if list views get slow.

**Requirement ↔ TestCase is many-to-many** (`requirement_testcase`) — one test often verifies
several requirements. A test case may exist with no linked requirement (e.g. a regression test
written after a bug); it is flagged in the UI, not blocked.

## 9. Deletion Behavior

| Entity | Behavior |
|---|---|
| Project | `archived_at`: read-only, hidden from default lists, still browsable |
| Requirement, Task, TestCase, Comment | `deleted_at`: hidden everywhere, restorable |
| Workstream | `archived_at`: hidden from pickers, still shown on existing items and in reports |
| Phase, Milestone | hard delete, only while nothing references them (references must be cleared or moved first) |
| Approval request | never deleted; cancelled instead |
| Subtask | hard delete |

**Deleting a task:** its subtasks, comments, tags, attachments, and GitHub links are left in
place and hidden with it — restoring the task restores everything. Dependencies involving it are
ignored while it's deleted. Webhook updates to its GitHub links continue, so a restore shows
accurate PR status.

**Deleting a test case:** its requirement links and past results remain for history; it drops
out of planned runs.

**Deleting a requirement** opens a dialog listing what's affected, with a choice per category:
- **Linked tasks and test cases:** *detach* them (they remain, now without a requirement, and
  are flagged in the UI) **or** soft-delete them too.
- **Child requirements:** *promote* them to the deleted requirement's parent (or top level)
  **or** soft-delete them too.

Every unlink is recorded in `activity_log` (`action = unlinked`). Restoring a requirement does
not re-link anything automatically; the log shows what was attached, and re-linking is manual.

**Permissions in the delete dialog:** "soft-delete them too" applies only to items the user
could delete directly (§5). For linked items or children they can't delete, only *detach* or
*promote* is offered, with a note explaining why. The dialog never lets someone delete
indirectly what they couldn't delete directly.

**Restore** follows delete: whoever may delete an item may restore it. The trash view shows each
user what they can restore; owners/admins see everything.

**Pending approvals:** deleting a requirement, gate, or test run cancels any pending approval
request on it (logged). Restoring the item does not reopen the request.

**Comments** are soft-deleted and shown as "comment deleted" so threads stay readable.

## 10. Audit — ActivityLog

- One generic table records **created / updated / deleted / restored / linked / unlinked**
  events for requirements, tasks, test cases, **phases, and milestones**. Sprint changes are not
  logged. Phase and milestone date and status changes are, so baselines and re-baselining are
  auditable.
- `field_changed` is required for `updated` events. Logged fields:
  - **Requirement / task / test case:** `status`, `assignee_id`, `reporter_id`, `reviewer_id`,
    `sprint_id`, `milestone_id`, `phase_id`, `workstream_id`, `priority`, `severity`,
    `start_date`, `due_date`, `requirement_id`, `parent_requirement_id`, `time_estimate`,
    `approved_revision_id`.
  - **Phase / milestone:** `status`, `start_date`, `end_date`, `baseline_start`,
    `baseline_end`, `target_date`, `baseline_date`.
  - `rank` is deliberately excluded — drag-and-drop would flood the log.
- `old_value` / `new_value` are text (the table is generic across types). For link events they
  hold the other entity's ID.
- `project_id` on every row makes the project activity feed a single indexed query.
- **Implementation rules:**
  - Only the shared helper `log_change(...)` writes to `activity_log` — never an endpoint
    directly. Endpoints pass enum members; the helper serializes them.
  - `log_change()` does **not** commit; it adds the row to the request's session, so the change
    and its log entry commit (or roll back) together.
- Content history for requirements lives in `requirement_revision`, not the log (§6.1).
  Approval decisions live in the `approval` rows (§6.2); their effect on a requirement is logged
  through `approved_revision_id`.
- Logging `time_estimate` changes, plus a future nightly snapshot job, is what makes a real
  burndown chart possible later.

## 11. Collaboration Features

### Comments
- Flat list (threading is v2), on **tasks and requirements**. Markdown body.
- Viewers can comment. Authors edit/delete their own comments; owners/admins can delete any.
- Soft-deleted.

### Tags
- Org-scoped vocabulary (`UNIQUE(organization_id, name)`), applied to tasks, requirements, and
  test cases through a polymorphic `entity_tag` table. Tags are free-form labels; structured
  rollups use workstreams (§6).

### Task dependencies
- `blocks` (directional) or `related_to` (symmetric; stored in canonical order so A↔B is saved
  once). A task can't depend on itself.
- `blocks` doubles as the finish-to-start link for a timeline view (tasks now have
  `start_date`).
- Circular-dependency protection for `blocks` via a service-layer graph traversal at creation
  time (a DB constraint can't detect transitive cycles).

### Link attachments
- URL + label on tasks, requirements, and test cases. Real file uploads are v2 (needs a storage
  backend decision, e.g. MinIO → S3/R2).

### Polymorphic tables
`comment`, `entity_tag`, `link_attachment`, and `approval_request` reference their parent by
`(entity_type, entity_id)` with no FK. This keeps adding a new entity type migration-free. With
soft delete, parents are never physically removed, so orphaning isn't a practical risk; the
service layer verifies the parent exists when a row is created, and a composite index on
`(entity_type, entity_id)` keeps lookups fast.

### Not in v1
- Watchers/subscribers and notifications → notifications planned for **v1.5** (§16).

## 12. GitHub Integration

**Framing:** GitHub integration is the `github` module (§1.1), on by default for software
projects and off for ERP projects. Integration is passive (read and mirror repo state); the tool
does not write code or push to repos.

1. **Connection** — a GitHub App. Installations are stored in `github_installation` (an org may
   have several, e.g. a personal account and a company org). API tokens are fetched short-lived
   per request from the installation ID.
2. **Repo ↔ Project mapping** — `project_repository`, linked to its installation. A repo may map
   to **multiple projects** (e.g. a monorepo); this is unambiguous because every ID carries its
   project key.
3. **Task ↔ GitHub linking** — `task_github_link` references a specific
   `project_repository` (so "PR #42" means *that* repo's #42). Link types: **pr / commit /
   branch**. `link_source` records whether a link was pasted manually or detected
   automatically. One PR may link to several tasks.
   - **Auto-detection (v1):** task IDs in **PR titles and branch names only**, case-insensitive
     (branches are usually lowercase, e.g. `pmt-ta-45-fix-login`), matched against the project
     keys mapped to that repo. **Tasks only** — requirement IDs are not linked in v1. A subtask
     ID (e.g. `pmt-ta-45.2-add-validation`) links its parent task, TA-45.
   - **Commits** can be linked manually by pasting a URL; they are not auto-detected.
   - If an ID is later removed from a PR title, the existing link stays; removal is manual.
4. **Webhooks** — each delivery is recorded in `github_webhook_delivery`:
   - Reject any request whose `X-Hub-Signature-256` doesn't verify.
   - `delivery_id` is unique, so GitHub redeliveries are processed once.
   - The endpoint stores the delivery, enqueues a job in the same transaction, and responds
     immediately; the worker does the matching and updates `github_status` (PRs only:
     open / draft / merged / closed). Failures are recorded on the delivery row.
   - `processed_at IS NULL` doubles as an outbox: a periodic sweeper re-enqueues unprocessed
     deliveries.
   - Deliveries for repos mapped only to projects with the module disabled are recorded but not
     matched.

**Deferred to v2 — automatic `Task.status` changes from GitHub events.** A webhook has no human
actor to run through `authorize()`. Linked GitHub accounts (§4) provide one path to
attribution; a scoped "system actor" is the alternative. Left as a v2 design question.

## 13. Background Jobs

- **Library:** procrastinate, with jobs stored in Postgres. Runs as the `worker` service.
- **v1 uses:** webhook processing, the webhook sweeper. **Later:** notifications (v1.5), nightly
  sprint/burndown snapshots, CI result ingestion, ERP module jobs (e.g. cost imports), v2 AI
  jobs.
- **Why not FastAPI `BackgroundTasks`:** in-process, no retries, lost on restart.
- **Portability conventions** (keep a future switch to ARQ/Celery + Redis to a day or two):
  1. All enqueueing goes through one module (e.g. `app/jobs/enqueue.py`,
     `enqueue_webhook_processing(delivery_id)`); endpoints never call the queue library
     directly.
  2. Job arguments are IDs and plain values, never ORM objects.
  3. Jobs are idempotent (every queue retries).
  4. Work whose loss matters is also tracked in the app's own tables (outbox pattern), not only
     in the queue.
  5. Library-specific features used in business logic are wrapped in our own helpers.

## 14. Search

- Postgres full-text search over title + description of requirements, tasks, and test cases:
  a generated `search_vector` (`tsvector`) column with a GIN index on each table.
- Typing an exact ID (`PMT-TA-45`, or `PMT-TA-45.2` for a subtask) jumps directly to that item.
- Saved filters / views are later.

## 15. Open Implementation Decisions

These were deliberately left for implementation time; none changes table shapes significantly.
All earlier core items (number allocation, rank UI, delete permissions, session handling) are
now settled in their sections; what remains is tied to the ERP modules.

- **ERP permissions** (decided with the ERP modules):
  - a financial-visibility flag on membership, checked in `authorize()`, for budget data;
  - whether `project_membership` moves up from v2 (outside consultants on client projects);
  - a targeted rule letting business-user testers record results on runs assigned to them;
  - how outside consultants and integrator staff are onboarded.
- **ERP modules:** each needs its own design pass (§16).
- **Reporting:** which reports and dashboards define a usable ERP version, and which numbers get
  frozen in published snapshots.

## 16. Roadmap

### v1.5
- **In-app notifications** (`notification` table, bell icon, polling): assigned to you, review
  requested, approval requested, status changes on tasks you're involved in, @mentions (via
  `username`). Generated by a worker job queued from `log_change()`.

### ERP modules (after the v1 core; design pending)
Proposed order, adjustable once priorities are clear:
1. **RAID & change requests** (`raid`) — one table typed risk / assumption / issue / decision /
   change; owner, workstream, due date; probability × impact scoring; mitigation/resolution;
   cost and schedule impact for change requests; a generic `entity_link` to connect items to
   requirements, tasks, and defects.
2. **Status reports** (`status_reports`) — per-period overall and per-workstream RAG, narrative,
   frozen key metrics; immutable once published.
3. **Budget & actuals** (`budget`) — budget lines (category, workstream, planned, forecast),
   cost entries (vendor, invoice/PO reference), money as `numeric(14,2)` with a project
   currency; approved change requests draw down contingency; possible import of actuals from
   the ERP's own AP data; possibly `time_entry` for internal labor.
4. **Data migration** (`data_migration`) — data objects, load cycles (Mock 1, Mock 2, Cutover),
   per-object per-cycle loads with counts, source vs. target totals, variance, and
   reconciliation sign-off. Mirrors the testcase / run / result pattern.
5. **Cutover** (`cutover`) — runbook steps (sequence, planned duration, owner, dependencies)
   executed and timed in each rehearsal. Same definition/execution pattern.

### Deferred until first need
- **API tokens** (`api_token`: hashed, prefixed, expiring, revocable; resolve to a `User` so
  `authorize()` is unchanged). First likely needs: scripts/imports, v2 Claude/MCP integration.
  CI will use a dedicated bot user.
- **CI test results** — likely via the GitHub App instead of tokens: on workflow completion,
  the worker downloads the JUnit XML artifact and records a `test_run` matched by
  `automation_ref`.

### v2+
- Configurable per-project workflows (replacing fixed statuses)
- User-configurable display labels (beyond the per-type mapping)
- Multi-project sprints (`sprint_project` join table)
- `time_entry` table for time-series tracking; true burndown (may move up with the budget module)
- Multiple reviewers per task
- Watchers/subscribers; email notifications
- `project.estimation_unit` (points vs. hours) for display
- Project-level access control (`project_membership`), gated by `project.is_restricted` (may move
  up with ERP)
- Comment threading
- Real file uploads (storage backend decision)
- Automatic `Task.status` changes from GitHub events
- Approval policies beyond all-must-approve (any-one, quorum); per-org settings for enforced
  review / no self-review
- Invitations and self-service email password reset
- Commit-message ID detection; requirement (`RQ`) linking from PRs
- Project key rename with old key kept as an alias; moving items between projects (or subtasks
  between tasks) with old IDs kept as aliases
- Saved filters/views
- Redis, if caching / rate limiting / real-time needs appear
- AI-assisted features (requirements drafting, task breakdown, test-case generation)
