# Waterline — Screen Inventory

A systematic derivation of every screen Waterline needs, worked through one step at a time.
Screens are derived from people, journeys, and the schema, not brainstormed, so the list can
be checked for completeness.

| Step | What it produces | Status |
|---|---|---|
| 1. People | Who uses Waterline, in what role, on what kind of project | **Done** (Sept 28, 2026) |
| 2. Journeys | What each person does end to end | **Done** (Oct 26, 2026): pieces 1–8 settled |
| 3. Entities × operations | List / view / create / edit / delete / restore / link / approve for every entity: the completeness check | **Done** (Oct 26, 2026) |
| 4. Cross-cutting views | Boards, search, reports, activity: views spanning entities | **Done** (Oct 27, 2026) |
| 5. States | Empty, loading, error, permission denied, conflict, archived, module disabled, deactivated user | **Done** (Oct 27, 2026) |
| 6. Consolidate | One inventory; page vs. panel vs. dialog vs. inline; mapped to build slices | **Done** (Oct 27, 2026) |
| 7. Design guide | Tokens, enum → visual mapping, components, patterns | **Done** (Oct 10, 2026): `docs/ui-design-guide.md`, the authoritative UI guide (DL-61) |

**The inventory is complete** (Oct 27, 2026; DL-157, DL-203). Step 6's consolidated table was
checked against the docs and the built screens before S2-C15 (TD-62, DC-2026-10-31), and the
screens it left without a slice were placed (DL-238, DL-239). Routes for screens not yet built
are proposals that each slice's planning confirms, and Slice 2's web rows (S2-C15 to S2-C21d)
are re-cut before they start (DL-139).

Early mockups (sprint board, requirement detail, delete-requirement dialog, test case) exist on
the "Waterline key screens" design canvas. They predate this inventory; where they differ,
step 6 governs.

## Scope

- **v1 is built for software projects.** ERP implementations come in **v2**.
- The cheap core generalizations already in the design (phases, workstreams, generalized
  approvals, project type and modules) stay in v1. ERP personas and modules are recorded here
  so v1 doesn't paint them into a corner, but their screens are designed in v2.
- **Export control is hidden from the UI for the foreseeable future** (owner decision, Oct 21,
  2026): it stays in the API, with what it needs built in Slice 2, but no screen offers it.
  Stories and dialogs below that mention export control are kept for when it returns and are
  marked *(hidden for now)*.

## Step 1 — People

### Software projects (v1)

| Persona | Project role | Main concerns |
|---|---|---|
| Project lead | admin | Planning, sprints, phases, milestones, approvals, progress |
| Engineer | member | Works tasks, links PRs, records test results. Often also a **reviewer**: reviewer is a per-task assignment, not a separate persona |
| Stakeholder / manager | viewer | Progress and reports; not needed right away, cheap to support now |

### ERP implementations (v2)

| Persona | Side | Project role | Main concerns |
|---|---|---|---|
| Implementation PM | Internal | admin | Owns the project and deliverables |
| Project admin | Internal | admin | Optional; may be folded into the PM's duties |
| Functional integrator | Internal | member | Does the implementation in one functional area (finance, operations, data migration…) |
| Client project lead | Client | admin | Client-side owner of technical details; often the client's admin; sees and does everything |
| Client core team (SMEs, functional leads, department managers) | Client | member | Tasks assigned to them and their team/department, requirements documentation, RAID log, reporting documents |
| General user | Client | viewer | Catch-all: views general tasks |
| Steering committee / client exec | Client | viewer + named approver | High-level reporting and tracking, key decisions, change requests, escalated risks/issues. Views and **signs off change requests and decisions**. Gets its own simplified landing page |

Business approvers and user testers are not separate personas; approvals and testing are done
by the roles above.

### Administration

| Persona | Scope |
|---|---|
| System admin | The whole instance, every workspace |
| Workspace owner/admin | The firm: internal staff, every client org and project, PMO reporting |
| Org owner/admin | One client org: its users and projects. Client admins manage their own users |
| Project admin | One project: its members, modules, settings, approval requests |

### Non-human actors

They use no screens but produce state screens must show: GitHub (webhooks, PR status, delivery
failures), the background worker (failed jobs), CI (later).

## Tenancy & access model (decided Sept 28, 2026)

```
Workspace (the firm: tenant boundary)
├── Internal staff: workspace members
├── PMO dashboard: rolls up every org and project (v2)
├── Teams & resource management (v2+)
├── Organization: Client A
│   ├── Client users: members of this org
│   ├── Project
│   └── Project
└── Organization: Client B
    └── Project
```

- **Workspace** — the firm. The schema supports many; v1 deploys with one, created by the seed
  CLI, with no UI to create more.
- **Organization** — normally one per client. A software-only setup is a workspace with one
  internal org.
- **Internal staff** hold a workspace membership and work across client orgs. **Client users**
  normally belong to one org only (typical, not enforced).
- **Internal staff see only the orgs and projects they are assigned to.** Workspace
  owners/admins see everything.
- **Project roles move into v1** (`project_membership`): different projects have different
  teams and needs. Project access is explicit membership; org, workspace, and system admins get
  admin access by inheritance (on an export-controlled project, management only: content needs
  an explicit membership, design-doc §3.1). This replaces the `project.is_restricted` flag. (DL-2)
- **Client admins manage their own org's users; internal admins can add client users too.**
  Account actions (deactivate, reactivate, reset password, sign out everywhere) follow rank
  (design-doc §4, "Account actions follow rank"): an org admin can't take them against a user
  who also belongs to the workspace or another org. The rank rule covers only account actions;
  org admins can still remove such a user from their org.
- **Approvals extend** to change requests and decisions when the RAID module ships (v2), so the
  steering committee can sign off on them. Project admins create and cancel approval requests.

## Step 2 — Journeys (done Oct 26, 2026)

Worked through one piece at a time. Each piece lists the stories a person needs to be able to
complete; the walk-through of each story (step → screen) happens once the list is settled.
Every entity that can be created can also be updated: workspace, organization, user, project.

