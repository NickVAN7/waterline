# Frontend rules

Vue 3 (Composition API, `<script setup lang="ts">`), TypeScript (strict), Vite, Vue Router,
Pinia, Vitest + Vue Test Utils, Playwright (from Slice 1).

## Layout

- `src/api/` — `schema.d.ts` (generated) and `client.ts`: the configured `openapi-fetch`
  `client`, `api()`, and `ApiError`
- `src/app/` — `createApp.ts` (the app the tests and `main.ts` both build), layouts (`AppLayout`
  is the shell), router, route focus, the session hook, `labels.ts` (display labels); the shell's
  parts in `src/app/shell/`; route guards in `src/app/guards/`
- `src/app/styles/` (`tokens.css`, `base.css`), `src/app/theme/` (`preset.ts`, and, once a board
  or grid ships, `svar-theme.css`)
- `src/components/` — shared UI components
- `src/composables/` — shared logic (auth state, permissions, forms)
- `src/stores/` — Pinia stores (current user, current org)
- `src/views/<area>/` — screens, grouped by the same area names as the backend, singular
  (`project/`, `task/`, …); `status/` and `errors/` aren't backend areas
- `src/test/` — shared test helpers: `a11y.ts` (`expectNoA11yViolations`), `api.ts` (typed
  responses), `projects.ts`, `overlay.ts` (`stubResizeObserver`, `stubDialog`), `router.ts`,
  `workspace.ts` (`mountWorkspaceView`, `mountSignedIn`), `org.ts` (`mountOrgView`, `mountOrgPages`)
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
  server (send neighbor IDs, not rank values), and transitions are validated by the server. Two
  exceptions: the `PasswordRequirements` list checks the requirements the server publishes as the
  user types (DL-91), and the add-person flow checks an email's shape before its user check
  (`useFormErrors`' `invalidate`; UI-FRM-4, UI-FRM-13).
- **Handle the error format** (`{code, message, details}`) consistently: 409 → prompt to
  reload; 404 → `NotFoundView` in place (see `ProjectHomeView`); 422 → field errors from `details.fields`
  (`loc`, `message`, `type` per field). Forms use `useFormErrors` for all of this. A 401 and a
  403 `password_change_required` are handled once, by the API client's session hook
  (`src/app/session.ts`); a view never handles them itself.
- **Requests:** same origin through the Vite proxy (`/api`), `credentials: 'include'`, JSON
  bodies only.
- **Rendered markdown** goes only through `MarkdownView` (from S2-C16): `markdown-it` with raw
  HTML off, then DOMPurify; never `v-html` on anything else. No remote images, links only
  `http`/`https`/`mailto`; the API carries only the markdown (design-doc §3, DL-140;
  ui-design-guide UI-MD-1).
- **Routes:** add new routes above the catch-all not-found route in `src/app/router.ts`; it
  must stay last. An org page (`/:orgSlug/…`) finds its org with `useRouteOrg`, which follows a
  slug change to the new URL; a null org is the not-found page.
- **Display labels** for stored values (e.g. task type per project type) come from one mapping
  module, `src/app/labels.ts`, never inline strings.
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
- A module whose slice hasn't shipped yet (`sprints`, `github` before Slices 4 and 7) can't be
  enabled (from S2-C0d, DL-136; design-doc §1.1): the API refuses it (422 `module_unavailable`)
  and the UI shows a disabled checkbox with "Not available yet", never a broken screen. Whether
  a module is available comes from the API's module guidance (`available`), never a frontend
  list.

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
- Actions: hide what a user may never do (`allowed_actions`, which also leaves out what the
  entity's state rules out for good, DL-232); disable with a visible reason what state blocks; never use opacity for disabled (UI-TOK-10).
- An error is never only in a toast. A toast never takes focus or covers the focused element
  (UI-FBK-1, UI-FBK-9, UI-FBK-10). An alert that reports an event has a dismiss button; a
  persistent banner does not (UI-FBK-13).
- Announcements: an alert for a new event is a new element (key it on `useFormErrors`'
  `alertKey`); a repeated live message is cleared and set again after `ANNOUNCE_DELAY_MS`; Retry
  focuses the control whose action failed before repeating it; a landmark with nothing in it
  isn't rendered (UI-FBK-2, UI-FRM-6, UI-FRM-7, UI-SHL-2; DL-93).
- A 404 looks identical whether the thing is missing or not visible to the user (UI-FBK-14).
- Loading: a skeleton after about 300 ms with `aria-busy`; a pending action shows on its
  control (UI-FBK-11, UI-FRM-8).
- On navigation set the page title and focus the `h1`; one `h1` per page (UI-SHL-9).
- Targets at least 24×24 px; focus ring from `--color-focus`, never `outline: none` (UI-TOK-5,
  UI-TOK-6).
- A new color pair is added to `check_contrast.py` in the same change (UI-TOK-3).
- Password fields allow paste, set `autocomplete`, and have no `maxlength`. A field where users
  choose their own new password has the `PasswordRequirements` list under it, built from `GET
/api/auth/password-policy`, never from numbers in the code (UI-FRM-10, DL-91).
- Every new view and component spec calls `expectNoA11yViolations()`; end-to-end flows run axe
  in both themes (guide §9).
- Overlays: a popover moves focus into itself when it opens (the filter, the current link, or the
  first, once loaded content has rendered): it sits at the end of `<body>`, so Tab from its
  button never reaches it. A PrimeVue menu's active item (`.p-focus`) gets the focus ring
  (`base.css`). Their e2e tests open them with the keyboard and assert which element has focus.
- A form alert's Retry never calls the submit directly: it goes through `retryFromSubmit`
  (`useFormErrors`), which focuses the submit button first, since the alert holding Retry goes
  as the action restarts (UI-FRM-7; S1-C15 review).
- Row menu items come only from `allows(row, …)`; never compare a row's id with the signed-in
  user's to decide an action (S1-C15 review). The one logged exception is the reset on your own
  row (TD-42).
- A dialog whose action navigates away (Create project opens the new project) closes with
  `close({ returnFocus: false })`: the native close event comes in a later task, and returning
  focus to the opener would take it from the new page's `h1` (S1-C16).
- A field group (`fieldset`) that can get a 422 shows its error as `FormField` does
  (`GroupError`: the icon, an id in the group's `aria-describedby`, `aria-invalid`), and every
  field named in `useFormErrors`' labels renders its error somewhere (S1-C16 review).
- `Button`'s `blocked` draws the disabled tokens (UI-TOK-10); `pending` keeps its own look.
- A form alert's dismiss returns focus to the form's submit button (`dismissToSubmit`, or
  `useSettingsSave`'s `dismissed`), never `dismissAlert()` alone: the alert held focus (UI-FBK-13;
  S1-C16a review).
- A reload after a 403 that leaves the page without the form (now a 403 or 404 page, or an
  error state) settles it as a navigation does, `settlePage()`: the alert that held focus is gone
  (UI-FRM-7, UI-SHL-9; S1-C16a review).
- A confirmation that names people shows each with their email and their "Deactivated" badge,
  keyed by id: names aren't unique (UI-FBK-6; S1-C16a review).
- A dialog component is mounted once per page: two copies share their fields' ids, so each label
  names both fields (S1-C16).
- A page with more than one paged list names each `Pagination` after its list (`label`,
  "Archived pagination"): two landmarks never share a name (UI-TBL-3; S2-C0g review).
- A control that may hold focus isn't removed by its own action: Pagination's Previous and Next
  stay at the ends, `aria-disabled`, with the reason tied by `aria-describedby` (UI-TBL-3,
  UI-TOK-10).
- A dialog that may be open while a 403 reloads `allowed_actions` isn't behind a `v-if` on those
  actions, and every dialog whose opener can vanish (a row's menu, a hidden button) passes
  `fallbackFocus` (`focusHeading`): otherwise the alert that held focus, or focus on close, drops
  to `<body>` (UI-FRM-14; S1-C16b review).
- A confirmation the client sends (`export_control_confirmed`) comes from the current server state
  as well as the box: a reload can take the box away while it's still ticked (DL-116; S1-C16c
  review).
- A save that sends only the changed fields compares them with the values the form was filled
  from, never with data loaded since (another section's save, a background reload, a `/me`
  reload): a field the form still shows the old value of would undo the newer one (TD-56; S2-C0h
  review).
- State that outlives a step of a multi-step dialog (an edited username, a confirmation box) is
  the dialog's, reset in `open()`, not a child's that a `v-if` unmounts; a confirmation is
  cleared whenever the identity it confirms changes, the email included (UI-FRM-13, design-doc
  §3.1; S2-C0h review).
- A value a form keeps but doesn't render (project settings' `export_controlled`, DL-133) is sent
  from the latest server data on every save, never from the form: a reload that keeps what was
  typed would bring a stale one back, and no control could remove it (S2-C0d review).
- A dialog's search or lookup that fails says so at its own field, not in the form's alert, whose
  Retry and dismiss belong to the submit (UI-FRM-7; S1-C16b review).
- A PrimeVue list that can scroll (an `AutoComplete` opened on focus) scrolls its listbox, the
  element the combobox controls (`scroll-height="none"`, and `pt.list`'s `max-h-56
overflow-y-auto`): axe's `scrollable-region-focusable` excuses only that, not PrimeVue's
  unnamed container (S2-C0h e2e).
- A PrimeVue overlay inside a modal dialog (the picker's `AutoComplete`) sets
  `append-to="self"`: the page behind a `showModal()` dialog is inert, so an overlay appended to
  `<body>` can't be used (S1-C16b).
- A polite live region sits outside the `aria-busy` region it reports on: screen readers hold
  back changes inside a busy one. A success with no other visible trace shows `SuccessStatus`,
  never only hidden text.
- A PrimeVue table's selected-row bar goes on the row's first cell, and only on the selected
  row: its tables use `border-collapse: separate`, where a `tr`'s border isn't drawn, and forced
  colors draw a transparent border. A class check in jsdom can't show the bar is drawn
  (UI-TOK-9; S2-C15 review).
- A blocked PrimeVue menu item is `aria-disabled` through `pt.item`, in the disabled tokens on
  `pt.itemContent` (which sets its own color over the item's), and
  stays focusable, its command doing nothing: a `disabled` item is skipped by the arrow keys and
  faded with opacity, so the keyboard never reaches its reason (UI-TOK-10; S2-C15 review).

## Tests

- Component and composable tests with Vitest, in a `*.spec.ts` next to the code; mock only the
  API client (`vi.spyOn(client, 'GET')`), with results typed from the generated schema. Assert
  what the user sees, not component internals.
- Coverage: 80% overall; 90% for composables, stores, and route guards.
- Whatever `createApp.ts` wires up (a plugin, the client's middleware, the session handler) has a
  test through `createWaterlineApp()` in `src/app/router.spec.ts`: unit tests of each piece don't
  show they're connected. Wait for a navigation to a lazy-loaded route with `vi.waitFor`, not
  `flushPromises`.
- A spec that opens a PrimeVue overlay (`Menu`, `Popover`) runs real transitions
  (`stubs: { transition: false }`) so its `show` and `hide` events fire, calls
  `stubResizeObserver()`, waits a tick after mounting before opening it, and registers
  `enableAutoUnmount(afterEach)` after its own clean-up hook (after-hooks run last to first), so
  each overlay is unmounted before the body is cleared.
- A page that changes its own URL's path (an org's slug change) is remounted: `App.vue` keys
  `RouterView` on `route.path`. Its spec mounts through a `RouterView` keyed the same way
  (`mountOrgPages`), and an outcome it reports is carried to the new page (S1-C15a review).
- A spec whose component makes a delayed request (a debounced check or search) registers
  `enableAutoUnmount(afterEach)`, and the component clears its timer on unmount: a component left
  mounted makes its request during the next test, which then sees a call it didn't make (S1-C16d
  CI).
- A spec that picks from an `AutoComplete` types by setting the value and triggering `input`
  alone (a `change`, as `setValue` sends, makes `force-selection` clear the text), then chooses
  with ArrowDown and Enter: a click on the option doesn't reach its handler in jsdom (S1-C16b).
- An e2e step after a dialog closes waits for the dialog to be hidden and focus to be back on
  its opener before it moves focus: the close event returns focus a task later, and would take
  it back (S1-C16b).
- A mocked 422 has the server's real shape: the top-level `message` is "The request is invalid.",
  and the reason is in `details.fields` (S2-C15 review).
- Playwright covers each slice's critical flows against the full stack (`wl e2e`), in the
  `light` and `dark` projects. Find fields with `getByRole('textbox', { name, exact: true })`,
  not `getByLabel`: the label's text includes the required asterisk, the accessible name
  doesn't.
