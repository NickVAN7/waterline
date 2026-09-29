# Frontend rules

Vue 3 (Composition API, `<script setup lang="ts">`), TypeScript (strict), Vite, Vue Router,
Pinia, Vitest + Vue Test Utils, Playwright (from Slice 1).

## Layout

- `src/api/` — `schema.d.ts` (generated) and the configured `openapi-fetch` client
- `src/app/` — layout, router, route guards
- `src/components/` — shared UI components
- `src/composables/` — shared logic (auth state, permissions, forms)
- `src/stores/` — Pinia stores (current user, current org)
- `src/views/<area>/` — screens, grouped by the same area names as the backend (`projects/`,
  `tasks/`, …)
- `e2e/` — Playwright tests

## Rules

- **All API calls go through the generated client.** Never hand-write API types or call `fetch`
  directly. After any backend API change, run `wl gen-client`; never edit `schema.d.ts` by hand.
- **The server is authoritative.** The UI may hide actions a user can't take, but never assumes
  it's enforcing permissions. Don't duplicate business rules; e.g. rank is computed by the
  server (send neighbor IDs, not rank values), and transitions are validated by the server.
- **Handle the error format** (`{code, message, details}`) consistently: 409 → prompt to
  reload; 404 → not-found view; 422 → field errors from `details.fields`
  (`loc`, `message`, `type` per field).
- **Requests:** same origin through the Vite proxy (`/api`), `credentials: 'include'`, JSON
  bodies only.
- **Rendered markdown** is sanitized before display.
- **Display labels** for stored values (e.g. task type per project type) come from one mapping
  module, never inline strings.
- UI guidance text (e.g. module recommendations) is rendered from the API response, not
  hard-coded.
- An enabled module whose slice hasn't shipped yet (`sprints`, `github` before Slices 4 and 7)
  shows its features and links greyed out or disabled (design-doc §1.1), never as broken
  screens. Whether a module is available comes from the API's module guidance (`available`),
  never a frontend list.

## Tests

- Component and composable tests with Vitest; mock only the API client, typed with the generated
  types.
- Coverage: 80% overall; 90% for composables, stores, and route guards.
- Playwright covers each slice's critical flows against the full stack.