| Piece | Status |
|---|---|
| 1. Setup and administration | Settled |
| 2. Projects | Settled |
| 3. Project lead: requirements and planning | Settled |
| 4. Project lead: tracking and testing | Settled |
| 5. Engineer (often also reviewer) | Settled |
| 6. Approver | Settled (Oct 26, 2026) |
| 7. Stakeholder | Settled (Oct 26, 2026) |
| 8. Everyone (account, finding things, collaborating) | Settled (Oct 26, 2026) |

### Piece 1 — Setup and administration

**Workspace (the firm)**
- First run: seed CLI, first sign-in, forced password change, then an empty workspace that
  needs its first org.
- Update workspace details.
- Add internal staff, change their workspace role, remove them (with the offer to remove their
  project memberships).
- Assign an internal staff member to an org or project (they see nothing until assigned).
- See everything at once: all orgs, all projects, all users.
- Review the audit log, filtered by person, event, and date.
- See who holds system admin (granting and revoking stay CLI-only).

**Organization**
- Create an org (name, slug checked against the reserved list).
- Update org details.
- Manage org-level settings: GitHub installations and the tag vocabulary.
- Hit the last-owner safeguard, with an explanation.

**User accounts**
- Create a user; if the email already exists, the existing user is added instead.
- Hand over the temporary password: the admin is shown a generated password, can replace it
  with their own, and passes it along. The user must change it at first sign-in.
- Update a user's details, **including email** (admin-only; reverses the earlier "no email
  change in v1" decision; self-service email change stays out until email sending exists).
- Reset a password for someone who is locked out.
- Deactivate and reactivate a user.
- Get blocked with an explanation: an org admin tries to deactivate, reset, or edit someone who
  also belongs to the workspace or another org.

**Composite stories**
- Offboard someone: deactivate, find their open tasks for reassignment, see their pending
  approvals pass to each request's requester (or the request flagged, if the requester is no
  longer a project admin; design-doc §6.2), clean up memberships.
- Change someone's job: an engineer becomes a project lead, or moves to another project.
- Access review: for a project, everyone with access and why, including inherited admins; for
  a person, everything they can reach.

**Operations**
- System admins see an indicator when background jobs or GitHub webhook deliveries have
  failed, leading to a read-only screen listing the failures. Retrying stays in the CLI.

### Piece 2 — Projects

**Create and find**
- Create a project: name, key (with the "can't change later" warning), type, modules with
  recommendations (**modules whose features haven't shipped can't be selected**, Oct 21, 2026),
  and optionally its **restriction** level (None / Internal / Confidential) and categories.
  *(Hidden for now: marking it export-controlled, which asks for a confirmation; design-doc
  §3.1.)* **Any org member can create a project and becomes its admin.**
- Browse the projects I can access, across orgs, and switch between them.
- Open a project and land on its home page.

**Configure**
- Update project details: name, description, type, **status**, **lead**. The key shows as
  fixed, with the reason.
- Turn modules on or off, with the "this hides data" warning. Unshipped modules can't be
  turned on.
- Set restriction level and categories.
- *(Hidden for now.)* Mark a project export-controlled (inherited admins keep management access
  but lose content access unless they are explicit members); remove the mark (explicit project
  admins only).

**Team**
- Add a person from the org or internal staff and set their project role.
- Change a role, or remove someone. Their pending approvals pass to each request's requester,
  or the request is flagged if the requester is no longer a project admin (design-doc §6.2);
  their open tasks are highlighted.
- See who has access and why, including inherited admins.
- Hand the project over to a new lead.

**Structure**
- Set up workstreams: create, assign a lead, reorder, archive.
- Set up phases: dates, baseline, order.
- Set up milestones, gates, and releases.
- Re-baseline dates after a slip.
- Connect a GitHub repo, see whether its webhooks are arriving, disconnect it.

**Close out**
- Archive a project (read-only, hidden from default lists) and unarchive it. **Archive only;
  projects are never deleted.** Archiving cancels the project's pending approval requests
  (Piece 6).
- Browse archived projects.
- See who changed project settings, and when.

### Piece 3 — Project lead: requirements and planning

**Requirements**
- Create a requirement, top-level or as a child, starting from the Acceptance Criteria
  template (the template varies by project type: Software/General vs. ERP).
- Reorganize the tree: reorder among siblings, or move a requirement to another parent.
- Edit and save a new revision with a change note.
- Read the requirement's **History** and **Revisions** tabs, and **compare any two
  revisions** (computed in the browser on the raw markdown, line then word).
- Request approval from named approvers, watch who has decided, and cancel a request.
- Approve by hand as a project admin.
- See "changed since approval" and request re-approval.
- Reject or defer a requirement, and bring a deferred one back. (Any status can move to any
  other, except that only a project admin moves a requirement into approved by hand.)
- Set priority, workstream, tags, and restriction.
- Delete a requirement (with the detach-or-delete choices) and restore it from **Trash**
  (Slice 2).
- Spot the gaps: requirements with no tasks, no test cases, or failing tests.

**Planning**
- Break a requirement into several tasks from the requirement's page.
- Create a task with no requirement: a bug, chore, or spike.
- Triage new tasks: type, priority, severity, assignee, reviewer, estimate.
- Order the backlog.
- Set dependencies and see what is blocked by what.
- Create a sprint (dates, goal), fill it from the backlog, and start it.
- Change a sprint mid-flight: add or pull a task.
- Complete a sprint. **If tasks are unfinished, Waterline asks whether to move them to the
  next sprint or back to the backlog.**
- Place tasks in a phase or milestone, and plan a release.

### Piece 4 — Project lead: tracking and testing

**Tracking**
- Watch the board: what is in progress, in review, and blocked.
- See why something is blocked and what it is holding up.
- Find work that needs attention (overdue, unassigned, untouched for a while, assigned to a
  deactivated user) **using the filter bar**; a dedicated view is v2.
- Check sprint progress against its goal: counts and progress bars in v1; burndown is v2.
- Check milestone and phase progress, including slippage against the baseline.
- Re-plan: move tasks between sprints or milestones, or cancel them.
- Request sign-off on a gate, then mark a milestone or release as done.
- Read the project's activity feed (Slice 3).
- Open the project home page and see the headline numbers: blocked work, untested
  requirements, pending approvals.

**Testing**
- Maintain the test case library: create, edit, link to requirements, tag, delete, restore.
- See coverage: each requirement, its test cases, and their latest results.
- Plan a test run: name it, tie it to a phase, milestone, or sprint, and pick its cases by
  requirement, type, tag, or workstream.
