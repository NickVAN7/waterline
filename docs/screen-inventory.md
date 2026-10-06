# Waterline — Screen Inventory

A systematic derivation of every screen Waterline needs, worked through one step at a time.
Screens are derived from people, journeys, and the schema, not brainstormed, so the list can
be checked for completeness.

| Step | What it produces | Status |
|---|---|---|
| 1. People | Who uses Waterline, in what role, on what kind of project | **Done** (Sept 28, 2026) |
| 2. Journeys | What each person does end to end | Next |
| 3. Entities × operations | List / view / create / edit / delete / restore / link / approve for every entity: the completeness check | |
| 4. Cross-cutting views | Boards, search, reports, activity: views spanning entities | |
| 5. States | Empty, loading, error, permission denied, conflict, archived, module disabled, deactivated user | Loading decided (Oct 5, 2026; "Noted for later steps") |
| 6. Consolidate | One inventory; page vs. panel vs. dialog vs. inline; mapped to build slices | |
| 7. Design guide | Tokens, enum → visual mapping, components, patterns (written last) | Notes recorded ("Noted for later steps") |

Early mockups (sprint board, requirement detail, delete-requirement dialog, test case) exist on
the "Waterline key screens" design canvas. They predate this inventory and will be revisited in
step 6.

## Scope

- **v1 is built for software projects.** ERP implementations come in **v2**.
- The cheap core generalizations already in the design (phases, workstreams, generalized
  approvals, project type and modules) stay in v1. ERP personas and modules are recorded here
  so v1 doesn't paint them into a corner, but their screens are designed in v2.

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
  an explicit membership, design-doc §3.1). This replaces the `project.is_restricted` flag.
- **Client admins manage their own org's users; internal admins can add client users too.**
  Account actions (deactivate, reactivate, reset password, sign out everywhere) follow rank
  (design-doc §4, "Account actions follow rank"): an org admin can't take them against a user
  who also belongs to the workspace or another org. The rank rule covers only account actions;
  org admins can still remove such a user from their org.
- **Approvals extend** to change requests and decisions when the RAID module ships (v2), so the
  steering committee can sign off on them. Project admins create and cancel approval requests.

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
  - The skeleton appears only if loading takes more than about 200 ms, so fast loads don't
    flash.
  - The loading region carries `aria-busy="true"`.
  - Any shimmer animation is off under `prefers-reduced-motion`.
  - Actions such as saving a form show a pending state on the control itself, not a skeleton.

  The first skeletons are built in Slice 1 (build plan, Checkpoint 14).
- **Design guide (step 7):** the skeleton-loader rules above; WCAG 2.2 AA (design-doc §1):
  never color alone for status, RAG, or badges (always text or an icon too), controls at least
  24×24 CSS pixels, sticky headers and toasts never covering the focused element, a
  single-pointer alternative to every drag, and password fields that allow paste and password
  managers.
- **Data classification** (design-doc §3.1): a banner on project pages and a badge on items
  showing the level and categories as text, never color alone; the export-control
  confirmation dialogs (adding a member to an export-controlled project, and marking a project
  export-controlled, listing its explicit members).
