# User guide

How to use Waterline: signing in, finding your way around, your projects and their
requirements, approvals, your account, and running a workspace or an organization.

## Signing in

Open Waterline and you're asked to sign in with your email and password. If you opened a link
to a particular page, you land on that page once you're signed in; otherwise you land on
**My work**.

- A wrong email or password shows "The email or password is incorrect." The email you typed
  stays, so you only retype the password.
- Leaving a field empty marks it "This is required." and puts the cursor in it.
- The eye button in the password field shows or hides what you've typed. You can paste a
  password, and password managers fill it in.
- If your session ends (you signed out in another tab, or an administrator signed you out),
  the next time a page loads something from the server you're taken back to sign in, with
  "Your session ended. Sign in again." Sign in and you return to the page you were on. Reloading
  the page also asks you to sign in.

To sign out, open the menu with your name at the top right and choose **Sign out** (in red, with
an icon). If the server
can't be reached, a message says so and you stay signed in.

## Getting around

Every page after sign-in has the same frame:

- **The header**, at the top: Waterline's name (a link to My work) followed by your
  organization's name, and, at the right, the menu with your name. The organization's name is a
  menu if you belong to more than one organization or may administer it: open it to choose
  another organization (to see its projects), or, if you're one of its owners or admins, its
  **Overview**, **Members**, or **Settings**. Otherwise it's just its name.
- **The sidebar**, on the left: **My work**, then the **project selector**. Open the selector to
  see the current organization's projects, under its name, and choose one, or choose **All
  projects** (a link below the list) for the organization's project list. With more than eight, a filter field narrows the list as you type.
  Once you're in a project, its pages are listed below the selector: **Home**, **Requirements**
  (if you may read its content), **Members**, **Settings** (if you may change any of its
  settings), and last **Trash** (if you may read its content).
- On a narrow screen the sidebar is behind the **Menu** button in the header, and on a phone the
  header wraps onto more than one line and scrolls away with the page.
- **Skip to main content** is the first thing the Tab key reaches, and jumps past the header and
  sidebar.

## My work

My work is your home page (`/`). **Favorite projects**, first, lists the projects you've
starred, by name; archived ones, and any you can no longer open, are left out. Each project row
on My work has a star, **Favorite <project>**: select it to add the project to your favorites,
and again to take it off. Only you see your favorites.

Its **Projects** section lists the projects you can open,
with each one's key, its organization, your access (your role on it, or "Admin (inherited)" if
you administer it through its organization or the workspace), and its status, on the right;
archived projects are left out. If you're on more than 10, it
says how many there are, and each organization's project list has the rest. If the list can't
be loaded, **Try again** loads it again.

**Approvals waiting for you** lists the approval requests that name you and that you haven't
decided yet, across your projects, the longest-waiting first: each shows the requirement's title
(as in the revision under approval), its ID, the revision's number, its project, who asked and
when, and their note. Open one to review it and decide (see "Deciding", under
Requirements). A request on a project whose content you can no longer see isn't listed.

**My past decisions**, under it, lists the requests you approved or rejected, newest first: each
shows the requirement and revision you decided on, your decision, when, the request's status now
(it may have been cancelled or approved by hand since), and your comment. Open one to see its
requirement.

Each section shows its first 10; if there are more, it says how many. If one section can't be
loaded, it shows **Try again** and the others still show; if the whole page can't be loaded, one
**Try again** loads it again.

## Projects

An organization's project list (`/<organization>/projects`) shows its projects that you can
see, each with its key, type, and status, 25 to a page (archived projects are left out:
organization owners and admins find them in the Overview's **Archived** list), with **Previous page** and **Next page** links when there are more. **Status**
and **Type** narrow the list; when no project matches, **Clear filters** shows them all again. The page you're on and the
filters are in the address, so a link or a reload opens the same list.

**New project**, in the project selector, is there if you may create projects in the organization
(any member may). Give it a name and a key: 3 to 6 letters or digits, starting with a letter,
that starts every item's number (`PMT-TA-45`) and can't be changed later; you're told as you type
if it's taken. Pick its type (Software, ERP implementation, or General), which suggests its
modules: each is described, and a module that isn't built yet can't be turned on: its box is
greyed out, with "Not available yet". You become its first admin and lead, unless you're an
organization owner or admin, who may name someone else instead: any active member of the
organization, or of the workspace's staff. You can also set its restriction: a level (None,
Internal, or Confidential, each described) and its **Categories**, why it's sensitive (Financial,
Proprietary, Personal data (PII)). Once created, the project opens.

