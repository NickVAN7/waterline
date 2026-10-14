# Waterline — User Guide

How to use each feature, from an end user's point of view. Kept current at every checkpoint.

> **Status:** Slice 1 in progress. You can sign in, change a temporary password, find your
> projects from My work, the org switcher, and the project selector, open a project's home, edit
> your profile and password, and choose a light or dark theme. Workspace owners and admins run
> the workspace from its administration pages. Organization administration, and the project
> pages, come next.

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

To sign out, open the menu with your name at the top right and choose **Sign out**. If the server
can't be reached, a message says so and you stay signed in.

## Getting around

Every page after sign-in has the same frame:

- **The header**, at the top: Waterline's name (a link to My work), your organization, and the
  menu with your name. If you belong to more than one organization, the organization's name is a
  button: open it and choose another to see its projects. With one organization it's just its
  name.
- **The sidebar**, on the left: **My work**, then the **project selector**. Open the selector to
  see the current organization's projects and choose one, or choose **All projects** for the
  organization's project list. With more than eight, a filter field narrows the list as you type.
  Once you're in a project, its pages are listed below the selector (for now, **Home**).
- On a narrow screen the sidebar is behind the **Menu** button in the header, and on a phone the
  header wraps onto more than one line and scrolls away with the page.
- **Skip to main content** is the first thing the Tab key reaches, and jumps past the header and
  sidebar.

## My work

My work is your home page (`/`). Its **Projects** section lists the projects you can open,
with each one's key and status; archived projects are left out. If you're on more than 10, it
says how many there are, and each organization's project list has the rest. If the list can't
be loaded, **Try again** loads it again.

## Projects

An organization's project list (`/<organization>/projects`) shows its projects that you can
see, 25 to a page, with **Previous page** and **Next page** links when there are more. The page you're
on is in the address, so a link or a reload opens the same page.

A project's home (`/<organization>/projects/<KEY>`) shows its name, its key, its status, and
"No lead" if it has no lead yet. An archived project says "This project is archived. It is
read-only." at the top. An address with an old organization name or a
lowercase key takes you to the project's own address. A project you can't see shows "Page not
found", the same as one that doesn't exist.

## Account settings

Open the menu with your name and choose **Account settings**.

- **Profile:** change your name or username, then **Save profile**. A username someone else has
  is refused with a message under the field. Your email is shown but can't be changed here; ask
  an administrator.
- **Password:** enter your current password and a new one, then **Change password**. Changing it
  signs you out everywhere else.

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

Workspace owners and admins (and system admins) find **Workspace administration** in the account
menu, at the top right. Its pages are linked along the top: **Staff**, **Organizations**,
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
- **Users** lists everyone in the workspace, with a **System admin** column you can read but not
  change (system admins are granted outside the app).
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
project, whether they reach its content or only its management.

## System status

`/status` shows whether Waterline is working, without signing in: "The API and database are
up." when everything is fine, or what's wrong (the database is unavailable, or the server can't
be reached) with a **Check again** button.

Any address Waterline doesn't know shows a "Page not found" page with links to My work and to
the system status.

## Light and dark

Waterline follows your device's light or dark setting. To choose one yourself, open the menu
with your name and pick **Light theme** or **Dark theme**; **System theme** goes back to
following your device. The choice is remembered in this browser.
