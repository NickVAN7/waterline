# Frontend rules

Vue 3 (Composition API, `<script setup lang="ts">`), TypeScript (strict), Vite, Vue Router,
Pinia, Vitest + Vue Test Utils, Playwright (from Slice 1).

## Layout

- `src/api/` — `schema.d.ts` (generated) and `client.ts`: the configured `openapi-fetch`
  `client`, `api()`, and `ApiError`
- `src/app/` — layout, router, styles; route guards in `src/app/guards/`
- `src/components/` — shared UI components
- `src/composables/` — shared logic (auth state, permissions, forms)
- `src/stores/` — Pinia stores (current user, current org)
- `src/views/<area>/` — screens, grouped by the same area names as the backend, singular
  (`project/`, `task/`, …); `home/` and `errors/` aren't backend areas
- `e2e/` — Playwright tests

## Rules

- **All API calls go through the generated client:** `await api(client.GET('/api/...'))`.
  `api()` returns the data or throws an `ApiError` (`status`, `code`, `message`, `details`;
  `code` is `network_error` or `unexpected_response` when there's no standard body). Never
  hand-write API types, call `fetch`, or import `openapi-fetch` outside `src/api/` (ESLint
  enforces the last two). After any backend API change, run `wl gen-client`; never edit
  `schema.d.ts` by hand.
- **The server is authoritative.** The UI may hide actions a user can't take, but never assumes
  it's enforcing permissions. Don't duplicate business rules; e.g. rank is computed by the
  server (send neighbor IDs, not rank values), and transitions are validated by the server.
- **Handle the error format** (`{code, message, details}`) consistently: 409 → prompt to
  reload; 404 → not-found view; 422 → field errors from `details.fields`
  (`loc`, `message`, `type` per field).
- **Requests:** same origin through the Vite proxy (`/api`), `credentials: 'include'`, JSON
  bodies only.
- **Rendered markdown** is sanitized before display.
- **Routes:** add new routes above the catch-all not-found route in `src/app/router.ts`; it
  must stay last.
- **Display labels** for stored values (e.g. task type per project type) come from one mapping
  module, never inline strings.
- UI guidance text (e.g. module recommendations) is rendered from the API response, not
  hard-coded.
- **Accessibility: WCAG 2.2 AA** (design-doc §1). Every drag has a single-pointer alternative
  (menu actions; on the board, the card's status control); status, RAG, and badges never rely on
  color alone (always text or an icon too); controls are at least 24×24 CSS pixels; sticky
  headers and toasts never cover the focused element; password fields allow paste and password
  managers. axe-core checks run in component and end-to-end tests and fail on any violation.
- **Loading states are skeleton loaders, not spinners:** an outline of the content's layout,
  shown only after about 200 ms (fast loads don't flash), on a region with `aria-busy="true"`,
  with any shimmer off under `prefers-reduced-motion`. Actions such as saving a form show a
  pending state on the control itself, not a skeleton.
- An enabled module whose slice hasn't shipped yet (`sprints`, `github` before Slices 4 and 7)
  shows its features and links greyed out or disabled (design-doc §1.1), never as broken
  screens. Whether a module is available comes from the API's module guidance (`available`),
  never a frontend list.

## Tests

- Component and composable tests with Vitest, in a `*.spec.ts` next to the code; mock only the
  API client (`vi.spyOn(client, 'GET')`), with results typed from the generated schema. Assert
  what the user sees, not component internals.
- Coverage: 80% overall; 90% for composables, stores, and route guards.
- Playwright covers each slice's critical flows against the full stack.