A project's home (`/<organization>/projects/<KEY>`) shows its name, its key, its status, its
restriction as a badge if it has one ("Confidential · Financial"), and its lead's name
("Deactivated" after it if their account is), or "No lead" if it has none. An archived project
says "This project is archived. It is read-only." at
the top. An address with an organization's old slug (the part of the address that names it)
or a lowercase key takes you to the project's own address. A project you can't see shows "Page
not found", the same as one that doesn't exist.

**Requirements**, in the sidebar under the project (`/<organization>/projects/<KEY>/requirements`),
shows its requirements as a tree, each with its ID (`ERP-RQ-7`) and its status. It opens with only the top-level
requirements showing: open a branch with its arrow, or with the Right arrow key on its row
(Left closes it). To open a requirement's whole branch at once, select its row and choose
**Expand requirement**; the button says "Expanding…" until it's done. It opens up to 500 rows
under the requirement, level by level, and says how many it opened; past that it says that
deeper rows stay closed, and you open them with their arrows or the Right arrow key. A project with more than 2,000
requirements shows the first 2,000, with a note saying so; there, a requirement you move to the
bottom of its level can fall past the first 2,000 and leave the tree the next time it loads. Anyone who can read the project's
content can open it; on an export-controlled project, that's only its members.

**New requirement** (members and admins), at the top of the page, opens a form: a **Title**
(required), a **Description**, a **Priority** (Critical, High, Medium, or Low; Medium to start),
and a **Parent** (the top level, or any requirement in the tree). The description starts from your
project type's template: **Context** and **Acceptance Criteria** for software and general
projects; **Business Process**, **Current State**, **Future State**, and **Acceptance Criteria**
for ERP implementations. Write the criteria as a numbered list. The description is markdown:
**Write** is the text, **Preview** shows how it will read (raw HTML shows as text, images as
links, and `- [ ]` and `- [x]` as "not done" and "done" marks). **Open as a full page** moves the
form, with what you've typed, to a page of its own (`…/requirements/new`). **Create requirement**
adds it, numbered `ERP-RQ-<n>`, and opens its page. A new requirement is a draft, at the bottom of
its level, with the project's restriction.

If you may edit requirements (members and admins), select a row and use **Move** (named after
the requirement, "Move ERP-RQ-7") to reorder it among the requirements at its level: **Move to
top**, **Move up**, **Move down**, **Move to bottom**, or **Move after…**, which asks which one
to place it after. **Move to…** gives it a new parent, or takes it to the top level; its own
children move with it. A move that doesn't apply says why in the menu ("already first").
If a requirement's place changed since you opened the page, the move is refused and the tree
reloads to show where things are now.

A requirement's ID in the tree opens it in a side panel (clicking elsewhere on the row only
selects it). On a wide window the panel runs down the right side of the window, and the page beside
it narrows; you can still scroll the tree, select in it, and open other requirements from it. On
a narrower window the panel covers the tree. Its row is marked
**Open**, in bold. To make the panel wider or narrower, drag the bar between the tree and the
panel, click the bar to step between narrow, medium, and wide, or focus it and press the Left or
Right arrow; the width is kept for next time. Another
requirement's ID shows that one in the panel instead. The panel has its own address
(`…/requirements?open=RQ-<n>`), so the browser's Back closes it, as do **Close** (the ✕ at its top)
and Esc; a change you make there shows in the tree. At the top of the panel, beside the ID and
status, **Open full page** goes to the requirement's page (`…/requirements/<n>`) and **Copy link**
copies that page's address, for sharing. Under the title are **Edit**, **Change status**, and
**⋯ More actions**, which holds **Change restriction…** and **Delete…**, as far as you may use them;
then the requirement's priority, reporter (with "Deactivated" after a deactivated reporter's name),
and restriction, and its description. The page shows the same, with the actions beside its title
and the ID and status under it. A status reads
**Approved · modified** when the requirement is Approved and has changed since its approved revision. If the
description has no "Acceptance Criteria" heading, a note says so. **Change status** (members and
admins) sets any status but its own and Approved, which comes only from an approval. If someone
changed the requirement since you opened it, the change is refused and the page shows the latest.
**Change restriction…** sets the requirement's restriction level and categories: members can raise
it, only the project's admins can lower it (None and Internal count as the same level, so a member
may switch between them), and it is never below the project's own. The badge
shows the restriction that applies, the stricter of the requirement's and the project's levels
with both sets of categories, so a requirement on a Confidential project reads Confidential
without one of its own; **None** in Change restriction means "same as the project".

