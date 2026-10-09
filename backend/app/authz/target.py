"""What an action is taken on, as `authorize()` sees it: where the entity sits, and the facts
the rules need (the project archived, its modules, the entity itself for a personal action)."""

import uuid
from dataclasses import dataclass, field

from app.models.org import Organization
from app.models.project import Project
from app.models.workspace import Workspace


@dataclass(frozen=True)
class Target:
    """`organization_id` is set for org- and project-level targets, `project_id` for project
    level (an entity inside a project is a project-level target). `archived` and
    `enabled_modules` describe that project."""

    workspace_id: uuid.UUID
    organization_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    archived: bool = False
    enabled_modules: frozenset[str] = field(default_factory=frozenset[str])
    entity: object = None


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
        entity=entity,
    )
