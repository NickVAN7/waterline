# Manual keyboard and screen-reader pass: Slice 1 (S1-C17)

The owner's pass on Slice 1's new screens (build plan, S1-C17; testing-strategy, "Accessibility";
ui-design-guide, Appendix A). Automated checks (axe in component and end-to-end tests, in both
themes; `expectFocusNotObscured()`) find only part of the problems, so this pass is the check
for the rest. Run it against the dev stack with the demo data (`uv run wl seed --demo` on an empty
database), in light and in dark.

**How to record it:** tick each line that holds; for a problem, write it under "Problems found"
with the screen, the step, and what happened. A problem is fixed in S1-C17 or logged in
`docs/tech-debt.md` with the owner's agreement; the slice's "Done when" needs none left unresolved.

- **Who:** the owner
- **Screen reader and browser:** not recorded
- **Date:** 2026-10-21
- **Demo users:** every password is `harbor-demo`; `olivia@harbor.example` (owns Acme), `wendy`
  (workspace admin), `admin` (system admin), `casey` (a project member in two orgs), `hana` (a
  viewer on PORTAL), `nora` (no memberships), `fiona` / `felix` (a temporary password)

**Set up first** (the demo data lacks these states):

- As `olivia`, create six more projects in Acme, so the project selector has more than eight and
  shows its filter.
- As `wendy`, deactivate one of PORTAL's members (Workspace administration, Users), for the
  Deactivated badge.
- As `olivia`, mark a project export-controlled in its Settings (not PORTAL, which the end-to-end
  tests use), for the export-control steps.

Slice 1 has no toasts: success messages are a status line on the page (`SuccessStatus`).

---

## The twelve steps (Appendix A), on every screen below

1. Tab order matches the visual order; nothing skipped or trapped; the focus ring is visible and
   never under the header.
2. Every control works by keyboard: Enter and Space on buttons; Esc closes dialogs, menus,
   popovers, and hints; arrow keys in menus and comboboxes.
3. Dialogs: focus lands inside (Cancel for a confirmation, Back on a confirmation step, the first
   field for a form); the page behind is inert; focus returns to the opener, or the next row, or
   the `h1` if the opener is gone.
4. Forms: submitted empty and with a server error, focus lands on the first invalid field and "N
   fields need attention" is read, each error with its label; a form-level failure's alert takes
   focus and its dismiss returns focus to the submit button.
5. Navigation: the title changes and focus lands on the `h1`, which is read; a missing address
   and a project you can't see look and read the same.
6. A success message ("Settings saved.") and a live availability check (a username, a slug, a
   project key) are each announced once, politely.
7. (No selectable tables in Slice 1.)
8. Zoom to 200% and 400% at 1280 px: no lost content, no horizontal page scroll except inside a
   table's own region.
9. A text-spacing override (line height 1.5, letter spacing 0.12 em, word spacing 0.16 em,
   paragraph spacing 2 em): nothing clipped or overlapping.
10. Forced colors (Windows high contrast): focus rings, badge borders (status, Deactivated, No
    lead), the sidebar's and the section nav's current-page bars, "Not available yet", and form
    boundaries stay visible.
11. Screen reader: headings, landmarks, button and link names, and badge text read sensibly out of
    context.
12. (No board or editable grid in Slice 1.)

## Screens

- [x] Sign in (`/sign-in`), as `olivia`; a wrong password; an empty form
- [x] Change your password (forced, as `fiona` or `felix`), with the requirements list
- [x] My work (`/`), and System status (`/status`)
- [x] The shell: skip link, header, org switcher (as `casey`), project selector (its filter with
      more than eight), user menu and its theme choice; the Menu button below 48 rem
- [x] Page not found, compared with a project you can't see: `/acme/projects/NOPE` and
      `/acme/projects/NOPE/members` against `casey` on `/acme/projects/ERP` and
      `/acme/projects/ERP/members` (they look and read the same); No access (`nora`)
- [x] A project's 403 pages: `hana` on `/acme/projects/PORTAL/settings`, `casey` on
      `/acme/projects/PORTAL/access`
- [x] Account settings (profile; change password with the requirements list)
- [x] Workspace administration (`wendy`): Staff, Organizations, Users, Settings, a person's
      access review; the 403 page (as `casey`)
- [x] Organization administration (`olivia`): Members, Settings; the 403 page (as `casey`)
- [x] An org's project list (`/acme/projects`), with its filters
- [x] Create project (New project in the selector), with the export-control confirmation
- [x] A project's home (`/acme/projects/PORTAL`), and an archived one (`LEGACY`)
- [x] Project members (`/acme/projects/PORTAL/members`): Add member, Add by email, Change role,
      Remove from project
- [x] The project's access review (`/acme/projects/PORTAL/access`)
- [x] Project settings (`/acme/projects/PORTAL/settings`): details, modules, classification,
      archive

## Items the reviews left for this pass

- [x] **Add-person dialog** (staff, org members, project members): each step's announcement;
      the "account exists" and "join the organization" steps start on Back and read their text
      with it; Name reads "No account has this email yet. Create one:"; Done reads what was done,
      then the "shown once" warning, not twice (S1-C15, S1-C16b, S1-C16c)
- [x] **Create organization and password reset:** Done reads its text and the warning, in
      order; the password and Copy reachable from Done (S1-C15, S1-C16d)
- [x] **Retry** in each dialog focuses the action that failed; **row menus** by keyboard; live
      availability announcements (username, slugs, project key) (S1-C15)
- [x] **Pagination:** the disabled Previous/Next stay focusable and say why (S1-C14a)
- [x] **Org settings:** a slug change moves to the new address, its `h1` focused, "Settings
      saved." read once; a rename updates the title, focus stays on Save; the read-only view
      after a 403 (S1-C15a)
- [x] **Create project:** the field groups' descriptions and long names read; the blocked button
      in forced colors; the dialog below 48 rem; the list filters by keyboard; "Not available
      yet" contrast in the sidebar (S1-C16)
- [x] **Project settings:** a module warning added to a focused checkbox is read; the lead help
      changing; the 403 page after a reload; the export-control dialog nested in Create project
      (Esc closes only it, focus back to Create project); the confirmation list at 320 px and 400%;
      the Deactivated badge in forced colors (S1-C16a)
- [x] **The member picker:** its list at 200% and 400%, inside the dialog, not clipped; Esc closes
      the list first, then the dialog; what is read for its results, "No one found.", and a
      second failed search; its 2 px danger border with PrimeVue's own invalid styling, and in
      forced colors (S1-C16b)
- [x] **A 403 in each dialog** (on the org roster and the project members page): focus stays on
      the alert, and after closing goes to the `h1` when the opener is gone (S1-C16b)
- [x] **A changed export control or member list** (two tabs: change it in one, add or save in
      the other): the alert is focused and read; the checkbox appears or goes without focus
      falling to the page; the ticked box and typed values are kept; the next save lists the
      current members (S1-C16c, S1-C16d)
- [x] **The access review table** at 320 px scrolls inside its region (S1-C16b)

## Problems found

None. The owner ran the pass and reported no problems (2026-10-21).