**Edit** (members and admins) turns the requirement's title, description, and priority into a
form in place, with a **Change note**. **Save** keeps your changes; a changed title or
description is saved as a new version, with the note, while a priority change alone isn't (and
keeps no note). **Cancel** drops them. If someone else saved the requirement while you were
editing, Save is refused: **Reload** shows the latest, and your changes are lost once you press
it, so copy anything you need first. While you edit, Change status waits until you save or
cancel. In the side panel, Esc doesn't close the panel while you edit. If you've changed
anything, **Close**, Back, another requirement's ID, or **Open full page** first asks **Discard
your changes?**: **Keep editing** returns you to the form with what you typed, and **Discard
changes** drops it and goes on.

Below the description, the **Approval** section shows the revision last approved ("Last approved:
revision 3") and the latest approval request: its status (Pending, Approved, Rejected, or
Cancelled), the revision it's for, who requested it and when, its note, and each approver with
their decision (**Not decided**, **Approved**, **Rejected**, or **Replaced**, for an approver who
lost access and whose place the requester took) and comment. With no request yet it says "No
approval has been requested." A project admin can:

- **Request approval:** pick the approvers from the project's members (deactivated people aren't
  listed; every one of them must approve), add an optional **Note**, and press **Request
  approval**. The request is for the current revision. Only one request can be pending at a
  time: while one is, Request approval is unavailable and says why. After a rejection, the dialog
  opens with the same approvers ticked; anyone who can no longer be named is left out, and the
  dialog says who.
- **Re-open approval:** on an Approved requirement that hasn't changed since, the same dialog
  starts a new round. The requirement stays Approved while it's pending; if it's rejected, the
  requirement goes back to Draft.
- **Cancel request:** after you confirm, the approvers can no longer decide on it. Decisions
  already made stay on record. **Keep request** leaves it as it is.
- **Approve by hand:** after you confirm, the requirement is approved at its current revision
  without a request, with you as the approver (to record a sign-off made outside Waterline). A
  pending request is cancelled.

If the requirement changed after approval was requested, a warning says approvers still decide
on the requested revision; cancel and request again to have them review the latest. If an
approver lost access and the requester is no longer a project admin to take their place, the
request can't complete: it says **An approver no longer has access**, and **Re-request** cancels
it and opens the dialog with its approvers ticked, leaving out anyone who can no longer be named;
the dialog says the earlier request is cancelled, and closing it leaves it cancelled. If someone
you picked can no longer be named when you send the request, the dialog says so and lists only
those who can.

**Deciding.** When you're a named approver and haven't decided yet, whatever your role (viewers
included), the request is in **Approvals waiting for you** on My work, and the Approval section
shows it for you to decide on:

- **Revision N, under approval** shows the title and description you're approving, which may be
  older than the requirement's current one.
- On a requirement approved before, **Changes since approved revision N** compares the approved
  revision with the one under approval, as the Revisions tab's compare does.
- Under **Your decision**, add an optional **Comment** (the requester and the other approvers
  see it), then press **Approve** or **Reject**. A decision is final. Rejecting ends the whole
  request; with no comment, Waterline asks first: **Reject without a comment** goes ahead, and
  **Add a comment** takes you back to the comment.
