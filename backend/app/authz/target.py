"""What an action is taken on, as `authorize()` sees it: where the entity sits, and the facts
the rules need (the project archived, its modules, the entity itself for a personal action, a
user's memberships for the rank rule)."""

import uuid
from dataclasses import dataclass, field

from app.enums import ClassificationCategory
from app.models.org import Organization
from app.models.project import Project
from app.models.workspace import Workspace
from app.rules.account_rank import Account


@dataclass(frozen=True)
class Target:
    """`organization_id` is set for org- and project-level targets, `project_id` for project
    level (an entity inside a project is a project-level target). `archived` and
    `enabled_modules` describe that project, and `export_controlled` whether it has the
    `export_controlled` category (design-doc §3.1). `user_id` is set for a user-level target
    (DL-73), whose `entity` is the user's `Account` (their memberships, for the rank rule)."""

    workspace_id: uuid.UUID
    organization_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    archived: bool = False
    enabled_modules: frozenset[str] = field(default_factory=frozenset[str])
    export_controlled: bool = False
    entity: object = None
    user_id: uuid.UUID | None = None


def workspace_target(workspace: Workspace) -> Target:
    """The workspace itself."""
    return Target(workspace_id=workspace.id)


def org_target(org: Organization) -> Target:
    """The org itself, in its workspace."""
    return Target(workspace_id=org.workspace_id, organization_id=org.id)


def project_target(project: Project, entity: object = None) -> Target:
    """The project, or `entity` inside it: the project's workspace, org, archived state, and
    modules."""
    return Target(
        workspace_id=project.workspace_id,
        organization_id=project.organization_id,
        project_id=project.id,
        archived=project.archived_at is not None,
        enabled_modules=frozenset(project.enabled_modules),
        # An unsaved project has no categories until the database default fills them.
        export_controlled=ClassificationCategory.EXPORT_CONTROLLED
        in (project.classification_categories or ()),
        entity=entity,
    )


def user_target(workspace_id: uuid.UUID, user_id: uuid.UUID, account: Account) -> Target:
    """A user, in their workspace, with their memberships for the rank rule (DL-73)."""
    return Target(workspace_id=workspace_id, user_id=user_id, entity=account)
