# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

In order of priority (owner, 2026-11-13):

1. **Today: the owner, as project lead** on their own software projects: planning requirements,
   tasks, phases and milestones, running approvals and test cycles, and tracking progress.
2. **Next, and design must not shut it out: a firm running projects for client organizations.**
   One workspace (the firm) holds client orgs and their projects (`docs/screen-inventory.md`,
   "Tenancy & access model"). The software-project personas are:
   - **Project lead** (project admin): planning, sprints, phases, milestones, approvals, progress.
   - **Engineer** (member): works tasks, links PRs, records test results; often also a reviewer
     (a per-task assignment, not a separate persona).
   - **Stakeholder / manager** (viewer): progress and reports.
   - **Administrators** at each level: system, workspace owner/admin, org owner/admin (client
     admins manage their own users), project admin.
3. **v2: ERP implementations run from a finance/operations point of view**: implementation PM,
   functional integrators, client project lead and core team, general users, and a steering
   committee that signs off change requests and decisions and gets its own simplified landing
   page (`docs/screen-inventory.md`, step 1).

## Product Purpose

A project management and reporting tool for gathering requirements, planning scope, executing,
testing, and reporting on a project, with traceability from requirement to sign-off. v1 is built
for software projects; ERP implementations come in v2. A traditional PM tool first; AI-assisted
features are a deliberate v2+ addition (`docs/design-doc.md` §1).

The name's idea: most of an iceberg, like most of a project (the hidden work, dependencies, and
risk), sits below the waterline. The tool keeps status visible above the line and the
traceability behind it available below.

## Positioning

- **One traceable chain** from requirement through its revisions and approvals, to the tasks and
  test cases that cover it, to sign-off: status above the waterline, the trail behind it below.
- **Workflow over enforcement.** Where a rule is really a team's process choice, the app makes
  the state visible (flags, warnings, badges) rather than blocking the action. Hard constraints
  are only for data integrity and security.
- **One core for software projects and ERP implementations.** Phases, workstreams, generalized
  approvals, and per-project type and modules are in v1 so the same codebase and data serve an
  ERP implementation seen from finance and operations (phases and gates, functional workstreams,
  formal sign-offs, UAT cycles, RAID, budget, data migration, cutover) without a retrofit.

## Operating Context

- Work happens inside a workspace → organization → project hierarchy with explicit project
  membership and inherited admin access; internal staff see only the orgs and projects they are
  assigned to.
- My work is the home page; projects hold requirements (a tree with a side panel), tasks,
  phases, milestones, workstreams, test cases and runs, approvals, comments, tags, links,
  dependencies, and an activity log. Lists have saved filters and CSV export.
- Non-human actors produce state the screens must show: GitHub (webhooks, PR status, delivery
  failures), the background worker (failed jobs), and later CI.
- The reader's guide lives in `docs/user-guide/` and is shown in the app's Documentation page.

## Capabilities and Constraints

- Monorepo: FastAPI backend, Vue 3 + TypeScript frontend (PrimeVue styled mode with the
  project's own preset, Tailwind CSS v4, SVAR for board, grid, and Gantt), docs in `docs/`.
- **The docs are the source of truth** (`CLAUDE.md`): `docs/design-doc.md` for product
  decisions, `docs/screen-inventory.md` for screens and layout patterns, and
  `docs/ui-design-guide.md` for every UI rule by ID (tokens, shell, forms, feedback, tables).
  Design work that would differ from them goes to the owner as a design change first.
- Project type (`software` / `erp` / `general`) selects display labels; modules are switched on
  per project and turning one off hides, never deletes, data. A module that hasn't shipped can't
  be enabled.
- Export control exists in the API but is hidden from the UI for the foreseeable future.
- v1 ships one workspace, created by the seed CLI; no UI to create more.

## Brand Commitments

- **The company's iceberg logo and the accent sampled from it are binding** (owner,
  2026-11-13): navy `#213870` in the light theme and ice blue `#87c9ee` in the dark theme, as
  recorded in `docs/ui-design-guide.md` §3.1. The exact brand hex values are still an open item
  there.
- "Waterline" is the working name, used for the repo, images, CLI, and the app's title.

## Evidence on Hand

- Real product content: the design docs and the reader's guide pages in `docs/user-guide/`
  (with light and dark screenshots in `docs/user-guide/images/`).
- No logo file is in the repository; the accent values were sampled from the logo image.
- No customers, testimonials, metrics, pricing, or case studies exist. Future work must not
  invent them.

## Product Principles

1. **Status above, trail below.** Surface where things stand at a glance; keep the
   traceability behind it one step away, never in the way.
2. **Show the state; don't block the work.** Warnings and badges over hard stops, except for
   integrity and security.
3. **Built for software now, ready for ERP.** Don't make a screen or term assume software-only
   when the shared core already generalizes.
4. **The docs decide.** Recorded decisions win over taste; change them through the owner.

## Accessibility & Inclusion

WCAG 2.2 Level AA on every screen (`docs/design-doc.md` §1): every drag has a single-pointer
alternative, status is never shown by color alone, targets are at least 24×24 CSS px, sticky
headers and toasts never cover focus, and password fields allow paste and password managers.
Rule-by-rule application is in `docs/ui-design-guide.md`.
