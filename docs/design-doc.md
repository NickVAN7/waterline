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
> 4. Sets the v1 scope to software projects, with ERP implementations in v2 (§1), and replaces
>    the tenancy model: a workspace above organizations, workspace/org/project roles, and
>    explicit project membership instead of `project.is_restricted` (§4, §5). Source:
>    `screen-inventory.md` (Sept 28, 2026).
>
> Table-level detail lives in `schema-doc.md`. The people who use Waterline, the tenancy and
access model, and the screens derived from them are in `screen-inventory.md`.

## 1. Overview

**Working name: Waterline.** Most of an iceberg sits below the waterline, as does most of a
project: the hidden work, dependencies, and risk. The tool keeps status visible above the line
and the traceability behind it available below. The name ties to the company's iceberg logo. It
is used for the repository (`waterline`), container images, the developer CLI (`waterline`, alias
`wl`), and the app's title; the Python package stays `app`, so a later rename is cheap.

A tool for gathering requirements, planning work scope, executing, testing, and reporting on a
project. It is designed to serve two kinds of work from one codebase:

- **Software projects** — requirements, tasks, sprints, test cases, GitHub integration.
- **ERP implementations**, run from a finance/operations point of view — phases and gates,
  functional workstreams, formal sign-offs, UAT cycles, and (as modules land) RAID logs, budget
  vs. actuals, data migration, cutover, and status reporting.

**Scope: v1 is built for software projects; ERP implementations come in v2.** The core
generalizations ERP needs stay in v1: phases, workstreams, generalized approvals (§6.2), and
project type and modules (§1.1). They are cheap to build now and would be an expensive retrofit
later, once v1 data and screens assume a software-only shape. ERP personas and modules are
recorded (`screen-inventory.md`, §16) so v1 doesn't paint them into a corner, but their modules
and screens are designed in v2.

Built for personal use initially, with the data model designed to scale to a firm (a
workspace, §4) running projects for several client organizations.

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
  when the project is created and selects the display labels the UI uses. Project admins can
  change it later; changing it changes labels and recommendations only, never data or enabled
  modules.
- **`project.enabled_modules`** — seeded from the type; project admins can turn modules on or
  off at any time.

| Module | Adds | Default on for | Status |
|---|---|---|---|
| `sprints` | Sprint planning; sprint board | software | v1 |
| `github` | GitHub App, repo mapping, PR/branch links (§12) | software | v1 |
| `raid` | Risks, assumptions, issues, decisions, change requests | erp | v2 |
| `status_reports` | Published RAG status snapshots | erp | v2 |
| `budget` | Budget lines, actuals, forecast | erp | v2 |
| `data_migration` | Data objects, load cycles, reconciliation | erp | v2 |
| `cutover` | Cutover runbook and rehearsals | erp | v2 |

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
| ORM / Migrations | SQLAlchemy 2.x (plain, not SQLModel) + Alembic | Mature; fits the relational, traceability-heavy model. SQLModel was rejected (build-plan, implementation decision 1) |
| Database | PostgreSQL | Also hosts the job queue and full-text search — no extra services in v1 |
| Background jobs | procrastinate (Postgres-backed queue) | No new infrastructure; jobs enqueue in the same transaction as the data they act on |
| Frontend | Vue 3 + TypeScript | Existing familiarity |
| Local dev | Docker Compose: `api`, `worker`, `web`, `postgres` | Worker runs the same image as `api` with a different command; `web` is the Vite dev server |
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
  **workspace** (§4), so an ID like `ERP-TA-45` means one item across every client the firm
  works for; **immutable** after creation (renaming would break every external reference).
  Because every entity prefix is two letters, a 3-character minimum means no project key can
  ever collide with a current or future prefix — no reserved-word list is needed.
- **URLs:** API URLs identify a project by its key alone (`/api/projects/{key}/…`). Browser URLs
  also show the org for readability (`/{org_slug}/projects/{key}/tasks/45`), but the slug only
  decorates: the key identifies the project, and a stale or wrong slug (e.g. after an org is
  renamed) redirects to the current one, so old links keep working. The redirect happens only
  after the project is authorized; for a project the user can't see it's a 404, so the redirect
  never reveals an org.
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
Decided Sept 28, 2026; `screen-inventory.md` ("Tenancy & access model") has the reasoning and
the people it serves.

