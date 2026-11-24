# Frontend rules

Vue 3 (Composition API, `<script setup lang="ts">`), TypeScript (strict), Vite, Vue Router,
Pinia, Vitest + Vue Test Utils, Playwright. Folders: developer guide section 2; each file says
what it holds (DL-317).

## Rules

- **All API calls go through the generated client:** `await api(client.GET('/api/...'))`, which
  returns the data or throws an `ApiError` (`status`, `code`, `message`, `details`). Never
  hand-write API types (ESLint stops `fetch` and `openapi-fetch` outside `src/api/`).
- **The server is authoritative.** The UI may hide actions a user can't take, but never enforces
  permissions or duplicates business rules (send neighbor IDs, not rank values). Two exceptions:
  `PasswordRequirements` (DL-91) and the add-person flow's email-shape check (UI-FRM-4, UI-FRM-13).
- **Errors** (`{code, message, details}`): 409 → prompt to reload; 404 → `NotFoundView` in
  place; 422 → field errors from `details.fields`; forms use `useFormErrors`, a row or menu
  action's failure `useActionFailure` (TD-129 lists the surfaces not yet on it). A 401 and a 403
  `password_change_required` are the session hook's (`src/app/session.ts`), never a view's.
- **Rendered markdown** only through `MarkdownView` (markdown-it, raw HTML off, then DOMPurify);
  never `v-html` on anything else; edited only in `MarkdownEditor` (design-doc §3, DL-140,
  UI-MD-1, UI-MD-2). Docs mode is for `docs/user-guide/` pages only, never stored content
  (DL-341); svg attributes it makes are listed in `ADD_URI_SAFE_ATTR`.
- **Routes:** new routes go above the catch-all not-found route in `src/app/router.ts`. An org
  page finds its org with `useRouteOrg`.
- **Display labels** come from `src/app/labels.ts`; UI guidance text from the API response.
- **Accessibility: WCAG 2.2 AA** (design-doc §1): every drag has a single-pointer alternative;
  never color alone; controls at least 24×24 CSS px; sticky headers and toasts never cover the
  focused element; password fields allow paste. axe runs in component and e2e tests.
- **Loading** is a skeleton after about 300 ms on an `aria-busy` region, shimmer off under
  `prefers-reduced-motion`; a pending action shows on its control.
- A module whose slice hasn't shipped (`sprints`, `github` before Slices 4 and 8) can't be
  enabled; whether it's available comes from the API's module guidance (`available`), never a
  frontend list (DL-136).

## UI

Full rules and IDs: `docs/ui-design-guide.md`. Spacing, alignment, width, and similar
look-and-feel adjustments are edited directly there, and get a decision-log entry only when the
owner says the look is settled (DL-393). The silent traps reviewers found, screen by screen and
test by test, are in `.claude/skills/vue-screen/traps.md`: read the ones that touch your change.

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

## Tests

- Component and composable tests with Vitest, in a `*.spec.ts` next to the code; mock only the
  API client (`vi.spyOn(client, 'GET')`), with results typed from the generated schema. Assert
  what the user sees, not component internals.
- Coverage: 80% overall; 90% for composables, stores, and route guards.
- Playwright covers each slice's critical flows against the full stack (`wl e2e`), in the
  `light` and `dark` projects. Find fields with `getByRole('textbox', { name, exact: true })`,
  not `getByLabel`: the label's text includes the required asterisk, the accessible name
  doesn't.
