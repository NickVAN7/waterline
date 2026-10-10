"""Targets: where an entity sits, and the facts `authorize()` needs about its project (design-doc
§5; app/authz/target.py)."""

import uuid
from datetime import UTC, datetime

from app.authz.target import Target, org_target, project_target, workspace_target
from app.enums import ProjectModule, ProjectType
from app.models.org import Organization
from app.models.project import Project
from app.models.workspace import Workspace

WORKSPACE_ID = uuid.UUID(int=1)
ORG_ID = uuid.UUID(int=10)


def project(**values: object) -> Project:
    return Project(
        organization_id=ORG_ID,
        workspace_id=WORKSPACE_ID,
        key="PMT",
        name="Payments",
        type=ProjectType.SOFTWARE,
        **values,
    )


def test_a_workspace_target_is_the_workspace_itself() -> None:
    workspace = Workspace(name="Acme Consulting", slug="acme")

    assert workspace_target(workspace) == Target(workspace_id=workspace.id)


def test_an_org_target_is_the_org_in_its_workspace() -> None:
    org = Organization(workspace_id=WORKSPACE_ID, name="Bolt Foods", slug="bolt")

    assert org_target(org) == Target(workspace_id=WORKSPACE_ID, organization_id=org.id)


def test_a_project_target_carries_its_org_workspace_and_modules() -> None:
    live = project(enabled_modules=[ProjectModule.SPRINTS.value], archived_at=None)

    assert project_target(live) == Target(
        workspace_id=WORKSPACE_ID,
        organization_id=ORG_ID,
        project_id=live.id,
        archived=False,
        enabled_modules=frozenset({"sprints"}),
        entity=None,
    )


def test_a_project_with_archived_at_set_is_an_archived_target() -> None:
    archived = project(enabled_modules=[], archived_at=datetime(2026, 10, 1, tzinfo=UTC))

    assert project_target(archived) == Target(
        workspace_id=WORKSPACE_ID,
        organization_id=ORG_ID,
        project_id=archived.id,
        archived=True,
        enabled_modules=frozenset(),
    )


def test_an_entity_inside_a_project_is_a_project_level_target_carrying_the_entity() -> None:
    live = project(enabled_modules=["sprints", "github"], archived_at=None)
    comment = object()

    assert project_target(live, comment) == Target(
        workspace_id=WORKSPACE_ID,
        organization_id=ORG_ID,
        project_id=live.id,
        enabled_modules=frozenset({"sprints", "github"}),
        entity=comment,
    )