- **Assign cases in a run to people (optional; a case may have no assignee).**
- Execute a run: step through the cases, recording each result and what actually happened.
- Turn a failure into a bug task, linked back to the result.
- Retest after a fix: **"re-run failed cases" creates a new run containing just the
  failures**, so the record of what failed and when is kept.
- Watch a run's progress: passed, failed, blocked, not run.
- Complete a run and request exit sign-off.
- Read one test case's history across runs.

### Piece 5 — Engineer (often also reviewer)

**Start of day**
- Land on **My work**, the home page for everyone: the projects I can open, plus my
  outstanding work across projects (tasks, reviews I owe, approvals I owe, test cases assigned
  to me). Until notifications arrive in v1.5, this is how people learn something is waiting.
- Pick up the next task, from my list or by taking an unassigned one from the sprint.

**Working a task**
- Read a task: description, the requirement it serves and its acceptance criteria, subtasks,
  dependencies, comments, history.
- Start it, and break it into subtasks that are checked off along the way.
- Link my work: name a branch with the task ID so it links automatically, or paste a PR or
  commit link; see the PR's status on the task. **A "copy branch name" button** gives a
  ready-made name (for example `wtl-ta-45-sign-in-throttling`).
- Record the estimate and the time taken.
- Mark it blocked and say what it is waiting on; unblock it.
- Link it to another task (blocks, or related to).
- Hand it off: set a reviewer and move it to review.
- Give a task back or reassign it.
- Hit an edit conflict because someone else saved first, and reload.

**Reviewing**
- See what is waiting for my review.
- Read the task, open its PR, then mark it done or send it back. **Sending back prompts for a
  comment but does not require one.**

**Testing**
- Write a test case and link it to the requirements it verifies.
- Record a quick ad-hoc result.
- Execute the cases assigned to me in a planned run. A result can be corrected while its run
  is still in progress.
- File a bug from a failure, fix it, and see it retested.

**Bugs**
- Report a bug with a severity, linked to the requirement or test result it came from.

### Piece 6 — Approver

Any project role can be a named approver, viewers included (design-doc §6.2).

**Finding what's waiting**
- See the **approvals I owe on My work**, across projects: what the item is, who asked, and
  how long it has waited.
- Open the item from there, including as a viewer with read-only access.
- Requests on archived projects never appear: archiving cancels them (below).

**Reviewing before deciding**
- Requirement: read the exact revision the request is bound to. For a re-approval, see the
  diff against the last approved revision. If the requirement was edited after the request was
  made, a notice says so; the decision still applies to the bound revision, and the requester
  can cancel and re-request.
- Gate: see what the milestone holds and its linked test runs.
- Test run: see the results summary, the failures, and the bug tasks filed from them.
- **See every task and subtask associated with the item**, with their statuses: a
  requirement's tasks, a gate's milestone tasks, a test run's bug tasks.
- **Read the item's comments**, as well as the other approvers, their decisions so far, and
  their decision comments.

**Deciding**
- Approve, with an optional comment.
- Reject. **Waterline prompts for a comment; it isn't required, but submitting without one
  asks the approver to confirm.** A rejection ends the whole request.
- **A decision is final: there is no "unapprove."** Instead, an approved item can be
  re-opened (below).
- See my past decisions.

**Edge cases the approver runs into**
- The request was cancelled, or made moot by a hand approval, while I was reviewing it. I'm
  told so and can't decide.
- I'm the requester's replacement for an approver who lost access, so the request shows up on
  My work as mine.

**Requester (project admin) follow-ups not already in Pieces 3 and 4**
- After a rejection, start a new round pre-filled with the same approvers.
- **Re-open an approved item**: start a new approval round on it. The item's status doesn't
  change while the round is pending. If the round is approved, the approval is updated as
  usual; if it is rejected, the item moves off approved (a requirement back to draft, a gate's
  milestone back to in progress). Re-approving an "Approved · modified" requirement isn't a
  re-open: a rejection leaves it "Approved · modified". A released milestone can't be re-opened
  (DL-195).
- Handle a flagged request ("an approver no longer has access") by cancelling it or
  re-requesting.
- After unarchiving a project, re-request any approvals that archiving cancelled.

### Piece 7 — Stakeholder

A project viewer: read-only, except for comments and any approvals they are named on.

**Getting oriented**
- Land on My work and see the projects I can view, each with its status, lead, and current
  phase or milestone. **My work is the cross-project view in v1**; a portfolio view comes when
  it outgrows that page (the PMO dashboard, v2).
- Open a project's home page and see the headline numbers: overall progress, blocked work,
  untested requirements, pending approvals.

**Following progress**
- Check milestone and phase progress, including slippage against the baseline.
- Check sprint progress against its goal.
- See what's in an upcoming release and how much of it is done.
- Look at the board and task lists read-only, using the filter bar.
- Read the project's activity feed to see what changed since I last looked (Slice 3). Until
  notifications arrive in v1.5, the feed is how changes are followed.

**Requirements and quality**
- Browse the requirement tree with each requirement's approval status, including
  "Approved · modified".
- See coverage: which requirements have tests, and whether those tests are passing.
- Read the latest test run's results and the bugs filed from them.

**Taking part**
- Comment on tasks and requirements.
- Approve or reject when named as an approver (Piece 6).
- Never see controls for actions I can't take: they're hidden, not disabled.

**Sharing what I see**
- **Export the current list to CSV** (v1): whatever the filter bar is showing, for tasks,
  requirements, test cases, and test results.
- Read published status reports (v1.5, below).

### Piece 8 — Everyone (account, finding things, collaborating)

Checked against the screens built in Slice 1 (`s2` branch, Oct 26, 2026). *Built* marks what
already exists; everything else is still to build.

**Account**
- Sign in. A deep link returns me to the page I opened; a wrong email and a wrong password get
  the same message; a deactivated account gets its own message. *Built.*
- When my session ends, sign in again ("Your session ended") and return to the page I was on.
  *Built.*
- Sign out from the user menu. If the server can't be reached, I stay signed in. *Built.*
- Change a temporary password at first sign-in: nothing else opens until it's done, and Sign
  out is offered. *Built.*