```
Workspace (the firm: tenant boundary)
├── Internal staff: workspace members
└── Organization (normally one per client)
    ├── Client users: org members
    └── Project
        └── Project members (admin / member / viewer)
```

- **`Workspace`** is the tenant boundary: the firm running the projects. The schema supports
  many; v1 deploys with **one**, created by the seed CLI alongside the first system admin, who
  also becomes its owner. There is no UI to create workspaces.
- **`Organization`** belongs to exactly one workspace (`organization.workspace_id`). An org is
  normally one client; a software-only setup is one workspace with one internal org. Its
  `slug` (unique in the workspace, renameable) appears in browser URLs (§3).
- **`Project`** belongs to **exactly one** `Organization`.
- **Three membership levels**, each with its own role, so one person can hold different roles
  in different places:

  | Level | Table | Roles | Who |
  |---|---|---|---|
  | Workspace | `workspace_membership` | owner / admin / member | Internal staff |
  | Organization | `membership` | owner / admin / member | Users of that org (client users) |
  | Project | `project_membership` | admin / member / viewer | The project's team |

- **Project access is always explicit project membership.** There is no "visible to the whole
  org" flag. System admins, workspace owners/admins, and owners/admins of the project's org
  **inherit project admin** on every project they can see, without a `project_membership` row.
- **Visibility:** internal staff (workspace members) see only the orgs and projects they are
  assigned to; workspace owners/admins see every org and project in the workspace.
  "Assigned" means a membership:
  - a user sees a **project** they hold a `project_membership` on, or inherit admin on;
  - a user sees an **org** they hold a `membership` in or a project membership on one of its
    projects. An org membership alone (role member) shows the org, not its projects;
  - only workspace owners/admins (and system admins) see the **workspace pages** (staff, org
    list, users). Workspace members and client users see only their orgs and projects, through
    the org switcher.
- **Client users normally belong to one org.** This is typical, not enforced.
- **One workspace for the foreseeable future.** It exists mainly to roll up dashboards and
  statistics across clients. Rules that only matter with several workspaces (e.g. users in more
  than one) are decided if a second workspace is ever needed.
- **Staff may also hold org memberships**, e.g. a workspace member who is an admin of a client
  org to manage that client's users.

### Users
- `username` — unique across the app (users can belong to several orgs); lowercase letters,
  digits, hyphens; set at account creation, changeable by the user. Exists now so @mentions can
  be added with notifications (v1.5); mentions will store user IDs, so renames break nothing.
- `is_active` — an inactive user **cannot sign in at all**; deactivation deletes their sessions
  immediately. Their past work (tasks, comments, log entries) still references them and is shown
  with a "deactivated" badge. Their open tasks stay assigned; the UI highlights them for manual
  reassignment.
