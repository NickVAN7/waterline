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


# --- Classification (design-doc §3.1) -----------------------------------------------------------


class ClassificationLevel(StrEnum):
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class ClassificationCategory(StrEnum):
    FINANCIAL = "financial"
    PROPRIETARY = "proprietary"
    PII = "pii"
    EXPORT_CONTROLLED = "export_controlled"  # project-only in v1


PROJECT_CATEGORIES = tuple(ClassificationCategory)
CONTENT_ITEM_CATEGORIES = tuple(
    category
    for category in ClassificationCategory
    if category is not ClassificationCategory.EXPORT_CONTROLLED
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
    PROJECT_CLASSIFICATION_CHANGED = "project_classification_changed"
    PROJECT_MEMBER_ADDED = "project_member_added"
    PROJECT_MEMBER_ROLE_CHANGED = "project_member_role_changed"
    PROJECT_MEMBER_REMOVED = "project_member_removed"


class AuditEntityType(StrEnum):
    WORKSPACE = "workspace"
    ORGANIZATION = "organization"
    PROJECT = "project"
    USER = "user"
