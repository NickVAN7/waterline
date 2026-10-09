"""Test-only helpers for the authorization core (S1-C7; DL-16, DL-44).

- A fixed tenancy layout and one `AuthzContext` per persona, for the pure unit tests.
- Test-only actions at org and project level (DL-44: the only real actions are the four
  workspace-level ones), registered in `REGISTRY` by each test that needs them.
- A test-only router over real projects, orgs, and workspaces, using the load-and-authorize
  dependency (`authorized`) and module gating, and a helper to sign a user in.
"""

import uuid
from dataclasses import dataclass
from typing import Annotated

import pytest
from fastapi import APIRouter, Depends
from httpx import AsyncClient
from pydantic import BaseModel
from sqlalchemy import ColumnElement, or_, true
from sqlalchemy.orm import QueryableAttribute

from app.authz.actions import REGISTRY, Action, ActionSpec, Level
from app.authz.context import AuthzContext, ProjectAccess
from app.authz.scoping import Scope
from app.authz.target import Target, org_target, project_target, workspace_target
from app.core.db import SessionDep
from app.core.security import generate_token, hash_token
from app.enums import OrgRole, ProjectModule, ProjectRole, WorkspaceRole
from app.models.org import Organization
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace
from app.routers.deps import authorized
from tests.factories.auth import UserSessionFactory

# --- A fixed layout (unit tests) ----------------------------------------------------------------
# Workspace WS holds orgs ORG and ORG2; WS2 holds ORG3. Projects PROJ and PROJ2 are in ORG,
# PROJ3 in ORG2, PROJ4 in ORG3.

WS = uuid.UUID(int=1)
WS2 = uuid.UUID(int=2)
ORG = uuid.UUID(int=10)
ORG2 = uuid.UUID(int=11)
ORG3 = uuid.UUID(int=12)
PROJ = uuid.UUID(int=100)
PROJ2 = uuid.UUID(int=101)
PROJ3 = uuid.UUID(int=102)
PROJ4 = uuid.UUID(int=103)

WORKSPACE_TARGET = Target(workspace_id=WS)
ORG_TARGET = Target(workspace_id=WS, organization_id=ORG)
PROJECT_TARGET = Target(workspace_id=WS, organization_id=ORG, project_id=PROJ)
ARCHIVED_PROJECT_TARGET = Target(
    workspace_id=WS, organization_id=ORG, project_id=PROJ, archived=True
)


def _user(n: int) -> uuid.UUID:
    return uuid.UUID(int=1000 + n)


# Who each persona is, relative to WS, ORG, and PROJ.
PERSONAS: dict[str, AuthzContext] = {
    "system_admin": AuthzContext(user_id=_user(1), is_system_admin=True),
    "workspace_owner": AuthzContext(user_id=_user(2), workspace_roles={WS: WorkspaceRole.OWNER}),
    "workspace_admin": AuthzContext(user_id=_user(3), workspace_roles={WS: WorkspaceRole.ADMIN}),
    "workspace_member": AuthzContext(user_id=_user(4), workspace_roles={WS: WorkspaceRole.MEMBER}),
    "org_owner": AuthzContext(user_id=_user(5), org_roles={ORG: OrgRole.OWNER}),
    "org_admin": AuthzContext(user_id=_user(6), org_roles={ORG: OrgRole.ADMIN}),
    "org_member": AuthzContext(user_id=_user(7), org_roles={ORG: OrgRole.MEMBER}),
    "project_admin": AuthzContext(
        user_id=_user(8), projects={PROJ: ProjectAccess(ProjectRole.ADMIN, ORG, WS)}
    ),
    "project_member": AuthzContext(
        user_id=_user(9), projects={PROJ: ProjectAccess(ProjectRole.MEMBER, ORG, WS)}
    ),
    "project_viewer": AuthzContext(
        user_id=_user(10), projects={PROJ: ProjectAccess(ProjectRole.VIEWER, ORG, WS)}
    ),
    # Admin of another project in the same org: sees ORG, not PROJ.
    "other_project_admin": AuthzContext(
        user_id=_user(11), projects={PROJ2: ProjectAccess(ProjectRole.ADMIN, ORG, WS)}
    ),
    # Owner of another org in the same workspace.
    "other_org_owner": AuthzContext(user_id=_user(12), org_roles={ORG2: OrgRole.OWNER}),
    # Owner of another workspace.
    "other_workspace_owner": AuthzContext(
        user_id=_user(13), workspace_roles={WS2: WorkspaceRole.OWNER}
    ),
    "nobody": AuthzContext(user_id=_user(14)),
}


