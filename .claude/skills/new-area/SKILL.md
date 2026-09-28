---
name: new-area
description: Use when adding a new Waterline aggregate (a new entry in the build plan's feature map, e.g. requirement, task, testcase) through every layer, or when adding an endpoint or authorization action to an existing area. Not for schema-only changes (use migration) or tests alone (use test-writer).
---

# Adding an area (and endpoints within one)

> **Status: draft.** Written before Slice 1 from the design docs. At the start of Slice 2,
> verify every step against the hand-built `project` area and correct this skill wherever they
> differ. After that, the `project` area is the reference implementation: open its file in each
> layer before writing the new one.

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

## 1. Model — `models/<area>.py`

- Base model and the mixins the schema doc calls for (soft delete, `version`).
- Enums through the enum helper; relationships `lazy="raise"`.
- Human-readable numbers: an `int number` column with `UNIQUE(project_id, number)`; never
  computed here.

## 2. Migration

Follow the `migration` skill.

## 3. Schemas — `schemas/<area>.py`

- `<Area>Create`, `<Area>Update`, `<Area>Read`, `<Area>ListItem`.
- **Create/Update never accept server-owned or immutable fields**: `id`, `number`, `rank`,
  `project_id` (or `task_id` for subtasks), `reporter_id` on create, `deleted_at`, timestamps,
  approval fields. Rank changes go through a reorder endpoint that takes neighbor IDs.
- Versioned entities: `version` is in `<Area>Read` and required in `<Area>Update`, so a stale
  save returns 409.
- Read schemas never expose secrets (`hashed_password`, `token_hash`) and only read
  relationships the repository loaded.

## 4. Repository — `repositories/<area>.py`

- Extend the base repository; add methods only for non-trivial queries.
- Every lookup is org-scoped. Lookups by URL use `(project key, number)` scoped to the caller's
  org, never a bare number.
- Load explicitly what each use needs (`selectinload`/`joinedload`).
- Soft-deleted rows are hidden unless the query opts in (trash/restore only).

## 5. Rules and authorization — `rules/<area>.py`, `authz/policies/<area>.py`

- Pure logic (transition tables, policy decisions) goes in `rules/`, with no database access.
- Register every action explicitly in the policy; unknown actions are denied.
- **Test first** (`test-writer` skill): the full action × role matrix from the design doc,
  including non-members and system admins, allowed and denied rows, and the targeted rules
  (reporter, assignee, reviewer, approval-state conditions). Then implement.
- Archived projects are read-only; module-gated areas are checked by the module dependency
  before `authorize()`.

## 6. Service — `services/<area>.py`

- Every mutation in this order: `authorize()` → change → `log_change()`; the request
  dependency commits. The service never commits (`flush()` only when it needs generated
  values).
- Numbers only from the numbering service; rank and counters only through the direct-update
  helper (no `version` bump).
- Check that every referenced entity (parent, phase, sprint, milestone, workstream, requirement)
  belongs to the same project; check cycles where the design calls for it.
- `log_change()` for every logged field in design-doc §10, with enum members.
- Writes to another area's tables go through that area's service. Services call services in
  **lower layers only** (the build plan's service layer order), one way and never in a cycle;
  never a service in the same layer or a higher one. Anything that needs to reach upward uses a
  registered handler, as the approval service does.
- Add the new service module to the import-linter layers contract in `backend/pyproject.toml`
  (in its layer, as an optional `(module)` entry) if it isn't listed there already.
- Stale saves raise the optimistic-locking error that maps to 409.

## 7. Router — `routers/<area>.py`

- Thin: validate input, resolve user and session, call one service method, return a response
  schema.
- URLs nested under the project with human-readable IDs:
  `/api/projects/{key}/<areas>/{number}`.
- Single-entity endpoints use the load-and-authorize dependency, so there is no way to get the
  entity without the check; list endpoints use the org-scoping helper. Invisible entities
  return **404**, never 403.
- Module-gated areas add the module dependency.
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
- cross-org 404 for every endpoint;
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
dependency, tests (including a wiring test and a cross-org 404), `wl gen-client`, and the user
guide.
