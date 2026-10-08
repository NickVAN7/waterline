# Waterline — Testing Strategy

Companion to `design-doc.md`, `schema-doc.md`, and `build-plan.md`. How the application is
tested, what each kind of test is for, and the gates every change passes.

## Principles

- **Test against the real thing.** Integration and API tests run against a real Postgres, not
  mocks or SQLite. The database enforces much of the design (constraints, partial indexes,
  CHECKs, transactions), so tests must exercise it.
- **Every checkpoint ships its tests.** No code lands without the tests that prove it; no step
  starts while anything is red.
- **Every test must be able to fail.** A test exists to catch a specific bug. Test-first (for
  `rules/` and `authz/`, by `spec-test-writer`) and the sabotage check (everywhere else) prove each test can fail;
  mutation testing measures it. A test no plausible bug would break is fixed or removed.
- **Deterministic.** Fake data uses a fixed seed; tests never depend on each other or on run
  order; a failure reproduces the same way every time.
- **Strictest where mistakes are most expensive.** Authorization and business rules are held to
  100% coverage and written test-first.

## Test layers

| Layer | What it tests | Database | Tools | Location |
|---|---|---|---|---|
| Unit | `rules/`, `authz/`, pure helpers (key validation, rank math, serialization) | No | pytest, Hypothesis | `backend/tests/unit/` |
| Integration | Repositories and services: queries, access scoping, soft delete, locking, numbering, `log_change()`, cross-area calls | Real Postgres | pytest (anyio), polyfactory | `backend/tests/integration/` |
| API | Endpoints over HTTP: status codes, request/response shapes, auth and cookies, error format, 404-not-403 | Real Postgres | httpx `AsyncClient` against the app, polyfactory | `backend/tests/api/` |
| Frontend unit/component | Composables, stores, components, route guards | No (API mocked at the client boundary) | Vitest, Vue Test Utils | `frontend/src/**/*.spec.ts` |
| End-to-end | Critical user flows through the browser against the full stack | Real Postgres (seeded) | Playwright (Chromium only in v1) | `frontend/e2e/` |

- **End-to-end tests start in Slice 1** (sign-in and project creation) and cover each slice's
  critical flows, not every screen. Most behavior is proven at the cheaper layers. CI seeds
  the stack with the non-interactive `wl seed` before running them.
- Frontend component tests mock only the API client, using the generated types, so mocks can't
  drift from the real API shapes.

## Test data: polyfactory + Faker

- **Factories create real rows** in the test database with realistic fake values. They are not
  mocks.
- **polyfactory** with async SQLAlchemy persistence (`create_async`, `create_batch_async`);
  Faker underneath. One factory per model, in `backend/tests/factories/`, named after the model
  (`TaskFactory`, `ProjectFactory`).
- The same library generates **API request bodies** from the Pydantic schemas for API tests.
- **Fixed seed:** Faker and polyfactory are reseeded from a fixed constant before every test,
  so each test's generated data is the same whether it runs alone, in the full suite, or in any
  order, and a failure reproduces exactly when the test is rerun on its own.
- **Explicit over implicit:** a test sets any value it depends on (`TaskFactory(status=...)`);
  everything else is generated. Factories build valid defaults, including required parents
  (a task factory creates its project and org unless given one).
- Factories go through the model layer directly, not services, so tests can set up states the
  services would refuse (e.g. data from before a rule existed).

## Database isolation

- Each test runs inside an outer transaction on a single connection; the app's session joins it
  with `join_transaction_mode="create_savepoint"`. Everything rolls back at the end, so tests
  never see each other's data.
- The test database is migrated once per session with Alembic (not `create_all`), so tests run
  against the real migrated schema.
- **Exception — concurrency tests** need separate connections and real commits (parallel
  transactions, or a background worker processing a job); they use the `concurrency` fixture,
  whose sessions really commit, and are marked `@pytest.mark.concurrency("<table>", ...)`;
  the named tables are truncated afterwards, pass or fail.

## Specialized tests

- **Property-based (Hypothesis):** for logic with a large input space.
  - Rank (fractional indexing): any sequence of inserts and moves preserves the intended order;
    generated keys always sort between their neighbors.
  - Numbering: any interleaving of allocations yields unique, increasing numbers.
  - Task transition rules: every (from, to, role, relationship) combination matches the table
    in design-doc §5.
  - Project key, slug (including the reserved list), username, and password policy
    validation.
  - Hypothesis uses a fixed database of examples in CI (`derandomize` in CI profile) so runs are
    reproducible.
