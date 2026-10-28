---
name: new-area
description: Use when adding a new Waterline aggregate (a new entry in the build plan's feature map, e.g. requirement, task, testcase) through every layer, or when adding an endpoint or authorization action to an existing area. Not for schema-only changes (use migration) or tests alone (use test-writer).
---

# Adding an area (and endpoints within one)

Verified against the hand-built `project` area in S2-C0c (DL-132). The `project` area is the
reference implementation: open its file in each layer before writing the new one.

Architecture and naming: `docs/build-plan.md` ("Backend architecture", "Feature map").
Conventions: `backend/CLAUDE.md`, `frontend/CLAUDE.md`, design-doc §3–§5 and §10.

## 0. Scope

- Find the area's row in the feature map: its file name, the tables it owns, and the services
  it may call. If it isn't there, stop and raise it with the owner.
- Find the area's layer in the build plan's service layer order; a new area goes in the lowest
  layer that is above everything it calls.
- Read the design-doc sections and schema-doc tables for the area.
- List the actions it needs (`view`, `create`, `update`, `delete`, `restore`, plus targeted
  actions such as transitions or reorder) and the roles allowed for each, from the design doc.
- Read the build plan's "API conventions" and follow them in every step below: list paging, sorting,
  and declared filters through a `ListSpec` (`app/core/lists.py`; unknown query parameters → 422);
  constraint errors through the registry (`info=user_error(...)` or `internal_only()` on every
  unique constraint, `app/core/constraint_errors.py`); `allowed_actions` on single-entity reads;
  identifiers (key and number for project items, UUIDs otherwise, `id` in every response);
  `useListQuery` on the frontend.

## 1. Model — `models/<area>.py`

- Base model and the mixins the schema doc calls for (soft delete, `version`,
  `RestrictionMixin`).
- Enums through the enum helper; relationships `lazy="raise"`.
- Human-readable numbers: an `int number` column with `UNIQUE(project_id, number)`; never
  computed here.

## 2. Migration

Follow the `migration` skill.

## 3. Schemas — `schemas/<area>.py`

- `<Area>Create`, `<Area>Update`, `<Area>Read`, and the list row, `<Area>Item`
  (`ProjectItem`).
- Every free-text request field has its DL-143 limit, `Field(max_length=...)` from
  `app/schemas/limits.py`, with the schema doc saying so.
- **Create/Update never accept server-owned or immutable fields**: `id`, `number`, `rank`,
  `project_id` (or `task_id` for subtasks), `reporter_id` on create, `deleted_at`, timestamps,
  approval fields. Rank changes go through a reorder endpoint that takes neighbor IDs.
- Versioned entities: `version` is in `<Area>Read` and required in `<Area>Update`, so a stale
  save returns 409.
- Read schemas never expose secrets (`hashed_password`, `token_hash`) and only read
  relationships the repository loaded.

## 4. Repository — `repositories/<area>.py`

- A plain class taking the session (`ProjectRepository(session)`), using the shared helpers in
  `repositories/base.py` (`get_by_id`, `direct_update`, `scope_clause`); add methods only for
  non-trivial queries. A list query is a method returning a `Select` for a `ListSpec`
  (`ProjectRepository.candidates`).
- Every lookup is access-scoped: only projects (and orgs) the caller can see (design-doc §4,
  "Visibility"). Lookups by URL use `(project key, number)` within an accessible project, never
  a bare number.
- Load explicitly what each use needs (`selectinload`/`joinedload`).
- Soft-deleted rows are hidden unless the query opts in (trash/restore only).

## 5. Rules and authorization — `rules/<area>.py`, `authz/actions.py`

- Pure logic (transition tables, policy decisions) goes in `rules/`, with no database access.
- Register every action explicitly in the one registry, `authz/actions.py` (DL-151), marked
  content or management (design-doc
  §3.1, §5), and marked personal where the right comes from the user's relationship to the item
  (e.g. `approval.decide`); unknown actions are denied.
- **Test first**, written by the `spec-test-writer` agent against your stubs (`test-writer`
  skill, section 4): the full action × role matrix from the design doc,
  across project, org, and workspace roles (including inherited project admin), users with no
  access, and system admins, allowed and denied rows, and the targeted rules (reporter,
  assignee, reviewer, approval-state conditions); personal-action rows (every admin level
  denied, and the relationship without content access to the project denied: on an
  export-controlled project, without an explicit membership) and, from Slice 2 (when the gate
  exists), export-control rows (inherited admins denied content on an export-controlled
  project). Then implement.
- Archived projects are read-only; module-gated areas pass `module=` to the load-and-authorize
  dependency (`authorized(loader, action, module=...)`), which returns 404 for a disabled module
  before `authorize()` (DL-47).

## 6. Service — `services/<area>.py`

- Every mutation in this order: `authorize()` → change → `log_change()`; the request
  dependency commits. The service never commits (`flush()` only when it needs generated
  values).
- Numbers only from the numbering service; rank, counters, an item's restriction, a move's
  parent change, and a new item's first revision pointer only through the direct-update helper
  (no `version` bump, so a new item starts at `version` 1; DL-168, DL-207, DL-214).
- An item's restriction level is null or at least the project's: a lower one is a 422
  `validation_error` of type `below_project` on the level field (DL-208). Raising a project's
  level lifts this item type's live rows stored below the new level (register a handler with
  `register_on_restriction_changed()` in `services/project.py`, as the requirement area does;
  no `include_deleted`),
  each logged, with `direct_update(..., touch_updated_at=False)`; restoring a row stored below
  its project's level raises it to the project's level, logged by the restoring user, and moves
  its `updated_at` (DL-209, DL-210).