- `is_system_admin` — may perform any action in any workspace, org, or project (one exception:
  deciding another person's approval, §6.2). Workspaces and orgs still have their own
  owners/admins with full control within them. The first system admin is created by a CLI /
  seed script. The last active system admin cannot be deactivated or demoted (lockout
  safeguard).
- `must_change_password` — set when an admin creates an account or resets a password; the user
  is prompted to choose their own on next sign-in.

### Account management (no invitations in v1)
- **System admins** create accounts anywhere.
- **Workspace owners/admins** create accounts and add existing users for any org in their
  workspace, and manage the workspace's staff (workspace memberships).
- **Org owners/admins** (including client admins) create accounts in their org and add existing
  users to it. Creating an account creates the user *and* their membership in that org in one
  step.
- **The add-person form asks for the email first.** If the email already has an account, the
  admin is asked to confirm adding that person (no name or password is asked for, and no
  duplicate is created); otherwise the form continues to full account creation (name,
  temporary password). The form therefore shows whether an email has an account, never which
  org it belongs to; invitations (v2+) would hide even that.
- **Project admins** add people to their project from the project org's members and the
  workspace's staff; the picker lists only those, never other clients' users, and adding by
  user ID rejects anyone else with a 404. They can also add by email, with the same email-first
  form:
  - a **new** email creates the user, an org membership (role member) in the project's org, and
    the project membership;
  - an org member's or workspace staff member's email adds only the project membership (staff
    never get an org membership this way);
  - any **other** existing account (e.g. a user in another client org) is added to the project's
    org as a member and to the project, after the admin confirms. The rank rule then keeps
    both orgs' admins from deactivating or resetting them.
- **Account actions follow rank.** Deactivating, resetting the password of, or signing out
  everywhere another user, or reactivating them, is allowed only when the target holds at least
  one membership in the actor's scope, and for **every** membership the target holds, the actor
  has a role covering it (the same workspace, org, or project, or one above it) at an equal or
  higher rank. The system-admin flag counts as a membership at the top rank. A user with no
  memberships left is managed by the workspace's owners/admins and system admins. The ranking,
  highest first:

  ```
  system admin
    > workspace owner > workspace admin > workspace member
      > org owner > org admin > org member
        > project-only user (project roles only)
  ```

  So an org admin can manage other admins and members of their own org and project-only users
  on its projects, but not a workspace member or admin, nor anyone who also belongs to another
  org or to a project outside it; otherwise one org's admin could lock someone out of, or take
  over, their access elsewhere. A workspace admin can't manage the workspace owner or a system
  admin (users in several workspaces: see "One workspace" above). Project admins
  have no account actions.

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
  deactivation, password changes and resets, and "sign out everywhere" take effect immediately
  by deleting session rows. **Removing a membership doesn't touch sessions:** every request
  re-checks memberships, so the lost access ends at once; a user with no memberships left can
  still sign in and sees a "no access" page. Deactivation is how someone is cut off.
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
    revoke. (Admin "sign out everywhere" is built in Slice 1, under the rank rule in "Account
    management".)
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
- `authorize()` checks, in order: `user.is_system_admin`; then a workspace owner/admin role in
  the entity's workspace; then an owner/admin role in the project's org; then the user's
  project role; then the targeted field-based rules below. Anything not granted along the way
  is denied.
- **Reads are authorized too**, not just mutations:
  - Single-entity reads call `authorize(user, "view", entity)`.
  - List endpoints can't check row by row, so their queries are **scoped at the query level to
    the user's accessible projects (and orgs)** (§4, "Visibility").
  - Both are enforced through a FastAPI dependency so an endpoint can't obtain an entity without
    the check.
  - Failures on entities the user can't see return **404, not 403**, so existence isn't leaked.
- **Module gating** is a separate dependency: a request to a module that is disabled for the
  project returns 404 before `authorize()` runs.

### Role capabilities

Roles at each level include the capabilities of the roles listed above them at that level.
"Project admin" below always includes **inherited** project admin (system admins, workspace
owners/admins, and owners/admins of the project's org).

**Project roles** (`project_membership`)

| Role | Capabilities |
|---|---|
| viewer | View the project and everything in it; comment on tasks and requirements; edit/delete own comments; decide approvals they are named on |
| member | Viewer + create and edit requirements, tasks, subtasks, test cases; record test results; manage sprints, phases, milestones, workstreams, dependencies, links; create and apply tags |
| admin | Member + create and cancel approval requests; edit the project's name, type, and enabled modules; manage the project's members and their roles, and create users for it (§4); map GitHub repositories to the project; every targeted-rule override below |

**Org roles** (`membership`)

| Role | Capabilities |
|---|---|
| member | Belongs to the org; can be added to its projects. No project access by itself |
| admin | Create, archive, and unarchive the org's projects, naming each new project's first admin (from the org's members and the workspace's staff; always given a `project_membership` row, even if they also inherit admin); project admin on every project in the org; create users in the org, add existing users as members, and remove members; rename and delete the org's tags and set their type; connect GitHub installations; account actions by rank (§4) |
| owner | Admin + manage the org itself and grant, change, or remove its owner and admin roles |

**Workspace roles** (`workspace_membership`)

| Role | Capabilities |
|---|---|
| member | Internal staff: sees only the orgs and projects they are assigned to, with no inherited access and no workspace pages |
| admin | Manage the workspace's staff; create orgs and assign their first owner; org owner capabilities in every org of the workspace, and so project admin on every project; account actions by rank (§4) on users in the workspace |
| owner | Admin + manage the workspace itself and grant, change, or remove its owner and admin roles |

**System admin:** anything, in any workspace, org, or project (except deciding someone else's
approval).

### Targeted rules — Task status transitions

| Transition | Allowed |
|---|---|
| `in_review → done` | assignee or reviewer; always project admin |
| `in_review →` any other status | reviewer; if no reviewer, the assignee; always project admin |
| `→ done` from any other status | assignee; if unassigned, the reviewer; always project admin |
| Assignee is also the reviewer | allowed |

Review is therefore *supported but not enforced* (consistent with §1). Enforced review and
blocking self-review are candidates for per-org settings later.

### Other targeted rules
- **Deletion** (soft delete; whoever may delete an item may also restore it):

  | Item | Who can delete |
  |---|---|
  | Task | reporter, or project admin |
  | Requirement | reporter while it has never been approved (`approved_revision_id IS NULL`); once approved, project admin only |
  | Test case | reporter, or project admin |
  | Subtask (hard delete) | any project member (member role or above) |
  | Phase, milestone (hard delete) | any project member (member role or above), only while nothing references them |

  An approved requirement is a signed-off artifact, which is why it needs a project admin.
- **Gate sign-off status:** only a project admin moves a gate into `approved` by hand or moves
  it out of `approved` to any other status; completing the gate's approval request sets it as
  a system effect. Members change other milestone statuses as usual. `approved` is refused on
  non-gate milestones.
- **Approvals (§6.2):** project admins create and cancel approval requests. Only the **named
  approver** can decide their own approval row. This is personal: nobody, including project,
  org, or workspace admins, or system admins, decides on another approver's behalf. A project
  admin can cancel the request instead.
- The **last owner** of an org, and the last owner of a workspace, cannot leave or be demoted.

### Request shape
Every protected mutation follows the same order, inside **one database transaction per
request**:

**authenticate → authorize() → apply the change → log_change() → commit**

A failed authorization produces a clean 403/404 with no side effects. Because the change and
its log entry commit together, a change is never saved without its audit record (and vice
versa).

## 6. Core Entities

```
Workspace ─┬─ WorkspaceMembership (internal staff)
           └─ Organization ─┬─ Membership (org users)
                            └─ Project (below)

Project ─┬─ ProjectMembership (admin / member / viewer)
         ├─ Requirement (self-referencing tree) ─┬─ RequirementRevision
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
- `reporter_id` (NOT NULL, set to the creator; project admins can reassign it). Drives delete
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
- **Who does what:** project admins (including inherited, §5) create and cancel requests; each
  named approver decides only their own row (§5). Named approvers may hold any project role,
  including viewer, so business stakeholders can sign off without edit rights.
- **v2:** the RAID module adds change requests and decisions as approvable entities, so the
  steering committee (project viewers named as approvers) can sign them off.
- **Completing a requirement request** sets `approved_revision_id` to the request's revision,
  `approved_at` to the completion time, and `approved_by` to the approver whose decision
  completed it (the full list lives in the `approval` rows). A `draft` requirement moves to
  `approved`.
- **Completing a gate request** moves the milestone to `approved`. Only gates use `approved`;
  a project admin can also set it or move it out of `approved` by hand (§5; logged like any
  status change), so a gate signed off outside the app can still be recorded. **Completing a test-run
  request** moves the run to `completed` (if it isn't already).
- **A rejected request changes nothing** on the entity, for every entity type; the request's
  status and the `approval` rows record the rejection, and a new round is a new request.
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
| Milestone | `planned` / `in_progress` / `approved` / `released` / `cancelled` (`approved`: gates only, set by the gate's approval request or by a project admin, §6.2) |
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
| Phase, Milestone | hard delete, only while nothing references them (references must be cleared or moved first; an approval request on a gate counts and can't be cleared) |
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
user what they can restore; project admins see everything in the project.

**Pending approvals:** deleting a requirement or test run cancels any pending approval request
on it, logged on the request (§10). Restoring the item does not reopen the request. A gate
with any approval request (pending or past) can't be deleted: its sign-off history must keep
pointing at a real milestone. Cancel the gate instead (status `cancelled`).

**Comments** are soft-deleted and shown as "comment deleted" so threads stay readable.

## 10. Audit — ActivityLog

- One generic table records **created / updated / deleted / restored / linked / unlinked**
  events for requirements, tasks, test cases, **phases, milestones, and approval requests**.
  Sprint changes are not logged. Phase and milestone date and status changes are, so baselines and re-baselining are
  auditable.
- `field_changed` is required for `updated` events. Logged fields:
  - **Requirement / task / test case:** `status`, `assignee_id`, `reporter_id`, `reviewer_id`,
    `sprint_id`, `milestone_id`, `phase_id`, `workstream_id`, `priority`, `severity`,
    `start_date`, `due_date`, `requirement_id`, `parent_requirement_id`, `time_estimate`,
    `approved_revision_id`.
  - **Approval request:** `created` when it is made, and `status` for every change (`pending`
    → `approved` / `rejected` / `cancelled`, whether cancelled by a project admin or by deleting
    the item). Individual decisions stay in the `approval` rows.
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
- Viewers can comment. Authors edit/delete their own comments; project admins can delete any.
- Soft-deleted.

### Tags
- Org-scoped vocabulary (`UNIQUE(organization_id, name)`), applied to tasks, requirements, and
  test cases through a polymorphic `entity_tag` table. Tags are free-form labels; structured
  rollups use workstreams (§6).
- **Defaults:** Waterline ships a built-in default set per project type (e.g. software:
  tech-debt, security, ux, performance; erp: fit-gap, customization, data-quality, regulatory),
  copied into each org when it is created (orgs that exist before tags ship get them then). A
  seeded tag keeps its project type (`tag.project_type`), so a project's picker offers the
  general tags plus its own type's. A name in several types' default sets is seeded once, as a
  general tag.
- **Who:** project members and admins create new tags (always general) and apply them;
  renaming, deleting, or setting a tag's type, which affects every project in the org, is for
  org owners/admins (including inherited).
- The picker doesn't offer another type's tags, but the server doesn't reject them (workflow
  over enforcement). Changing a project's type changes what the picker offers; tags already
  applied stay.

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
   have several, e.g. a personal account and a company org), connected by org owners/admins
   (including inherited). API tokens are fetched short-lived per request from the installation
   ID. A project needs no installation: it links to repos only through optional
   `project_repository` rows, which project admins manage.
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
     `enqueue_webhook_processing(session, delivery_id)`); endpoints never call the queue library
     directly.
  2. Job arguments are IDs and plain values, never ORM objects.
  3. Jobs are idempotent (every queue retries).
  4. Work whose loss matters is also tracked in the app's own tables (outbox pattern), not only
     in the queue.
  5. Library-specific features used in business logic are wrapped in our own helpers.

### Transactional enqueue (S0-C3 spike result)

**Question:** can a job be enqueued inside the request's own `AsyncSession` transaction, so it
commits or rolls back with the data? **Answer: yes**, with one condition: the job must be
deferred on the request's database connection. procrastinate (3.10) accepts an external
connection: `task.configure(connection=<psycopg AsyncConnection>).defer_async(...)`. The
request's psycopg connection comes from the session
(`(await (await session.connection()).get_raw_connection()).driver_connection`). procrastinate's
default `defer_async()` does **not** share the transaction: it uses its own connection pool.

Evidence (`docs/spikes/S0-C3-transactional-enqueue.py`, run through the real `SessionDep`
dependency; procrastinate 3.10.0, SQLAlchemy 2.1.1, psycopg 3.3.6, Postgres 18.6):

| # | Scenario | Observed |
|---|---|---|
| A | Default `defer_async()` in a request that then fails | Data rolled back, **job kept** |
| B | Defer on the request's connection; request succeeds | Data and job both committed |
| C | Defer on the request's connection; request fails | Data and job both rolled back |
| D | Another connection looks for the job before the request commits | Not visible until commit |
| E | Worker wake-up (procrastinate's `NOTIFY`) | Sent only on commit, never for a rolled-back job |
| F | Worker runs the committed job | Succeeds and reads the row the request wrote. The orphan job from A also ran, against a row that never existed |
| G | Same `queueing_lock` deferred twice in one request | `AlreadyEnqueued`, after which the request's transaction is aborted (`InFailedSqlTransaction`); inside a savepoint (`begin_nested()`) the conflict raises there and the request's transaction stays usable |
| H | Test harness (outer transaction, `join_transaction_mode="create_savepoint"`) | Job visible inside the test; gone after its rollback |
| I | Defer **by task name** (`App.configure_task(name, connection=...)`) from an app where the task isn't registered | Committed with the data; a worker that registers the task runs it |
| J | Same, from a procrastinate app that was **never opened** | Works: deferring on the request's connection doesn't use procrastinate's pool |

**Consequences:**
1. **`app/jobs/enqueue.py` defers on the caller's session.** Every enqueue function takes the
   `AsyncSession` (e.g. `enqueue_webhook_processing(session, delivery_id)`) and defers on its
   connection, so the job commits or rolls back with the data (convention 1). Nothing calls
   procrastinate's pool-based `defer_async()` from request or service code: an orphan job would
   run against data that was never committed (scenario A/F).
2. **No race with the worker.** A job is invisible, and the worker isn't woken, until the
   request commits, so a job never runs before its data exists.
3. **Getting the driver connection is library-specific**, so it lives only in `enqueue.py`
   (convention 5).
4. **A failed enqueue fails the request.** The defer runs in the request's transaction, so an
   error there aborts it. Where a conflict is expected (a `queueing_lock` for "at most one
   pending job"), `enqueue.py` defers inside a savepoint and treats `AlreadyEnqueued` as
   "already queued".
5. **Convention 4 (outbox) still applies.** Transactional enqueue makes the job itself
   reliable, but a later move to a Redis-backed queue couldn't be transactional, so work whose
   loss matters (webhook deliveries) keeps its own row (`github_webhook_delivery`) as the
   source of truth; the job carries only its ID.
6. **Tests:** the rolled-back per-test transaction covers enqueueing (assert the job row inside
   the test). A test in which a worker processes a job needs real commits, so it uses the
   `concurrency` fixture.
7. **`enqueue.py` defers by task name and never imports job modules.** Job functions call
   services, often in higher layers (webhook processing calls the `webhook` service, layer 6),
   so importing them into `enqueue.py`, which services at every layer use, would break the
   service layers contract. Only the worker imports the job modules. Scenario I shows deferring
   by name works on the request's connection. The API process doesn't need to open
   procrastinate's app or pool at all: every defer runs on the request's connection
   (scenario J). Only the worker opens it.
8. **Schema:** procrastinate ships `schema.sql` plus versioned migration files (38 at 3.10,
   in `procrastinate/sql/migrations/`; since 3.0 a change can come as a `_pre_` file, applied
   before deploying the new code, and a `_post_` file, applied after), and one pending file in
   `future_migrations/`. They are applied through Alembic; a procrastinate upgrade gets an
   Alembic migration applying its new files in their order; procrastinate's tables are
   excluded from autogenerate. *Decided in S0-C4:* a version's `_pre_` and `_post_` files go in
   the same migration, applied with the workers stopped (v1 accepts a brief job-processing
   pause during deploys, so there is no mixed-version window to split them across).

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
  - a financial-visibility flag on a membership, checked in `authorize()`, for budget data;
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

### v2 — ERP implementations
v1 is built for software projects (§1); v2 adds what ERP implementations need. Each item needs
its own design pass.

**ERP modules** (design pending). Proposed order, adjustable once priorities are clear:
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

**Workspace and steering views:**
- **PMO dashboard** at workspace level. The first version rolls up **published status reports**
  only, with no live drill-down. Needs comparable portfolio fields on every project (client,
  PM, go-live date, current phase, health) and project templates, so phase and workstream names
  line up across clients.
- **Steering committee landing page:** RAG status, change requests and decisions awaiting their
  sign-off (§6.2), and escalated risks and issues. RAID items need an escalation level.
- **Resourcing and resource management:** workspace-level internal teams (e.g. Finance,
  Operations, Data Migration) that project workstreams link to, giving cross-client views of
  each team's work and load. Needs its own design pass (v2+).
- **Workstream members**, for a client core team's "my team's work" view (a department maps to
  a workstream; today a workstream has only a lead). Decided in the ERP design pass.

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
