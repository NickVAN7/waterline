---
title: Requirements
group: Using Waterline
order: 3
description: Write requirements, arrange them in a tree, edit them, and follow their history.
---

**Requirements** describe what a project has to deliver. Each one has an ID like
`PORTAL-RQ-7`, a status, a priority, and a description with its acceptance criteria. They sit in
a tree, so a large requirement can be broken into smaller ones under it.

## Browse the tree

Open **Requirements** in the project's sidebar. The tree starts with only the top-level
requirements showing: open a branch with its arrow. To open everything under one requirement at
once, select its row and choose **Expand requirement**. A requirement with a pending approval
request shows **Awaiting approval** beside its status.

> [!TIP]
> ++→++ opens a selected row's branch and ++←++ closes it.

## Create a requirement

1. Select **New requirement** at the top of the page.
2. Give it a **Title**, then pick its **Priority** and **Parent**.
3. Fill in the **Description**. It starts from your project type's template, which includes an
   **Acceptance Criteria** heading: write the criteria as a numbered list. **Preview** shows how
   it will read.
4. Select **Create requirement**.

New requirements start as **Draft**, at the bottom of their level.

## Open and edit a requirement

Select a requirement's ID in the tree to open it in a side panel. On a wide window you can keep
working in the tree while it's open, and open other requirements from it. **Open full page** gives the
requirement a page of its own, and **Copy link** copies its address to share.

![A project's requirements as a tree, with one requirement open in a panel beside it showing its status, details, and description.](images/requirement-panel.webp)

Select **Edit** to change the **Title**, **Description**, or **Priority**, add a **Change note**
if it helps, and select **Save**. A changed title or description is saved as a new revision.

> [!WARNING]
> If someone else saved the requirement while you were editing, your save is refused. Copy what
> you typed before you reload, or it's lost.

## Change its status or restriction

**Change status** sets where the requirement stands, such as **In progress** or **Deferred**. It becomes
**Approved** only through an approval.

A requirement can be restricted more tightly than its project: under **More actions**, choose
**Change restriction…** and pick its level and categories. Anyone who edits requirements can
raise a restriction; only the project's admins can lower it, and never below the project's own.

## Get it approved

Project admins ask the right people to sign off on the requirement from its **Approval** section.
See [Approvals](/docs/approvals) for how a request works and how to decide on one.

## See what changed

**History** lists every change, who made it, and when. **Revisions** lists the saved versions of
the title and description; **Compare revisions** shows what changed between any two.

## Move or delete a requirement

Select a row and open its **Move** menu to move the requirement up or down among its neighbors, or
**Move to…** to give it a new parent. Its children move with it.

To delete a requirement, open it, then **More actions** and **Delete…**. It goes to the
project's [Trash](/docs/trash), where it can be restored.

## Who can do this

| Action | Who can do this |
|---|---|
| See requirements | Anyone who can see the project's content |
| Create, edit, move, or change status | Project members and admins |
| Raise or lower a restriction | Members raise it; project admins raise or lower it |
| Request approval, or approve by hand | Project admins |
| Delete | Its reporter, until it's first approved, and project admins |