- Check that every referenced entity (parent, phase, sprint, milestone, workstream, requirement)
  belongs to the same project; check cycles where the design calls for it.
- `log_change()` for every logged field in design-doc §10, with enum members.
- Writes to another area's tables go through that area's service. Services call services in
  **lower layers only** (the build plan's service layer order), one way and never in a cycle;
  never a service in the same layer or a higher one. Anything that needs to reach upward uses a
  registered handler, as the approval service does.
- Add the new service module to the import-linter layers contract in `backend/pyproject.toml`
  (in its layer, as an optional `(module)` entry) if it isn't listed there already.
- An update to an entity **without** `version` goes through `apply_changes`
  (`app/audit/admin_event.py`): it locks and re-reads the row, sets what differs, and flushes, so
  the event's old values are true under concurrent edits (TD-57); validate before it, log what it
  returns. A versioned entity never uses it (its re-read would reload `version` and defeat the
  409): it calls `check_version` and lets the ORM's version check refuse a stale save.
- A one-field 422 is `ValidationFailedError.on(loc, message, type)`.
- Stale saves raise the optimistic-locking error that maps to 409.

## 7. Router — `routers/<area>.py`

- Thin: validate input, resolve user and session, call one service method, return a response
  schema.
- URLs nested under the project with human-readable IDs:
  `/api/projects/{key}/<areas>/{number}`.
- Single-entity endpoints use the load-and-authorize dependency
  (`Annotated[ProjectEntity, Depends(authorized(load_project, Action.PROJECT_VIEW))]`), so there
  is no way to get the entity without the check; list endpoints use the access-scoping helper
  (`project_scope`). Invisible entities return **404**, never 403.
- Every endpoint documents its error responses with `responses=ERRORS` (`routers/deps.py`).
- Module-gated areas pass `module=` to `authorized(...)` (DL-47).
- Register the router in `main.py`.

## 8. Factory — `tests/factories/<area>.py`

One factory per model, creating valid required parents (project, org) unless given them.

## 9. Tests

Follow the `test-writer` skill. The minimum for a new area:
- authorization matrix (unit) plus wiring tests (API) for each action;
- service rules, including same-project checks and cycle checks;
- `log_change()` entries for each logged field;
- soft delete and restore, including who may restore;
- 409 on a stale `version`; 422 on invalid input with field errors;
- 404 for every endpoint for a user with no access: in another org, in the same org but not on
  the project, or a workspace member not assigned to it;
- numbering: first number, sequence, never reused after delete.

## 10. Frontend

- `uv run wl gen-client` (never hand-edit `schema.d.ts`).
- Screens in `frontend/src/views/<area>/`, following `frontend/CLAUDE.md`: generated client
  only, 409/404/422 handling, labels from the mapping module, actions hidden (not enforced) by
  permission.
- Component tests; add a Playwright test only if the flow is in the slice's "Done when" list.

## 11. Docs

- `docs/user-guide.md`: how to use the feature.
- `docs/developer-guide.md`: only if the area introduced a new pattern.
- Schema doc via the `migration` skill; design doc only for approved changes.
- `docs/build-plan.md` feature map, if calls-into or ownership changed.

---

## Adding an endpoint or action to an existing area

Use steps 3 and 5–10 only: schema for the request/response, the action registered and its
matrix rows written first, the service method, the router endpoint with the load-and-authorize
dependency, tests (including a wiring test and the no-access 404s), `wl gen-client`, and the user
guide.
