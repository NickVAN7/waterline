# UI Feedback for Waterline

## General / User Account

### Overall things to address
- When you're viewing a page, when you scroll to the bottom, the sidebar on the left also scrolls and the content at the top disappears. This shouldn't happen.
- The breadcrumbs need some work throughout the app - they aren't intuitive, and could use a sleeker look.
- Let's explore a Frontend/UI skill to add to the page design process - it needs some work. (Ideas: Impeccable, agent-skills,Anthropics frontend design )
- We need to work on the text displayed in the browser tab - it's become jumbled and long in the tab.
- It would be good to add a distiction between Org and Project items in the left-hand menu... or at least a way to tell the user that they're looking at a Organization's options, and not the Projects.

### Sign In screen
- None

### Home/My Work
- Let's move the "favorite" star to the left-hand side, in front of the Project name.
- Each project's row in cluttered - let's remove the access, or find another way to list it.
- Make a note to discuss, and explore options of better organizing the Projects section - It might make sense to group projects by Organization. Also, I don't like that not all of a user's projects are shown on the My Work page.
- This probably contradicts a past decision, but I don't think we need a "My past decisions" on the My Work page.

### Account Dropdown
- None

### User Account settings
- "Change password" should be a button, and not a linked text.

### Documentation
- This section needs some serious work - the generated markdown is does not look good. Make a note that we need to discuss this much more in-depth to make this page usable.



## Organization

### Organization Overview
- "Archived" section, should be "Archived Projects"
- The status of a project in the Archived section, should be "Canceled" or "Archived" - it doesn't make sense to have a archived project in a Planning status.
- The "Name Acme Manufacturing" isn't really needed right below the header - can remove it.
- Maybe add the slug to the title: "Acme Manufacturing (acme) overview"... or find a better way to include it.

### Organization Settings
- None

### Organization Members
- Need to change the 'deactivated' tag/label thing and distinguish deactivated users a different way.
- Showing deactivated shouldn't change the width of the columns either.
- When adding a member to the orgainization, should we prompt the admin to add them to the org's projects? It seems inefficient for the admin to have to add them in two places if they add through the org's members - although, adding a user from the project, also adds them to the org... but it might not hurt.

### Add a person form (organization)
- None


## Project

### Project overview screen (All Projects)
- It would be good to add a way to tell what organization a project belongs to on this screen, and in general on the project's pages.

### Project Dropdown
- The dropdown arrow should be right-justified, and not just next to the project name.
- I don't like the "All projects" button being blue and underlined like that, let's highlight it in a different way.
- The project filter may not be needed in all cases - it might be better to allow the user to search/filter by clicking a button, which would then let the filter field be shown.

### Project settings
- Is there a way to minimize the Modules section? It takes up a lot of space on the page... let's discuss.
- There should be another way to move a project's status other than this page. Maybe on the main project page... but that isn't developed yet.
- Save Restriction button should be the primary color (match Save settings)

### Project members
- Let's move "Show deactivated" to the bottom of the list... it looks weird on the top by itself.

### Add a member form (Projects)
- I don't like how the user list automatically opens on this form - my assumption is that it's because that object has the focus, but we should probably change the focus to the title of the form anyway.
- On the Add by email form, the default role should be "Member", not "viewer".

### Access review screen
- The "Why they reach it" column needs a different name - how does it differ from the Project Role column?
- The value of "none" in Project role doesn't make sense - if they are admins from inherited roles (Workspace/System/org), then they should just be Admin. A related note, I don't know if these admins need to be expicitly called out in the Member access list. It might be confusing for a project admin to see these people... but TBD.
- You should be able to go back to the members page from this one.


## Requirements

### Project's requirements
- the hints "Select a requirement to expand/move it" shouldn't show like they are.
- Let's move the "Expand requirements" and "move" buttons to be right-justified to the table.
- There is too much space between the Title, and the Requirement table.
- There should be a filter, or a column on the requirements table that specifies if a requirement is awaiting approval... maybe a new status label?

### Requirements pop out sidebar
- The design isn't great - the purpose of a pop-out bar, is so you can still interract with the main page, and see the requirement - you can't do that when this is popped out.
- The "open full page" should not be highlighted like that... let's work on that.
- the "open full page", "copy link", and "close" buttons are terrible - they should be a 'copy' icon, and a 'x' icon in the top right corner.
- Let's move the other buttons ("edit", "change status", "change restriction", "delete") to the bottom.
- The "Delete" button should not be the only button that's solid and highlighted.
- The History tab needs some help on the spacing and could probably use a small line inbetween each item.
- The Revisions tab also could use some help on the spacing.
- Let's revisit the 'compare revisions' feature... not sure if it's necessary right now.

### Requirements full page
- All of the items from the "requirements pop out sidebar" section above apply here.
- The spacing needs some serious work. It reads and appears as a wall of text - there's no real distinction between a title and a description/content.
- Is there a specific reason the checkboxes in the description aren't checkable?

## Trash page
- I don't think we need this as it's own item in the sidebar - it should be accessible from the REquirements page, but
- Remove the explanation text from below the title.

## Workspace

### Workspace Admin Users settings
- We should add a Organization/project column in the Users table - it could probably be combined with the Role column.

### Workspace Organizations page
- Let's try to add more info on this page/table - maybe number of projects, is there anything else that would be helpful for users?
