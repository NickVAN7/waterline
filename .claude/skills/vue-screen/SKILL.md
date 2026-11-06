---
name: vue-screen
description: Use when building or reshaping a Waterline screen, dialog, or page section in frontend/src/views/ (a list, a detail or review page, a settings form, a dialog). The recipe distilled from Slice 1's and S2-C0's screens - which built screen to copy, the page states in order, and the checks reviewers kept finding missing. Not for the backend half of a new area (new-area) or tests alone (test-writer).
---

# Building a screen

Distilled in S2-C0i from Slice 1's screens and S2-C0d to S2-C0h's (DL-124). The rules are in
`frontend/CLAUDE.md` and `docs/ui-design-guide.md`; this is the order to apply them in. Open the
reference screen for your kind before writing anything, and copy its shape.

| Kind | Reference | Its pieces |
|---|---|---|
| A paged list | `views/workspace/UsersView.vue` | `useLoad` + `useListQuery` (`returnWhenEmpty`), `Pagination`, `RowActions`, `SuccessStatus` |
| A project page | `views/project/ProjectAccessView.vue` | `useProjectPage` (loading, not found, the redirect), `ProjectHeader` |
| A settings form | `views/project/ProjectSettingsView.vue`, `components/NameSlugSettings.vue` | `useSettingsSave`, `useFormErrors`, only changed fields sent (TD-56) |
| A dialog | `views/roster/ChangeRoleDialog.vue`; multi-step: `views/roster/AddPersonDialog.vue` | `ModalDialog`, `useFormErrors`, `retryFromSubmit`, `fallbackFocus` |
| An admin page | any view under `views/workspace/` or `views/org/` | `meta.adminArea`, `ForbiddenView` with `WHO_TO_ASK` |

## 1. Before the code

- Read the screen's docs: the build-plan row, its design-doc section, the ui-design-guide rules
  it names, and the screen inventory once it covers the screen (DL-157).
- List the API calls; if one is missing or its shape is wrong, stop (the `new-area` skill, or a
  design change). The page reads `allowed_actions` from the API; it never works out a permission.

## 2. The route

- `src/app/router.ts`, above the catch-all, lazy (`() => import(...)`); `meta.adminArea` on an
  admin page; `meta.settlesItself` when the `h1` waits for data (every project page, through
  `useProjectPage`), or the title and focus settle before there's an `h1`; an org page finds its
  org with `useRouteOrg`.
- The page title and the focus on its one `h1` come from `PageHeader` (or `ProjectHeader`) and
  `routeFocus` (UI-SHL-9).

## 3. The page states, in this order in the template

1. **Not allowed or not found:** `NotFoundView` or `ForbiddenView`, and the same 404 whether it's
   missing or hidden (UI-FBK-14). A 404 after the page loaded (the thing deleted since) swaps in
   the not-found page through `settlePage()`.
2. **Failed:** `ErrorState` keyed on `failures`, `live` after the first, with Retry.
3. **Loading:** `Skeleton` in the region that holds `aria-busy` (UI-FBK-11).
4. **Empty:** `EmptyState`, saying what would fill it.
5. **Data:** headings on every section (`sr-only` when the page shows it another way), a table
   in a focusable `role="region"` named by its heading (UI-TBL-1 to UI-TBL-3).

A polite announcement (a count, a saved message) sits outside the busy region (`SuccessStatus`).

## 4. Actions and forms

- Hide what `allows(row, action)` refuses; disable with a visible reason what state blocks
  (UI-TOK-10). Never compare ids to decide an action.
- Every label, badge, and status from `src/app/labels.ts` (icon + text + tone, UI-FBK-5).
- Forms: `FormField`-based fields, the server validates, a 422 goes inline with focus on the
  first invalid field, `aria-disabled` while pending (UI-FRM-2 to UI-FRM-8).
- A 403 in a dialog reloads the page's data and the user (`refused()` in the reference list);
  a 409 prompts a reload.
- Walk `frontend/CLAUDE.md`'s "UI" list once against the new code before the first test run:
  each line there is a bug a reviewer found in a built screen.

## 5. Tests

Use the `test-writer` skill. A screen's spec, next to it, covers at least:

- each page state from section 3, from typed responses (`src/test/api.ts`);
- each action shown and hidden by `allowed_actions`, with the request it sends;
- each error path the screen handles (403, 404, 409, 422), and where focus goes after it;
- `expectNoA11yViolations()` on the loaded page and on every open dialog.

Mount through the shared helpers (`mountWorkspaceView`, `mountOrgView`, `mountOrgPages`). A
Playwright test only for a flow in the slice's "Done when" list, in both themes, with axe and the
focus checks (`e2e/support/a11y.ts`).

## 6. Docs

- `docs/user-guide.md`: what the screen is for and how to use it, in the words on the screen
  (`user-guide-verifier` follows it literally at the slice's end).
- `ui-reviewer` reviews the screen at the checkpoint (the `checkpoint` skill). A finding that a
  rule would have prevented adds the rule to `frontend/CLAUDE.md`, and, if it changes the order
  above, to this skill.
