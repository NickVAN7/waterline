# Manual keyboard and screen-reader pass: Slice 2 (S2-C22)

The owner's pass on Slice 2's new and reshaped screens (build plan, S2-C22; testing-strategy,
"Accessibility"; ui-design-guide, Appendix A). Automated checks (axe in component and end-to-end
tests, in both themes; `expectFocusNotObscured()`) find only part of the problems, so this pass
is the check for the rest. Run it against the dev stack with the demo data (`uv run wl seed
--demo` on an empty database), in light and in dark.

**How to record it:** tick each line that holds; for a problem, write it under "Problems found"
with the screen, the step, and what happened. A problem is fixed in S2-C22 or logged in
`docs/tech-debt.md` with the owner's agreement; the slice's "Done when" needs none left
unresolved. Two tech-debt entries are decided here: TD-91 and TD-94 (below).

- **Who:** the owner
- **Screen reader and browser:** not recorded (the owner, 2026-11-09)
- **Date:** 2026-11-09
- **Result:** no problems found (the owner). The owner's UI feedback, design direction rather
  than failures of this pass, is in `docs/reviews/s2/S2-ui-feedback.md`
- **Demo users:** every password is `harbor-demo`; `olivia@harbor.example` (owns Acme), `wendy`
  (workspace admin), `admin` (system admin), `ella` (PORTAL's admin), `finn` (a PORTAL member),
  `hana` (a PORTAL viewer), `casey` (a member in two orgs), `nora` (no memberships), `fiona` /
  `felix` (a temporary password)

**Set up first** (the demo data has no requirements, and lacks these states):

- As `ella`, on PORTAL's Requirements: create about eight requirements, three levels deep in one
  branch (Move to… a child under a child), with one description that has `#` and `##` headings, a
  long URL, and a list; edit one's title and description twice, so it has three revisions.
- As `ella`, request approval on one requirement naming `hana` and `finn`; on another, naming
  `finn` only, then approve it as `finn` and edit it as `ella` ("Approved · modified").
- As `ella`, delete one requirement that has children ("Delete them too"), and one with "Move
  them up", so Trash has items.
- As `olivia`, create six more projects in Acme (the selector's filter, with more than eight),
  one of them with the key `OPS` and `olivia` as its first admin. The UI doesn't offer export
  control (DL-133), so mark `OPS` export-controlled through the API, confirming its explicit
  members (from the repository root, with the stack up):

  ```sh
  J=$(mktemp); O='Origin: http://localhost:5173'; C='Content-Type: application/json'
  curl -s -c $J -H "$O" -H "$C" http://localhost:5173/api/auth/sign-in \
    -d '{"email":"olivia@harbor.example","password":"harbor-demo"}' >/dev/null
  IDS=$(curl -s -b $J http://localhost:5173/api/projects/OPS/members \
    | python3 -c 'import json,sys; print(json.dumps([m["user_id"] for m in json.load(sys.stdin)["items"]]))')
  curl -s -b $J -X PUT -H "$O" -H "$C" http://localhost:5173/api/projects/OPS/restriction \
    -d "{\"level\":null,\"categories\":[\"export_controlled\"],\"export_control_confirmed\":true,\"confirmed_member_ids\":$IDS}"
  ```

  The last command prints the project with `"export_controlled"` in its categories. As `wendy`
  (a workspace admin with no membership there), `OPS` is then an export-controlled project you
  manage but whose content you can't see.
- As `wendy`, deactivate one of PORTAL's members (Workspace administration, Users), for the
  Deactivated badge and "Show deactivated".
- Sign in as `ella` in a second browser too, for a second session; star PORTAL on My work.

---

## The twelve steps (Appendix A), on every screen below

1. Tab order matches the visual order; nothing skipped or trapped; the focus ring is visible and
   never under the header (no toasts in Slice 2: success messages are a status line on the page).
2. Every control works by keyboard: Enter and Space on buttons; Esc closes dialogs, menus,
   popovers, panels, and hints, one layer at a time; arrow keys in menus, comboboxes, radios, and
   the requirement tree.
3. Dialogs and the side panel: focus lands inside (Cancel for a confirmation, the first field for
   a form, the title for the panel); the page behind is inert; focus returns to the opener, or the
   next row, or the `h1` if the opener is gone.
4. Forms: submitted empty and with a server error, focus lands on the first invalid field and "N
   fields need attention" is read, each error with its label; a form-level failure's alert takes
   focus, is read once, and its dismiss returns focus to the control that caused it (or the `h1`).
5. Navigation: the title changes and focus lands on the `h1`, which is read; a missing address
   and a project or requirement you can't see look and read the same.
6. (No toasts in Slice 2.) Each success message ("Requirement saved.", "… moved to Trash.", "Your other sessions are
   signed out.") and each live check is announced once, politely.
7. (No bulk-selection table in Slice 2; instead:) the requirement tree (a treegrid): the selected row's bar and the row actions by keyboard; a
   move and a refused move announced.
8. Zoom to 200% and 400% at 1280 px: no lost content, no horizontal page scroll except inside a
   table's or the tree's own region.
9. A text-spacing override (line height 1.5, letter spacing 0.12 em, word spacing 0.16 em,
   paragraph spacing 2 em): nothing clipped or overlapping.
10. Forced colors (Windows high contrast): focus rings, badge borders, the sidebar's and the tree's
    current or selected bars, disabled controls, the diff's underline and strike, danger buttons,
    and form boundaries stay visible.
11. Screen reader: headings, landmarks, button and link names, and badge text read sensibly out of
    context; hidden prefixes ("Project:", "Your decision:", the diff's "added"/"removed") read
    once, not doubled.
12. (No board or editable grid in Slice 2.)

## Screens

- [ ] The shell (S2-C0e, S2-C0f): the project selector (the org name in its description, All
      projects a link, New project a button), the org menu (the admin links after the orgs), the
      user menu with Documentation; the header at 320 px and 400%; Sign out's red at rest, hover,
      and focus in both themes; the admin navs behind Menu below 48 rem
- [ ] Sign in and Change your password at 320 px with text spacing (S2-C0e)
- [ ] My work (`/`, S2-C14, S2-C20b, S2-C21c): the three regions in order, the starred project at
      the top and its star by keyboard, the approvals section, one section unavailable and a
      failed Try again; 320 px, 400%, 200% text spacing
- [ ] An org's overview (`/acme`, S2-C0f, S2-C0g): both lists over 25 rows (paging each, both
      counts announced), both themes, 320 px
- [ ] Account settings (S2-C0g, S2-C21b): the Theme radios; `/account/password` (focus on the
      `h1`, the requirements read with the field, "Password changed." once); Sessions (this
      session, the other one, Sign out other sessions, and its blocked state once signed out)
- [ ] Workspace administration as `wendy` (S2-C0h, S2-C0i, S2-C0j, S2-C21a): Users (the Role cell
      wrapping at 320 px; a badge-only Role cell read as "System admin" alone; the Status column
      in both themes), Show deactivated on every roster, a person's access review (the Role cell
      and "Workspace role" read as one phrase), the Danger zone in both themes, forced colors, 320 px
- [ ] Project settings (S2-C0c, S2-C0d): the First admin select with a long list, the disabled
      module checkboxes (one name plus "dimmed", in both themes, forced colors, browse mode), the
      refusal's alert read once; the header's badges at 320 px and 400%
- [ ] Project members (S2-C0g, S2-C0h): the header actions wrapping and their tab order; the
      member picker by keyboard (the list on Tab, Esc, not covering Role or the buttons);
      add-person step 2 (focus on Name with its sentence, on Back when the email is an account)
- [ ] The project's access review without its Access column (S2-C0d)
- [ ] Organization members (`/acme/members`, as `olivia`): Show deactivated, and a refused action
      (as `olivia`, make `liam` an Acme admin; sign in as him in a second browser and open
      the page from a link; as `olivia`, make him a member again; then act as him): opened
      directly from a link, after the refused dialog, focus on the 403 page's `h1` and its title
      read; the same on the project members page and Workspace administration's Staff
- [ ] Requirements (`/acme/projects/PORTAL/requirements`, S2-C15, S2-C17, S2-C18c): the treegrid
      by keyboard end to end, Shift+Tab back into it, Tab after Expand all or a move; the selected
      bar in both themes, grayscale, and forced colors; Move up, Move to…, and a refused move read;
      the disabled items' contrast; "Expand requirement" and its blocked reason at 320 px, 200%, and
      400%; New requirement and the create dialog
- [ ] A requirement's page (S2-C18, S2-C18a): the 403 alert read once; "Changing the status…" then
      "Status: X"; edit mode's focus order and its "Edit the requirement" landmark, "Saving the
      requirement…" and "Requirement saved.", focus on Edit after Save and Cancel, the 409 alert;
      the priority radios at 400% and 320 px with text spacing, in forced colors; the restriction
      dialog and the restriction badges on the page, in grayscale and forced colors; an archived
      requirement at 320 px; opened directly from a link, then edited after it was deleted in
      another tab: focus on "Page not found", the title read
- [ ] The side panel (S2-C18b): its Tab order and the ring on its title; Esc in its status menu,
      restriction dialog, edit form, and editor tabs (one layer each; in Firefox and Safari too);
      its title read, and again after Try again; "Link copied."; the archived banner; Back and
      Forward with it open; 200%, 400%, text spacing, forced colors
- [ ] History (S2-C19): the tab and "Show more" in the Tab order on the page and in the panel; an
      entry read as one sentence with its badges; "2 more entries" read once; no stray
      announcement when it reloads after a status change; the tab's bar on the raised surface
- [ ] Revisions and compare (S2-C19a): heading order (h2, h3 Compare and All revisions, h4 Title
      and Description); `<ins>`/`<del>` with their hidden prefixes, not doubled; From/To and swap
      by keyboard; focus after "Compare revision N with revision N-1" and "Show N unchanged lines";
      the tone pairs in the mono box in both themes; a long URL at 320 px and 400%; text spacing
- [ ] Approvals (S2-C20, S2-C20a): the section's tab order on the page and in the panel; the
      blocked Request approval reading its reason; the request dialog's checkboxes at 320 px and
      400%; Re-request in the panel; Keep request and Cancel request named; as `hana`, the decide
      panel (Comment, Approve, Reject; Reject without a comment; the announcements once; Retry
      after a network failure); the 403 and 409 paths' focus; on a throttled network, where focus
      lands first
- [ ] Delete and Trash (S2-C21): the delete dialog read on open (Cancel focused, the consequences
      before it), nested over the panel; "… moved to Trash." after the `h1`; Open Trash a link;
      Trash at 320 px and 400%, Deleted-by with 200% text spacing; the danger Delete and the radios
      in forced colors
- [ ] Documentation (`/docs`, S2-C21d): the user menu's item by keyboard; both themes; focus not
      obscured after a jump; 320 px reflow; text spacing; contrast

## Decided in this pass

Both decided by the owner on 2026-11-09, before the pass; the pass confirms them.

- [ ] **TD-91** (closed: already fixed in S2-C20a): with a screen reader's heading list on a
      requirement whose description has headings, its `#` is a level-3 heading under
      "Description".
- [ ] **TD-94** (built): "Expand requirement" opening the whole branch is heard as "Expanding…",
      then "Opened all 2 rows under PMT-RQ-2." ("Opened 1 row under …" for one).

## Problems found

None (the owner, 2026-11-09).
