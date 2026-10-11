"""Projects (build plan, "The projects API", DL-76)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app.authz.actions import Action
from app.core.db import SessionDep
from app.core.errors import ErrorBody
from app.core.lists import Page
from app.routers.deps import (
    AuthzContextDep,
    SignedInUserDep,
    authorized,
    load_org,
    load_project,
)
from app.schemas.project import (
    ModuleGuidance,
    ProjectCreate,
    ProjectItem,
    ProjectRead,
    ProjectUpdate,
)
from app.schemas.workspace import SlugAvailability
from app.services.org import OrgEntity
from app.services.project import OrgProjectQuery, ProjectEntity, ProjectService, module_guidance

router = APIRouter(tags=["project"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorBody}
    for code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    )
}

OrgViewed = Annotated[OrgEntity, Depends(authorized(load_org, Action.ORG_VIEW))]
Creating = Annotated[OrgEntity, Depends(authorized(load_org, Action.PROJECT_CREATE))]
Viewed = Annotated[ProjectEntity, Depends(authorized(load_project, Action.PROJECT_VIEW))]
Updated = Annotated[ProjectEntity, Depends(authorized(load_project, Action.PROJECT_UPDATE))]
Archived = Annotated[ProjectEntity, Depends(authorized(load_project, Action.PROJECT_ARCHIVE))]
Unarchived = Annotated[ProjectEntity, Depends(authorized(load_project, Action.PROJECT_UNARCHIVE))]
ProjectQuery = Annotated[OrgProjectQuery, Query()]  # pyright: ignore[reportInvalidTypeForm]


@router.post("/orgs/{org_id}/projects", status_code=status.HTTP_201_CREATED, responses=_ERRORS)
async def create_project(
    org: Creating, body: ProjectCreate, ctx: AuthzContextDep, session: SessionDep
) -> ProjectRead:
    """Create a project; its first admin (the caller, or `first_admin_id` with
    `project.assign_first_admin`) becomes its lead. 422 on `key`: the key rule's problems or
    `taken`; on `first_admin_id`: `account_inactive`."""
    return await ProjectService(session).create(ctx, org, body)


@router.get("/orgs/{org_id}/projects", responses=_ERRORS)
async def list_projects(
    org: OrgViewed,
    query: ProjectQuery,
    ctx: AuthzContextDep,
    session: SessionDep,
) -> Page[ProjectItem]:
    """The org's projects the caller can open; archived ones only with `include_archived`."""
    return await ProjectService(session).list_in_org(ctx, org, query)


@router.get("/orgs/{org_id}/project-key-availability", responses=_ERRORS)
async def project_key_availability(
    org: Creating, key: str, session: SessionDep
) -> SlugAvailability:
    """Whether `key`, uppercased, could be a new project's key in the workspace."""
    return await ProjectService(session).key_availability(org, key)


@router.get("/projects/{key}", responses=_ERRORS)
async def get_project(project: Viewed, ctx: AuthzContextDep, session: SessionDep) -> ProjectRead:
    """The project, with the actions the caller may take on it."""
    return ProjectService(session).read(ctx, project)


@router.patch("/projects/{key}", responses=_ERRORS)
async def update_project(
    project: Updated, body: ProjectUpdate, ctx: AuthzContextDep, session: SessionDep
) -> ProjectRead:
    """Change the project's details. 422 on `lead_id`: `not_member` or `account_inactive`."""
    return await ProjectService(session).update(ctx, project, body)


@router.post("/projects/{key}/archive", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS)
async def archive_project(project: Archived, ctx: AuthzContextDep, session: SessionDep) -> None:
    """Archive the project: read-only until unarchived."""
    await ProjectService(session).archive(ctx, project)


@router.post("/projects/{key}/unarchive", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS)
async def unarchive_project(project: Unarchived, ctx: AuthzContextDep, session: SessionDep) -> None:
    """Unarchive the project."""
    await ProjectService(session).unarchive(ctx, project)


@router.get("/module-guidance", responses=_ERRORS)
async def get_module_guidance(_user: SignedInUserDep) -> ModuleGuidance:
    """Which modules each project type recommends, a note per module, and which have shipped."""
    return module_guidance()
