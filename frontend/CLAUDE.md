# Frontend rules

Vue 3 (Composition API, `<script setup lang="ts">`), TypeScript (strict), Vite, Vue Router,
Pinia, Vitest + Vue Test Utils, Playwright (from Slice 1).

## Layout

Folder purposes only; each file says what it holds (DL-317).

- `src/api/` — the generated schema and the configured API client (`api()`, `ApiError`)
- `src/app/` — the app's setup, the shell, the router and its guards, route focus, the session
  hook, and display labels; styles and tokens in `src/app/styles/`, the PrimeVue preset (and,
  once a board or grid ships, the SVAR theme) in `src/app/theme/`
- `src/components/` — shared UI components
- `src/composables/` — shared logic (auth state, permissions, forms)
- `src/stores/` — Pinia stores (current user, current org)
- `src/views/<area>/` — screens, grouped by the same area names as the backend, singular
  (`project/`, `task/`, …); `status/` and `errors/` aren't backend areas
- `src/test/` — shared test helpers (axe, typed responses, mounting, overlay stubs)
- `e2e/` — Playwright tests; `e2e/support/` holds their helpers

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
  ui-design-guide UI-MD-1). Markdown is edited only in `MarkdownEditor` (UI-MD-2). Docs mode
  (`docs`: callouts, keys, heading ids, own-origin links, bundled images) is for the guide's
  pages under `docs/user-guide/` only, never stored content (DL-341). Markup a docs-mode rule
  makes (a callout's icon) has its attributes checked after sanitizing: DOMPurify tests every
  attribute value against the URL pattern, so an svg's `viewBox`, size, and paths are dropped
  unless listed in `ADD_URI_SAFE_ATTR` (owner, after S3-C0g).
- **The guide** (`docs/user-guide/*.md`, loaded by `views/docs/guide.ts`) changes only when what
  a user does or sees changes; every behavior change goes in `docs/behavior-reference.md`
  (DL-335). `guide.spec.ts` fails on a page without its front matter, with a `#` heading, or with
  a link to a page or section that doesn't exist.
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

- A form on a page sets `max-w-(--content-narrow)` on itself (or a wrapper it shares): `main`
  has no width cap, so an uncapped form's fields span the screen (UI-SHL-7, DL-360; S3-C0h
  review). Dialogs and the auth card have their own width.
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
  (UI-FBK-5); a selected row also has a leading bar, and a checked box when the table is multi-select
  (UI-TOK-9).
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
- A link inside running text (a paragraph, a list item, rendered markdown) is underlined:
  `--color-link` against `--color-text` is about 1.7:1, so color alone can't mark it
  (UI-TOK-13).
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
- A reload after a user's action that replaces the page (a 403 that leaves a 403 or 404 page, a
  save that finds the item gone) calls `replacedPage()`, which sets the title and focuses the new
  `h1` on a visit's first page too; never `settlePage()`, which skips focus on a first page
  because that page came from a load. Its spec mounts directly on the URL (UI-FRM-7, UI-SHL-9;
  S1-C16a review, S2-C22 review).
- A confirmation that names people shows each with their email and their "Deactivated" badge,
  keyed by id: names aren't unique (UI-FBK-6; S1-C16a review).
- A dialog component is mounted once per page: two copies share their fields' ids, so each label
  names both fields (S1-C16).
- A page with more than one paged list names each `Pagination` after its list (`label`,
  "Archived pagination"): two landmarks never share a name (UI-TBL-3; S2-C0g review).
- A dialog's 404 (the item gone since the page loaded) goes through the page's own gone handler,
  which brings the not-found page (`replacedPage()`) or focuses the panel's title
  (`RequirementDetail`'s `editGone`), never a bare reload: focus comes back to the opener a task later, and the reload
  then removes it (UI-SHL-9; S2-C21 review).
- A reload after a 403 that removes the control holding focus, while the page stays, moves focus
  to the failure alert when focus is left on `<body>` (`RequirementsTree`'s `movable` watch,
  `RequirementView`'s status change): never leave it there (UI-FRM-7; S2-C18 review).
- A page whose `h1` changes in place (a rename saved, a reload after a 409 or 403) calls
  `syncTitle()`, so the window title follows: settling only on the first load leaves the old name
  (UI-SHL-9; S2-C18a review).
- After a dialog's action reloads a list, focus moves to the row now in that position only when
  the person or item has left the list (`useRefocusWhenGone`); one still listed, at any row,
  keeps the focus the dialog returned to its opener (UI-FRM-14; S2-C21a review).
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
  `<body>` can't be used (S1-C16b). A popup `Menu` places itself in document coordinates, so
  `self` puts it off to the side, and the dialog scrolling to it closes it: it goes in a fixed
  layer whose corner is kept at the document's (`StatusMenu`), checked end to end inside the
  side panel (S2-C18b).
- Inside a modal dialog, a PrimeVue popup's Escape is cancelled at the popup (`StatusMenu`'s
  layer, `@keydown.esc.prevent`), and so is an in-place edit form's (`RequirementDetail`):
  PrimeVue doesn't cancel it, and an uncancelled Escape also closes the dialog. The e2e presses
  Esc in the open popup and expects the dialog to stay (S2-C18b review).
- A container that handles Esc for itself (the split pane, `ItemPanel`) ignores an Esc from a
  `<dialog>` inside it: a modal's keydown still bubbles through its DOM ancestors, and its own
  cancel comes after, so the container would close too. The e2e presses Esc in a dialog opened
  from the panel and expects the panel to stay (S3-C0d review).
- A boundary or a control's only visible line (a pane's edge, a separator) is a `border` or an
  `outline`, never a background: forced colors turn backgrounds into Canvas, and the line
  vanishes. The e2e compares it with a `CanvasText` probe (S3-C0d review, after DL-356).