- Change my password on its own page; it signs me out everywhere else. The requirements are
  listed under the field and ticked as I type. *Built.*
- Edit my profile: name and username. Email is shown read-only. *Built.*
- Choose System, Light, or Dark under Appearance, remembered in this browser. *Built.*
- See **No access** when I'm signed in but belong to nothing; Account settings and Sign out
  still work. *Built.*
- **See my active sessions and sign out of the others** (v1), in Account settings.
- Sign in with GitHub, and link or unlink my GitHub account (Slice 7).

**Getting around**
- The header (org switcher), the sidebar (My work, the project selector with a filter past
  eight projects), the skip link, and the Menu button on narrow screens. *Built.*
- My work's Projects section: key, org, my access, status. *Built.* Its work sections (tasks,
  reviews, approvals, test cases) come with their slices.
- **Favorite projects on My work** (v1): star a project to keep it at the top. Favoriting
  items (requirements, tasks, test cases) is v1.5+. (Recently viewed is not needed.)
- Open any item from a shared link; if I can't see it, I get the same 404 as for an item that
  doesn't exist. Page not found links to My work and System status. *Built.*
- **System status** at `/status`, without signing in. *Built.*
- **Documentation** in the user menu (v1): opens the user guide inside the app.
- Use everything by keyboard and screen reader (WCAG 2.2 AA).

**Finding things**
- Search requirements, tasks, and test cases by text from a **search bar in the header**,
  limited to what I can see, with a results page (Slice 6).
- Type an ID such as `WTL-TA-45` to jump to the item.
- Narrow any list with the filter bar, by one field or several; the filters live in the URL,
  so a filtered list can be bookmarked or shared.
- **Save a filter-bar setup by name** (v1), such as "my open bugs", and reapply it.
- Copy a link to any item.
- Find a deleted item in Trash and restore it, if allowed (Slice 2).

**Collaborating**
- Comment on requirements, tasks, and test cases. **Edit or delete my own comments** (an
  "edited" marker shows); **project admins can delete anyone's.** Deleted comments are soft
  deleted.
- Tag items, and attach links (no file uploads in v1).
- Link items: tasks and test cases to requirements, and tasks to tasks.
- Read an item's history.
- Hit an edit conflict, see that someone else saved first, and reload.

## Step 3 — Entities × operations (done Oct 26, 2026)

Every user-facing entity in `schema-doc.md` against every operation, checked against the
journeys, the design doc's delete and restore rules (design-doc §9), and the screens built on
`s2` (Oct 26, 2026). Internal tables without screens are left out (`project_counter`;
`requirement_testcase` appears under Link; webhook deliveries under the operations screen).

**Key:** **B** built · ✓ in a journey (including the stories added below) · — not applicable

**Tenancy & people**
| Entity | List | View | Create | Edit | Remove | Restore | Link / other |
|---|---|---|---|---|---|---|---|
| Workspace | — | B settings | — (CLI) | B | — | — | |
| Staff (workspace member) | B | — | B | B role | B | — | |
| Organization | B | B overview | B | B | later (archive) | — | GitHub installations ✓ (S7) |
| Org member | B | — | B | B role | B | — | |
| User | B | B access review | B | B admin; B own profile | B deactivate | B reactivate | admin email edit B |
| Session (own) | ✓ | — | B sign-in | — | ✓ sign out others | — | admin "sign out everywhere" B |
| GitHub identity (S7) | — | — | ✓ link | — | ✓ unlink | — | |
| Project | B | B home | B | B settings | B archive | B unarchive | favorite ✓ |
| Project member | B | B access | B | B role | B | — | |
| Audit event | ✓ | — | — | — | — | — | screen before the first non-local deployment |

**Planning**
| Entity | List | View | Create | Edit | Remove | Restore | Link / other |
|---|---|---|---|---|---|---|---|
| Phase | ✓ | ✓ | ✓ | ✓ dates, baseline, order | ✓ hard delete while unreferenced | — | |
| Workstream | ✓ | — | ✓ | ✓ lead, order | ✓ archive | ✓ unarchive | |
| Milestone / gate / release | ✓ | ✓ | ✓ | ✓ re-baseline | ✓ hard delete while unreferenced; cancel | — | gate approval ✓; mark released ✓ |
| Sprint | ✓ Sprints page | ✓ summary | ✓ | ✓ goal, dates | ✓ planned only | — | start / complete ✓ |
| Requirement | ✓ tree | ✓ | ✓ | ✓ new revision | ✓ delete dialog | ✓ Trash | tasks, test cases, approval ✓; CSV ✓ |
| Requirement revision | ✓ Revisions tab | ✓ | automatic | — | — | — | compare any two ✓ |
| Task | ✓ backlog, board | ✓ | ✓ | ✓ | ✓ | ✓ Trash | requirement, dependency, PR, sprint ✓; CSV ✓ |
| Subtask | ✓ | inline | ✓ | ✓ check off, reorder | ✓ hard delete | — | |
| Task dependency | ✓ blocked by | — | ✓ | — | ✓ | — | |

**Testing & sign-off**
| Entity | List | View | Create | Edit | Remove | Restore | Link / other |
|---|---|---|---|---|---|---|---|
| Test case | ✓ library | ✓ history across runs | ✓ | ✓ | ✓ | ✓ Trash | requirements ✓; CSV ✓ |
| Test run | ✓ | ✓ progress | ✓ planned, ad-hoc | ✓ assign cases | cancel ✓ (never deleted) | — | re-run failed ✓; exit sign-off ✓ |
| Test result | ✓ in its run | ✓ | ✓ record | ✓ correct while the run is open | ✓ remove a `not_run` case from a run | — | bug from a failure ✓; CSV ✓ |
| Approval request | on its item; mine on My work | ✓ on the item | ✓ | — | cancel ✓ | re-open ✓ | |
| Approval (own row) | ✓ My work | — | — | decide ✓ | — | — | |

