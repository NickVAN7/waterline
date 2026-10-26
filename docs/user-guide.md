# Waterline — User Guide

How to use each feature, from an end user's point of view. Kept current at every checkpoint.

> **Status:** Slice 1's features. You can sign in, change a temporary password, find your
> projects from My work, the org menu, and the project selector, create projects, run a
> project's members and settings and review who can reach it, edit your profile, change your
> password, and choose a light or dark theme. Workspace owners and admins run the workspace from its
> administration pages, and organization owners and admins run their organization's members and
> settings from theirs. Requirements, tasks, and test cases come in later slices.

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
  Once you're in a project, its pages are listed below the selector: **Home**, **Members**, and,
  if you may change any of its settings, **Settings**.
- On a narrow screen the sidebar is behind the **Menu** button in the header, and on a phone the
  header wraps onto more than one line and scrolls away with the page.
- **Skip to main content** is the first thing the Tab key reaches, and jumps past the header and
  sidebar.

## My work

My work is your home page (`/`). Its **Projects** section lists the projects you can open,
with each one's key, its organization, your access (your role on it, or "Admin (inherited)" if
you administer it through its organization or the workspace), and its status, on the right;
archived projects are left out. If you're on more than 10, it
says how many there are, and each organization's project list has the rest. If the list can't
be loaded, **Try again** loads it again.

## Projects

An organization's project list (`/<organization>/projects`) shows its projects that you can
see, each with its key, type, and status, 25 to a page, with **Previous page** and **Next page** links when there are more. **Status**
and **Type** narrow the list; **Clear filters** shows them all again. The page you're on and the
filters are in the address, so a link or a reload opens the same list.

**New project**, in the project selector, is there if you may create projects in the organization
(any member may). Give it a name and a key: 3 to 6 letters or digits, starting with a letter,
that starts every item's number (`PMT-TA-45`) and can't be changed later; you're told as you type
if it's taken. Pick its type (Software, ERP implementation, or General), which suggests its
modules: each is described, and a module that isn't built yet can't be turned on: its box is
greyed out, with "Not available yet". You become its first admin and lead, unless you're an
organization owner or admin, who may name someone else instead: any active member of the
organization, or of the workspace's staff. You can also set its restriction: a level (None,
Internal, or Confidential, each described) and why it's sensitive (Financial, Proprietary,
Personal data). Once created, the project opens.

A project's home (`/<organization>/projects/<KEY>`) shows its name, its key, its status, its
restriction as a badge if it has one ("Confidential · Financial"), and its lead's name
("Deactivated" after it if their account is), or "No lead" if it has none. An archived project
says "This project is archived. It is read-only." at
the top. An address with an organization's old slug (the part of the address that names it)
or a lowercase key takes you to the project's own address. A project you can't see shows "Page
not found", the same as one that doesn't exist.

**Members**, in the sidebar under the project (`/<organization>/projects/<KEY>/members`), lists
its members and their roles (Admin, Member, Viewer); anyone on the project can see it. The
project's admins (and organization owners and admins, workspace owners and admins, and system
admins) can also:

- **Add member**: search the organization's members and the workspace's staff by name, email,
  or username, choose one, and give them a role.
- **Add by email**: works as **Add person** does under workspace administration (the email
  first, then either an existing account or a new one with a temporary password, shown once).
  An account from outside the organization is added only after you confirm adding them to the
  organization too, as a member.
- On an export-controlled project, every add first asks you to check that the person is
  authorized for export-controlled data.
- A row offers **Change role** and **Remove from project**. A project has no last-admin rule:
  its admins may change or remove any role, their own included. Removing the lead leaves the
  project with no lead.
- **Access review**, at the top beside the add buttons, opens the project's access review
  (`/<organization>/projects/<KEY>/access`): everyone who can open the project, with their
  project role, if any, why they reach it (the
  role, or an admin role above it), and, on an export-controlled project, whether they reach its
  content or only its management.

**Settings**, in the sidebar under the project, is there if you may change any of its settings
(`/<organization>/projects/<KEY>/settings`). Each part shows only if you may use it:

- **Details** (project admins): name, description, type (it changes labels and recommended
  modules, never data or the modules on), status (for information only), lead, and modules,
  then **Save settings**. The lead is one of the project's members, or **No lead**, which is
  flagged. A deactivated member is marked "Deactivated" and can't be named; a deactivated lead
  stays the lead, marked, until you name someone else. A module that isn't built yet is greyed
  out, with "Not available yet". Turning off
  a module that holds data, or one recommended for the type, warns you what will be hidden;
  nothing is deleted, and turning it back on brings everything back.
- **Restriction** (project admins): the level and categories, then **Save restriction**. Export
  control isn't offered here; a project is made export-controlled only through the API, and
  saving keeps it. On an export-controlled project, system, workspace, and organization admins without a membership
  can manage it but not see its content, and may only raise its restriction: lowering the level
  or removing a category needs one of its explicit project admins.
- **Archive** (organization owners and admins): **Archive project**, once confirmed, makes it
  read-only for everyone until **Unarchive project**. Nothing is deleted.

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
its **Actions for …** menu, which lists only what you may do to that person.

- **Staff** lists the workspace's staff and their roles. **Add person** asks for the email first.
  If the email already has an account, you confirm adding that person (you're shown only the
  email). If not, you create the account: name, username (suggested from the name; you're told
  if it's taken), and a temporary password, generated for you, which you can replace. Once it's
  saved, the password is shown once: copy it and give it to the person, who must change it when
  they first sign in. From a row you can **Change role** (stepping down yourself included) and
  **Remove from staff**, which by default also removes them from the workspace's projects; clear
  the box to let them keep those projects. The last owner can't step down or leave until you
  choose who becomes owner: Waterline asks for that person when it happens.
- **Organizations** lists the workspace's organizations. **Create organization** asks for its
  name, its slug (used in its web addresses; you're told if it's taken), and its first owner: an
  existing person, or a new account with a temporary password, shown once.
- **Users** lists everyone in the workspace. **Role** shows **System admin** for system admins
  (granted outside the app, so you can read it but not change it), and **User** for everyone
  else; **Status** shows **Active** or **Deactivated**.
- **Settings** renames the workspace and changes its slug (workspace owners and system admins).

**Account actions.** Where your role covers someone (the rank rule: you can act on people at your
level or below, everywhere they belong), their row offers **Edit details** (email, name, and
username; changing the email signs them out everywhere), **Reset password** (a new temporary
password, shown once), **Sign out everywhere**, and **Deactivate** (they're signed out and can't
sign in until reactivated; their work stays). A deactivated person shows a **Deactivated** badge
and is offered **Reactivate** instead. The last active owner, or the last system admin, can't be
deactivated.

**Access review.** A person's row offers **Access review** to those who may see it: every
organization and project they can reach, why (their role, or a role above it), and, for each
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
  as **Staff** does under workspace administration: **Add person** asks for the email first, then
  either confirms an existing account or creates one with a temporary password, shown once; a
  row offers **Change role** and **Remove from organization**, which by default also removes the
  person from the organization's projects; and the last owner can't step down or leave until you
  choose who becomes owner. Only owners (and workspace owners and admins, and system admins)
  grant, change, or remove the owner and admin roles. Rows also offer the account actions and the
  access review your role covers (see "Account actions" and "Access review" above).
- **Settings** renames the organization and changes its slug, which is in its web addresses
  (organization owners and workspace admins; organization admins see the values). After a slug
  change the page moves to its new address; links with the old slug no longer open it.

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
