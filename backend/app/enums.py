"""Domain enums: the values stored in enum columns and used by `rules/`.

No SQLAlchemy here, so `rules/` can import these without reaching the database (models map
them with `core.enums.enum_type`). Values are the stored strings; they match the schema doc's
`enum: ...` lists, which the docs consistency tests compare with the models.
"""

from enum import StrEnum

# --- Tenancy (design-doc §4; schema-doc "Users, Tenancy & Auth") ------------------------------


class WorkspaceRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class OrgRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class ProjectRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


# --- Projects (design-doc §1.1, §7) ------------------------------------------------------------


class ProjectType(StrEnum):
    SOFTWARE = "software"
    ERP = "erp"
    GENERAL = "general"


class ProjectStatus(StrEnum):
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ProjectModule(StrEnum):
    """Modules a project may enable. Only shipped-or-v1 modules are allowed values; each v2
    module is added (with the `enabled_modules` CHECK) when it ships (schema-doc, `project`)."""

    SPRINTS = "sprints"
    GITHUB = "github"


# --- Numbering (design-doc §3, "Number allocation") --------------------------------------------


class NumberPrefix(StrEnum):
    """Entity prefixes numbered per project (`project_counter.prefix`). Module prefixes (e.g.
    risks, issues) are added when those modules are designed."""

    REQUIREMENT = "RQ"
    TASK = "TA"
    TEST_CASE = "TC"


# --- Restriction (design-doc §3.1) --------------------------------------------------------------


class RestrictionLevel(StrEnum):
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"


class RestrictionCategory(StrEnum):
    FINANCIAL = "financial"
    PROPRIETARY = "proprietary"
    PII = "pii"
    EXPORT_CONTROLLED = "export_controlled"  # project-only in v1


class AccessKind(StrEnum):
    """Content or management (design-doc §3.1, §5): how each action is marked, and what an
    inherited admin keeps on an export-controlled project without an explicit membership."""

    CONTENT = "content"
    MANAGEMENT = "management"


PROJECT_CATEGORIES = tuple(RestrictionCategory)
CONTENT_ITEM_CATEGORIES = tuple(
    category
    for category in RestrictionCategory
    if category is not RestrictionCategory.EXPORT_CONTROLLED
)

# --- Admin audit events (design-doc §10.1; schema-doc `audit_event`) ---------------------------


class AuditAction(StrEnum):
    WORKSPACE_CREATED = "workspace_created"
    USER_CREATED = "user_created"
    USER_DEACTIVATED = "user_deactivated"
    USER_REACTIVATED = "user_reactivated"
    PASSWORD_RESET = "password_reset"  # noqa: S105 -- an event name, not a password
    PASSWORD_CHANGED = "password_changed"  # noqa: S105 -- an event name, not a password
    SIGNED_OUT_EVERYWHERE = "signed_out_everywhere"
    USER_UPDATED = "user_updated"
    SYSTEM_ADMIN_GRANTED = "system_admin_granted"
    SYSTEM_ADMIN_REVOKED = "system_admin_revoked"
    WORKSPACE_UPDATED = "workspace_updated"
    WORKSPACE_MEMBER_ADDED = "workspace_member_added"
    WORKSPACE_MEMBER_ROLE_CHANGED = "workspace_member_role_changed"
    WORKSPACE_MEMBER_REMOVED = "workspace_member_removed"
    ORG_CREATED = "org_created"
    ORG_UPDATED = "org_updated"
    ORG_MEMBER_ADDED = "org_member_added"
    ORG_MEMBER_ROLE_CHANGED = "org_member_role_changed"
    ORG_MEMBER_REMOVED = "org_member_removed"
    PROJECT_CREATED = "project_created"
    PROJECT_UPDATED = "project_updated"
    PROJECT_ARCHIVED = "project_archived"
    PROJECT_UNARCHIVED = "project_unarchived"
    PROJECT_RESTRICTION_CHANGED = "project_restriction_changed"
    PROJECT_MEMBER_ADDED = "project_member_added"
    PROJECT_MEMBER_ROLE_CHANGED = "project_member_role_changed"
    PROJECT_MEMBER_REMOVED = "project_member_removed"


class AuditEntityType(StrEnum):
    WORKSPACE = "workspace"
    ORGANIZATION = "organization"
    PROJECT = "project"
    USER = "user"


# --- Requirements (design-doc §6; schema-doc "Requirements") ----------------------------------


class RequirementStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class Priority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Approvals (design-doc §6.2; schema-doc "Approvals") --------------------------------------


class ApprovalEntityType(StrEnum):
    REQUIREMENT = "requirement"
    MILESTONE = "milestone"
    TEST_RUN = "test_run"


class ApprovalRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ApprovalDecision(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REPLACED = "replaced"


# --- Change log (design-doc §10; schema-doc `activity_log`) -----------------------------------


class ActivityEntityType(StrEnum):
    REQUIREMENT = "requirement"
    TASK = "task"
    TESTCASE = "testcase"
    PHASE = "phase"
    MILESTONE = "milestone"
    APPROVAL_REQUEST = "approval_request"
    TEST_RESULT = "test_result"
    PROJECT = "project"


class ActivityAction(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    RESTORED = "restored"
    LINKED = "linked"
    UNLINKED = "unlinked"


class ActivityField(StrEnum):
    STATUS = "status"
    ASSIGNEE_ID = "assignee_id"
    REPORTER_ID = "reporter_id"
    REVIEWER_ID = "reviewer_id"
    SPRINT_ID = "sprint_id"
    MILESTONE_ID = "milestone_id"
    PHASE_ID = "phase_id"
    WORKSTREAM_ID = "workstream_id"
    PRIORITY = "priority"
    SEVERITY = "severity"
    START_DATE = "start_date"
    END_DATE = "end_date"
    DUE_DATE = "due_date"
    TARGET_DATE = "target_date"
    BASELINE_START = "baseline_start"
    BASELINE_END = "baseline_end"
    BASELINE_DATE = "baseline_date"
    REQUIREMENT_ID = "requirement_id"
    PARENT_REQUIREMENT_ID = "parent_requirement_id"
    TIME_ESTIMATE = "time_estimate"
    APPROVED_REVISION_ID = "approved_revision_id"
    APPROVER_ID = "approver_id"
    RESTRICTION_LEVEL = "restriction_level"
    RESTRICTION_CATEGORIES = "restriction_categories"
    LEAD_ID = "lead_id"
    ACTUAL_RESULT = "actual_result"