def rows(allowed: set[str]) -> list[tuple[str, bool]]:
    """One `(persona, expected)` row per persona: True exactly for those in `allowed`."""
    unknown = allowed - PERSONAS.keys()
    assert not unknown, f"no such persona: {unknown}"
    return [(persona, persona in allowed) for persona in PERSONAS]


# --- Test-only actions (DL-44) ------------------------------------------------------------------


@dataclass(frozen=True)
class Comment:
    """A stand-in for an item a personal action is about (e.g. one's own comment)."""

    author_id: uuid.UUID


def is_author(user_id: uuid.UUID, entity: object) -> bool:
    return isinstance(entity, Comment) and entity.author_id == user_id


WS_MEMBER_LEVEL = "test_workspace.member_level"
ORG_CREATE_PROJECT = "test_org.create_project"
ORG_MANAGE = "test_org.manage"
ORG_OWNER_LEVEL = "test_org.owner_level"
PROJECT_VIEW = "test_project.view"
PROJECT_EDIT = "test_project.edit"
PROJECT_MANAGE = "test_project.manage"
PROJECT_UNARCHIVE = "test_project.unarchive"
SYSTEM_ONLY = "test_project.system_only"
EDIT_OWN_COMMENT = "test_comment.edit_own"
UNREGISTERED = "test_project.unregistered"

# The inherited project admin (design-doc §5, "Role capabilities"): workspace owners/admins and
# owners/admins of the project's org.
_WS_ADMIN = WorkspaceRole.ADMIN
_ORG_ADMIN = OrgRole.ADMIN

TEST_ACTIONS: dict[str, ActionSpec] = {
    WS_MEMBER_LEVEL: ActionSpec(Level.WORKSPACE, workspace_role=WorkspaceRole.MEMBER),
    # An org member's `project.create` (design-doc §5, "Org roles").
    ORG_CREATE_PROJECT: ActionSpec(
        Level.ORGANIZATION, workspace_role=WorkspaceRole.ADMIN, org_role=OrgRole.MEMBER
    ),
    ORG_MANAGE: ActionSpec(
        Level.ORGANIZATION, workspace_role=WorkspaceRole.ADMIN, org_role=OrgRole.ADMIN
    ),
    ORG_OWNER_LEVEL: ActionSpec(
        Level.ORGANIZATION, workspace_role=WorkspaceRole.ADMIN, org_role=OrgRole.OWNER
    ),
    PROJECT_VIEW: ActionSpec(
        Level.PROJECT,
        project_role=ProjectRole.VIEWER,
        mutation=False,
        workspace_role=_WS_ADMIN,
        org_role=_ORG_ADMIN,
    ),
    PROJECT_EDIT: ActionSpec(
        Level.PROJECT,
        project_role=ProjectRole.MEMBER,
        workspace_role=_WS_ADMIN,
        org_role=_ORG_ADMIN,
    ),
    PROJECT_MANAGE: ActionSpec(
        Level.PROJECT, project_role=ProjectRole.ADMIN, workspace_role=_WS_ADMIN, org_role=_ORG_ADMIN
    ),
    PROJECT_UNARCHIVE: ActionSpec(
        Level.PROJECT,
        project_role=ProjectRole.ADMIN,
        archive_exempt=True,
        workspace_role=_WS_ADMIN,
        org_role=_ORG_ADMIN,
    ),
    # No role grants it: only a system admin.
    SYSTEM_ONLY: ActionSpec(Level.PROJECT),
    # A personal action, with every role level set, to prove no role grants it.
    EDIT_OWN_COMMENT: ActionSpec(
        Level.PROJECT,
        workspace_role=WorkspaceRole.MEMBER,
        org_role=OrgRole.MEMBER,
        project_role=ProjectRole.VIEWER,
        relationship=is_author,
    ),
}


def register_test_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, spec in TEST_ACTIONS.items():
        monkeypatch.setitem(REGISTRY, name, spec)