- A PrimeVue component whose own CSS sets `overflow` or `nowrap` (Breadcrumb: `overflow-x: auto`
  with its scrollbar hidden, `flex-wrap: nowrap`) is checked for clipped content at the
  narrowest room it can get, beside the split pane included, not only at a 320px viewport; the
  check measures the component, never the document (S3-C0e review).
- Content moved between containers (a teleport's target changing at a breakpoint) puts focus
  back where it was: moving a node that holds focus blurs it, and a dialog's open or close moves
  it again (S3-C0d review).
- A status note that reports an action's result (not a form alert) is cleared when what it
  describes changes: a new selection, a reload, or the next run of the action
  (`RequirementsTree`'s expand note; S2-C18c review).
- A control that rewrites another control's value, or its own, after the user's input (the
  compare's From and To swap) says the new values in a polite live region: the user heard the
  value they picked, not the one it became (S2-C19a review).
- A polite live region sits outside the `aria-busy` region it reports on: screen readers hold
  back changes inside a busy one. A success with no other visible trace shows `SuccessStatus`,
  never only hidden text.
- A child that asks its host to reload `allowed_actions` after a 403 waits for that reload (a
  function prop it awaits, `ApprovalSection`'s `reloadPage`) and reloads its own entity's actions
  too, before it looks where focus is: an emitted event returns before the reload removes the
  control that held focus (UI-FRM-7; S2-C20 review).
- A dialog whose first field loads after it opens moves focus to that field once loaded
  (`RequestApprovalDialog`'s `focusList`), and marks the loading group `data-autofocus`, so the
  first focus doesn't pass through a later field: ModalDialog picks before the load (S2-C20
  review).
- `MarkdownView` under a heading gets that heading's `level` (`:level="2"` under an `h2`): its
  default shift only keeps content off `h1`, and a `#` under an `h3` would read as the page's
  next section (UI-MD-1, UI-SHL-8; S2-C20a review). `:level="0"` is only for a guide page's
  bundled body, never stored content (DL-310).
- A required checkbox group can't take `aria-required`: its legend carries a visually hidden
  "(required)" beside the hidden asterisk (UI-FRM-2; S2-C20 review).
- A PrimeVue table's selected-row bar goes on the row's first cell, and only on the selected
  row: its tables use `border-collapse: separate`, where a `tr`'s border isn't drawn, and forced
  colors draw a transparent border. A class check in jsdom can't show the bar is drawn
  (UI-TOK-9; S2-C15 review).
- A rule that overrides a PrimeVue style (a forced-colors fix) is unlayered, outside `@layer
base`: PrimeVue's layer comes later and wins over `base`, and `!important` isn't allowed
  (`base.css`'s active-bar rule; S2-C17a review).
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
- jsdom draws table rows slowly, and CI's runner about 2.5 times slower again: a spec draws only
  the rows it needs. A spec of a row limit puts the big branch where the limit leaves it closed,
  since TreeTable draws only open rows; one that must draw hundreds says why and sets its own
  timeout with 4 times the CI time as headroom (`RequirementsTree`'s Expand requirement specs;
  S2-C18c's CI).
- A mocked 422 has the server's real shape: the top-level `message` is "The request is invalid.",
  and the reason is in `details.fields` (S2-C15 review).
- An e2e reflow check on content in a modal dialog measures the dialog and its panels
  (`scrollWidth` against `clientWidth`), never the document: a top-layer dialog scrolls itself.
  A forced-colors check compares with the system color the rule sets (a probe styled
  `Highlight`), never only "not transparent": forced colors turn a background into an opaque
  Canvas. Prove each can fail once (S2-C17a review).
- Playwright covers each slice's critical flows against the full stack (`wl e2e`), in the
  `light` and `dark` projects. Find fields with `getByRole('textbox', { name, exact: true })`,
  not `getByLabel`: the label's text includes the required asterisk, the accessible name
  doesn't.
