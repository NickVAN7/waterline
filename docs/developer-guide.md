# Waterline — Developer Guide

How to set up a workstation, run the project, and add to it. Kept current at every checkpoint;
if a step here is wrong, fixing it is part of the work. The *why* behind the rules lives in
`design-doc.md` and `build-plan.md`; this guide is the *how*.

> **Status:** S2-C14 (My work: approvals) built; next is S2-C15 (history: `docs/reviews/`).

## 1. Workstation setup

### Prerequisites

| Tool | Version | Why |
|---|---|---|
| Git | ≥ 2.31 | Source control |
| Docker + Compose v2 | Docker ≥ 20.10, Compose ≥ 2.24.4 (`wl e2e`'s override uses `!reset` and `!override`), daemon running | The local stack: Postgres, the API, the worker, and the web dev server |
| uv | ≥ 0.12 | Python versions, dependencies, and running everything; `uv audit` (`wl audit`) |
| Python | 3.14 | The backend (`uv` installs it: `uv python install 3.14`) |
| Node | 22.x, ≥ 22.18 (with npm) | The frontend's tools (tests, lint, types, client generation) run on the host |
| GitHub CLI (`gh`) | any recent, signed in (`gh auth login`) | The pull-request workflow (section 10): opening PRs and checking CI. Not checked by `wl doctor` |

On Windows, work inside WSL 2 with Docker Desktop's WSL integration enabled, and keep the clone
on the Linux filesystem (not under `/mnt/c`).

### First-time setup

Clone the repository, then work from its root:

```bash
git clone https://github.com/NickVAN7/waterline.git && cd waterline
uv sync --all-packages           # root env: the `wl` CLI, its test/lint tools, pre-commit
uv run wl doctor                 # check the toolchain; fix anything marked ✗ (the pre-commit
                                 # warning clears after `pre-commit install` below)
uv sync --directory backend      # backend env (backend/.venv)
npm ci --prefix frontend         # frontend tools (frontend/node_modules). Its
                                 # vulnerability count includes allowlisted advisories: `wl
                                 # audit` is the gate; don't run `npm audit fix`
(cd frontend && npx playwright install chromium)    # the end-to-end tests' browser
(cd frontend && sudo env "PATH=$PATH" npx playwright install-deps chromium)
                                 # its system libraries, once per machine (apt; `env PATH`
                                 # because sudo resets PATH and won't find an npx installed by
                                 # fnm or nvm); skip it if they're there (see Troubleshooting)
uv run pre-commit install        # git hooks: ruff, Prettier, ESLint, generated files
cp .env.example .env             # local settings (never committed); edit if needed, and
                                 # set VITE_PRIMEUI_LICENSE (below)
uv run wl up                     # build and start the stack; applies migrations
uv run wl check                  # the commit gate; should be green on a fresh clone
                                 # (`wl check --full` is what CI runs, section 10)
```

Then open <http://localhost:5173>: it sends you to sign in. Build the demo data first ("Demo
data" in section 5) to have someone to sign in as; <http://localhost:5173/status> shows whether
the API and database are up without signing in. Without a browser, `curl
http://localhost:8000/api/health` answers `{"status":"ok","database":"ok"}`.

**The PrimeUI license key** (DL-135): PrimeVue 5 needs the owner's Community License key, or every
page shows an "Invalid PrimeUI License" notice and `wl e2e` (so `wl check --full`) fails on it.
Ask the owner for the key and put it in `.env` as `VITE_PRIMEUI_LICENSE` (never committed; CI has
it as the repository secret of the same name). Vite builds it into the app, so `wl up` after
changing it; it ships in the browser bundle, which is expected.

Nothing is installed on the workstation beyond the tools above: Postgres, the API, the worker,
and the Vite dev server run in Docker. Tests and the other `wl` tools run on the host and reach
Postgres on `localhost:${POSTGRES_PORT}`.

The dev containers run as you, not root (TD-11): `wl` passes your user and group IDs to the
images (`HOST_UID`, `HOST_GID`), so anything they write into the mounted source is yours, and
`wl up` creates `frontend/node_modules` before Docker would make that mount point as root.

`wl doctor` exits non-zero if any required tool is missing or too old, and warns (without
failing) if the pre-commit hooks aren't installed.

## 2. Repository layout

```
backend/        FastAPI app (its own uv project: backend/pyproject.toml, backend/uv.lock)
frontend/       Vue 3 + TypeScript (Vite); its own npm project (package.json, package-lock.json)
docs/           design, schema, build plan, testing strategy, screen inventory, UI design
                guide (ui-design-guide.md, with reference copies in ui/), these guides,
                tech-debt log, decision log, reviews/ (s<n>/: one record per checkpoint;
                design-changes/: one per design change), spikes/
tools/cli/      the developer CLI (`waterline` / `wl`), a member of the root uv workspace
pyproject.toml  root uv workspace: makes `wl` and pre-commit runnable from the repo root
docker-compose.yml   the local stack: postgres, migrate, api, worker, web (section 5)
.github/workflows/ci.yml   CI: `wl check --full` on every push to main and every pull request (section 10)
docker/postgres/initdb/   first-start scripts for the postgres container (test database)
.env.example    local settings template; copy to .env (gitignored)
.claude/        Claude Code setup: skills (checkpoint, test-writer, migration, new-area,
                design-change, vue-screen), agents (checkpoint-reviewer,
                security-reviewer, fresh-clone-verifier, user-guide-verifier,
                docs-consistency, spec-test-writer, repo-auditor, ui-reviewer,
                simplicity-auditor),
                hooks (see section 11)
```

There are **three Python environments**, deliberately separate:

- `.venv/` (root): the `wl` CLI, its test/lint tools, and pre-commit. Never deployed.
- `backend/.venv/`: the app and its dev tools. Its lockfile is `backend/uv.lock`.
- The backend's dependencies never mix with the CLI's (build-plan, "Developer CLI").

## 3. The developer CLI (`wl`)

Run from anywhere in the repo as `uv run wl <command>` (or `wl <command>` with the root venv
activated). `waterline` is the same program. Every command accepts `--dry-run`, which prints the
underlying commands instead of running them, and stops at the first failing step.

| Command | Does |
|---|---|
| `wl doctor` | Toolchain check: Git, Docker (daemon, Compose), uv, Python 3.14, Node 22, npm, pre-commit hooks (found via `git rev-parse`, so worktrees and `core.hooksPath` work) |
| `wl check` | The gate before every commit (DL-99): lockfiles up to date, generated client fresh, lint, format check, types, import rules, tests, coverage gates — backend, then frontend, then CLI — and mutation testing when anything it depends on changed since its last green run (the backend's `app/`, `tests/`, `pyproject.toml`, or `uv.lock`; the hash is kept in `backend/mutants/inputs.sha256`), saying so when it skips it. `--full` is everything CI runs: mutation testing whatever changed, then `wl audit`, then `wl e2e` |
| `wl e2e [args]` | The Playwright end-to-end tests on their own stack: the Compose project `waterline-e2e` (`docker-compose.e2e.yml`: no published database or API port, the web server on `127.0.0.1:5174`, `DEMO_SEED_ENABLED=true`), cleared of anything an earlier run left, built, seeded with `seed --demo`, tested in the `light` and `dark` projects, and always torn down with its volume. Runs beside the dev stack, but only one `wl e2e` at a time: a second run shares the project, and its first step clears the first run's stack. Extra args go to `playwright test` (e.g. `wl e2e sign-in --project light`) |
| `wl audit` | Supply-chain gates (needs the network): `uv audit` on `uv.lock` and `backend/uv.lock`, `npm audit` on `frontend/package-lock.json` (both include dev dependencies), and gitleaks over the whole git history. Fails on any known vulnerability not in `audit-allowlist.toml`, or any secret. See "Supply-chain audit" below |
| `wl lint` | Backend: ruff check, ruff format --check, pyright, import-linter. Frontend: ESLint, Prettier --check, vue-tsc. CLI and `.claude/hooks/`: ruff check, ruff format --check, pyright |
| `wl review-copy <dir> [--with-env]` | A throwaway copy of the repository as it is about to be committed: a clone, the uncommitted changes (`git diff HEAD --binary`) applied, and the untracked, non-ignored files; `.env` only with `--with-env`. The reviewers' sabotage copy and `fresh-clone-verifier`'s copy (DL-29). Never changes the repository |
| `wl test` | All tests with coverage gates |
| `wl fmt` | ruff format and safe ruff fixes (backend, CLI, and `.claude/hooks/`); Prettier and safe ESLint fixes |
| `wl backend check\|lint\|test\|fmt` | The same, backend only |
| `wl backend mutate` | Mutation testing (mutmut) over `app/rules/` and `app/authz/`, from a clean slate; fails on any mutant not killed (section 9) |
| `wl backend test <args>` | pytest with `<args>` passed through, e.g. `wl backend test -k health -x`. A filtered run skips coverage (`--no-cov`), since a subset can't meet the gate, and runs in one process (`-n 0`), so `breakpoint()` works; pass `-n auto` to spread it over workers |
| `wl frontend check\|lint\|test\|fmt` | The same, frontend only (the npm scripts in `frontend/package.json`) |
| `wl frontend test <args>` | `vitest run <args>`, e.g. `wl frontend test src/api -t network`, without the coverage gate |
| `wl gen-client` | Export `backend/openapi.json` from the code, then generate `frontend/src/api/schema.d.ts` from it. Run after any API change and commit both files |
| `wl up [args]` | `docker compose up --detach --wait --build --renew-anon-volumes`: build the images, start the stack (migrations first), and wait until it's up. Extra args go to compose (e.g. `wl up postgres`) |
| `wl down [args]` | `docker compose down`. Data survives in the named volume; `wl down -v` deletes it |
| `wl logs [service]` | `docker compose logs --follow`, for one service when named (e.g. `wl logs api`) |
| `wl migrate` | `docker compose run --rm --build migrate`: `alembic upgrade head` against the dev database, in the Compose `migrate` service (its image rebuilt first if dependencies changed) |
| `wl backend migration "<message>"` | `alembic revision --autogenerate -m "<message>"` on the host; review the generated file by hand |


**App admin commands** (`backend/app/cli.py`, run as `python -m app.cli <command>` in a one-off
container from the api service's image: `docker compose run --rm api ...`, after the migrations):

| Command | Does |
|---|---|
| `wl seed [flags]` | Create the workspace and its first system admin, who is its owner (refused once a workspace exists). Each value comes from its flag, else its environment variable, else a prompt (the password twice); with no terminal, a missing value is an error. Flags and variables: `--workspace-name` (`SEED_WORKSPACE_NAME`), `--workspace-slug` (`SEED_WORKSPACE_SLUG`), `--email` (`SEED_EMAIL`), `--username` (`SEED_USERNAME`), `--name` (`SEED_NAME`); the password has no flag, only `SEED_PASSWORD` or the prompt, since `wl` prints the command it runs. Every value is checked first (slug, username, email, and the password policy), all problems at once |
| `wl seed --demo` | Build the demo dataset instead, workspace and system admin included ("Demo data" in section 5): refused once a workspace exists, and unless `DEMO_SEED_ENABLED=true` (the `.env.example` default; off otherwise, and never on in production, since every demo account has the same public password). Takes no other values |
| `wl admin grant-system-admin <email>` | Give the account the system-admin flag (the only way to; design-doc §4) |
| `wl admin revoke-system-admin <email>` | Take it away, handing over their undecided approvals where the flag was their only access (logged with no actor); refused for the last active system admin |

The CLI is a **thin orchestrator**: the real tool configuration is in each project's
`pyproject.toml`, so `uv run pytest` in `backend/` gives the same result as `wl backend test`,
both coverage gates included (the 100% gate on `app/authz/` and `app/rules/` is a pytest hook in
`backend/tests/conftest.py`).

**Supply-chain audit.** `wl audit` first checks that it can reach the advisory databases and
fails with a clear message if it can't; there's no switch to skip it. Then:

- **Python:** `uv audit --frozen` in the root and in `backend/` (all groups, dev included; the
  command is experimental in uv, hence `--preview-features audit-command`).
- **npm:** `python -m waterline_cli.audit npm` runs `npm audit --json` in `frontend/` and fails
  on any advisory the allowlist doesn't name (npm has no ignore option).
- **Secrets:** the manual-stage pre-commit hook `gitleaks-history` scans every commit. The
  `gitleaks` pre-commit hook scans staged changes on every commit. Both use the gitleaks
  version pinned in `.pre-commit-config.yaml`; pre-commit builds it the first time (installing
  Go for that if needed, so the first run needs the network and takes a little longer).

Policy: any known vulnerability fails. To ignore an advisory (only when it can't be fixed yet),
add an entry to `audit-allowlist.toml` (`[[python]]` or `[[npm]]`, with `id`, `reason`, and
`tech_debt`) and the matching tech-debt entry, whose Fix by is the deadline; the docs
consistency tests fail if the entry isn't open or its Fix by has passed. Remove both once the
fix lands. A red audit is fixed before any checkpoint starts, with a `chore(deps):` commit on
the slice branch. A real secret is rotated at once (pushed history is never rewritten); a false
positive goes in `.gitleaksignore` (its fingerprint) with the owner's approval.

**Adding a command:** add a function returning its steps to `tools/cli/src/waterline_cli/steps.py`,
a Typer command in `main.py` that calls `run_steps(..., dry_run=dry_run)`, and a dry-run case in
`tools/cli/tests/test_commands.py`. The `--help` and `--dry-run` tests pick up new commands
automatically.

## 4. Backend architecture

Calls flow one way: **routers → services → repositories → models**. See `build-plan.md`
("Backend architecture", "Feature map") for each layer's responsibilities and
`backend/CLAUDE.md` for the rules that are easy to break.

```
backend/app/
  main.py         create_app(): settings, database, routers (all under /api)
  core/settings.py     Settings (env vars / repo-root .env), TEST_DATABASE_NAME
  core/db.py           engine, sessionmaker, get_session / SessionDep (one transaction per request)
  core/base_model.py   Base, naming convention, IdMixin, TimestampMixin, BaseModel,
                       SoftDeleteMixin, VersionMixin, check_version
  core/enums.py        enum_type (VARCHAR + CHECK enum columns)
  core/errors.py       error format: AppError and its subclasses, ErrorBody, the handlers
  core/request_guard.py   the Origin and JSON-only checks (middleware, before everything else)
  core/migration_filters.py   what Alembic autogenerate ignores (procrastinate's objects)
  core/security.py     password hashing (Argon2id, off the event loop), session tokens
  models/ schemas/ repositories/ services/ routers/   one file per aggregate in each
  routers/deps.py      shared router dependencies: SettingsDep, AuthServiceDep, SignedInUserDep,
                       AuthzContextDep, authorized()
  rules/          pure business rules, no database
  authz/          authorize(), the action registry, targets, list scoping (pure: no queries)
  audit/          log_admin_event() (Slice 1, S1-C4) and log_change() (Slice 2)
  jobs/           background jobs: app.py (jobs_app), enqueue.py, task_names.py, tasks/, worker.py
```

- Every route lives under `/api` (including the OpenAPI schema at `/api/openapi.json` and
  interactive docs at `/api/docs`), so the Vite proxy can serve the app and API from one
  origin. The docs are served only when `API_DOCS_ENABLED=true` (the `.env.example` default
  for local dev); the setting defaults to off, and stays off in production.
- `wl up` runs the API in Compose (the `api` service, uvicorn with `--reload` on the mounted
  `backend/`): <http://localhost:8000/api/health>, and the docs at
  <http://localhost:8000/api/docs>. `create_app` is a factory, so settings are read when the
  app starts, not on import. To run it on the host instead (e.g. under a debugger), stop the
  service (`docker compose stop api`) and run
  `uv run --directory backend uvicorn --factory app.main:create_app --reload`.
- **The API's schema is a committed file.** `backend/openapi.json` is exported from the code by
  `python -m app.openapi_export` (no database or `.env` needed) and is the input to the
  frontend's generated types. After any change to a route, schema, or error response, run
  `uv run wl gen-client` and commit `backend/openapi.json` and `frontend/src/api/schema.d.ts`
  with the change. `wl check` (and the pre-commit hooks) fail while either is out of date, and
  neither may be edited by hand.

### Errors

Every error response has one body: `{"code": ..., "message": ..., "details": {...}}`
(`ErrorBody` in `app/core/errors.py`). Clients branch on `code`, never on `message`.

- **Raise, don't build responses.** Services and repositories raise an `AppError` subclass;
  handlers registered in `create_app` turn it into the response. Never raise FastAPI's
  `HTTPException` or return an error `JSONResponse` from an endpoint.

  | Raise | Status | Default `code` |
  |---|---|---|
  | `NotFoundError` | 404 | `not_found` (also for entities the caller may not see: 404, not 403) |
  | `ForbiddenError` | 403 | `forbidden` |
  | `ValidationFailedError([FieldError(loc, message, type)])`, or `ValidationFailedError.on(loc, message, type)` for one field | 422 | `validation_error` (same `details.fields` shape as request validation) |
  | `ServiceUnavailableError` | 503 | `service_unavailable` |

  Pass a more specific message, `code`, or `details` where the client needs them:
  `ForbiddenError("Change your password first.", code="password_change_required")`. A new kind
  of error is a new subclass with its own status and code.
- **Handled for you:** request validation is 422 `validation_error` with
  `details.fields = [{"loc": [...], "message": ..., "type": ...}]`; an unknown route is 404
  `not_found`; a wrong method is 405 `method_not_allowed`.
- **Constraint violations** (`app/core/constraint_errors.py`): every unique constraint
  declares, in its `info`, either the field error a user gets when they trigger it,
  `info=user_error("email", "taken", "This email is already in use.")`, or `internal_only()`
  when no request should ever violate it (a random token). A mapped violation becomes 422
  `validation_error` on that field (`loc: ["body", "email"]`); an unmapped `IntegrityError` is
  a logged 500. `test_every_unique_constraint_in_the_app_declares_its_error` fails if a new
  unique constraint declares neither. CHECK and foreign-key constraints may declare one too.
  The service still checks first (a clear message, live availability checks): the constraint
  is the source of truth for a race.
- **Anything else** (an exception no handler covers) is 500 `internal_error`, "Something went
  wrong.", with empty `details`: nothing about the error reaches the client. It is logged on the
  server (logger `app.core.errors`) with its traceback. `UnhandledErrorMiddleware` does this;
  if the response had already started (a streaming response failing midway), the status can't
  change, so the exception is re-raised for the server to log.
- **Stale rows:** a stale save is 409 `stale_version` when the row was changed by someone else,
  and 404 `not_found` when it's gone: deleted, or soft-deleted since this request loaded it (a
  row already soft-deleted when loaded, e.g. one being restored, isn't gone). On a
  non-versioned table a stale row can only mean it's gone. On a versioned table SQLAlchemy
  can't tell the two apart, so `get_session` decides, in one place (`stale_row_error`): a
  `before_flush` hook records the versioned rows each flush writes (and whether each was
  soft-deleted when loaded), and after the rollback it looks them up, then raises
  `StaleRowError` (409) or `NotFoundError` (404). A `StaleDataError` raised outside a
  `SessionDep` request has no handler: it's a 500. `direct_update` returning `None` means the
  row is gone too: raise `NotFoundError`. An error whose table can't be read stays 409 (the
  conservative answer; a test using SQLAlchemy's real wording fails if the wording changes).
- Document an endpoint's error statuses with `responses=ERRORS` (`app/routers/deps.py`: 401,
  403, 404, and 422, each an `ErrorBody`).

### Security helpers

`app/core/security.py`:

- `await hash_password(password)` → an Argon2id hash for storing; `await
  verify_password(hash, password)` → `True`/`False` (a malformed hash is `False`, never an
  error). Both run in a worker thread: always await them, never call argon2 directly.
- `await verify_password_for_unknown_user(password)` → always `False`, after the same hashing
  work: sign-in calls it when the email has no account, so timing doesn't reveal which emails
  exist. `password_needs_rehash(hash)` → whether a stored hash uses older parameters (re-hash
  on a successful sign-in).
- `generate_token()` → a new session token (32 random bytes, 43 URL-safe characters) for the
  cookie; `hash_token(token)` → its SHA-256 hex digest, the only form ever stored.
- Mark tests of security behavior `@pytest.mark.security` (run just those with
  `wl backend test -m security`).

### Authentication

Sign-in, sign-out, and `/me` are in the `auth` area (`routers/auth.py`, `services/auth.py`,
`repositories/auth.py`); design-doc §4 has the rules.

- **The signed-in user:** an endpoint that needs one takes `user: SignedInUserDep`
  (`app/routers/deps.py`). It reads the `__Host-session` cookie, finds a live session (within
  its lifetime and idle timeout, its user active), brings `last_seen_at` up to date at most
  every 5 minutes, and returns the user; otherwise it raises 401 `not_authenticated`. While the
  user must change their password it raises 403 `password_change_required` instead (the forced
  change). Only `/me` and change-password take `UserPendingPasswordChangeDep`, which lets that
  user through; sign-out needs no user at all, nor `GET /api/auth/password-policy` (open to
  anyone, DL-91: the requirements, each with its `code`, which is the 422 `type` it prevents,
  a `label`, and its number, from `rules/password_policy.py`). Any other new endpoint takes `SignedInUserDep`.
- **Change password** (`POST /api/auth/change-password`, `current_password` and
  `new_password`): 422 on `current_password` (`incorrect`) or `new_password` (the password
  policy's problems, each its own `type`); on success the session keeps its row but gets a new
  token (a new cookie), the user's other sessions are deleted, `must_change_password` is cleared,
  and `password_changed` is recorded.
- **Password and identifier messages:** `password_errors()`, `identifier_error()`,
  `required_error()`, `email_error()`, and `new_user_errors()` (`app/services/user.py`) turn the
  problems into field errors (`under=` for a nested object, e.g. `("body", "new_owner")`); use
  them wherever a password, username, slug, or new account is set.
- **Accounts an admin creates** (staff, an org's first owner, org members, project members)
  go through `UserService.create_account(actor_id, workspace_id, new, organization_id=...)`:
  validated, `must_change_password` set, `user_created` recorded. Pass the org's ID when the
  account is made through that org (its members, later its projects' members), so its admins see
  the event (design-doc §10.1, "Scope"); the roster does this for org members.
- **Staff and org members share one set of rules** (`app/services/roster.py`, DL-70): the
  email-first add, the create, the owner-only rule for owner and admin roles, stepping down, the
  last-owner guard and handover, and the lock order (the person's projects first, DL-235, then
  the owners' rows; adding an owner takes that lock too, TD-25). A role change or removal also
  hands the person's pending approvals over where it took their access (design-doc §6.2):
  `ApprovalService.lock_projects` before anything else, `replace_for` after the change, as
  deactivation and `revoke-system-admin` do. The workspace and org services each describe their
  roster in a `RosterSpec` and call a `Roster`. Project members are a third roster with no owner role
  (`owner=None`, `manage_admins=None`; DL-71): it uses the list, the email-first add (whose
  `admit` hook adds the project's `outside_org` and `join_org` step, DL-78, and returns any details
for the added event, such as the export-control confirmation, DL-81), and `add_user`; the
  project service changes roles and removes members itself. Two adds of one person racing: the
  roster turns the loser's unique violation into `already_member` on the field it used (`loc`,
  DL-80). Project member changes lock the project row first, then the membership.
- **Removing a member "with their projects"** calls the handlers registered with
  `register_on_member_removed()` (`app/services/roster.py`), each given a `MemberRemoval`
  (`organization_id` is None for staff). The project area registers one
  (`ProjectService.remove_with_projects`): it removes the person's memberships on the org's (or
  workspace's) projects, archived ones included, clearing a lead, with `via` in each event. Tests
  of what the roster passes stand in for it with the `removals` fixture (`tests/api/conftest.py`).
- **Changing a project's restriction** calls the handlers registered with
  `register_on_restriction_changed()` (`app/services/project.py`), each given the project (its
  new level already set) and the actor. Each item area registers one that lifts its live rows
  stored below the project's level (`RequirementService.lift_to_project`, DL-208 to DL-210), so a
  lower lifts nothing.
- **An approval request completing or rejected** calls the handlers registered for its entity
  type with `register_on_approved()` and `register_on_rejected()` (`app/services/approval.py`),
  each given the request and the deciding user. An approvable area registers both (the
  requirement area: `RequirementService.complete_approval`, which records the approval, and
  `reject_approval`, which moves a rejected re-open round back to `draft`, DL-195); the decision
  holds the entity's lock.
- **The user check** (`GET /api/workspaces/{id}/user-check`, DL-66) answers one of `email`,
  `username`, or `name`; `suggest_username()` (`app/rules/identifiers.py`) builds the name's
  username, and `UserService.check` adds `-2`, `-3`, … while it's taken.
- **Account actions** (DL-72, DL-73) take a user loaded by `load_user` (`app/routers/deps.py`):
  an `AccountSubject` (the user, their workspace, and their memberships as the rank rule's
  `Account`, from `UserRepository.accounts`). Deactivate, reset password, and sign out everywhere
  are in `AuthService`; reactivate and profile edits in `UserService`. Record their events with
  `UserService.log_account_event`, which writes one per covering org (DL-75). An email change ends
  the user's sessions through the handler `auth` registers with `register_on_email_changed()`.
- **Projects** (`app/services/project.py`, DL-76): a key is normalized with
  `normalize_project_key` (create, the availability check, and the by-key loader `load_project`);
  a taken key is the unique constraint's 422. Update, archive, and unarchive lock the project row
  first (`ProjectRepository.lock`) and check again, so an archive committing meanwhile still
  denies an update. Modules come from `app/rules/modules.py`: the
  type's seed (`seed_modules`), its recommendations, and which modules have shipped (`_SHIPPED`;
  a module's slice adds itself there). The project list's `ListSpec` (`PROJECTS`) and row mapping
  (`item`) live in `app/services/my_work.py`, the lower layer, so the project area can share them;
  an endpoint with other query parameters besides a list's extends its query model
  (`OrgProjectQuery`), since FastAPI reads a query model only as the sole query parameter.
- **My work** (`app/services/my_work.py`): each section's query runs in a savepoint and a
  database error marks it `available: false` (the one sanctioned savepoint-and-continue).
- **Last-owner guards** count active owners (DL-74): lock the owners with `lock_owners`, then
  compare `active_owners` (both on the workspace and org repositories). A deactivation locks the
  owners of every workspace and org the user belongs to first, so it queues behind a handover
  (TD-27).
- **Updates** of an entity without `version` go through `apply_changes(session, entity,
  values)` (`app/audit/admin_event.py`, TD-57; a versioned one uses `check_version`, whose 409
  the re-read would defeat): it locks and re-reads the row (`FOR NO KEY UPDATE`), sets each value that differs, and
  flushes, so two edits at once compare in turn. Validate before it; the event records what it
  returns, `change_details(changed)`: `{"old": {...}, "new": {...}}`, the changed fields only.
- **Length limits** (DL-143) are `Field(max_length=...)` on the request schemas, from
  `app/schemas/limits.py`; a value over one is FastAPI's 422 `string_too_long` on the field.
- **`ReservedSlug`** isn't returned by any route: `create_app` adds it to the OpenAPI schema's
  components (`_add_schema_components`, `app/main.py`).
- **Error codes:** sign-in returns 401 `invalid_credentials` for an unknown email or a wrong
  password (the same body either way) and 403 `account_inactive` for a deactivated account with its
  correct password; a password over 256 characters is a 422 on `password` (`string_too_long`) before
  any hashing (DL-49), as is a `current_password` over 256 on change password (DL-52). A
  successful sign-in deletes the session the browser sent, if any (DL-53). Sign-out is always 204,
  with or without a session, and clears the cookie.
- **Middleware errors** (DL-54): besides its own responses, every `POST`, `PUT`, `PATCH`, or
  `DELETE` can return 403 `origin_rejected` (no path is exempt yet), and any request whose body
  isn't JSON can return 415 `unsupported_media_type` (`app/core/request_guard.py`). They come before
  routing, so no route declares them in the OpenAPI schema; clients branch on `code` as for any
  error.
- **Session lengths:** `SESSION_IDLE_TIMEOUT` and `SESSION_LIFETIME` in `.env` (ISO 8601
  durations such as `P7D`; defaults 7 and 30 days; Compose passes them to the backend
  services). The idle timeout must be over 5 minutes, the gap between `last_seen_at` writes;
  the app refuses to start otherwise. The test `settings` fixture pins both to the defaults;
  a test of other lengths builds its app from `settings.model_copy(update=...)`. Both are
  checked against the database clock, so tests backdate `last_seen_at` or `expires_at` with
  `func.now() - timedelta(...)`. Expired rows aren't deleted
  yet (the nightly cleanup is TD-14); they're ignored.
- **The `Origin` and JSON-only checks** run in `RequestGuardMiddleware`
  (`app/core/request_guard.py`), before routing: a `POST`, `PUT`, `PATCH`, or `DELETE` whose
  `Origin` doesn't name the request's own `Host` is 403 `origin_rejected`; then any request with
  a body that isn't `application/json` is 415 `unsupported_media_type`. `ORIGIN_EXEMPT_PATHS`
  is empty; adding a path needs the owner's approval (design-doc §4).
- **The cookie** is set with `Secure`, `HttpOnly`, `SameSite=Lax`, and `Path=/` in every
  environment. Reach the dev server at `localhost`: browsers accept a `Secure` cookie over plain
  http only there.

### Authorization

`app/authz/` decides; it never queries (mutation testing runs only database-free unit tests
against it). Design-doc §5 has the rules; the build plan's "Authorization (§5)" the actions.

- **Actions** are registered in `REGISTRY` (`app/authz/actions.py`), one `ActionSpec` each: its
  level, the lowest workspace, org, and project role that grants it, whether it's a mutation,
  `archive_exempt`, for a personal action its `relationship`, `visible` (granted to anyone
  who can see the target, e.g. `org.view` for a project member with no org role), and a targeted
  `rule(ctx, target)` checked after the roles (e.g. `user.check`: an admin role anywhere in the
  target's workspace, DL-68). Each action is marked `access`, content or management (design-doc
  §3.1; the default is content, the closed side, so every management action says so). The
  export-control gate reads it: a content action on an export-controlled project needs an
  explicit `project_membership`, whatever the user's admin level, and `ensure()` makes that
  denial a 404; a personal action needs content access too.
  `explicit_when_export_controlled` makes only the explicit project role grant it on an
  export-controlled project (`project.lower_restriction`, DL-82). Real actions
  are members of
  `Action` (exported as an OpenAPI enum). An area registers its actions in its own checkpoint
  (DL-44); an unregistered action is denied. A project-level action normally sets
  `workspace_role=ADMIN, org_role=ADMIN` (inherited project admin).
- **The context** (`AuthzContext`): the user's system-admin flag and memberships (each org's
  workspace in `org_workspaces`; each project's org, workspace, and `archived` state), loaded once
  per request (`UserRepository.authz_context`; an endpoint takes `ctx: AuthzContextDep`).
- **Targets:** `workspace_target(ws)`, `org_target(org)`, `project_target(project, entity)` (with
  the project's `archived`, `enabled_modules`, and `export_controlled`), and
  `user_target(workspace_id, user_id, account)` for a user (level `user`, DL-73), whose actions
  apply the rank rule to `rank_account(ctx)` (`app/authz/context.py`). A user is seen by
  themselves, the workspace's owners/admins and system admins, and anyone with a membership of
  theirs in scope (`in_scope`, `app/rules/account_rank.py`); otherwise a 404.
- **Checks:** `authorize(ctx, action, target)` → bool; `ensure(...)` raises 404 when the user
  can't see the target or, on an export-controlled project, its content without an explicit
  membership, and 403 when they can but may not act; `allowed_actions(ctx, target)` for a
  single-entity read; `module_enabled(target, module)`.
- **Endpoints on one entity** take `authorized(loader, action, module=...)`
  (`app/routers/deps.py`): `loader` is a dependency returning `(entity, target)` or None; the
  endpoint gets the entity only once the check passes (404 for missing or unseen, then the
  module, then 403). `hide_denial=True` makes every denial a 404 (the access review).
- **Lists** scope their query: `project_scope(ctx)` / `org_scope(ctx)` give the `Scope`, and
  `scope_clause(scope, id_column, workspace_column, org_column)` (`app/repositories/base.py`)
  the `WHERE`. A list of content across projects (My work's approvals) takes
  `content_scope(ctx)` instead, and passes `scope_clause` the row's project's
  `export_controlled=` expression (as `ProjectRepository.visible` does): an export-controlled
  project's rows are then reached only through an explicit membership.
- **Tests:** `tests/support/authz.py` has the personas, test-only actions
  (`register_test_actions(monkeypatch)`), a test-only router, and `sign_in_as`;
  `tests/support/content.py` a test-only content router (`register_content_actions`).

### Import rules (enforced)

`import-linter` checks these on every `wl lint` / `wl check`; the contracts are in
`backend/pyproject.toml` under `[tool.importlinter]`:

| Contract | Means |
|---|---|
| Layers | `routers → services → repositories → models`; a lower layer never imports a higher one, directly or indirectly |
| Routers never touch repositories or models | Routers go through a service |
| Rules are pure | `app/rules/` may not reach SQLAlchemy, psycopg, procrastinate, models, repositories, services, routers, jobs, or audit — **directly or indirectly**. Anything a rule needs (e.g. an enum) must live in a module that doesn't import SQLAlchemy |
| authz and audit sit below services | `app/authz/` and `app/audit/` never reach services or routers, directly or indirectly (services call them) |
| Only the worker imports job modules | `app.main`, routers, services, repositories, models, schemas, core, authz, audit, rules, `jobs.enqueue`, and `jobs.app` never import `app.jobs.tasks` or `app.jobs.worker`, directly or indirectly; enqueue by task name. A new top-level `app.*` module is added to this contract's list |
| Jobs never import routers | Jobs reuse services, not HTTP endpoints |
| Service layers: services call lower layers only | Each service is in a layer (`docs/build-plan.md`, "Cross-area rules"); it may import only services in lower layers, directly or through any other module (e.g. `jobs/`), never a same-layer sibling. Reach upward with a registered handler. A new service module is added to its layer in the contract |

`backend/tests/unit/test_import_contracts.py` proves each contract fails on a real violation,
so a contract can't silently stop working. If you add or change a contract, add a violation
case there — including an indirect path (A → B → forbidden) wherever indirect imports matter.

## 5. Database

### The Compose stack

| Service | Runs | Host port |
|---|---|---|
| `postgres` | Postgres 18, data in the `postgres-data` volume | `POSTGRES_PORT` (5432) |
| `migrate` | `alembic upgrade head` once, then exits | — |
| `api` | uvicorn with `--reload`, `backend/` mounted | `API_PORT` (8000) |
| `worker` | the procrastinate worker, `backend/` mounted | — |
| `web` | the Vite dev server, `frontend/` mounted; proxies `/api` to `api` | `WEB_PORT` (5173) |

- `api`, `worker`, and `migrate` share the backend image; `migrate` runs first, and `api` and
  `worker` start only once it has succeeded (the worker can't run without procrastinate's
  schema). So `wl up` always leaves a migrated database. Inside Compose they reach Postgres at
  `postgres:5432`, whatever `POSTGRES_PORT` publishes on the host.
- `wl up` rebuilds the images when their inputs changed (cached otherwise), so a dependency
  change (`uv add`, `npm install`) takes effect on the next `wl up`. It also renews the web
  container's `node_modules` volume from the image; the host's `frontend/node_modules` is a
  separate install, used by the host tools.
- The `api` reloads on code changes. The `worker` doesn't: after changing a job or a service it
  calls, restart it (`docker compose restart worker`).
- `wl logs` follows every service's logs; `wl logs api` just one.
- The backend image is named after the Compose project (`waterline-backend`). A second stack
  under another project name (`COMPOSE_PROJECT_NAME`, e.g. a fresh-clone check) gets its own
  image, containers, network, and volumes. It publishes the same host ports, though, so stop the
  main stack first (`wl down`) or change the ports in its `.env`.
- Ports are published on `127.0.0.1` only, so nothing in the stack (the dev database, with its
  public default password, included) is reachable from other machines on your network.

### Demo data

`uv run wl seed --demo` fills an empty dev database with a fixed workspace to look at in the
browser (`backend/app/demo.py`; build plan, S1-C13a). The end-to-end tests run on the same data.
To start over: `uv run wl down -v && uv run wl up && uv run wl seed --demo`. It runs only where
`DEMO_SEED_ENABLED=true` (in `.env.example`; an `.env` copied before S1-C13a needs the line
added).

Every account's email is `<username>@harbor.example`, and every password is `harbor-demo`.
The workspace is Harbor Consulting (`harbor`), with two orgs, Acme Manufacturing (`acme`) and
Globex Retail (`globex`). Each step is recorded in the audit log as the person who would take it:
the system admin creates the orgs, each org's owner adds its members, creates its projects, and
archives `LEGACY`, and each lead adds the project's members. Each step is checked against the
permission its endpoint checks, so a step the app would refuse fails the seed.

| Username | Role |
|---|---|
| `admin` | System admin, workspace owner |
| `wendy` | Workspace admin |
| `olivia`, `oscar` | Owner of `acme`, of `globex` |
| `liam`, `lena`, `luke` | Leads (project admins) of `ERP`, `PORTAL`, and the archived `LEGACY` (`acme`) |
| `leo`, `lucy` | Leads of `INV` and `FIN` (`globex`; `FIN` is Confidential, `financial`) |
| `amara`, `ella`, `ivan`, `noah` | Project admin of `ERP`, `PORTAL`, `INV`, `FIN` |
| `ben`, `chloe` | Members of `ERP` and the archived `LEGACY` |
| `finn`, `jade`, `omar`, `priya` | Members of `PORTAL`, `INV`, `FIN`, `FIN` |
| `sam` | Member of both `acme` projects (`ERP`, `PORTAL`) |
| `max` | Member of both `globex` projects (`INV`, `FIN`) |
| `casey` | In both orgs: member of `PORTAL` and `INV` |
| `dev`, `hana`, `kira`, `quinn` | Viewers of `ERP`, `PORTAL`, `INV`, `FIN` |
| `fiona`, `felix` | Members of `ERP` who must change their password at sign-in (one per theme run of the end-to-end flow) |
| `nora` | No memberships: the no-access page |

### Local Postgres

- On **first start with an empty volume** the `postgres` image creates the dev database and
  user from `.env` (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`), and
  `docker/postgres/initdb/` creates the test database, `waterline_test`, owned by the same user.
- Those first-start steps never run again on an existing volume. To start over (or after
  changing the user, password, or init script): `wl down -v && wl up`.
- `POSTGRES_PORT` in `.env` sets both the published port and where the host (tests, `wl backend
  migration`) connects; change it if something else already uses 5432.
- Tables are created only by Alembic, never by hand or with `create_all`: the `migrate` service
  applies migrations on every `wl up`, and `wl migrate` applies a new one while the stack runs.

### Sessions and transactions

- Endpoints get a session with `SessionDep` (`app/core/db.py`). It is **one transaction per
  request**: committed after the endpoint returns and **before** the response is sent (the
  dependency uses `scope="function"`), rolled back on any exception. A failed commit is a 500,
  never a false success.
- Services may `flush()` when they need database-generated values; nothing else commits.
- The one exception to "one session per request" is the health check, which pings on its own
  short-lived session (`SessionMakerDep`) so a dropped connection is reported as 503 instead of
  failing the request's commit.
- Sessions use `expire_on_commit=False`, so objects stay readable while the response is built.

### Models

- App tables subclass `BaseModel` (`app/core/base_model.py`), which gives them:
  - `id`: a UUIDv7 assigned **when the object is constructed**, so it's known before flush.
  - `created_at` / `updated_at`: `timestamptz` from the database clock (`now()`, the
    transaction's start time), `updated_at` refreshed by the ORM on every update. The mapper
    uses `eager_defaults`, so both come back with the INSERT/UPDATE and are readable without
    a lazy load. Never set them by hand.
- A table without an `id` (e.g. a composite primary key) subclasses `Base` with
  `TimestampMixin` instead.
- **If a model defines `__mapper_args__`, merge the mixin's:**
  `__mapper_args__ = {**TimestampMixin.__mapper_args__, "version_id_col": ...}`. Replacing it
  drops `eager_defaults`, and then reading a timestamp after flush fails in async code.
- **Parent and child in one flush:** knowing the parent's `id` early doesn't tell SQLAlchemy to
  insert the parent first. Without a `relationship()` between them, flush the parent before
  adding the child (or add the relationship).
- **Constraint names** come from the naming convention on `Base.metadata`, so leave `name=`
  off except for CHECK constraints, which need a short one:

  | Kind | Pattern | Example |
  |---|---|---|
  | Primary key | `pk_<table>` | `pk_task` |
  | Foreign key | `fk_<table>_<column>_<referred table>` | `fk_task_project_id_project` |
  | Unique | `uq_<table>_<columns>` | `uq_project_workspace_id_key` |
  | Check | `ck_<table>_<name>` | `ck_task_status` |
  | Index | `ix_<table>_<columns>` | `ix_task_project_id` |

- Import every model module in `app/models/__init__.py`, so Alembic autogenerate sees it.

**Enums** (`app/core/enums.py`). Define the enum as a `StrEnum` in `app/enums.py`, which
doesn't import SQLAlchemy (so `rules/` can use it), and map it with `enum_type`, naming it after
the column:

```python
status: Mapped[TaskStatus] = mapped_column(enum_type(TaskStatus, "status"))
```

It's a `VARCHAR(64)` with a CHECK named `ck_<table>_status` that lists the values (`"in_review"`,
not `"IN_REVIEW"`); the ORM rejects other strings before they reach the database. Filter with
members (`Task.status == TaskStatus.DONE`), never string literals. Adding, renaming, or removing a
value needs a hand-written migration (autogenerate doesn't see CHECK changes; see the `migration`
skill).

**Soft delete** (`SoftDeleteMixin`, for `deleted_at` tables). Every ORM `SELECT`, including the
related rows a query loads, hides rows with `deleted_at` set. Trash and restore queries opt in:
`select(Task).execution_options(include_deleted=True)` (the key is `INCLUDE_DELETED`). Two
caveats: `session.get()` returns an object already in the session's identity map without
querying (so load by ID with `get_by_id`, below), and raw SQL (`text()`) is never filtered. The
filter also applies to loading a **parent**: a comment whose task is soft-deleted loads with
`comment.task == None`, so trash and restore screens put `include_deleted=True` on the query
that loads the parents too. And the filter reaches related rows only through the query that
loaded the object: loading a relationship on an object no filtered query loaded (one just
created in the session, or loaded with `include_deleted=True`), e.g. `await
session.refresh(task, ["comments"])`, isn't filtered. Load related rows with a query and
`selectinload` instead.

**Optimistic locking** (`VersionMixin`, for `version` tables). List it **before** `BaseModel`:

```python
class Task(VersionMixin, SoftDeleteMixin, BaseModel): ...
```

Every ORM update checks and increments `version`. Update schemas carry the version the client
loaded, and the service calls `check_version(task, payload.version)` before changing anything;
the ORM's own check then catches a write between this request's load and its commit. Both raise
`StaleDataError`, which `get_session` turns into **409** `{"code": "stale_version", ...}` (see
"Errors" in section 4); the UI prompts a reload.

**Direct updates** (`app/repositories/base.py`). Rank moves (with a requirement's parent change,
by a move, a delete's promote, or a restore at the top level, DL-214, DL-215), counters, an item's restriction (DL-168), and a new item's first revision pointer
(DL-207) use `direct_update`, which runs
`UPDATE … RETURNING` outside the unit of work, so it doesn't bump `version` (someone editing the
item's content at the same time doesn't get a 409; a new requirement starts at `version` 1).
Every call says whether `updated_at` moves, with the required `touch_updated_at` keyword
(DL-210): a rank write passes `False` (a display-order change isn't an edit), as do the first
revision pointer and items lifted by a project raise (nobody edited them); a counter write such
as adding a subtask, an item's own restriction change, and a parent change pass `True`. It returns the new values (so `{"next_subtask_number": Task.next_subtask_number + 1}`
works as a counter), or `None` if no row has that id, and writes every changed column onto the
object if the session has it loaded, so it stays readable without a lazy load.

**List endpoints** (`app/core/lists.py`; build plan, "API conventions", "Lists"). Declare a
`ListSpec` per list: sortable fields (an allowlist; `id` is always the last tiebreaker), the
default sort, `sort_first` (a fixed order ahead of the requested sort, built in the repository
module: the users list's system admins with no workspace role last, DL-188), filters (`Filter(name, column, FilterType.ENUM, enum=...)`, or `CustomFilter` for
a filter on another table, written with `EXISTS`, never a join, so no item repeats: DL-35),
`search` columns for `?q=`, `archived_column` (archived rows hidden, with `?include_archived=true`
or alone with `?archived_only=true`; both at once is a 422 `conflict`, DL-181, DL-182),
`soft_deleted`, and `paging="cursor"` for append-only feeds. The router takes `Annotated[SPEC.query_model, Query()]` (unknown
parameters are a 422, and every filter is in the OpenAPI schema) and passes the parsed query to
the service; the **repository** builds a statement already scoped to what the user may see and
calls `fetch_page(...)` (items, `total`, `limit`, `offset`) or `fetch_feed(...)` (newest first,
`next_cursor`), with `current_user_id` for `me`. A filter marked `restricted=True` (a field only
some users may filter by) and `include_deleted` apply only when the
endpoint passes them in `permitted=` (decided through `authorize()`); otherwise they're a 422
`not_permitted` on the parameter. Response bodies are `Page[ItemSchema]` / `Feed[ItemSchema]`;
`page.with_items(rows)` turns a `PageResult` into the response with the rows built from it.
Parameters by filter type: enum, reference, and user `name` (repeat for any of; a user filter
also takes `me`), `name__not`, `name__is_null`; date `name__lt`, `name__gt`, `name__is_null`;
text `name__contains`; boolean `name`; number `name__gte`, `name__lte`. Examples:
`tests/support/lists.py`.

**Admin events** (`app/audit/admin_event.py`, design-doc §10.1): every admin and security action
calls `log_admin_event(session, action=..., actor_id=..., workspace_id=..., ...)` in the same
request. It adds the row to the session (no flush, no commit), so the event and the change
commit together; the database refuses any later edit. `details` must never hold a password,
hash, or token: a key that names one raises `SecretInDetailsError`.

**Change log** (`app/audit/change_log.py`, design-doc §10): after changing an item, call
`log_change(session, project_id=..., entity_type=..., entity_id=..., action=...,
changed_by=..., field=..., old=..., new=...)` for each logged field (design-doc §10 lists them;
`field` is required for `updated`). Pass enum members, IDs, and dates as they are: the helper
stores them as text; for link events `old`/`new` are the other entity's ID. `changed_by` is None
only when an app CLI command made the change, and `changed_at` is the database's. Like admin
events, it adds the row without flushing or committing, and the database refuses any later edit
or delete (DL-193). An item's history is read through `ActivityService` (names resolved at read
time, DL-160).

**Numbers** (`app/services/numbering.py`, design-doc §3): requirements, tasks, and test cases
get their per-project number from `NumberingService(session).allocate_number(project,
NumberPrefix.TASK)`, inside the request's transaction (a rollback undoes it). One atomic upsert
on `project_counter` locks only that (project, prefix) row until commit, so parallel requests
never collide and other prefixes and the project itself aren't blocked. Never compute
`MAX(number) + 1`.

**Get by ID** (`app/repositories/base.py`): `get_by_id(session, Model, id)` is always a query,
never `session.get()`, so the soft-delete filter applies even to an object already in the
session (`include_deleted=True` for trash and restore screens). Repositories use it for every
load by ID. It is **not scoped** to the user's orgs and projects: endpoints reach single
entities only through the load-and-authorize dependency, and any other caller authorizes
before using or returning the row. List and feed queries never use it.

**Restriction** (`RestrictionMixin`, design-doc §3.1; "classification" until S2-C0d, DL-134):
adds `restriction_level` (enum `internal` or `confidential`, nullable: null is the None level) and
`restriction_categories` (`text[]`, default `{}`). The model also adds
`restriction_categories_check(...)` to its `__table_args__` with the categories it allows:
`PROJECT_CATEGORIES` on `project`, `CONTENT_ITEM_CATEGORIES` on content items
(`export_controlled` is project-only in v1). `app/rules/restriction.py` has the effective
restriction (`effective(item, project)`) and whether a change raises or lowers it
(`change(old, new)`; None ranks as Internal). The project service checks an export-control
confirmation with `_confirmation(values, needed=..., members=...)`: the 422s
`confirmation_required`, `members_changed`, and `confirmation_not_needed`, under the project's row
lock, with the confirmation returned for the audit event (DL-81). `set_restriction` checks its
rights after taking the project's lock, against the project and the caller's own project role
read again under it (`_with_current_role`): a removal takes that lock first, so an explicit admin
removed meanwhile can't lower (owner decision, S1-C13 review).

**Relationships** are always `lazy="raise"`: load what you use with `selectinload` /
`joinedload` in the repository. Touching an unloaded relationship raises instead of emitting
SQL (which async sessions can't do).

**Convention checks** (`tests/unit/core/test_model_conventions.py`) walk every mapped model and
fail if a relationship isn't `lazy="raise"`, a model dropped `eager_defaults=True` (for example
by replacing `__mapper_args__`), a model has a `version` column that isn't checked (for
example `VersionMixin` listed after `TimestampMixin`), or a restrictable model (`project`,
`requirement`, `task`, `testcase`, or one with a `restriction_*` column) doesn't use
`RestrictionMixin`.

### Migrations

- Change the models, then `wl backend migration "add phase"` to autogenerate a revision in
  `backend/migrations/versions/` (named `YYYY_MM_DD_HHMM-<rev>_<slug>.py`, formatted by ruff).
  **Review it by hand**: autogenerate misses some changes (e.g. renames) and can't write data
  migrations. Database functions and triggers aren't in the models at all, so they are always
  written by hand with `op.execute` (e.g. `audit_event`'s append-only trigger), with a
  downgrade that drops them.
- `wl migrate` applies it to the dev database; the test run applies all migrations to the test
  database automatically.
- Never edit a committed migration; add a new one. Every migration must downgrade cleanly.
- There is one migration history: every migration, app tables or infrastructure (such as
  procrastinate's schema), chains after the current head. No branch labels.
- The database URL comes from app settings (`migrations/env.py`), never from `alembic.ini`.
- **Migration checks** run with the tests (so in `wl check`), each on a scratch database:
  every migration upgrades from empty, round-trips (down one step and up again), and
  `alembic check` finds no drift between the models and the migrations. To check drift by hand
  against the dev database: `uv run --directory backend alembic check`.

## 6. Background jobs

Jobs run on procrastinate, with the queue in Postgres (design-doc §13). The rules come from the
S0-C3 spike (design-doc §13, "Transactional enqueue").

### Running the worker

```bash
uv run --directory backend python -m app.jobs.worker
```

It processes jobs until stopped (Ctrl+C or SIGTERM finish the current job first). `wl up` runs
it as the Compose `worker` service (it doesn't reload: `docker compose restart worker` after
changing a job); run it on the host as above only with that service stopped. The API never opens
a procrastinate connection; only the worker does.

### Enqueueing

- Enqueue **only** through a function in `app/jobs/enqueue.py`, passing the caller's session:
  `await enqueue_ping(session, "hello")`. The job is written in the caller's transaction, so it
  commits or rolls back with the data, and the worker isn't woken until the commit.
- Arguments are IDs and plain values, never ORM objects. Jobs must be idempotent (every queue
  retries).
- For "at most one pending job" pass a `queueing_lock`; the function returns `None` when a job
  with that lock is already queued, and the caller's transaction stays usable.
- Never call procrastinate's `defer_async()` directly: without the caller's connection it uses
  a separate transaction, and a failed request leaves an orphan job behind.

### Adding a job

1. Add its name to `app/jobs/task_names.py`.
2. Write it in a module under `app/jobs/tasks/`, registered with
   `@jobs_app.task(name=task_names.MY_JOB)`, and import the module in
   `app/jobs/tasks/__init__.py`. Put run-time options (e.g. `retry=`) on the decorator, but
   **defer-time options (`queue`, `priority`, `lock`, `queueing_lock`) only in `enqueue.py`**:
   the API process never registers jobs, so decorator options would apply in the worker but be
   silently ignored when enqueueing. `tests/unit/jobs/test_task_registry.py` checks this for
   every name in `task_names.py`.
3. Add an `enqueue_my_job(session, ...)` function to `app/jobs/enqueue.py` that calls
   `_defer(session, task_names.MY_JOB, ...)`.
4. Test the enqueue function in the rolled-back harness, and the job itself (the job function
   can be called directly; a full worker run needs the `concurrency` fixture).

`enqueue.py` defers by **name** and never imports job modules: jobs call services, often in
higher layers, and the import-linter contract "Only the worker imports job modules" enforces
it.

### procrastinate's schema

- The migration `add procrastinate schema` applies a vendored copy of procrastinate 3.10.0's
  `schema.sql` (`backend/migrations/sql/`), so it never changes when procrastinate does. Its
  downgrade removes every procrastinate object, including queued jobs.
- Autogenerate ignores procrastinate's objects (`app/core/migration_filters.py`).
- **Upgrading procrastinate:** stop the workers, bump the pinned version, then add a hand-written
  migration that applies procrastinate's migration files for the versions in between
  (`procrastinate/sql/migrations/`, in file-name order, vendored under `migrations/sql/`). A
  version's `_pre_` and `_post_` files go in the same migration: v1 deploys with the workers
  stopped, so there's no mixed-version window to split them across. Restart the workers after
  deploying.

## 7. Frontend

Vue 3 (Composition API, `<script setup lang="ts">`), TypeScript strict, Vite, Vue Router, Pinia.
The rules are in `frontend/CLAUDE.md`, and the UI rules in full, by rule ID, in
`docs/ui-design-guide.md`; this section is the how.

```
frontend/src/
  main.ts            imports the styles and mounts createWaterlineApp()
  App.vue            AuthLayout or AppLayout (the route's `meta.layout`) around the router view,
                     keyed by path (a new path is a new page; a query change keeps it)
  api/client.ts      the configured openapi-fetch `client`, `api()`, `ApiError`, the session hook
  api/schema.d.ts    generated by `wl gen-client`; never edit
  app/               createApp.ts (Pinia, router, PrimeVue, session hook), router.ts, the two
                     layouts (AppLayout is the shell), shell/ (OrgMenu, UserMenu,
                     ProjectSelector, ProjectPages, LinkPopover, SidebarLink), labels.ts
                     (display labels),
                     routeFocus.ts,
                     session.ts; guards/auth.ts; styles/ (main.css, tokens.css, base.css);
                     theme/preset.ts (PrimeVue's colors)
  components/        shared UI components: Button, Alert, FormAlert, FormField, TextField,
                     SelectField, PasswordField, PasswordRequirements, TemporaryPasswordField,
                     TemporaryPasswordNotice, Badge, EmptyState, ErrorState, Skeleton,
                     Pagination, SuccessStatus, PageHeader, ModalDialog,
                     ConfirmDialog, GroupError, RowActions, Icon, NameSlugSettings
  composables/       shared logic: useFormErrors, useLoad, useListQuery, usePasswordPolicy,
                     useAvailability, useRouteOrg, useSettingsSave, useSignOut, useTheme,
                     useUsernameSuggestion, useWorkspace,
                     temporaryPassword,
                     allowedActions (`allows()`)
  stores/            Pinia stores: currentUser, currentOrg (the current org and project)
  views/<area>/      screens by backend area name, singular: auth/ (sign-in, change password),
                     my_work/, project/ (org project list, project home, the create
                     dialog, the restriction badge and fields, settings, members with
                     the AddMemberDialog picker, the access review), user/ (account
                     settings, access review, the account-action dialogs), workspace/ (staff,
                     orgs, users, settings), org/ (overview, members, settings), roster/ (what staff and
                     org and project members share: `RosterPage`, the list with its row menus, and the add
                     person, change role, and remove dialogs); plus status/ and errors/ (404,
                     403, no access)
  test/              helpers for the specs: a11y.ts, api.ts (typed responses), projects.ts,
                     overlay.ts (`stubResizeObserver`, `stubDialog`), router.ts, workspace.ts
                     (`mountWorkspaceView`, `mountSignedIn`), org.ts (`mountOrgView`,
                     `mountOrgPages`)
frontend/e2e/        Playwright specs; support/ (a11y.ts, demo.ts)
```

**Routes:** `/` My work; `/sign-in` (signed out only); `/account` (account settings);
`/account/password` (change password, from account settings); `/account/change-password` (the
forced change); `/account/no-access` (a user with no memberships, who is sent there from
everything but account settings and change password); `/status` (open to
anyone); `/workspace/staff`, `/workspace/orgs`, `/workspace/users`,
`/workspace/users/{user_id}/access`, and `/workspace/settings` (workspace administration, DL-104;
`/workspace` goes to staff; anyone without `workspace.view`, or whom the API refuses, gets the
403 page, `ForbiddenView`, saying who to ask, UI-FBK-14);
`/{org_slug}/members` and `/{org_slug}/settings` (org administration, DL-104, for anyone with
`org_member.manage` in the org's `/me` entry; anyone else, or anyone the API refuses with a 403,
gets the 403 page, and an org the API no longer finds, the not-found page, since an org's
existence isn't public, UI-FBK-14);
`/{org_slug}/projects` and `/{org_slug}/projects/{key}` (an org's projects and a
project's home; a stale org slug or a lowercase key is redirected to the project's own; an org
page open when its org's slug changes moves to the new URL, `useRouteOrg`);
`/{org_slug}/projects/{key}/members`, `/{org_slug}/projects/{key}/access`, and
`/{org_slug}/projects/{key}/settings` (a project's members, for anyone who sees it; its access
review, for `project.view_access`; its settings, for whoever `hasSettings`; anyone else gets the
403 page, and the redirects are a project home's, `useProjectPage`);
anything else, the not-found page. Every top-level segment is on the reserved-slug list
(`router.spec.ts` checks it against `ReservedSlug` in `backend/openapi.json`).

- **Running it:** `wl up` serves it at <http://localhost:5173> (the `web` service, hot reload on
  the mounted source). To run Vite on the host instead: `docker compose stop web`, then
  `npm run dev --prefix frontend`; it proxies `/api` to `API_PROXY_TARGET`, default
  `http://localhost:8000` (the `api` service's published port).
- **One origin:** the browser only talks to Vite, which forwards `/api/*` to the API
  (`vite.config.ts`, `changeOrigin` off so the API sees the browser's own `Host` and `Origin`).
  Vite's own CORS handling is off (`server.cors: false`), so cross-origin behaviour, including
  preflights, is decided by the API alone. Every route the router doesn't know shows the
  not-found page; Vite serves `index.html` for any non-file path, so deep links work.
- **Calling the API:** always through `@/api/client`, typed by the generated schema:

  ```ts
  import { api, ApiError, client } from '@/api/client'

  const health = await api(client.GET('/api/health')) // typed from the schema
  ```

  `client` sends requests to the page's origin with `credentials: 'include'` and JSON bodies.
  `api()` returns the data, or throws an `ApiError` with the response's `status`, `code`,
  `message`, and `details`. When there's no standard body to read, the code is
  `network_error` when the API couldn't be reached (fetch couldn't connect, `status` 0; or
  a proxy answered 502, 503, or 504 without the standard body, which is what Vite sends when the
  API is down) or `unexpected_response` otherwise (`status` 0 for a success whose body isn't
  JSON). Any other failure (e.g. a cancelled request) is rethrown as it is, not wrapped.
  Branch on `code`, never `message`. ESLint rejects `fetch` (bare, `window.`,
  `globalThis.`, `self.`) and `openapi-fetch` imports outside `src/api/`;
  `src/api/lint-rules.spec.ts` proves the rules fire.
- **After an API change:** `uv run wl gen-client`, then use the new types; commit both
  generated files.
- **Signing in and route guards:** `src/app/guards/auth.ts` loads the current user once
  (`GET /api/auth/me`; a 401 means signed out) and sends a signed-out visitor to `/sign-in`
  with `next` (the page they asked for), and a user who must change their password to
  `/account/change-password`. `meta.public` opens a route to anyone, `meta.guest` only to the
  signed out. `next` is used only when it's a path on this site (`safeNext`: one leading `/`,
  never `//` or `/\`). A 401 on any later request (the session ended) or a 403
  `password_change_required` goes through the client's session hook (`onSessionProblem`,
  wired in `src/app/session.ts`), so views never handle either.
- **Forms:** `useFormErrors(labels)` maps a 422's `details.fields` to each field (by the last
  part of `loc`), moves the rest into the form's alert, and builds the screen-reader
  announcement; other failures get our own wording (`FORM_MESSAGES`: retry for a network error,
  reload for a 409). See `src/views/auth/SignInView.vue`.
- **Styles:** Tailwind v4 utilities from the tokens (`src/app/styles/tokens.css`, a copy of
  `docs/ui/tokens.css`; a new color pair goes in `docs/ui/check_contrast.py`, run as
  `python3 docs/ui/check_contrast.py frontend/src/app/styles/tokens.css`). PrimeVue reads the
  same tokens through `src/app/theme/preset.ts`. Dark mode follows the system;
  `data-theme="light"`/`"dark"` on `<html>` overrides it: account settings' Appearance section
  sets it (`useTheme`, kept in `localStorage`, applied by `main.ts` before mounting).
- **Loading a region:** `useLoad(() => api(...))` gives `data`, `error`, `loading`, and `retry`.
  Show `Skeleton` while there's no data (it appears after 300 ms), `ErrorState` (Try again) on
  an error, mark the region `aria-busy` while loading, and announce "Loading …" and the result
  in a polite live region. A 404 from a record's own read shows `NotFoundView` in place. See
  `src/views/my_work/MyWorkView.vue`.
- **List state in the URL:** `useListQuery({ limit })` reads the page from `?offset=`;
  `linkTo(offset)` is the location of another page, which `Pagination` links to (a
  `nav aria-label="Pagination"` whose Previous and Next stay focusable, `aria-disabled`, at the
  ends). A query-only navigation moves neither focus nor the title (`routeFocus.ts`), so the list
  announces its new count instead. `returnWhenEmpty(page.data)` sends a page that loads empty
  past the first (an old link, or its last row removed) back to the first (TD-58); a page with
  two paged lists names the second's offset apart (`offsetKey`, the org overview's
  `archived_offset`) and each `Pagination` after its list (`label`). Put the polite live region outside the `aria-busy` region:
  screen readers hold back changes inside a busy one. See `src/views/project/OrgProjectsView.vue`.
- **A success with no other visible trace** (a saved profile) shows `SuccessStatus` under the
  form's buttons, which is visible and polite.
- **Allowed actions:** `allows(entity, 'project.create')` (`@/composables/allowedActions`)
  hides an action the user may never take; the server still checks.
- **Menus and popovers** come from PrimeVue (`Menu`, `Popover`; UI-STY-3). `LinkPopover` is the
  menu button with a popover of links that the org menu and project selector share; opening
  it moves focus inside (the popover sits at the end of `<body>`, out of the Tab order). A spec
  that opens one stubs `ResizeObserver` (`stubResizeObserver()`, `@/test/overlay`), turns
  transitions back on (`stubs: { transition: false }`, so the overlay's `show` and `hide` events
  fire), waits a tick after mounting before opening it, and unmounts its wrappers
  (`enableAutoUnmount(afterEach)`) before the body is cleared.
- **Dialogs:** `ModalDialog` is the native `<dialog>` (UI-FRM-14): `open()` puts focus on the
  element marked `data-autofocus` (a confirmation's Cancel) or the first field, and closing
  returns focus to whatever had it, or to `fallbackFocus` when that's gone (a removed row).
  `RowActions` puts focus back on its own button before an action runs, so a dialog it opens
  returns there. Specs call `stubDialog()` (`@/test/overlay`): jsdom has no `showModal()`. A form
  alert's Retry goes through `retryFromSubmit(form, submit)`, which focuses the submit button
  before repeating the action (UI-FRM-7).
- **Live availability** (UI-FRM-9): `useAvailability(value, noun, check, skip)` debounces, keeps
  only the latest answer, and gives the message for a polite live region under the field; `skip`
  leaves out a value that needs no check (the person's own username).
- **Temporary passwords** (UI-FRM-11): `TemporaryPasswordField` before saving (generated, at
  least the policy's minimum, from `GET /api/auth/password-policy`), `TemporaryPasswordNotice`
  after (shown once, with Copy). A dialog that reopens its form keys it on each opening, so the
  field generates a new password.
- **Admin rosters:** a page gives the dialogs in `views/roster/` a `Roster` (its roles, scope
  words, and endpoints); the dialogs show what the server answers, including the last-owner
  refusal that brings up the replacement-owner picker (DL-59). `AccountActions` holds the account
  dialogs and turns a row into its menu items from the row's `allowed_actions` (DL-102).
- **Adding a screen:** a view in `src/views/<area>/`, a route in `src/app/router.ts` (above the
  not-found route, which must stay last), and a `*.spec.ts` next to it that calls
  `expectNoA11yViolations()` (`@/test/a11y`). Give the page one `h1`, in `PageHeader` with the
  page's primary actions (UI-SHL-8; the auth card's pages use a plain, smaller `h1`): navigation sets the title
  to `<h1> · Waterline` and moves focus to it. A page whose `h1` comes from its data sets
  `meta: { settlesItself: true }` and calls `settlePage()` once it has loaded (see
  `src/views/project/ProjectHomeView.vue`).

## 8. Conventions

- **Python 3.14**, pyright **strict**, ruff (rules and line length 100 in `pyproject.toml`).
  No relative imports.
- Files are named by aggregate and the name repeats across layers (`models/task.py`,
  `schemas/task.py`, …). Create a layer's file when its slice needs it, not up front.
- Schemas are Pydantic models separate from the ORM models: `TaskCreate`, `TaskUpdate`,
  `TaskRead`, `TaskListItem`.
- Never hand-edit generated files (`backend/openapi.json`, `frontend/src/api/schema.d.ts`)
  or lockfiles; change dependencies with `uv add` / `uv remove` in the right project, or
  `npm install` / `npm uninstall` in `frontend/`.
- Warnings are errors in tests (`filterwarnings = ["error"]`).

## 9. Testing

Strategy, layers, and gates: `testing-strategy.md`. Layout in `backend/tests/`:

| Folder | For | Example |
|---|---|---|
| `unit/` | Pure code, no database (rules, authz, helpers) | `test_import_contracts.py` |
| `integration/` | Repositories and services against Postgres | `core/test_db.py` |
| `api/` | Endpoints over HTTP | `test_health.py` |
| `factories/` | polyfactory factories, one per model (`TaskFactory` in `task.py`) | `BaseFactory` |
| `support/` | Test-only helpers, e.g. tables for exercising the base model | `models.py` |

- A schema-doc column marked `Added in Slice <n>.` for a slice that isn't finished shows as a
  skipped case of `test_model_column_matches_schema_doc`; nothing else should skip.
- Tests use pytest's `importlib` import mode, so test folders have no `__init__.py` (only the
  importable helper packages `factories/` and `support/` do).
- **Postgres must be running** (`wl up`). Each worker migrates its own test database to head
  once per session (`waterline_test` itself under `-n 0`); tests never touch the dev database.
- **Tests run in parallel** (pytest-xdist, DL-100): `pytest` alone spreads the suite over one
  worker per core, at most 8 (`addopts` in `pyproject.toml`). Each worker drops, recreates, and
  migrates its own database, `waterline_test_gw<n>`, at its start; they stay until the next run
  (`wl down -v` clears them). `-n 0` runs in one process on `waterline_test` (filtered runs do,
  and so does mutmut). Coverage is combined across workers, so the gates are unchanged. A test
  that passes alone but fails in the full run depends on another test's state or order: fix
  the test, never the worker count. Run one full `pytest` at a time against a stack: a second
  run drops the first run's worker databases.
- **Async tests** run on the anyio plugin: mark the module `pytestmark = pytest.mark.anyio`.
  A synchronous test must not use async fixtures.

**Database fixtures** (`tests/conftest.py`). Each test that uses one gets its own connection
inside an outer transaction that is always rolled back, so tests never see each other's data:

| Fixture | Gives |
|---|---|
| `session` | An `AsyncSession` for arranging and asserting; factories persist through it |
| `sessionmaker` | Sessions that join the test transaction (`join_transaction_mode="create_savepoint"`): their commits only release savepoints |
| `connection` / `engine` | The raw connection and the session-scoped test engine |
| `client` (api/) | An `httpx.AsyncClient` on the real app, whose per-request sessions join the test transaction; built by `api_client(app)` (`tests/support/api.py`) on `https://testserver`, sending `Origin: https://testserver` by default. Build any other client with `api_client` too: httpx won't send the `Secure` session cookie over `http://`, and a mutation without the `Origin` is a 403 |
| `settings` | `Settings` from the environment, with API docs on and the session lengths pinned to their defaults |

```python
pytestmark = pytest.mark.anyio


async def test_health_reports_database_ok(client: AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.status_code == 200
```

**Factories** (`tests/factories/`). Subclass `BaseFactory[Model]` with `__model__ = Model`,
then `await TaskFactory.create_async(status=...)` in a test that uses `session`. `BaseFactory`
persists with `flush` (never commit), leaves `id` and database-set timestamps to the model, and
is reseeded from a fixed seed before every test, so generated values are reproducible. Set any
value the test depends on explicitly.

- Each factory sets `__set_as_default_factory_for_type__ = True`, so a related model is built
  through its own factory. Foreign keys are never generated: a model's many-to-one
  `relationship()` builds the parent (`ProjectFactory` builds an org and its workspace), or the
  test passes one (`ProjectFactory.create_async(organization=org)`).
- Text fields get realistic values with `Use(...)` and Faker (`BaseFactory.__faker__`), in the
  formats the rules expect: lowercase emails, slug-format usernames and slugs (`fake_slug`),
  project keys. Nullable fields default to `None` explicitly, so a factory never makes an
  archived or restricted row by chance.
- Every factory user's password is `FACTORY_PASSWORD` (`tests/factories/user.py`), hashed once
  per run.
- A primary-key column that isn't a foreign key (e.g. `project_counter.prefix`) is only set if
  the factory sets `__set_primary_key__ = True`.

**Rules** (`app/rules/`, pure: no database) are written **test-first**, and so is `app/authz/`:
write interface stubs (signatures and types, returning one fixed wrong answer), invoke the
`spec-test-writer` agent, which writes the tests from the design doc's rules and tables without
reading the implementation and proves each fails against the stub, then implement until they pass.
For `app/authz/` it also writes the integration and API tests and their test-only routers in
`tests/support/`; tell it which built modules it may read (the app factory, `app/core/errors.py`,
the auth dependencies), never the ones being implemented. It tests a real endpoint only when the
docs specify it (method, path, error responses) and you've stubbed its route; for any other
endpoint, write the denial test yourself once it's built, under the sabotage check (DL-32). Its
files and their `git hash-object` go in the review record ("Spec tests"); a spec test changes only
with the owner's approval. S1-C3's rules predate `spec-test-writer` (DL-11): their tests were
written test-first by the implementing session, and aren't hash-protected spec tests; the later
ones (`suggest_username` in `identifiers.py`, `modules.py`, `restriction.py`) came with spec
tests. The rules: `identifiers.py` (project keys, slugs and the reserved top-level routes in `RESERVED_SLUGS`,
usernames; each check returns an `IdentifierProblem` for the field error), `password_policy.py`
(`password_problems(...)`; the caller checks the hash and passes `same_as_current`), and
`account_rank.py` (`can_manage_account(actor, target)`, from both users' memberships),
`modules.py` (each type's recommended modules, and the shipped ones it seeds, DL-136), and
`restriction.py` (the effective restriction, and the raise and lower rules). `app/rules/`
and `app/authz/` are held to 100% line and branch coverage by a hook in `tests/conftest.py`, so a
plain `uv run pytest` fails below it. A `match` that covers every type of its subject (pyright
checks: the function's return type would otherwise allow `None`) marks its last `case` with `#
pragma: no branch`, since that case can't fail to match.

**Property tests** (Hypothesis) cover rules with a large input space: generate inputs, check an
invariant against an independent oracle (e.g. "accepted exactly when 3-6 uppercase letters or
digits, starting with a letter"), never against the code under test. Locally, examples vary
between runs and failures are replayed from `.hypothesis/` (gitignored); CI (`CI` set) uses the
`ci` profile, derandomized. A property over the database (e.g. numbering) runs each example in
a savepoint it rolls back, with `suppress_health_check=[HealthCheck.function_scoped_fixture]`.

**Mutation testing** (`wl backend mutate`; in `wl check` when anything it depends on changed, and always in `wl check --full` and CI, DL-99): mutmut changes `app/rules/`
and `app/authz/` one small edit at a time (`[tool.mutmut]` in `pyproject.toml`) and runs their
unit tests against each; every mutant must be killed. On a failure, `uv run mutmut results`
lists the survivors and `uv run mutmut show <name>` shows one: kill it with a new or sharper
test. Only an equivalent mutant (one that can't change behavior) may be excluded, with
`# pragma: no mutate` and a comment why. The run starts from a clean `mutants/` (gitignored),
since mutmut's cached results can be stale. A new unit-test folder for `app/rules/` or
`app/authz/` goes in `pytest_add_cli_args_test_selection`.

**Concurrency tests** need real commits on separate connections (parallel transactions, or a
worker in the same test), so they use the `concurrency` fixture instead: it yields a
sessionmaker whose sessions really commit, on an engine with a pool for 20 parallel transactions
and a Postgres `lock_timeout` of 5 seconds. It refuses to run alongside any
rolled-back-transaction fixture (`connection`, `sessionmaker`, `session`, `client`). Afterwards,
pass or fail, it truncates the tables named in `@pytest.mark.concurrency(...)` and then checks
that **every** table is empty: a test that left rows elsewhere fails with the table's name (and
the rows are removed, so later tests start clean). Truncating cascades along foreign keys, so
naming a parent (`workspace`) also empties the tables that reference it. Helpers in
`tests/support/concurrency.py`:

- `committing_factories(concurrency)`: factories inside it write through a session that commits
  on exit, for committed parents (`async with committing_factories(concurrency): project = await
  ProjectFactory.create_async()`).
- `run_in_parallel(concurrency, n, work)`: runs `work(session, index)` in `n` (up to 20)
  transactions that are all open before any work starts (a start barrier), commits each, and
  returns the results in order; the section fails with `TimeoutError` after 10 seconds.
- `wait_until_blocked_on_a_lock(engine, pid)`: for a test that needs one transaction to be
  waiting on another's lock before it continues.

Sabotage-check a race test against a non-atomic version of the code (`test-writer` skill): the
allocation tests fail against a read-then-write allocator.

```python
@pytest.mark.concurrency("procrastinate_jobs", "procrastinate_workers")
async def test_committed_job_is_processed_by_the_worker(concurrency: SessionMaker, ...) -> None:
    async with concurrency() as session:
        await enqueue_ping(session, "hello")
        await session.commit()
    ...
```

For a race, hold one transaction's row lock, start the other in a task, and use
`wait_until_blocked_on_a_lock(engine, pid)` (`tests/support/concurrency.py`) before letting the
first commit, so the two really overlap; bound it with `anyio.fail_after`. See
`tests/integration/core/test_versioning_concurrency.py`, which also uses
`committed_support_tables` for committed test-only tables.

**Migration tests** use `scratch_database`: a new, empty database for one test, dropped
afterwards (see `tests/integration/test_migrations.py`).

- Name tests after the behavior (`test_member_cannot_delete_approved_requirement`); one
  behavior per test; parametrize tables.
- **Coverage gates:** backend 90% line + branch overall (in `pyproject.toml`), and 100% for
  `app/authz/` and `app/rules/` (run by `wl backend test`).
- **Frontend tests** are Vitest specs next to the code they test (`src/**/*.spec.ts`), run in
  jsdom with Vue Test Utils. Mock only the API client: spy on the method the component calls,
  with results typed from the generated schema (see `src/views/status/StatusView.spec.ts`, and
  the helpers in `src/test/api.ts`):

  ```ts
  vi.spyOn(client, 'GET').mockResolvedValue({ data: healthy, response: new Response() })
  ```

  Assert what the user sees (text, roles, links), not component internals. Spies are restored
  after each test (`restoreMocks`). The client itself is tested against a fake `fetch`
  (`src/api/client.spec.ts`). **Coverage gates** (`vitest.config.ts`): 80% of lines overall,
  90% in `src/composables/`, `src/stores/`, and `src/app/guards/`. Every view and component
  spec runs axe (`expectNoA11yViolations`, WCAG 2.2 AA tags plus `target-size`; contrast is
  left to the browser runs, since jsdom can't compute it).
- **End-to-end tests** (`frontend/e2e/`, Playwright, Chromium) run through `wl e2e` against
  the demo data, each spec in the `light` and `dark` projects. Each page is checked with axe
  (`expectNoA11yViolations(page)`, contrast included, once running animations have finished,
  so an overlay mid-fade isn't read as low contrast) and, on the shell's pages,
  `expectFocusNotObscured(page)` (`e2e/support/a11y.ts`). `signIn(page, username)`
  (`e2e/support/demo.ts`) signs in as a demo user. A flow that changes data uses its
  own user or keys per run (`forcedChangeUser`: `fiona` in light, `felix` in dark).
- **CLI tests** live in `tools/cli/tests/`: every command's `--help` works, every command has
  `--dry-run`, dry-run output matches the expected commands, and the doctor checks are tested
  with fake probes. The CLI is held to **100% line + branch coverage** (in
  `tools/cli/pyproject.toml`), so a test that claims to cover an error path but never reaches
  it fails the gate. The Claude Code hooks (`.claude/hooks/`, with their shared
  `hook_paths.py`) are tested here too (`tools/cli/tests/hooks/`, importing them from
  `.claude/hooks/` through pytest's `pythonpath`), under the same gate and pyright's strict
  mode.

**Docs consistency tests** (`tests/unit/docs/test_docs_consistency.py`, parsers in
`tests/support/docs.py`) read the docs, `.claude/`, `Base.metadata`, and `git log`; no
database. They check:

| Check | Fails when |
|---|---|
| Model tables documented | a model table has no ``### `<table>` `` section in `schema-doc.md`, or is listed under "Deferred tables" |
| Columns and enum values | a model's columns, or an enum column's values, differ from its schema-doc field table. The column check runs per column (`table.column`). A documented column whose Notes cell starts with `Added in Slice <n>.` is **skipped** (`added in Slice <n> (schema-doc)`) until slice `<n>` is finished (its last checkpoint, or a later slice's, has a `checkpoint(<ID>):` commit), and required from then on; a malformed marker is a `DocsStructureError`. A model column with no documented row always fails |
| One owner per table | a schema-doc table isn't in exactly one "Owns (tables)" cell of the build plan's feature map, or the map names a table schema-doc lacks |
| Tech-debt log | an entry lacks Added/What/Why/Fix by/Status, numbers aren't 1..n, a `TD-<n>` reference (in `docs/` outside `docs/reviews/`, the `CLAUDE.md` files, or `.claude/`) has no entry, or an open entry's Fix by is already past |
| Decision log | an entry lacks Date/Decision/Supersedes/Superseded by/Applies to/Source, numbers aren't 1..n, a Superseded by is neither `none` nor another entry (`DL-<n>`), or a `DL-<n>` reference (same files as TD references) has no entry |
| Audit allowlist | an `audit-allowlist.toml` entry names a tech-debt entry that doesn't exist or is resolved |
| Status line | this guide's Status line names neither the latest `checkpoint(<ID>):` commit nor the one after it. "After" is the next row of the slice's build-plan "### Checkpoints" table, whose `#` column may hold an inserted checkpoint (`13a`, ID `S1-C13a`); a malformed ID or `#` cell, or rows out of order, is a `DocsStructureError` |
| § references | a `§N` / `§N.M` (same files as TD references) isn't a numbered heading in `design-doc.md`; `§` means a design-doc section, so refer to this guide's sections as "section N". The exceptions: `guide §N` (or `ui-design-guide §N`) names a section of `docs/ui-design-guide.md`; in that guide a bare `§N` is its own section; in `.claude/agents/ui-reviewer.md` a bare `§N` is its own section or the guide's; and in both, `design-doc §N` still means the design doc |
| Claude configuration | the agents and skills in `.claude/` differ from those listed in the build plan's "Claude configuration" or section 11 below |
| Review records | from Slice 2 on (DL-138, DL-165): the latest `checkpoint(<ID>):` commit has no `docs/reviews/s<n>/<ID>.md`; a slice has an `S<n>-C1` record but no `S<n>-C0` or `S<n>-C0a` record; or the record of the slice's last row has no `## simplicity-auditor` heading |

Fixing a failure: the message names both files and the mismatch. Update whichever side is
wrong (usually the doc); when the right answer is a design question, ask the owner. A
`DocsStructureError` means a doc no longer has the structure the parser expects (a heading,
table header, or field line); restore the structure, or update the parser in the same commit.
Never skip or weaken a check to get green. The status and overdue checks need full git history
(a shallow clone fails with a message saying so).

## 10. Git workflow

- Work proceeds one **checkpoint** at a time (`build-plan.md`), one commit per checkpoint,
  closed out with the `checkpoint` skill.
- **Pull requests:** each slice works on one branch, `s<n>` (e.g. `s1`), with one draft PR
  opened at the branch's first push (build plan, "Pull requests"). Push after every checkpoint
  commit, so CI runs on each; only finished commits are pushed. Groups (each slice's section
  lists them) are review points, not branches. Design changes from chat are `docs:` commits on
  the slice branch (tooling code in `chore:` or `ci:` commits, reviewed by `checkpoint-reviewer`;
  DL-18). Pushed commits are never rewritten (no amend, rebase, or force-push): red
  CI on a pushed checkpoint is fixed with a `fix(<ID>): …` commit. At the end of the slice,
  once the owner approves its last checkpoint, the slice retro's changes are applied on the
  branch with green CI (DL-19), and the owner says so, mark the PR ready and merge it with
  a **merge commit**: `gh pr merge --merge`, never squash or rebase (the branch stays: no
  branch can be deleted). Claude first checks the merge state and that every commit is linked
  to a GitHub account: a commit GitHub can't attribute needs an extra approval, which you can't
  give on your own PR (DL-33). A merge commit keeps every commit's hash (so review records' base
  commits stay valid), and `main` keeps one `checkpoint(<ID>):` commit per checkpoint in its
  history, which the docs consistency tests read. GitHub enforces the rules (DL-27): on every
  branch, no force-push or deletion; on `main`, changes only through a pull request with the
  `wl check` status check green, merged with a merge commit.
- **CI** (`.github/workflows/ci.yml`, GitHub Actions) runs `uv run wl check --full` on every push
  to `main` and every pull request (its job is still named `wl check`, the status check the
  ruleset requires), so a green `wl check --full` locally means a green run there. It
  checks out the full history (`fetch-depth: 0`, for the docs consistency tests), installs the
  dependencies from the lockfiles (`uv sync --locked`, `npm ci`), and runs the tests against a
  `postgres:18` service container; the test database is created by the same init script as in
  Compose (`docker/postgres/initdb/`). There's no `.env` in CI: the workflow sets the
  `POSTGRES_*` variables. A new tool the checks need goes into the workflow's setup steps and
  the developer guide's prerequisites together. `wl check --full` includes `wl audit`, so CI also
  scans the dependencies and the git history for every push; it needs the network, which the
  runners have.
- The pre-commit hooks run gitleaks on the staged changes (secrets); ruff (lint with safe
  fixes, and format) on the backend and CLI;
  Prettier and ESLint (safe fixes) on the frontend (they need `frontend/node_modules`); a check
  that `backend/openapi.json` and `frontend/src/api/schema.d.ts` match what `wl gen-client`
  would produce, so a generated file can't be hand-edited or left stale; and
  whitespace/YAML/TOML/merge-conflict/large-file checks. If a hook modifies files, review them,
  `git add`, and commit again.
- `uv run wl check` must pass before a checkpoint goes to review, and CI (`wl check --full`)
  before it's reported (DL-99). A failure only CI finds gets a `fix(<ID>):` commit.

## 11. Claude Code configuration

The repository's Claude Code setup lives in `.claude/` and is version-controlled.

- **Skills** (`.claude/skills/`): `checkpoint`, `test-writer`, `migration`, `new-area`,
  `design-change`, `vue-screen` (the recipe for a screen or dialog).
- **Agents** (`.claude/agents/`): `checkpoint-reviewer`, `security-reviewer`,
  `fresh-clone-verifier`, `user-guide-verifier`, `docs-consistency`, `spec-test-writer`,
  `repo-auditor`, `ui-reviewer`, `simplicity-auditor`.
- **When the agents run:** `spec-test-writer` at the start of every checkpoint that adds or
  changes `app/rules/` or `app/authz/` (section 9); then, through the `checkpoint` skill and one
  at a time, `security-reviewer` when the build plan names the checkpoint for it or it touches
  security-relevant code, `checkpoint-reviewer` at every checkpoint (it also sabotage-checks
  two or three behaviors in a temporary copy, and reviews a design change's tooling code under
  a `DC-<YYYY-MM-DD>` review ID), `ui-reviewer` when the diff touches `frontend/src/` or
  `frontend/e2e/` (read-only: accessibility and frontend conventions against
  `docs/ui-design-guide.md`, by rule ID; DL-62), and `fresh-clone-verifier`,
  `user-guide-verifier` (the user guide followed in a browser, DL-124), `docs-consistency`, and
  `repo-auditor` (a whole-repository audit that runs no tests, DL-41), then
  `simplicity-auditor` (a whole-repository audit for overengineering, from the prompts vendored
  in `.claude/audit/`, whose findings go to the owner, DL-138) at the last checkpoint of a
  slice. `checkpoint-reviewer`, `security-reviewer`, and `repo-auditor` findings each name a
  concrete case and are written in plain English (DL-39, DL-41, DL-42). Reviewers never run tests at the same
  time: they share the test database. `docs-consistency` also runs in every design change, before
  committing. It is read-only: it reports clear-cut fixes (citing the recorded decision) and
  decisions for the owner, which are never decided for them.
- **Design changes** outside a checkpoint's scope (decisions from a chat session, or code that
  must differ from the docs) use the `design-change` skill: one decision-log entry per decision
  (`docs/decision-log.md`), every affected doc updated, `docs-consistency`, then a `docs:`
  commit. A change to code already built becomes a new checkpoint with a letter suffix
  (`S1-C13a`); checkpoints are never renumbered. Review answers that change built code are
  bundled into the next planned checkpoint, or one follow-up per group (DL-131). Developer-tooling and process code (hooks, the
  `wl` CLI, CI, the docs consistency tests) is built in the change itself, in `chore:` or `ci:`
  commits, after a `checkpoint-reviewer` pass recorded in
  `docs/reviews/design-changes/DC-<YYYY-MM-DD>-<slug>.md` (DL-18, DL-43). Every design change,
  docs-only or tooling, gets a record there, holding its `docs-consistency` pass (and, for
  tooling, `checkpoint-reviewer`'s passes) (DL-126). A checkpoint in progress is parked with `git stash` while a design change is applied,
  and its review base becomes the design change's last commit (DL-20).
- **Hooks** (`.claude/settings.json`, scripts in `.claude/hooks/`), run with `uv`, which must be
  on your `PATH`:
  - Claude's edit tools can't change `backend/openapi.json`, `frontend/src/api/schema.d.ts`, or
    a committed migration. Regenerate the client with `uv run wl gen-client`; fix a
    committed migration with a new one. They also can't change `.pre-commit-config.yaml`, which
    is yours to edit (DL-30; the git guard blocks any redirect naming it too), or git's own files:
    anything in `.git/`, `~/.gitconfig`, or `.config/git/` (DL-31).
  - After Claude edits a file, it is formatted with the backend's ruff (backend), the developer
    CLI's ruff (`tools/cli/` and `.claude/hooks/`, as `wl lint` checks them), or Prettier
    (frontend).
  - The **git guard** (`guard_git.py`) is an allow-list (DL-26). A Bash call that involves git or gh
    must be **one command in a listed form, and nothing else**: no `&&`, `;`, `|`, `cd`, variables,
    `$(...)`, `bash -c`, or environment prefixes. Use `git -C <path>` for another directory, and
    `git commit -F - <<'EOF'` for a commit message: the delimiter must be quoted, since an unquoted
    heredoc runs the `$(...)` and backticks in its body. Anything else that mentions git or gh is
    blocked; ask the owner to run it (`! <command>` in the prompt). Git or gh appearing only as data
    is fine, in a command that only reads and prints (`grep`, `cat`, `ls`, `head`, `tail`, `wc`,
    `echo`, `diff`, `jq`, …; not `sort -o`, `uniq`, `rg --pre`, a pager, or
    `test`/`[`/`[[`/`printf`, which can evaluate a `$(...)` in an array subscript) and with no
    expansion anywhere (`$VAR`, `${…}`, `$(...)`, backticks), since an expansion can hide a command
    (`${x:-$(cmd)}`). A call that mentions git may not redirect into `.git/` (its config or hooks),
    into a git config file (`~/.gitconfig`, `~/.config/git/`), or to a file named only at run time
    (DL-24); no call, git or not, may redirect to a target with an unquoted glob (`*`, `?`, `[`),
    which bash expands to an existing file such as `.git/config`, or naming
    `.pre-commit-config.yaml`, an input redirect too (DL-30). A call that doesn't mention git may
    still build a target with an expansion (TD-20). Aliases aren't followed: only the listed
    subcommands run. Allowed:
    - Reads, each with only its listed options (`tools/cli`'s tests and `READ_ONLY` in the hook
      list them; e.g. `log --oneline -5 --format=… --since=…`, `diff --stat --cached -U3`,
      `grep -n -i -A3`): `status`, `log`, `diff`, `show`, `rev-parse`, `ls-files`, `ls-tree`,
      `blame`, `grep`, `merge-base`, `rev-list`, `cat-file`, `describe`, `shortlog`, and
      `hash-object <file>` with no options (DL-29; `-w` would write an object). An option
      that runs a program or writes a file (`grep -O<cmd>`, `--output=<file>`, `--ext-diff`,
      `--textconv`) isn't listed. Also `branch` (`--show-current`, or `-a`/`-r`/`-v`/`-vv` with
      `--list <pattern>`), `remote [-v]`, and `config --get <key>`, `config get <key>`,
      `config --list`/`-l`/`list`.
    - Local changes: `add` (`-A`, `-u`, `-N`, paths), `rm` (`-r`, `--cached`, paths), `mv`,
      `restore` (`--staged`, `--worktree`, paths), `checkout -- <paths>`, `stash`
      (`push [-u] [-m <message>]`, `pop`, `drop`, `apply`, `list`, `show`), `fetch [--prune]
      [<remote> [<branch>]]`.
    - Branches: `switch <branch>`, `switch -c <new branch>` (not `main`).
    - `commit` with `-m <message>`, `-F <file>`, `-F -` (a heredoc), `-a`, `-q`, `--allow-empty`,
      `--no-edit`, `--amend`: off `main` only (DL-21); `--amend` only while HEAD is unpushed
      (DL-23).
    - `push [-u] <remote> <branch>` with a literal branch other than `main`, or a bare `push` off
      `main` whose push destination (`@{push}`) isn't `main` (DL-22). No other push option, so
      nothing forces, deletes, or skips hooks (DL-23, DL-24). Configuration that redirects a push
      isn't checked: GitHub refuses any push to `main`, force-push, or deletion it could cause
      (DL-27, DL-28).
    - `reset`: paths (`[HEAD] -- <paths>`), or `[--soft|--mixed|--hard] [<commit>]` that drops
      no pushed commit (DL-23) and, on `main`, only to `main` itself: a target that git resolves
      to `refs/heads/main` or a remote's `main` (DL-21).
    - `pull --ff-only [<remote> <branch>]`; on `main`, only from a configured remote's `main` (a
      path to another repository isn't a remote; a bare pull needs `main`'s upstream to be a
      remote's `main`) (DL-21).
    - `merge`, `rebase`, `cherry-pick`, `revert`, `am`: `--abort` only.
    - gh: `pr create`/`view`/`list`/`checks`/`diff`/`status`/`ready`/`edit`, `run
      list`/`view`/`watch`, `auth status` (no options: `--show-token` prints the token), `repo
      view`, `issue list`/`view`, and `gh api` reads. `gh pr merge`, and any other `gh api` call (a
      method, a field, an input file, GraphQL), asks you first (DL-25).
  - Every allowed git form, reads included, is run against real git by its tests: each runs in a
    throwaway clone with a bare remote, and the test asserts exactly which refs and config lines it
    changes. (The gh forms are tested against the guard only.) What it can't see is logged in TD-20:
    a script or program that runs git itself, a write to a shell startup file, and a non-git
    redirect target built by an expansion. Its tests,
    and the other hooks', are in `tools/cli/tests/hooks/`. All three hooks, and the
    `hook_paths.py` helpers they share, are linted, formatted, type-checked, and tested with the
    developer CLI (`wl lint`, `wl test`).
- Type `/hooks` in Claude Code to see the active hooks. To turn hooks off temporarily on your
  own machine, set `"disableAllHooks": true` in `.claude/settings.local.json` (not committed).

## 12. Troubleshooting

| Symptom | Fix |
|---|---|
| `wl e2e` fails with Chromium exiting 127, or `error while loading shared libraries: libnspr4.so` | Chromium's system libraries are missing: `cd frontend && sudo env "PATH=$PATH" npx playwright install-deps chromium`. Plain `sudo npx …` says `npx: command not found`, because sudo resets `PATH`. |
| `warning: VIRTUAL_ENV=… does not match the project environment path` | Harmless when running `uv run` inside `backend/` from an activated root venv; `wl` strips `VIRTUAL_ENV` for its subprocesses. Deactivate the root venv or use `wl`. |
| `wl doctor`: Docker daemon not reachable | Start Docker Desktop (with WSL integration on Windows) or `sudo service docker start`. |
| `wl doctor`: Python 3.14 not found by uv | `uv python install 3.14` |
| `uv lock --check` fails in `wl check` | A `pyproject.toml` changed without relocking: run `uv lock` in that project (root or `backend/`) and commit the lockfile. |
| `wl check` reinstalls pytest/ruff/pyright in the root venv, or they're missing | A plain `uv sync` at the root installs only the root's own dependencies and removes the CLI's dev tools. Use `uv sync --all-packages`. (`uv run` adds missing packages back on its own.) |
| Tests stop with "Can't reach the test database" | Start the stack: `uv run wl up`. If it says `database "waterline_test" does not exist`, the volume predates the init script: `uv run wl down -v && uv run wl up`. |
| `wl up`: port 5432 is already allocated | Another Postgres is running. Set `POSTGRES_PORT` in `.env` (e.g. 5433) and rerun `wl up`. The same goes for 8000 (`API_PORT`) and 5173 (`WEB_PORT`). |
| `wl up` fails with `service "migrate" didn't complete successfully` | A migration failed: `docker compose logs migrate` shows why. Fix it (with a new migration if the failing one is committed) and rerun `wl up`. |
| `wl up`: the `web` build fails at `npm ci` | `frontend/package-lock.json` doesn't match `package.json`: run `npm install --prefix frontend` and commit the lockfile. |
| `npm ci` on the host fails with `EACCES` in `frontend/node_modules` | The folder was created as root by a `wl up` from before the dev containers ran as you (TD-11): `sudo rm -rf frontend/node_modules && npm ci --prefix frontend`. |
| `wl check` fails at `openapi_export --check` or `check:client` | The API changed without regenerating the client: `uv run wl gen-client` and commit `backend/openapi.json` and `frontend/src/api/schema.d.ts`. |
| The status page (`/status`) says "Could not reach the server" | The API isn't running or reachable from Vite: `wl logs api`; for a host-run Vite, check `API_PROXY_TARGET`. |
| A job change has no effect | The `worker` doesn't reload: `docker compose restart worker`. |
| `wl up`: `set POSTGRES_DB in .env` | No `.env` yet: `cp .env.example .env`. |
| The API fails at startup with a validation error for `postgres_user` | No `.env` (or the variables aren't set): `cp .env.example .env`. |
| `MissingGreenlet` when reading `created_at`/`updated_at` | The model replaced `__mapper_args__` without keeping `eager_defaults`; merge `TimestampMixin.__mapper_args__` (see "Models"). The convention checks catch this. |
| `InvalidRequestError: 'Task.subtasks' is not available due to lazy='raise'` | The repository didn't load that relationship; add `selectinload(Task.subtasks)` to its query. |
| A versioned model never raises `StaleDataError` | `VersionMixin` is listed after `BaseModel`/`TimestampMixin`; list it first. The convention checks catch this. |
| `ForeignKeyViolation` flushing a new parent and child together | No `relationship()` between them, so the child may be inserted first; flush the parent first. |
| The worker logs `TaskNotFound` | The job's module isn't imported in `app/jobs/tasks/__init__.py`, or its name differs from the one in `task_names.py`. |
| CI fails at the docs consistency tests with "git history is shallow" | The checkout lost `fetch-depth: 0`; restore it in `.github/workflows/ci.yml`. |
| CI fails at "Install dependencies" (`--locked`) | A `pyproject.toml` or `package.json` changed without its lockfile: run `uv lock` (root or `backend/`) or `npm install --prefix frontend`, and commit the lockfile. |
| `ModuleNotFoundError: No module named 'app'` in tests | Run pytest from `backend/` (or through `wl`); `pythonpath` is set in `backend/pyproject.toml`. |
