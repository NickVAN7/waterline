# UI Feedback for Waterline

Each item's Slice 2 row follows its arrow (DL-137); S2-C0i checks none was dropped.

## General / User Account

### Overall things to address
- PrimeUI license - have a community license, but that needs to be added to the application. → S2-C0e
- Organizational management should be made more apparent - maybe moved as a setting/dropdown on the Org's name in the toolbar. → S2-C0f
- IT should be more obvious that we're in Acme Manufacturing's organization - maybe change the "Waterline" header to "Waterline - Acme Manufacturing" → S2-C0e
- All pop-up forms should be centered on the user's screen and not in the top-left of the screen. → S2-C0e
- I think the "Classified" label on projects needs to be adjusted - I think "Restriction" is a better label. We can change that throughout the whole app, and remove the "Restricted" classification. This would make the only restrictions "None", "Internal", and "Confidential" → S2-C0d

### Sign In screen
- App name "Waterline" is too small, and "Sign In" is too large. → S2-C0e
- There is too much space in the top of the form - you can compress the spacing a bit. → S2-C0e

### Home/My Work
- Is pretty good, we could move the labels (Planning/Active) to be right-justified. That would clean up the Project list a bit. → S2-C0g
- It would be helpful to show the org a project belongs to somewhere on this screen too. → S2-C0g
- IT would be helpful to show a user's role/access on this screen. → S2-C0g
- There needs to be a distinction between organizations in the project dropdown on the left-handed menu bar. / → S2-C0e

### Account Dropdown
- Move light/dark/mode to account setting screen instead of dropdown. → S2-C0e, S2-C0g
- Add a symbol next to Sign out, or distinguish it somehow (red color) → S2-C0e

### User Account settings
- Maybe Change password should be it's own page, with a button on the bottom of the screen. → S2-C0g


## Organization

### Organization Settings
- General settings should be primary page - or maybe an Org overview page as a landing page. That could include a list of projects with an overview, and links to change project settings. (this assumes that anyone who can see the organization management page can edit the project's settings.) → S2-C0f
- When on Organization settings page, we should minimize the left-handed toolbar - or maybe it should become a sidebar for the Org's settings. It's confusing when you're looking at the org's Members/Settings and see the selected Project's Members/Settings. → S2-C0f

### Add a person form (organization)
- Should be centered on the screen, not in the top-left. → S2-C0e
- There isn't an validation on the email field - you can just enter any string and it accepts it and moves to the next page. Not sure if it will accept it for complete account creation. Update: it doesn't accept it. → S2-C0h
- I'd like to see more distinction between the Email and the email address. → S2-C0h
- When the email isn't valid, Let's add the ability to edit the email address on the second window (where the Name/Username/Password are set), instead of being kicked back to the first window. The second window can act like the 'Edit Details' screen. → S2-C0h


## Project

### Project overview screen (All Projects)
- Same as mentioned in Home/My Work - we could move the labels (Planning/Active) to be right-justified. That would clean up the Project list a bit. → S2-C0g
- It might be useful to list the project type (Software/ERP/etc) on this screen. → S2-C0g

### Project Dropdown
- New Project shouldn't be indented → S2-C0e
- All projects should be highlighted a bit more (And differently) → S2-C0e

### Project settings
- There is a lot of space at the top of the form. → S2-C0h
- "Sprints"/"GitHub" checkboxes are available to check, but say "Not available yet". They should mirror the other modules until the functionality is avialable. This goes for project creation as well. → S2-C0d
- We can completely disable/remove the "Export Controlled" settings from the UI/app for the forseeable future. We can add them back in in the future if needed. This goes for project creation as well. → S2-C0d
- Archiving a Project should be harder to do - Maybe add a warning border or "danger section" label. The "Archive a project" button on the confirmation screen should be red. → S2-C0h
- Move the "Classification"/Category banner somewhere less obtrusive. → S2-C0d

### Add a member form (Projects)
- (repeat) pop up form should be centered on the screen. → S2-C0e
- When you click into the members field, the list of members should drop down. It's good that the list filters as you type though. → S2-C0h

### Access review screen
- What is the Access column showing? "Content and Management" doesn't tell a lot. → S2-C0d
- It's not clear what this page is for or what it does - Maybe a better title "Customer Portal Project access review" → S2-C0g


## Workspace

### Workspace Admin Users settings
- System admin shouldn't be it's own column - it can be a label and role (add a column like that) → S2-C0g
- Deactivated label should move to new column and not show next to name. → S2-C0g
