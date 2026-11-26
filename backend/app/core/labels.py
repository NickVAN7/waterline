"""The words a person sees for stored values, where the server writes them out: CSV exports
(S3-C14, owner: labels as on screen). The requirement statuses and priorities match the
frontend's `src/app/labels.ts`; task labels are set here first, and its task screens use the
same words."""

from app.enums import Priority, RequirementStatus, Severity, TaskStatus, TaskType

PRIORITY = {
    Priority.CRITICAL: "Critical",
    Priority.HIGH: "High",
    Priority.MEDIUM: "Medium",
    Priority.LOW: "Low",
}
REQUIREMENT_STATUS = {
    RequirementStatus.DRAFT: "Draft",
    RequirementStatus.APPROVED: "Approved",
    RequirementStatus.IN_PROGRESS: "In progress",
    RequirementStatus.DONE: "Done",
    RequirementStatus.REJECTED: "Rejected",
    RequirementStatus.DEFERRED: "Deferred",
}
# An approved requirement edited since its approval: the tree's status badge (design-doc §6.1;
# `requirementStatusBadge` in labels.ts).
APPROVED_MODIFIED = "Approved · modified"
TASK_STATUS = {
    TaskStatus.TODO: "To do",
    TaskStatus.IN_PROGRESS: "In progress",
    TaskStatus.BLOCKED: "Blocked",
    TaskStatus.IN_REVIEW: "In review",
    TaskStatus.DONE: "Done",
    TaskStatus.CANCELLED: "Cancelled",
}
TASK_TYPE = {
    TaskType.FEATURE: "Feature",
    TaskType.BUG: "Bug",
    TaskType.CHORE: "Chore",
    TaskType.SPIKE: "Spike",
    TaskType.CONFIG: "Config",
    TaskType.DATA: "Data",
    TaskType.TRAINING: "Training",
}
SEVERITY = {
    Severity.S1: "S1",
    Severity.S2: "S2",
    Severity.S3: "S3",
    Severity.S4: "S4",
}
