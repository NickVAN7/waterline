# Frontend rules

Vue 3 (Composition API, `<script setup lang="ts">`), TypeScript (strict), Vite, Vue Router,
Pinia, Vitest + Vue Test Utils, Playwright (from Slice 1).

## Layout

- `src/api/` — `schema.d.ts` (generated) and `client.ts`: the configured `openapi-fetch`
  `client`, `api()`, and `ApiError`
- `src/app/` — `createApp.ts` (the app the tests and `main.ts` both build), layouts, router,
  route focus, the session hook; route guards in `src/app/guards/`
- `src/app/styles/` (`tokens.css`, `base.css`), `src/app/theme/` (`preset.ts`, and, once a board
  or grid ships, `svar-theme.css`)
- `src/components/` — shared UI components
- `src/composables/` — shared logic (auth state, permissions, forms)
- `src/stores/` — Pinia stores (current user, current org)
- `src/views/<area>/` — screens, grouped by the same area names as the backend, singular
  (`project/`, `task/`, …); `status/` and `errors/` aren't backend areas
- `src/test/` — shared test helpers: `a11y.ts` (`expectNoA11yViolations`), `api.ts` (typed
  responses), `router.ts`
- `e2e/` — Playwright tests; `e2e/support/` holds their helpers (`a11y.ts`: axe and
  `expectFocusNotObscured`; `demo.ts`: the demo users)

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
  reload; 404 → not-found view (TD-32); 422 → field errors from `details.fields`
  (`loc`, `message`, `type` per field). Forms use `useFormErrors` for all of this. A 401 and a
  403 `password_change_required` are handled once, by the API client's session hook
  (`src/app/session.ts`); a view never handles them itself.
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
  shown only after about 300 ms (fast loads don't flash), on a region with `aria-busy="true"`,
  with any shimmer off under `prefers-reduced-motion`. Actions such as saving a form show a
  pending state on the control itself, not a skeleton.
- An enabled module whose slice hasn't shipped yet (`sprints`, `github` before Slices 4 and 7)
  shows its features and links greyed out or disabled (design-doc §1.1), never as broken
  screens. Whether a module is available comes from the API's module guidance (`available`),
  never a frontend list.

## UI

Full rules and rule IDs: `docs/ui-design-guide.md`. The ones that break silently:

- Tokens only: colors, type sizes, radii, and sizes come from `src/app/styles/tokens.css`,
  through Tailwind utilities or `var(--…)`. No hex, `rgb()`, or `px` literals (`0` and 1 px
  borders are fine), and no Tailwind arbitrary values like `p-[13px]` (UI-STY-1). Spacing is Tailwind's built-in scale.
- PrimeVue colors are set only in `src/app/theme/preset.ts`. Never override them in a component
  or with `!important` (UI-STY-2, UI-TOK-12). Native elements first; never hand-roll a focus
  trap or ARIA state (UI-STY-3). No new UI dependency without a design change (UI-STY-5).
- SVAR (board, editable grid, later Gantt): imported only inside its wrapper component; MIT
  `@svar-ui/*` only, exact versions; `<Willow :fonts="false">`; its colors are set only in
  `svar-theme.css`; every move or edit goes through `api.intercept` so the server decides; the
  move alternative to a drag is our own menu outside the widget (UI-STY-7, UI-SVR-1 to 6).
- Never color alone: a badge is icon + text + tone from the display-mapping module
  (UI-FBK-5); a selected row also has a checked box and a leading bar (UI-TOK-9).
- Forms: visible labels; the server validates; a 422 shows inline errors, moves focus to the
  first invalid field, and has no summary box; a required field has the red asterisk; the submit
  button is `aria-disabled` while pending, never `disabled` (UI-FRM-2, UI-FRM-4 to 8).
- Actions: hide what a user may never do (`allowed_actions`); disable with a visible reason what
  state blocks; never use opacity for disabled (UI-TOK-10).
- An error is never only in a toast. A toast never takes focus or covers the focused element
  (UI-FBK-1, UI-FBK-9, UI-FBK-10). An alert that reports an event has a dismiss button; a
  persistent banner does not (UI-FBK-13).
- A 404 looks identical whether the thing is missing or not visible to the user (UI-FBK-14).
- Loading: a skeleton after about 300 ms with `aria-busy`; a pending action shows on its
  control (UI-FBK-11, UI-FRM-8).
- On navigation set the page title and focus the `h1`; one `h1` per page (UI-SHL-9).
- Targets at least 24×24 px; focus ring from `--color-focus`, never `outline: none` (UI-TOK-5,
  UI-TOK-6).
- A new color pair is added to `check_contrast.py` in the same change (UI-TOK-3).
- Password fields allow paste, set `autocomplete`, and have no `maxlength` (UI-FRM-10).
- Every new view and component spec calls `expectNoA11yViolations()`; end-to-end flows run axe
  in both themes (guide §9).

## Tests

- Component and composable tests with Vitest, in a `*.spec.ts` next to the code; mock only the
  API client (`vi.spyOn(client, 'GET')`), with results typed from the generated schema. Assert
  what the user sees, not component internals.
- Coverage: 80% overall; 90% for composables, stores, and route guards.
- Whatever `createApp.ts` wires up (a plugin, the client's middleware, the session handler) has a
  test through `createWaterlineApp()` in `src/app/router.spec.ts`: unit tests of each piece don't
  show they're connected. Wait for a navigation to a lazy-loaded route with `vi.waitFor`, not
  `flushPromises`.
- Playwright covers each slice's critical flows against the full stack (`wl e2e`), in the
  `light` and `dark` projects. Find fields with `getByRole('textbox', { name, exact: true })`,
  not `getByLabel`: the label's text includes the required asterisk, the accessible name
  doesn't.