**Collaboration & cross-cutting**
| Entity | List | View | Create | Edit | Remove | Restore | Link / other |
|---|---|---|---|---|---|---|---|
| Comment | ✓ on its item | — | ✓ | ✓ own | ✓ own; admins any | — | |
| Tag (org vocabulary) | ✓ | — | ✓ | ✓ rename, type | ✓ | — | apply to / remove from items ✓ |
| Link attachment | ✓ | — | ✓ | — (remove and re-add) | ✓ | — | |
| Activity log | ✓ project feed (S3); item history | — | automatic | — | — | — | |
| Saved filter | ✓ | — | ✓ | ✓ rename | ✓ | — | personal only |
| Repository mapping (S7) | ✓ | ✓ webhook health | ✓ | — | ✓ disconnect | — | |
| Task GitHub link (S7) | ✓ on the task | ✓ PR status | ✓ automatic or pasted | — | ✓ | — | |

**Stories added to the journeys by this step**
- Piece 2 (structure): delete a phase or milestone while nothing references it; cancel a gate
  that has any approval history instead; unarchive a workstream.
- Piece 3 (planning): delete a task and restore it from Trash; delete a subtask; remove a
  dependency; apply and remove tags on items.
- Piece 3 (planning): **a simple Sprints page** listing planned, active, and completed sprints;
  opening a completed sprint shows what was finished and what rolled over (reconstructed from
  the activity log until sprint snapshots exist, schema-doc). **Delete a sprint only while it
  is planned**; its tasks return to the backlog.
- Piece 4 (testing): remove a planned (`not_run`) case from a run.
- Piece 5: remove a GitHub link from a task; remove a link attachment (editing one is remove
  and re-add).
- Piece 8: rename and delete my saved filters. **Saved filters are personal in v1**; sharing
  them is v2.

**Decided not to add:** a project-level approvals page. The project home's pending-approvals
number and the filter bar on each list cover it in v1.

## Step 4 — Cross-cutting views (done Oct 27, 2026)

Views that combine several entities. Each is a page unless noted; step 6 settles page vs.
panel vs. dialog.

| View | Combines | Slice |
|---|---|---|
| **My work** | favorite projects, my projects, my tasks, reviews I owe, approvals I owe, test cases assigned to me | Projects section built (S1); other sections with their slices (2, 3, 5) |
| **Project home** | status, lead, current phase, milestone, and sprint; headline numbers: blocked work, untested requirements, pending approvals | Shell built (S1); numbers fill in with their slices |
| **Org overview** | the org's projects with status and lead; archived projects below | Built (S1) |
| **Board** | tasks by status; filter by sprint, assignee, workstream | 3 |
| **Backlog** | ranked tasks not in a sprint | 3 |
| **Sprints page and sprint summary** | sprints, their tasks, what finished and what rolled over | 4 |
| **Requirement tree with coverage** | requirements with **coverage columns**: task count and progress, test-case count, latest result, approval state. **This is the traceability view in v1**; a separate requirement × test case matrix is not built | 2 (tree, approval), 3 (tasks), 5 (tests) |
| **Timeline (dated table)** | phases and milestones with baseline vs. current dates and **slippage**; the Gantt chart replaces the visual in v2 | 3 (a basic page holding phases), 4 (milestones, slippage) |
| **Releases** | no separate page in v1: the board and task list **filter by milestone**, and each milestone shows a **progress bar** | 4 |
| **Test run execution** | a run's cases, results, assignees, and the bugs filed from failures | 5 |
| **Search results** | requirements, tasks, and test cases, from the header search bar | 6 |
| **Activity feed; item history** | the project's changes; one item's changes | 3 (feed), 2 (item history) |
| **Trash** | deleted requirements, tasks, and test cases | 2 (tasks 3, test cases 5) |
| **Access review** | per project and per person | Built (S1) |
| **Audit log** | admin and security events | Before the first non-local deployment |
| **Operations screen** | failed background jobs and webhook deliveries | 7 |
| **Status report** | a finished period's summary | v1.5 |

No other regularly used views are needed in v1. Per-person workload and sprint load views are
v2 ("Noted for later steps").

## Step 5 — States (done Oct 27, 2026)

Most states are rules in `docs/ui-design-guide.md`; this step checks each against the screens
and fills the gaps.

**Already decided**
| State | Rule |
|---|---|
| Loading | Skeleton after about 300 ms, `aria-busy` (UI-FBK-11, UI-FBK-12) |
| Empty | "Nothing yet" (primary action only if allowed) vs. "No results match" with Clear filters (UI-FBK-8) |
| A region fails to load | `ErrorState` with Try again (UI-FBK-15) |
| A form fails (403, 409, network, 500) | Dismissible alert at the top of the form, typed values kept (UI-FRM-7) |
| Not found, or can't see | Identical 404 inside the shell (UI-FBK-14) |
| Admin page, not an admin | 403 naming who to ask (UI-FBK-14) |
| Edit conflict | 409 alert with Reload (UI-FRM-7) |
| Archived project | Non-dismissible read-only banner (UI-FBK-6); actions disabled with the reason beside them (UI-FBK-4) |
| Deactivated user | "Deactivated" badge after their name (UI-FBK-6); narrowed below |
| Session ended | Sign in again, then back to the page (built) |
| Signed in, belongs to nothing | No access page (built) |
| Restricted item or project | Restriction badge in the header and on items (UI-FBK-6) |

**Decided in this step**
- **A turned-off module's page** (a bookmark to Sprints after the module was turned off): an
  explanatory page inside the project, not a 404: *"The Sprints module is turned off for this
  project. Contact your administrator for questions."* A module that hasn't shipped has no page
  at all.
- **A link to a deleted item** (from a comment, history, or a bookmark): the **standard 404**
  for everyone. Trash is the way back.
- **Archived projects on My work:** none of an archived project's items appear on My work
  (tasks, reviews, test cases; approvals are already cancelled by archiving). They stay
  visible inside the project.