- Once everyone has approved, that revision is recorded as approved ("Last approved: revision
  N"): a Draft requirement becomes Approved; one in any other status keeps its status. If the request was
  cancelled or decided meanwhile, the section says it isn't pending any more and shows where it
  stands.

The Approval section waits while you edit, as Change status does.

Below the Approval section, the **History** tab lists every change to the requirement, newest first,
with who made it and when: "Ben Ortiz changed the status from Draft to In progress". A person
since deactivated keeps their name, with "Deactivated" after it, and a change made by an app
command reads **System**. A move names the old and the new parent by their IDs ("changed the
parent from ERP-RQ-3 to the top level"), with "Deleted" after a parent that's in the Trash, and
an approval names the version approved ("approved revision 3"). Saved edits to the title or
description are versions, not History entries. History shows the latest entries first; **Show
more** adds the next ones. A move made in the tree while a requirement's side panel is open shows
in its History the next time you open it.

The **Revisions** tab beside it lists the saved versions of the title and description, newest
first: each one's number, who saved it and when, and its change note ("No change note." when
there's none); **Show more** adds older ones. **Compare revisions** shows what changed between
any two: pick them in **From** and **To** (the older one is always From). It opens on the current revision against the one before, or, when the
requirement is "Approved · modified", on the approved revision against the current one; a
revision's **Compare revision 3 with revision 2** picks it against the one before. The title
shows on its own, and the description as its markdown text, inline: added words are underlined
and removed ones struck through, and a screen reader says "Added:" or "Removed:" before each; a
removed or added blank line shows as "(blank line)", and a line break as "(line break)". Picking a From newer than To swaps the two,
and a screen reader says so.
Runs of more than three unchanged lines fold away behind **Show 12 unchanged lines**. With only
one revision there's nothing to compare yet.

**Delete…** (the requirement's reporter, while it has never been approved, and project admins), in
**⋯ More actions** on its page and in the side panel, asks first: **Delete ERP-RQ-7?**
says it moves to the project's Trash, where it can be restored. If it has children, choose what
happens to them: **Move them up to its parent** (the default; they take its place) or **Delete
them too**, with their own children. When you can't delete one of them yourself, only moving them
up is offered, and the dialog says why. Any pending approval request on it (and on its children,
when they go too) is cancelled; restoring doesn't bring the request back. **Delete requirement**
deletes it and opens the requirements tree, which says "ERP-RQ-7 moved to Trash." with **Open
Trash**. A link to a deleted requirement shows the page-not-found page.

**Trash**, last in the sidebar under the project (`/<organization>/projects/<KEY>/trash`), lists
the deleted requirements you may restore, newest first: each one's ID and title, who deleted it
("Deactivated" after someone since deactivated; **System** for an app command), and when.
Project admins see everything; a member sees the never-approved requirements they reported. One
that would bring back a child you couldn't restore yourself is listed without **Restore**.
**Restore ERP-RQ-7** brings it back with the children deleted with it, which leave the list too;
children deleted on their own stay in the Trash. A requirement whose parent is still in the
Trash comes back at the bottom of the top level. The page then says "Restored ERP-RQ-7." with
**Open ERP-RQ-7**. An archived project's Trash lists the same items, with no Restore. Nothing
is removed from the Trash automatically.

**Members**, in the sidebar under the project (`/<organization>/projects/<KEY>/members`), lists
its active members and their roles (Admin, Member, Viewer); anyone on the project can see it. The
project's admins (and organization owners and admins, workspace owners and admins, and system
admins) can also:

- **Show deactivated**, above the list: deactivated members are listed too, each marked
  **Deactivated**. An archived project's list has no **Show deactivated**: it shows its active
  members only.

- **Add member**: the list of the organization's members and the workspace's staff opens as soon
  as you're in the field; type a name, email, or username to narrow it, choose one, and give them
  a role.
- **Add by email**: works as **Add person** does under workspace administration (the email
  first, then either an existing account or a new one with a temporary password, shown once).
  An account from outside the organization is added only after you confirm adding them to the
  organization too, as a member.
- On an export-controlled project, every add first asks you to check that the person is
  authorized for export-controlled data.
- A row offers **Change role** and **Remove from project**. A project has no last-admin rule:
  its admins may change or remove any role, their own included. Removing the lead leaves the
  project with no lead. Removing someone who can then no longer see the project's content hands
  their undecided approvals to whoever requested each one, if that person is still a project
  admin.
- **Access review**, at the top beside the add buttons, opens the project's access review
  (`/<organization>/projects/<KEY>/access`): everyone who can open the project, with their
  project role, if any, why they reach it (the
  role, or an admin role above it), and, on an export-controlled project, whether they reach its
  content or only its management.

**Settings**, in the sidebar under the project, is there if you may change any of its settings
(`/<organization>/projects/<KEY>/settings`). Each part shows only if you may use it:

- **Details** (project admins): name, description, type (it changes labels and recommended
  modules, never data or the modules on), status (for information only), lead, and modules,
  then **Save settings**. The lead is one of the project's active members, or **No lead**, which
  is flagged. A deactivated lead stays the lead, marked "Deactivated", until you name someone
  else. A module that isn't built yet is greyed
  out, with "Not available yet". Turning off
  a module that holds data, or one recommended for the type, warns you what will be hidden;
  nothing is deleted, and turning it back on brings everything back.
- **Restriction** (project admins): the level and categories, then **Save restriction**. Export
  control isn't offered here; a project is made export-controlled only through the API, and
  saving keeps it. On an export-controlled project, system, workspace, and organization admins without a membership
  can manage it but not see its content (Requirements and Trash leave their sidebar, and those
pages say they can't open them), and may only raise its restriction: lowering the level
  or removing a category needs one of its explicit project admins.
- **Danger zone** (organization owners and admins), set apart at the bottom: **Archive
  project**, once confirmed with the red **Archive project** button, makes it read-only for
  everyone until **Unarchive project**. Nothing is deleted.

Each save sends only what you changed, so it never undoes a change someone else made to another
field since you opened the page.

Anyone else who opens a project's **Settings** or **Access review** is told the page is for the
project's admins, and to ask one of them.

## Account settings

Open the menu with your name and choose **Account settings**.

- **Profile:** change your name or username, then **Save profile**. A username someone else has
  is refused with a message under the field. Your email is shown but can't be changed here; ask
  an administrator.
- **Appearance:** choose **System** (follow your device), **Light**, or **Dark**. It applies at
  once and is remembered in this browser.
- **Password:** **Change password** opens its own page (`/account/password`): enter your current
  password and a new one, then **Change password**. Changing it signs you out everywhere else.
- **Sessions:** every browser you're signed in on, by its browser and system ("Firefox on
  Windows", or "Unknown device" when it can't tell), with **This session** on the one you're
  using, when each signed in, and when it was last active (**Active now** for this one).
  **Sign out other sessions** signs out every one but this, and says "Your other sessions are
  signed out."; with no others, it says "You have no other sessions."

## Documentation

Open the menu with your name and choose **Documentation** to read this guide inside Waterline
(`/docs`). The list of sections under its title links to each one; a section's address
(`/docs#docs-account-settings`, say) opens the guide at that section, so you can share it.

## Choosing a password

Wherever you choose a new password, the requirements are listed under the field: at least 8
characters, and not your email, your username, or your current password. Each one is ticked as
you type. If the server refuses the password, the requirement it didn't meet is marked "Not
met:". A password longer than 256 characters is refused with a message under the field.

## Changing a temporary password

When an administrator creates your account or resets your password, the password they give you
is temporary. After signing in with it, you go straight to **Change your password**, and nothing
else opens until you've changed it. Enter the temporary password as your current password, then
a new one that meets the requirements listed under it. Once it's changed you land on **My work**.
**Sign out** on the same page leaves without changing it.

## No access

If you're signed in but no longer belong to any organization or project, you see **No access**,
with your email and a note to ask an administrator to add you. Account settings and **Sign out**
still work.

## Workspace administration

Workspace owners and admins (and system admins) find **Administration** in the account menu, at
the top right. Its pages are listed in the sidebar, in place of the project selector: **Staff**, **Organizations**,
**Users**, and **Settings** (workspace admins see the settings; owners and system admins change
them). Anyone else who opens these pages is told to ask a workspace owner or admin. Each row's actions are in
its **Actions for …** menu, which lists only what you may do to that person. **Staff**,
**Users**, and an organization's **Members** list active people only: select **Show
deactivated**, above the list, to include deactivated people, each marked **Deactivated**. That's
how you find someone to reactivate. A list with only deactivated people shows as empty ("No
staff yet"), with a pointer to **Show deactivated**.

- **Staff** lists the workspace's staff and their roles. **Add person** asks for the email and
  the role first, and, when you press **Continue**, tells you if it isn't an email address. If the email already has an account, you
  confirm adding that person (you're shown only the email). If not, you create the account: the
  email, which you can still correct there (a changed email is checked again, and if it turns out
  to have an account you're asked to confirm adding that person instead), name, username
  (suggested from the name; you're told if it's taken), and a temporary password, generated for
  you, which you can replace. Once it's
  saved, the password is shown once: copy it and give it to the person, who must change it when
  they first sign in. From a row you can **Change role** (stepping down yourself included) and
  **Remove from staff**, which by default also removes them from the workspace's projects; clear
  the box to let them keep those projects. The last owner can't step down or leave until you
  choose who becomes owner: Waterline asks for that person when it happens. A role change or
  removal that leaves someone unable to see a project's content hands their undecided approvals
  there to whoever requested each one, if that person is still a project admin.
- **Organizations** lists the workspace's organizations. **Create organization** asks for its
  name, its slug (used in its web addresses; you're told if it's taken), and its first owner: an
  existing person, or a new account with a temporary password, shown once.
- **Users** lists everyone in the workspace. **Role** shows their workspace role (**Owner**,
  **Admin**, or **Member**) and **System admin** for system admins (**Owner, System admin**;
  granted outside the app, so you can read it but not change it); someone with neither shows
  **User**. System admins with no workspace role are listed last. **Status** shows **Active** or
  **Deactivated**.
- **Settings** renames the workspace and changes its slug (workspace owners and system admins).

**Account actions.** Where your role covers someone (the rank rule: you can act on people at your
level or below, everywhere they belong), their row offers **Edit details** (email, name, and
username; changing the email signs them out everywhere), **Reset password** (a new temporary
password, shown once), **Sign out everywhere**, and **Deactivate** (they're signed out and can't
sign in until reactivated; their work stays, and their undecided approvals go to whoever
requested each one, if that person is still a project admin). Once deactivated, they leave the
list unless **Show deactivated** is selected, where they show a **Deactivated** badge and are
offered **Reactivate** instead. The last active owner, or the last system admin, can't be
deactivated.

**Access review.** A person's row offers **Access review** to those who may see it: their
**Role** as the users list shows it (**None** with neither), then every organization and
project they can reach, why (their role, or a role above it), and, for each
export-controlled project, whether they reach its content or only its management (the **Access**
column shows only when one of their projects is export-controlled).

## Organization administration

Organization owners and admins (and workspace owners and admins, in every organization) find
the organization's pages in the organization menu, the organization's name in the header (switch
organizations first to administer another). They're listed in the sidebar, in place of the
project selector: **Overview**, **Members**, and **Settings**. Anyone else who opens these pages
is told to ask the organization's owners or admins.

- **Overview** (`/<organization>/overview`) shows the organization's name and slug, and its
  projects with their key, type, status, and lead ("No lead" if there's none); each project's
  name opens its settings. Archived projects are listed below, under **Archived**; open one's
  settings to unarchive it.

- **Members** lists the organization's members and their roles (Owner, Admin, Member). It works
  as **Staff** does under workspace administration: **Add person** asks for the email and the role first,
  then either confirms an existing account or creates one with a temporary password, shown once; a
  row offers **Change role** and **Remove from organization**, which by default also removes the
  person from the organization's projects (a role change or removal that leaves someone unable
  to see a project's content hands their undecided approvals there to whoever requested each
  one, as for staff); and the last owner can't step down or leave until you choose who becomes
  owner. Only owners (and workspace owners and admins, and system admins)
  grant, change, or remove the owner and admin roles. Rows also offer the account actions and the
  access review your role covers (see "Account actions" and "Access review" above).
- **Settings** renames the organization and changes its slug, which is in its web addresses
  (organization owners and workspace admins; organization admins see the values). After a slug
  change the page moves to its new address; links to the organization's own pages with the old
  slug no longer open, while links to its projects still go to the project.

## System status

`/status` shows whether Waterline is working, without signing in: "The API and database are
up." when everything is fine, or what's wrong (the database is unavailable, or the server can't
be reached) with a **Check again** button.

Any address Waterline doesn't know shows a "Page not found" page with links to My work and to
the system status.

## Light and dark

Waterline follows your device's light or dark setting. To choose one yourself, open
**Account settings** and pick **Light** or **Dark** under **Appearance**; **System** goes back
to following your device. The choice is remembered in this browser.