# --- A test-only router over real rows (API tests) ----------------------------------------------


async def load_project(project_id: uuid.UUID, session: SessionDep) -> tuple[Project, Target] | None:
    project = await session.get(Project, project_id)
    return None if project is None else (project, project_target(project))


async def load_org(org_id: uuid.UUID, session: SessionDep) -> tuple[Organization, Target] | None:
    org = await session.get(Organization, org_id)
    return None if org is None else (org, org_target(org))


async def load_workspace(
    workspace_id: uuid.UUID, session: SessionDep
) -> tuple[Workspace, Target] | None:
    workspace = await session.get(Workspace, workspace_id)
    return None if workspace is None else (workspace, workspace_target(workspace))


class Named(BaseModel):
    id: uuid.UUID
    name: str


class Rename(BaseModel):
    name: str


router = APIRouter(prefix="/test/authz")

ViewProject = Annotated[Project, Depends(authorized(load_project, PROJECT_VIEW))]
EditProject = Annotated[Project, Depends(authorized(load_project, PROJECT_EDIT))]
UnarchiveProject = Annotated[Project, Depends(authorized(load_project, PROJECT_UNARCHIVE))]
UnregisteredOnProject = Annotated[Project, Depends(authorized(load_project, UNREGISTERED))]
ViewSprints = Annotated[
    Project, Depends(authorized(load_project, PROJECT_VIEW, module=ProjectModule.SPRINTS))
]
EditSprints = Annotated[
    Project, Depends(authorized(load_project, PROJECT_EDIT, module=ProjectModule.SPRINTS))
]
CreateProjectInOrg = Annotated[Organization, Depends(authorized(load_org, ORG_CREATE_PROJECT))]
ViewWorkspace = Annotated[Workspace, Depends(authorized(load_workspace, Action.WORKSPACE_VIEW))]


@router.get("/projects/{project_id}")
async def view_project(project: ViewProject) -> Named:
    return Named(id=project.id, name=project.name)


@router.post("/projects/{project_id}/rename")
async def rename_project(project: EditProject, body: Rename, session: SessionDep) -> Named:
    project.name = body.name
    await session.flush()
    return Named(id=project.id, name=project.name)


@router.post("/projects/{project_id}/unarchive")
async def unarchive_project(project: UnarchiveProject, session: SessionDep) -> Named:
    project.archived_at = None
    await session.flush()
    return Named(id=project.id, name=project.name)


@router.post("/projects/{project_id}/unregistered")
async def unregistered_action(project: UnregisteredOnProject) -> Named:
    return Named(id=project.id, name=project.name)


@router.get("/projects/{project_id}/sprints")
async def view_sprints(project: ViewSprints) -> Named:
    return Named(id=project.id, name=project.name)


@router.post("/projects/{project_id}/sprints")
async def edit_sprints(project: EditSprints) -> Named:
    return Named(id=project.id, name=project.name)


@router.post("/orgs/{org_id}/create-project")
async def create_project_in_org(org: CreateProjectInOrg) -> Named:
    return Named(id=org.id, name=org.name)


@router.get("/workspaces/{workspace_id}")
async def view_workspace(workspace: ViewWorkspace) -> Named:
    return Named(id=workspace.id, name=workspace.name)


SESSION_COOKIE = "__Host-session"


async def sign_in_as(client: AsyncClient, user: User) -> None:
    """Give `client` a live session for `user` (a session row, and its cookie)."""
    token = generate_token()
    await UserSessionFactory.create_async(user=user, token_hash=hash_token(token))
    client.cookies.set(SESSION_COOKIE, token)


def scope_filter(
    scope: Scope,
    id_column: QueryableAttribute[uuid.UUID],
    workspace_column: QueryableAttribute[uuid.UUID],
    organization_column: QueryableAttribute[uuid.UUID] | None = None,
) -> ColumnElement[bool]:
    """`Scope`'s documented meaning as a WHERE clause (what a repository builds from it)."""
    if scope.everything:
        return true()
    clauses = [id_column.in_(scope.ids), workspace_column.in_(scope.workspace_ids)]
    if organization_column is not None:
        clauses.append(organization_column.in_(scope.organization_ids))
    return or_(*clauses)
