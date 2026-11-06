"""A test-only content router (S2-C4; DL-16): the export-control gate over HTTP, until S2-C5's
requirement routes exist (build plan, Slice 2 checkpoint table, row 4).

Over a real project, through the load-and-authorize dependency (`authorized`):

- a content read and a content mutation (design-doc §3.1: content is everything inside the
  project);
- a personal action (design-doc §5: the relationship rule decides, for a user with content
  access), on a stand-in item whose author the request names;
- a management mutation (§3.1: the project's settings, members, restriction);
- a content-scoped list: `ProjectRepository.visible(content_scope(ctx))`, the projects whose
  content the user can see.
"""

import uuid
from typing import Annotated

import pytest
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.authz.actions import REGISTRY, ActionSpec, Level
from app.authz.scoping import content_scope
from app.authz.target import Target, project_target
from app.core.db import SessionDep
from app.enums import AccessKind, OrgRole, ProjectRole, WorkspaceRole
from app.models.project import Project
from app.repositories.project import ProjectRepository
from app.routers.deps import AuthzContextDep, authorized
from tests.support.authz import Comment, is_author

CONTENT_READ = "test_content.read"
CONTENT_EDIT = "test_content.edit"
EDIT_OWN_ITEM = "test_content.edit_own"
MANAGE = "test_content.manage"

# Inherited project admin (design-doc §5, "Role capabilities").
_WS_ADMIN = WorkspaceRole.ADMIN
_ORG_ADMIN = OrgRole.ADMIN

CONTENT_ACTIONS: dict[str, ActionSpec] = {
    # Project viewers and up, inherited admins (like `requirement.view`).
    CONTENT_READ: ActionSpec(
        Level.PROJECT,
        access=AccessKind.CONTENT,
        workspace_role=_WS_ADMIN,
        org_role=_ORG_ADMIN,
        project_role=ProjectRole.VIEWER,
        mutation=False,
    ),
    # Project members and up, inherited admins.
    CONTENT_EDIT: ActionSpec(
        Level.PROJECT,
        access=AccessKind.CONTENT,
        workspace_role=_WS_ADMIN,
        org_role=_ORG_ADMIN,
        project_role=ProjectRole.MEMBER,
    ),
    # A personal action, with a role at every level, to prove no role grants it.
    EDIT_OWN_ITEM: ActionSpec(
        Level.PROJECT,
        access=AccessKind.CONTENT,
        workspace_role=WorkspaceRole.MEMBER,
        org_role=OrgRole.MEMBER,
        project_role=ProjectRole.VIEWER,
        relationship=is_author,
    ),
    # Project admins, inherited included (like `project.update`).
    MANAGE: ActionSpec(
        Level.PROJECT,
        access=AccessKind.MANAGEMENT,
        workspace_role=_WS_ADMIN,
        org_role=_ORG_ADMIN,
        project_role=ProjectRole.ADMIN,
    ),
}


def register_content_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, spec in CONTENT_ACTIONS.items():
        monkeypatch.setitem(REGISTRY, name, spec)


async def load_project(project_id: uuid.UUID, session: SessionDep) -> tuple[Project, Target] | None:
    project = await session.get(Project, project_id)
    return None if project is None else (project, project_target(project))


async def load_item(
    project_id: uuid.UUID, author: uuid.UUID, session: SessionDep
) -> tuple[Project, Target] | None:
    """The project, with a stand-in item inside it written by `author`."""
    project = await session.get(Project, project_id)
    return None if project is None else (project, project_target(project, Comment(author)))


class Named(BaseModel):
    id: uuid.UUID
    name: str


class Text(BaseModel):
    text: str


class Keys(BaseModel):
    keys: list[str]


router = APIRouter(prefix="/test/content")

ReadContent = Annotated[Project, Depends(authorized(load_project, CONTENT_READ))]
EditContent = Annotated[Project, Depends(authorized(load_project, CONTENT_EDIT))]
EditOwnItem = Annotated[Project, Depends(authorized(load_item, EDIT_OWN_ITEM))]
Manage = Annotated[Project, Depends(authorized(load_project, MANAGE))]


@router.get("/projects/{project_id}/items")
async def read_content(project: ReadContent) -> Named:
    return Named(id=project.id, name=project.name)


@router.post("/projects/{project_id}/items")
async def edit_content(project: EditContent, body: Text, session: SessionDep) -> Named:
    project.description = body.text
    await session.flush()
    return Named(id=project.id, name=project.name)


@router.post("/projects/{project_id}/own-item")
async def edit_own_item(project: EditOwnItem, body: Text, session: SessionDep) -> Named:
    project.description = body.text
    await session.flush()
    return Named(id=project.id, name=project.name)


@router.post("/projects/{project_id}/manage")
async def manage(project: Manage, body: Text, session: SessionDep) -> Named:
    project.name = body.text
    await session.flush()
    return Named(id=project.id, name=project.name)


@router.get("/projects")
async def content_projects(ctx: AuthzContextDep, session: SessionDep) -> Keys:
    """The keys of the projects whose content the user can see, in key order."""
    statement = ProjectRepository(session).visible(content_scope(ctx)).order_by(Project.key)
    return Keys(keys=[project.key for project in await session.scalars(statement)])