- **Concurrency:** truly parallel transactions for number allocation, optimistic locking
  (second save gets 409), the one-active-sprint rule, and approval completion.
- **Approvals** (Slice 2 for requirements, Slices 4–5 for gates and test runs):
  - completion moves a requirement to `approved`, a gate to `approved`, and a test run to
    `completed`; a rejection changes nothing on the entity;
  - requests log `created` and every status change, including a cancellation caused by
    deleting a requirement, by a project admin approving the requirement by hand, or by
    cancelling a test run;
  - manual requirement approval (design-doc §5): a project admin (including inherited) moving
    a requirement into `approved` sets `approved_revision_id` to the current revision,
    `approved_by` to that admin, and `approved_at`, and cancels a pending request; members get
    403; moving out of `approved` keeps `approved_revision_id`; `status` and
    `approved_revision_id` are logged;
  - eligibility (design-doc §6.2): a viewer can be named; someone without project access is
    rejected with 404 (on an export-controlled project, an inherited admin without an explicit
    membership too);
  - replacement of an approver who loses the access needed to decide, once for each path
    (project membership removed directly, with an org removal, and with a workspace removal;
    the org or workspace membership or role that gave inherited admin removed or changed;
    `revoke-system-admin`; the project marked export-controlled while the approver has no
    explicit membership, and an explicit membership removed on an export-controlled project;
    deactivation): the row becomes `replaced` and the requester gets a new pending row; no new
    row when the requester is already named; the row stays pending and the request is flagged
    when the requester no longer holds project admin; decided rows are never replaced;
    `replaced` rows don't count toward the policy; the change is logged (`approver_id`, old and
    new user IDs, `changed_by` the actor, null from the CLI);
  - no replacement in an archived project, on each path that still takes access away there
    (removal from the org or workspace with their projects; an org or workspace role change or
    removal; `revoke-system-admin`; deactivation): the access is removed, the approver's row
    stays pending, and the request is flagged; removing a project member directly is still
    denied there;
  - a replacement that leaves every counted row approved completes the request (`approved_by`
    the counted approver with the latest `decided_at`; the `status` change logged; the
    entity's `on_approved` effect applied);
  - a gate with any approval request can't be deleted; `approved` is refused on non-gate
    milestones.
- **Docs consistency** (`backend/tests/unit/docs/`, no database): the docs agree with the code
  and each other. Models vs. schema doc (tables, columns, enum values); exactly one feature-map
  owner per table; the tech-debt log's format, references, and deadlines; the decision log's
  format and references; every `audit-allowlist.toml` entry names an open tech-debt entry; the
  developer guide's status line vs. `git log`; design-doc § references; the agents and skills listed vs. those in
  `.claude/`. Parsers are strict: a doc that loses the structure they expect fails the test
  instead of passing by finding nothing. The column check runs per column: a documented
  column whose Notes cell starts with `Added in Slice <n>.` (schema-doc conventions) is
  reported as **skipped** (`added in Slice <n> (schema-doc)`) until slice `<n>` is finished
  (its last checkpoint, or any later slice's, has a `checkpoint(<ID>):` commit), and required
  like any other column from then on; a malformed marker is a `DocsStructureError`. Judgment calls
  (contradictions in prose, superseded rules) are the `docs-consistency` agent's job.
- **Accessibility** (WCAG 2.2 AA, design-doc §1; from Slice 1, Checkpoint 14):
  - automated checks with axe-core in component tests (`vitest-axe`) and end-to-end tests
    (`@axe-core/playwright`), failing on any violation;
  - a manual keyboard and screen-reader pass on each slice's new screens at slice
    verification, since automated checks find only part of the problems.
- **Migrations** (`tests/integration/test_migrations.py`, each on a scratch database):
  - Every migration upgrades from an empty database to head.
  - Every migration downgrades one step and upgrades again (round-trip).
  - Autogenerate against the migrated database reports no drift between models and migrations.
- **Security (a named category, `@pytest.mark.security`):**
  - The full `authorize()` matrix: every action × role, plus fail-closed for unknown actions.
    Roles span three levels (design-doc §5): project viewer, member, and admin; org member,
    admin, and owner; workspace member, admin, and owner; plus system admin and users with no
    access. Inherited project admin (org and workspace owners/admins, system admins) is tested
    on its own rows, and so is its absence for org and workspace members.
  - Project creation (design-doc §5, "Org roles"): allowed to org members, admins, and owners (and
    so to workspace owners/admins and system admins); denied to users whose only link to the org is
    a project membership (staff or client), to workspace members with no role in the org, and (404)
    to users of another org. The first admin (the creator, or someone an org owner/admin names) gets
    a `project_membership` with role admin and becomes the lead; naming another first admin
    (`project.assign_first_admin`) is allowed to org owners/admins, including inherited, and denied
    (403) to a plain org member. The org entries in `/me` list `project.create` and
    `project.assign_first_admin` exactly where this matrix allows them. Editing the project's
    description, status, and lead is a project-admin action.
  - Personal actions (design-doc §5): rows for each, with every admin level (system admin
    included) and every project role denied, the relationship rule allowing it only for a user
    with content access to the project, and the relationship without that access denied.
  - Classification (design-doc §3.1, Slice 1): removing `export_controlled`, and on an
    export-controlled project lowering the level or removing any category, is refused for an
    inherited admin and allowed for an explicit project admin; every member-add path (picker,
    email-first add, creating a user for the project), marking a project export-controlled,
    and creating one export-controlled require the confirmation (422 without it);
    classification changes record their audit event.
  - The export-control gate (design-doc §5, Slice 2 onward): on an export-controlled project,
    inherited admins without an explicit membership get 404 for every content action, read or
    mutation, and are allowed management actions; explicit members are allowed.
  - Effective classification (Hypothesis property): never lower than the project's level, and
    its categories are always a superset of the project's.
  - Access to a project, org, or workspace the user can't see returns 404, never 403 or data;
    list endpoints return only the user's accessible projects and orgs.
  - Account actions (deactivate, reactivate, reset password, sign out everywhere, and an admin
    changing another user's email, name, or username; the email change and the admin password reset
    refuse the actor's own account, and the email change ends the target's sessions) follow the rank
    rule (design-doc §4), tested on both sides of each boundary: same rank allowed, higher rank or a
    membership outside the actor's scope denied, and a user with no memberships denied to org
    admins.
  - Project membership: adding by user ID someone outside the project org's members and the
    workspace's staff returns 404 (the email path follows design-doc §4); removing a membership ends access on the user's next request.
  - Workspace pages return 404 to everyone but workspace owners/admins and system admins.
  - Access review (design-doc §5): the per-project view only for project admins (including
    inherited); the per-person view for workspace owners/admins and system admins, for org
    owners/admins only within their rank scope (the full rank rule: an org admin is denied a
    person who also belongs to another org or to a project outside it), and for the user
    themselves; everyone else 404.
  - My work (design-doc §11) shows only the user's accessible projects, never an archived
    one, and leaves out export-controlled content without an explicit membership; a section
    whose query fails is returned as unavailable while the others still return.
  - Adding by email reveals at most whether an account exists, never its org or workspace;
    an existing account from another org is added to the project's org and the project only
    after confirmation.
  - Only a project admin moves a gate into or out of `approved`, or a requirement into
    `approved`, by hand; members are denied.
  - An org-slug redirect happens only for a project the user can see.
  - Cookie attributes, token replacement at sign-in and password change, non-JSON bodies
    rejected (415 `unsupported_media_type`; `application/json; charset=utf-8` and a bodyless
    mutation are allowed).
  - No API `GET` changes state (session bookkeeping aside).
  - The `Origin` check (design-doc §4) on each mutating method: allowed when host and port
    match (`Host: x` with `https://x` and with `http://x`; `Host: x:443` with `https://x`;
    `Host: x:8000` with `http://x:8000`; `Host: X` with `https://x`, since case is ignored);
    403 `origin_rejected` for a different host, a different port (`Host: x:8000` with
    `https://x`), a missing `Origin`, `Origin: null`, a non-`http(s)` `Origin` (e.g.
    `file://x`), an unparseable `Origin`, and a missing `Host`, including for a request with
    no session or with `must_change_password` set (the check runs first). Each exempt
    endpoint (from Slice 7) is reachable without `Origin` and still rejects a request that
    fails its own authentication.
  - Disabled-module endpoints return 404.
  - The API test client uses an `https://` base URL (a shared fixture): httpx won't send the
    `Secure` session cookie over `http://`, which would make a signed-in test silently
    unauthenticated.
  - Sign-in with an unknown email runs the dummy-hash verification (asserted by call, not by
    measuring time, which would be flaky).
  - Every Slice 1 admin action records its audit event.

## Coverage gates

| Scope | Minimum |
|---|---|
| Backend overall | 90% line + branch |
| `backend/app/authz/`, `backend/app/rules/` | 100% line + branch, and no surviving mutants |
| Frontend | 80% line (composables, stores, and guards held to 90%) |
| Developer CLI (`tools/cli/`) | 100% line + branch |

Coverage gates fail CI, and plain `pytest` (the backend's 100% gate is a hook in
`tests/conftest.py`, not a separate step). Excluding code from coverage requires a comment
saying why.

## Test-first and proving tests can fail

- **Test-first** for `rules/` and `authz/`, by the `spec-test-writer` agent (DL-11): the session
  implementing the checkpoint first writes interface stubs (signatures and types, returning one
  fixed wrong answer), then the agent writes the tests from the design doc's tables and rules
  without reading the implementation, and proves each fails against the stub's answer or its
  opposite. The session then implements until they pass. **Spec tests are protected:** the
  agent's file list, with each file's `git hash-object`, goes in the review record ("Spec
  tests"); if the implementation can't pass one, the owner decides whether the doc or the test
  is wrong, and any change they approve is listed there. `checkpoint-reviewer` compares the
  committed files with the recorded hashes, and an unlisted change is a blocker.
- **Sabotage check** everywhere else: for each behavior, make the smallest change that breaks it
  (invert a condition, remove a `log_change()` call, drop an org filter), confirm a test fails,
  and restore the code.
- **Independent sabotage spot-check:** `checkpoint-reviewer` picks two or three of the
  checkpoint's behaviors by risk, from the docs (not from the author's list), breaks each in a
  temporary copy of the repository, and records which test caught it. None failing is a major
  finding (a blocker in `rules/` or `authz/`). The author's own checks are evidence, not
  verification: nothing counts as verified because the session that did the work says so.
- Tests are written **alongside** the code: in the same checkpoint and commit.
- The `test-writer` skill (`.claude/skills/test-writer/`) is the working procedure: a behavior
  table with a source, layer, the bug each test catches, and the proof it fails; rules for
  assertions; banned patterns.

## Mutation testing

- **Tool:** mutmut (backend dev dependency). It makes small deliberate changes to the code
  (flipped comparisons, removed conditions, swapped operators) and checks that some test fails
  for each one.
- **Scope:** `backend/app/rules/` and `backend/app/authz/`, which are pure, fast to test, and
  where a missed bug is a security or business-rule defect.
- **Gate:** no surviving mutants. A survivor is killed with a new or sharper test. Only a mutant
  that cannot change behavior (an equivalent mutant) may be excluded, with `# pragma: no mutate`
  and a comment explaining why.
- **When:** from Slice 1, when those folders first contain code. Run by
  `wl backend mutate`, included in `wl check` and CI. mutmut exits 0 whatever survives, so the
  command finishes with a gate (`tests/support/mutation_gate.py`) that fails on any mutant not
  killed (survived, untested, timed out, or otherwise), and starts from a clean slate so a
  cached result can't hide a survivor.

## Workflow and gates

- **Pre-commit hooks** (local, fast): ruff format and lint, Prettier and ESLint, a check
  that no generated file is hand-edited, and gitleaks on the staged changes.
- **`wl check`** (the developer CLI; `waterline check` in full) runs everything CI runs, locally.
  CI calls the same command, so local and CI can't diverge.
- **CI (GitHub Actions)** is the full gate: lint, type checks (pyright, vue-tsc), all backend
  tests with coverage, mutation testing on `rules/` and `authz/` (from Slice 1, S1-C3),
  import-linter contracts, migration checks, frontend tests with coverage, generated-client
  freshness, end-to-end tests (from Slice 1), and the supply-chain audit (`wl audit`).
- **Supply-chain audit** (`wl audit`, part of `wl check`; DL-13): known vulnerabilities in both
  Python lockfiles and the npm lockfile, dev dependencies included, and secrets anywhere in the
  git history. Any known vulnerability fails; an advisory is ignored only through an
  `audit-allowlist.toml` entry with a reason and an open tech-debt entry whose Fix by is the
  deadline. A red audit is fixed before any checkpoint starts (`chore(deps):` commit).
- **Pull requests:** each slice works on one branch with one draft PR, and CI runs on every
  push; a checkpoint goes to the owner only with green CI, and the slice's PR merges to `main`
  (a merge commit) only with green CI (build-plan, "Pull requests"). Until branch protection is
  enabled (TD-15), that is checked by hand before merging.
- **Flaky tests are bugs:** a test that fails intermittently is fixed or quarantined with a
  tech-debt entry the same day, never retried until green.

## Test naming and structure

- Files mirror the code: `tests/integration/services/test_task.py` tests `services/task.py`.
- Test names state the behavior: `test_member_cannot_delete_approved_requirement`.
- Arrange / act / assert, one behavior per test; parametrize tables (roles, transitions) instead
  of copying tests.
