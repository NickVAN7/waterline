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
  `rules/` and `authz/`) and the sabotage check (everywhere else) prove each test can fail;
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
| End-to-end | Critical user flows through the browser against the full stack | Real Postgres (seeded) | Playwright | `frontend/e2e/` |

- **End-to-end tests start in Slice 1** (sign-in and project creation) and cover each slice's
  critical flows, not every screen. Most behavior is proven at the cheaper layers.
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
  - Project key and username validation.
  - Hypothesis uses a fixed database of examples in CI (`derandomize` in CI profile) so runs are
    reproducible.
- **Concurrency:** truly parallel transactions for number allocation, optimistic locking
  (second save gets 409), the one-active-sprint rule, and approval completion.
- **Approvals** (Slice 2 for requirements, Slices 4–5 for gates and test runs): completion
  moves a requirement to `approved`, a gate to `approved`, and a test run to `completed`; a
  rejection changes nothing on the entity; requests log `created` and every status change,
  including a cancellation caused by deleting a requirement or cancelling a test run; a gate with any approval request can't
  be deleted; `approved` is refused on non-gate milestones.
- **Docs consistency** (`backend/tests/unit/docs/`, no database): the docs agree with the code
  and each other. Models vs. schema doc (tables, columns, enum values); exactly one feature-map
  owner per table; the tech-debt log's format, references, and deadlines; the developer guide's
  status line vs. `git log`; design-doc § references; the agents and skills listed vs. those in
  `.claude/`. Parsers are strict: a doc that loses the structure they expect fails the test
  instead of passing by finding nothing. Judgment calls (contradictions in prose, superseded
  rules) are the `docs-consistency` agent's job.
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
  - Access to a project, org, or workspace the user can't see returns 404, never 403 or data;
    list endpoints return only the user's accessible projects and orgs.
  - Account actions (deactivate, reactivate, reset password, sign out everywhere) follow the rank rule
    (design-doc §4), tested on both sides of each boundary: same rank allowed, higher rank or
    a membership outside the actor's scope denied, and a user with no memberships denied to
    org admins.
  - Project membership: adding by user ID someone outside the project org's members and the
    workspace's staff returns 404 (the email path follows design-doc §4); removing a membership ends access on the user's next request.
  - Workspace pages return 404 to everyone but workspace owners/admins and system admins.
  - Adding by email reveals at most whether an account exists, never its org or workspace;
    an existing account from another org is added to the project's org and the project only
    after confirmation.
  - Only a project admin moves a gate into or out of `approved` by hand; members are denied.
  - An org-slug redirect happens only for a project the user can see.
  - Cookie attributes, token replacement at sign-in and password change, rejected
    cross-origin mutations, non-JSON bodies rejected.
  - Disabled-module endpoints return 404.

## Coverage gates

| Scope | Minimum |
|---|---|
| Backend overall | 90% line + branch |
| `backend/app/authz/`, `backend/app/rules/` | 100% line + branch, and no surviving mutants |
| Frontend | 80% line (composables, stores, and guards held to 90%) |
| Developer CLI (`tools/cli/`) | 100% line + branch |

Coverage gates fail CI. Excluding code from coverage requires a comment saying why.

## Test-first and proving tests can fail

- **Test-first (TDD)** for `rules/` and `authz/`: the test is written from the design doc's
  table or rule before the code, and must fail for the right reason before the code is written.
- **Sabotage check** everywhere else: for each behavior, make the smallest change that breaks it
  (invert a condition, remove a `log_change()` call, drop an org filter), confirm a test fails,
  and restore the code.
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
  `wl backend mutate`, included in `wl check` and CI.

## Workflow and gates

- **Pre-commit hooks** (local, fast): ruff format and lint, Prettier and ESLint, and a check
  that no generated file is hand-edited.
- **`wl check`** (the developer CLI; `waterline check` in full) runs everything CI runs, locally.
  CI calls the same command, so local and CI can't diverge.
- **CI (GitHub Actions)** is the full gate: lint, type checks (pyright, vue-tsc), all backend
  tests with coverage, mutation testing on `rules/` and `authz/`, import-linter contracts, migration checks, frontend tests with coverage,
  generated-client freshness, and end-to-end tests (from Slice 1).
- **Branch protection:** nothing merges to `main` without green CI.
- **Flaky tests are bugs:** a test that fails intermittently is fixed or quarantined with a
  tech-debt entry the same day, never retried until green.

## Test naming and structure

- Files mirror the code: `tests/integration/services/test_task.py` tests `services/task.py`.
- Test names state the behavior: `test_member_cannot_delete_approved_requirement`.
- Arrange / act / assert, one behavior per test; parametrize tables (roles, transitions) instead
  of copying tests.