- **Deactivated users** are **left out of every picker** (assignee, reviewer, approver, lead,
  member pickers) and **left out of the member and user lists** (org members, project members,
  workspace staff and users), which show active people only. **Admins of that scope** get a
  **"Show deactivated"** filter on those lists, which is how they find someone to reactivate;
  no one else sees deactivated people listed. Their existing work keeps their name with the
  "Deactivated" badge (an item they're assigned, comments, history), and items still assigned
  to them are highlighted for reassignment.
- **A new project's Get started checklist** on the project home page: three items, each
  linking to where it's done and ticked automatically from the project's data. The checklist
  disappears when all three are done, and a project admin can hide it sooner. It's shown only
  to the project's admins (owner, Oct 27, 2026). The ticks are loose: they show the step has
  been started, not that it's complete.
  1. **Invite your team:** add members and set up their roles. Ticked once the project has a
     member besides its creator.
  2. **Compile your plan:** add milestones and phases, with dates. Ticked once the project has
     a phase or milestone with a date; the item stays hidden until phases and milestones ship.
  3. **Start your project:** add a requirement, a test case, and a task. (Each part appears
     once its feature ships: requirements in Slice 2, tasks in Slice 3, test cases in Slice 5.)

  GitHub is not part of the default setup.

## Step 6 — Consolidated inventory (done Oct 27, 2026)

Every v1 screen, with its type, route, and slice. **Built** = on the `s2` branch as of Oct 26,
2026. Routes for screens not yet built are proposals that each slice's planning confirms.
`…/:key` below stands for `/:orgSlug/projects/:key`.

### Layout patterns (decided Oct 27, 2026)

- **Opening an item from a list or the board** (requirement, task, test case, test run):
  a **side panel** over the list, so the list keeps its place, with **Open full page**. The
  panel has its own URL (the list's route with the item open, e.g. `?open=TA-45`), so Back
  closes it and the address can be shared. A direct link to an item, and **Copy link**, use
  the **full-page** route.
- **Creating an item:** a **dialog** with the essential fields, which the user can **expand
  into a full page** (typed values kept). After creating, the user lands on the new item to
  fill in the rest.
- **Project navigation** stays **flat** in v1, in this order (a turned-off or unshipped
  module's entry is left out): Home, Requirements, Tasks (Board and Backlog as tabs),
  Sprints, Timeline, Test cases, Test runs, Activity, Members, Settings, and **Trash at the
  bottom** of the list (changes DL-146, which linked Trash from the requirements page header
  instead of the project pages). Grouping the navigation is a later change if it gets
  crowded.

### Shell, account, and errors

| Screen | Type | Route | Slice | Status |
|---|---|---|---|---|
| Sign in | page (auth layout) | `/sign-in` | 1 | Built |
| Change temporary password | page (auth layout) | `/account/change-password` | 1 | Built |
| Account settings (profile, appearance) | page | `/account` | 1 | Built |
| Change password | page | `/account/password` | 1 | Built |
| Active sessions, sign out others | section of Account settings | `/account` | 2 (S2-C21b, DL-238) | — |
| GitHub account link / unlink | section of Account settings | `/account` | 7 | — |
| Saved filters (rename, delete) | section of Account settings, plus the filter bar's menu | `/account` | 3 (DL-239) | — |
| No access | page | `/account/no-access` | 1 | Built |
| My work | page | `/` | 1, sections in 2, 3, 5 | Projects built |
| Favorite projects | section of My work; star on project rows | `/` | 2 (S2-C21c, DL-238) | — |
| Documentation (user guide) | page, from the user menu | `/docs` | 2 (S2-C21d, DL-238) | — |
| Search results | page, from the header search bar | `/search` | 6 | — |
| System status | page, no sign-in | `/status` | 0 | Built |
| Page not found (404) / Forbidden (403) | page in the shell | any | 1 | Built |
| Turned-off module | page in the project | the module's route | 4, with Sprints (DL-239) | — |

### Workspace administration

| Screen | Type | Route | Slice | Status |
|---|---|---|---|---|
| Staff (add, role, account actions, remove; "Show deactivated" for admins) | page + dialogs | `/workspace/staff` | 1 | Built (deactivated filter in S2-C21a, DL-238) |
| Organizations (list, create) | page + dialog | `/workspace/orgs` | 1 | Built |
| Users (account actions, edit details, email; "Show deactivated" for admins) | page + dialogs | `/workspace/users` | 1 | Built (deactivated filter in S2-C21a, DL-238) |
| Per-person access review | page | `/workspace/users/:userId/access` | 1 | Built |
| Workspace settings | page | `/workspace/settings` | 1 | Built |
| Audit log | page | `/workspace/audit` | 7, before the first non-local deployment (DL-239) | — |
| Operations (failed jobs, webhook deliveries) + indicator | page; indicator in the header | `/workspace/operations` | 7 | — |

### Organization

| Screen | Type | Route | Slice | Status |
|---|---|---|---|---|
| Org overview (projects, archived below) | page | `/:orgSlug/overview` | 1 | Built |
| Org members ("Show deactivated" for admins) | page + dialogs | `/:orgSlug/members` | 1 | Built (deactivated filter in S2-C21a, DL-238) |
| Org settings (details, tag vocabulary, GitHub installations) | page | `/:orgSlug/settings` | 1; tags 6; GitHub 7 | Details built |
| Org projects list; create project | page + dialog | `/:orgSlug/projects` | 1 | Built |

### Project

| Screen | Type | Route | Slice | Status |
|---|---|---|---|---|
| Project home (headline numbers, Get started checklist) | page | `…/:key` | 1; numbers with their slices; checklist 3 (DL-239) | Shell built |
| Members (add, role, remove; "Show deactivated" for admins) | page + dialogs | `…/:key/members` | 1 | Built (deactivated filter in S2-C21a, DL-238) |
| Project access review | page | `…/:key/access` | 1 | Built |
| Project settings (details, modules, restriction, archive) | page | `…/:key/settings` | 1 | Built |
| Workstreams | section of Settings (or its own tab) | `…/:key/settings` | 3 | — |
| Phases; milestones, gates, releases | section of Timeline | `…/:key/timeline` | 3 (phases), 4 | — |
| Repositories (connect, webhook health, disconnect) | section of Settings | `…/:key/settings` | 7 | — |
| Activity feed | page | `…/:key/activity` | 3 | — |
| Trash | page (bottom of the project nav) | `…/:key/trash` | 2 | — |

### Requirements and approvals

| Screen | Type | Route | Slice | Status |
|---|---|---|---|---|
| Requirement tree with coverage columns | page | `…/:key/requirements` | 2 (coverage 3, 5) | — |
| Requirement detail (History, Revisions tabs; approval) | side panel / full page | `…/:key/requirements/:number` | 2 | — |
| Create requirement | dialog, expandable to full page | `…/:key/requirements/new` | 2 | — |
| Revision compare | inline in the Revisions tab | — | 2 | — |
| Delete requirement (detach, promote, delete) | dialog | — | 2 | — |
| Request approval (approver picker); cancel; re-open | dialogs | — | 2 | — |
| Decide (approve, reject with comment prompt) | panel on the item | — | 2 | — |
| Approve by hand | confirm dialog | — | 2 | — |

### Tasks, sprints, and timeline

| Screen | Type | Route | Slice | Status |
|---|---|---|---|---|
| Board | page (tab of Tasks) | `…/:key/tasks/board` | 3 | — |
| Backlog | page (tab of Tasks) | `…/:key/tasks/backlog` | 3 | — |
| Task detail (subtasks, dependencies, links, PRs, comments, history) | side panel / full page | `…/:key/tasks/:number` | 3 (comments 6, PRs 7) | — |
| Create task | dialog, expandable to full page | `…/:key/tasks/new` | 3 | — |
| Send back from review (optional comment) | dialog | — | 3 (prompt 6) | — |
| Sprints page and sprint summary | page | `…/:key/sprints`, `…/:key/sprints/:id` | 4 | — |
| Create / edit sprint; complete sprint (where unfinished tasks go) | dialogs | — | 4 | — |
| Timeline (phases and milestones, baseline vs. current, slippage) | page | `…/:key/timeline` | 3 (basic, phases), 4 (milestones, slippage) | — |

### Testing

| Screen | Type | Route | Slice | Status |
|---|---|---|---|---|
| Test case library | page | `…/:key/test-cases` | 5 | — |
| Test case detail (history across runs) | side panel / full page | `…/:key/test-cases/:number` | 5 | — |
| Create test case | dialog, expandable to full page | `…/:key/test-cases/new` | 5 | — |
| Test runs list | page | `…/:key/test-runs` | 5 | — |
| Plan a run (pick cases, assign) | dialog, expandable to full page | `…/:key/test-runs/new` | 5 | — |
| Run execution (record results, file a bug) | side panel / full page | `…/:key/test-runs/:id` | 5 | — |
| Re-run failed cases; complete run; exit sign-off | dialogs | — | 5 | — |
| Ad-hoc result | dialog from a test case | — | 5 | — |

### Shared pieces (used across screens)

Filter bar with saved filters and **Export CSV**; comment thread (edit, delete, "edited");
tags; link attachments; item history; restriction badge; status badges; skeletons, empty and
error states; confirm dialog; the export-control confirmation dialogs (API-made projects only).

## Design changes from steps 2 to 6 (to carry into design-doc and schema-doc)

- `project.status`: planning / active / on_hold / completed / cancelled. New projects start in
  planning. Informational only: it blocks nothing and is separate from archiving.
- `project.lead_id` (nullable user): must be a project member; defaults to the first admin (the creator by default). If the
  lead is removed from the project, the field clears and the project is flagged as having no
  lead. A label for "who to ask", not a permission.
- Any org member can create a project; its first admin (the creator by default) becomes project admin.
- Admins (only) can edit a user's email, under the same scope rule as deactivate and reset;
  recorded as an audit event. Users cannot change their own email in v1.
- Temporary passwords are generated, shown once to the admin, and replaceable by the admin.
- Read-only system-admin screen for failed jobs and failed webhook deliveries, plus an
  indicator.
- Access-review views (per project and per person). On an export-controlled project the
  project view separates management access from content access (design-doc §3.1).
- Update operations for workspace, organization, user, and project details.
- Completing a sprint with unfinished tasks prompts for where they go (next sprint or backlog).
- Any two requirement revisions can be compared, not only approved versus current.
- Cases in a test run can be assigned to a person ahead of execution (optional): a nullable
  assignee on the run's result row.
- "Re-run failed cases" creates a new test run from a run's failures; a retest never
  overwrites the earlier result. A result can be corrected while its run is in progress.
- **My work** is the home page after sign-in: the user's projects plus their outstanding
  tasks, reviews, approvals, and assigned test cases across projects. It leaves out content
  of export-controlled projects where the user has no explicit membership (design-doc §3.1).
- Tasks offer a "copy branch name" action built from the task ID and title.
- Sending a task back from review prompts for an optional comment.
- **(Piece 6, Oct 26, 2026) Archiving a project cancels all its pending approval requests**,
  each logged on the request (`status`, design-doc §10); after unarchiving, a project admin
  re-requests. This replaces the design-doc §6.2 rule that keeps requests pending and flagged
  in an archived project (approver replacement there no longer has pending rows to act on).
- **(Piece 6)** Rejecting prompts for an optional comment and asks for confirmation if it is
  left empty.
- **(Piece 6)** Approval decisions are final (no un-approve). A project admin can **re-open**
  an approved requirement or gate by starting a new request on it; its status is unchanged
  while the request is pending. **A rejected re-open round moves the item off approved**
  (requirement → draft; gate milestone → in progress). This is an exception to design-doc
  §6.2's "a rejected request changes nothing on the entity", which still holds for first
  rounds. Re-approving an "Approved · modified" requirement isn't a re-open, and a released
  milestone can't be re-opened (owner, Oct 27, 2026). *Open (decided by Slice 5): what a rejected
  re-open round does to a completed test run's sign-off.*
- **(Piece 6)** The approver's review view shows the item's associated tasks and subtasks and
  its comments (comments ship in Slice 6).
- **(Piece 7, Oct 26, 2026) CSV export of the current list** in v1: the list's filters and
  columns as shown, for tasks, requirements, test cases, and test results. Bulk export of a
  whole project stays v2.
- **(Piece 8, Oct 26, 2026)** A self-service **session list** in Account settings: see my active
  sessions and sign out of the others (until now, "sign out everywhere" was admin-only).
- **(Piece 8)** **Saved filters** in v1: a named filter-bar setup per user, per list.
- **(Piece 8)** **Favorite projects** on My work in v1 (per user); favoriting items is v1.5+.
- **(Piece 8)** Slice 6 search gets a **site-wide search bar** in the header and a results page.
- **(Piece 8)** **Comments:** authors edit and soft-delete their own, with an "edited" marker;
  project admins can delete anyone's.
- **(Piece 8)** **Documentation** entry in the user menu, rendering the user guide in the app.
- **(Step 3, Oct 26, 2026)** A **Sprints page** (Slice 4): planned, active, and completed
  sprints, and a summary of a completed one. A **planned sprint can be hard deleted** (its
  tasks return to the backlog); active and completed sprints can't (adds a row to design-doc
  §9's delete table).
- **(Step 3)** Saved filters are personal in v1; sharing is v2.
- **(Step 4, Oct 27, 2026)** Traceability is **coverage columns on the requirement tree**, not a
  separate matrix page.
- **(Step 4)** A **timeline table** of phases and milestones (baseline vs. current dates,
  slippage): a basic page holding phases in Slice 3, milestones and slippage in Slice 4 (owner,
  Oct 27, 2026); the Gantt chart stays v2.
- **(Step 4)** Releases have no page of their own in v1: filter by milestone, plus a progress
  bar on each milestone.
- **(Step 5, Oct 27, 2026)** A turned-off module's page explains that it's off ("Contact your
  administrator for questions") instead of a 404.
- **(Step 5)** My work leaves out every item of an archived project.
- **(Step 5)** Deactivated users are left out of all pickers and of the member and user lists;
  admins see them with a "Show deactivated" filter (**changes built Slice 1 lists**, which mix
  them in with a badge). Their existing work keeps their name with the badge.
- **(Step 5)** A three-item **Get started checklist** on a new project's home page (items
  above), ticked from the project's data, hidden when complete or by a project admin; needs a
  per-project "checklist hidden" flag.
- **(Step 6, Oct 27, 2026)** Items open from lists and the board in a **side panel** with its
  own URL and **Open full page**; direct links use the full page.
- **(Step 6)** Create dialogs can **expand into a full page**, keeping typed values.
- **(Step 6)** Project navigation stays flat in v1; **Trash moves to the bottom of the project
  navigation** (changes DL-146's link from the requirements page header).
- **(Oct 21, 2026, carried in from Slice 2 planning)** "Classification" is renamed
  "Restriction" app-wide, levels None / Internal / Confidential (the Restricted level is
  removed); export control hidden from the UI but kept in the API; unshipped modules can't be
  selected in the UI or the API; Trash and the requirement History/Revisions tabs ship in
  Slice 2; the project activity feed moves to Slice 3; requirement statuses have no transition
  table; acceptance-criteria templates vary by project type.

## Noted for later steps

- **Steering committee landing page** (v2): RAG status, change requests and decisions awaiting
  their sign-off, escalated risks and issues. RAID items will need an escalation level. Leaves
  out export-controlled content for anyone without an explicit membership (design-doc §3.1, §16).
- **PMO dashboard** (v2, workspace level): the first version rolls up **published status
  reports** only, no live drill-down. Needs comparable portfolio fields on every project
  (client, PM, go-live date, current phase, health) and project templates so phase and
  workstream names line up across clients. Leaves out export-controlled content for anyone
  without an explicit membership (design-doc §3.1, §16).
- **Resourcing and resource management** is an important part of workspace management:
  workspace-level internal teams (Finance, Operations, Data Migration) that project workstreams
  link to, giving cross-client views of each team's work and load. Needs its own design pass
  (v2+).
- **"My team's work"** for client core teams: a department maps to a workstream; workstreams
  may need members (currently only a lead). Decide in the ERP design pass.
- **Loading states (step 5; decided Oct 5, 2026): skeleton loaders, not spinners.** While a
  page or panel loads, it shows a skeleton: an outline of the content's layout (blocks where
  the headings, rows, and cards will be).
  - The skeleton appears only if loading takes more than about 300 ms, so fast loads don't
    flash (DL-63).
  - The loading region carries `aria-busy="true"`.
  - Any shimmer animation is off under `prefers-reduced-motion`.
  - Actions such as saving a form show a pending state on the control itself, not a skeleton.

  The first skeletons are built in Slice 1 (build plan, Checkpoint 14a).
- **Design guide (step 7; done as a draft, `docs/ui-design-guide.md`):** the styling approach
  (PrimeVue plus Tailwind, one token set; SVAR for the board and editable grids); the brand
  accent from the logo; the skeleton-loader rules above; WCAG 2.2 AA (design-doc §1): never
  color alone for status, RAG, or badges (always text or an icon too), controls at least 24×24
  CSS pixels, sticky headers and toasts never covering the focused element, a single-pointer
  alternative to every drag, and password fields that allow paste and password managers; and
  bulk selection (UI-TBL-6 to UI-TBL-8).
- **Data restriction** (design-doc §3.1; DL-134): a badge in the project header and on items
  showing the level (None, Internal, Confidential) and categories as text, never color alone
  (DL-137); the export-control confirmation dialogs, which the UI reaches only on a project made
  export-controlled through the API (adding a member to it), since the UI no longer offers
  export control (DL-133).
- **Markdown** (Oct 21, 2026): rendered in the browser (no raw HTML, no remote images); a plain
  textarea with a preview tab; limits of 200 characters for titles and 20,000 for
  descriptions; requirement-ID auto-links in Slice 3, @mentions later.
- **Status reports** (simplified version targeted for v1.5; full version by v2 with the PMO
  dashboard and ERP): a published status report **summarizes a finished period** (a sprint,
  phase, or iteration). The PMO dashboard's first version rolls these up.
- **Export to a slide deck or document** (v1.5 candidate, v1 if cheap): a stakeholder-ready
  summary of a view or period.
- **Project templates** (v2): create a project from another project's structure.
- **Import and export** (v2): bulk import of requirements and tasks; export of a project's
  data at close-out.
- **Bulk edit** of tasks (v2+): select several and set sprint, assignee, or priority at once.
- **Creating a linked follow-up task from inside a task** (later). Linking existing tasks is
  in v1.
- **Needs-attention view** (v2): one list of overdue, unassigned, stale, and orphaned work.
  In v1 the filter bar covers this.
- **Comparing two test runs** to see what regressed (later).
- **Sprint load views** (v2): estimate totals per sprint and per person.
- **Archiving an organization** (later): for v1, archiving its projects is enough.
- **Email notification of failed jobs and webhooks** (later, once email sending exists).
- **Shared saved filters** (v2).
- **Approval delegation** (v2): an approver hands their pending approvals to someone else
  while away.
