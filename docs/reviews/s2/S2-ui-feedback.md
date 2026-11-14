# UI Feedback for Waterline

Each item's Slice 3 row follows its arrow (`docs/reviews/s3/S3-plan.md`, Part 3); S3-C33
checks none was dropped. A `Qn` is the plan record's question.

## General / User Account

### Overall things to address
- When you're viewing a page, when you scroll to the bottom, the sidebar on the left also scrolls and the content at the top disappears. This shouldn't happen. → S3-C0j
- The breadcrumbs need some work throughout the app - they aren't intuitive, and could use a sleeker look. → S3-C0e
- Let's explore a Frontend/UI skill to add to the page design process - it needs some work. (Ideas: Impeccable, agent-skills,Anthropics frontend design ) → S3-C0j (Q12i)
- We need to work on the text displayed in the browser tab - it's become jumbled and long in the tab. → S3-C0j
- It would be good to add a distiction between Org and Project items in the left-hand menu... or at least a way to tell the user that they're looking at a Organization's options, and not the Projects. → S3-C0j

### Sign In screen
- None

### Home/My Work
- Let's move the "favorite" star to the left-hand side, in front of the Project name. → S3-C0f
- Each project's row in cluttered - let's remove the access, or find another way to list it. → S3-C0f (DL-334)
- Make a note to discuss, and explore options of better organizing the Projects section - It might make sense to group projects by Organization. Also, I don't like that not all of a user's projects are shown on the My Work page. → S3-C0f (DL-329, DL-330, DL-349)
- This probably contradicts a past decision, but I don't think we need a "My past decisions" on the My Work page. → S3-C0f (DL-333)

### Account Dropdown
- None

### User Account settings
- "Change password" should be a button, and not a linked text. → S3-C0j

### Documentation
- This section needs some serious work - the generated markdown is does not look good. Make a note that we need to discuss this much more in-depth to make this page usable. → S3-C0g, S3-C0h



## Organization

### Organization Overview
- "Archived" section, should be "Archived Projects" → S3-C0k
- The status of a project in the Archived section, should be "Canceled" or "Archived" - it doesn't make sense to have a archived project in a Planning status. → S3-C0k
- The "Name Acme Manufacturing" isn't really needed right below the header - can remove it. → S3-C0k
- Maybe add the slug to the title: "Acme Manufacturing (acme) overview"... or find a better way to include it. → S3-C0k

### Organization Settings
- None

### Organization Members
- Need to change the 'deactivated' tag/label thing and distinguish deactivated users a different way. → S3-C0k
- Showing deactivated shouldn't change the width of the columns either. → S3-C0k
- When adding a member to the orgainization, should we prompt the admin to add them to the org's projects? It seems inefficient for the admin to have to add them in two places if they add through the org's members - although, adding a user from the project, also adds them to the org... but it might not hurt. → S3-C0m (Q12g)

### Add a person form (organization)
- None


## Project

### Project overview screen (All Projects)
- It would be good to add a way to tell what organization a project belongs to on this screen, and in general on the project's pages. → S3-C0e (the trail starts at the org)

### Project Dropdown
- The dropdown arrow should be right-justified, and not just next to the project name. → S3-C0j
- I don't like the "All projects" button being blue and underlined like that, let's highlight it in a different way. → S3-C0j
- The project filter may not be needed in all cases - it might be better to allow the user to search/filter by clicking a button, which would then let the filter field be shown. → S3-C0j

### Project settings
- Is there a way to minimize the Modules section? It takes up a lot of space on the page... let's discuss. → S3-C0l (Q12c)
- There should be another way to move a project's status other than this page. Maybe on the main project page... but that isn't developed yet. → S3-C30 (Q12f)
- Save Restriction button should be the primary color (match Save settings) → S3-C0l

### Project members
- Let's move "Show deactivated" to the bottom of the list... it looks weird on the top by itself. → S3-C16: into the filter bar (TD-97)

### Add a member form (Projects)
- I don't like how the user list automatically opens on this form - my assumption is that it's because that object has the focus, but we should probably change the focus to the title of the form anyway. → S3-C0l
- On the Add by email form, the default role should be "Member", not "viewer". → S3-C0l

### Access review screen
- The "Why they reach it" column needs a different name - how does it differ from the Project Role column? → S3-C0k
- The value of "none" in Project role doesn't make sense - if they are admins from inherited roles (Workspace/System/org), then they should just be Admin. A related note, I don't know if these admins need to be expicitly called out in the Member access list. It might be confusing for a project admin to see these people... but TBD. → S3-C0k (Q12h)
- You should be able to go back to the members page from this one. → S3-C0e (breadcrumbs)


## Requirements

### Project's requirements
- the hints "Select a requirement to expand/move it" shouldn't show like they are. → S3-C0l
- Let's move the "Expand requirements" and "move" buttons to be right-justified to the table. → S3-C0l
- There is too much space between the Title, and the Requirement table. → S3-C0l
- There should be a filter, or a column on the requirements table that specifies if a requirement is awaiting approval... maybe a new status label? → S3-C0l (Q12b: the badge), S3-C26 (the filter)

### Requirements pop out sidebar
- The design isn't great - the purpose of a pop-out bar, is so you can still interract with the main page, and see the requirement - you can't do that when this is popped out. → S3-C0d (DL-321)
- The "open full page" should not be highlighted like that... let's work on that. → S3-C0d (DL-325)
- the "open full page", "copy link", and "close" buttons are terrible - they should be a 'copy' icon, and a 'x' icon in the top right corner. → S3-C0d (DL-325)
- Let's move the other buttons ("edit", "change status", "change restriction", "delete") to the bottom. → S3-C0d (DL-325 keeps them in the header)
- The "Delete" button should not be the only button that's solid and highlighted. → S3-C0d (DL-325)
- The History tab needs some help on the spacing and could probably use a small line inbetween each item. → S3-C0l
- The Revisions tab also could use some help on the spacing. → S3-C0l
- Let's revisit the 'compare revisions' feature... not sure if it's necessary right now. → S3-C0l (Q12e: kept, restyled)

### Requirements full page
- All of the items from the "requirements pop out sidebar" section above apply here. → S3-C0d (DL-326)
- The spacing needs some serious work. It reads and appears as a wall of text - there's no real distinction between a title and a description/content. → S3-C0l
- Is there a specific reason the checkboxes in the description aren't checkable? → no change (Q12d: read-only in v1; subtasks are the checklist for tasks)

## Trash page
- I don't think we need this as it's own item in the sidebar - it should be accessible from the REquirements page, but [completed by the owner, Nov 10, 2026: "…and any other pages that will allow the user to 'Trash' an item"] → S3-C0l (Requirements), S3-C20 (Tasks), Slice 5 (Test cases); DL-350
- Remove the explanation text from below the title. → S3-C0l

## Workspace

### Workspace Admin Users settings
- We should add a Organization/project column in the Users table - it could probably be combined with the Role column. → S3-C0k

### Workspace Organizations page
- Let's try to add more info on this page/table - maybe number of projects, is there anything else that would be helpful for users? → S3-C0k
