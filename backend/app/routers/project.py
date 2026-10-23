"""Projects (build plan, "The projects API", DL-76)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.authz.actions import Action
from app.core.db import SessionDep
from app.core.lists import Page
from app.routers.deps import (
    ERRORS,
    AuthzContextDep,
    SignedInUserDep,
    authorized,
    load_org,
    load_project,
)
from app.schemas.project import (
    ClassificationUpdate,
    MemberCandidate,
    ModuleGuidance,
    ProjectAccessReview,
    ProjectCreate,
    ProjectItem,
    ProjectMemberAdd,
    ProjectMemberCreate,
    ProjectMemberRead,
    ProjectMemberRoleUpdate,
    ProjectRead,
    ProjectUpdate,
)
from app.schemas.workspace import SlugAvailability
from app.services.org import OrgEntity
from app.services.project import (
    MEMBER_CANDIDATES,
    PROJECT_MEMBERS,
    OrgProjectQuery,
    ProjectEntity,
    ProjectService,
    module_guidance,
)

router = APIRouter(tags=["project"])

OrgViewed = Annotated[OrgEntity, Depends(authorized(load_org, Action.ORG_VIEW))]
Creating = Annotated[OrgEntity, Depends(authorized(load_org, Action.PROJECT_CREATE))]
FirstAdminAssigning = Annotated[
    OrgEntity, Depends(authorized(load_org, Action.PROJECT_ASSIGN_FIRST_ADMIN))
]
Viewed = Annotated[ProjectEntity, Depends(authorized(load_project, Action.PROJECT_VIEW))]
Updated = Annotated[ProjectEntity, Depends(authorized(load_project, Action.PROJECT_UPDATE))]
Archived = Annotated[ProjectEntity, Depends(authorized(load_project, Action.PROJECT_ARCHIVE))]
Unarchived = Annotated[ProjectEntity, Depends(authorized(load_project, Action.PROJECT_UNARCHIVE))]
MembersManaged = Annotated[
    ProjectEntity, Depends(authorized(load_project, Action.PROJECT_MEMBER_MANAGE))
]
AccessViewed = Annotated[
    ProjectEntity,
    Depends(authorized(load_project, Action.PROJECT_VIEW_ACCESS, hide_denial=True)),
]
ProjectQuery = Annotated[OrgProjectQuery, Query()]  # pyright: ignore[reportInvalidTypeForm]
MemberQuery = Annotated[PROJECT_MEMBERS.query_model, Query()]  # pyright: ignore[reportInvalidTypeForm]
CandidateQuery = Annotated[MEMBER_CANDIDATES.query_model, Query()]  # pyright: ignore[reportInvalidTypeForm]


@router.post("/orgs/{org_id}/projects", status_code=status.HTTP_201_CREATED, responses=ERRORS)
async def create_project(
    org: Creating, body: ProjectCreate, ctx: AuthzContextDep, session: SessionDep
) -> ProjectRead:
    """Create a project; its first admin (the caller, or `first_admin_id` with
    `project.assign_first_admin`) becomes its lead. 422 on `key`: the key rule's problems or
    `taken`; on `first_admin_id`: `account_inactive`."""
    return await ProjectService(session).create(ctx, org, body)


@router.get("/orgs/{org_id}/first-admin-candidates", responses=ERRORS)
async def first_admin_candidates(
    org: FirstAdminAssigning, query: CandidateQuery, session: SessionDep
) -> Page[MemberCandidate]:
    """The create dialog's picker: the org's active members and the workspace's active staff,
    offset-paged with `?q=` (DL-152). Needs `project.assign_first_admin`."""
    return await ProjectService(session).first_admin_candidates(org, query)


@router.get("/orgs/{org_id}/projects", responses=ERRORS)
async def list_projects(
    org: OrgViewed,
    query: ProjectQuery,
    ctx: AuthzContextDep,
    session: SessionDep,
) -> Page[ProjectItem]:
    """The org's projects the caller can open; archived ones only with `include_archived`."""
    return await ProjectService(session).list_in_org(ctx, org, query)


@router.get("/orgs/{org_id}/project-key-availability", responses=ERRORS)
async def project_key_availability(
    org: Creating, key: str, session: SessionDep
) -> SlugAvailability:
    """Whether `key`, uppercased, could be a new project's key in the workspace."""
    return await ProjectService(session).key_availability(org, key)


@router.get("/projects/{key}", responses=ERRORS)
async def get_project(project: Viewed, ctx: AuthzContextDep, session: SessionDep) -> ProjectRead:
    """The project, with the actions the caller may take on it."""
    return await ProjectService(session).read(ctx, project)


@router.patch("/projects/{key}", responses=ERRORS)
async def update_project(
    project: Updated, body: ProjectUpdate, ctx: AuthzContextDep, session: SessionDep
) -> ProjectRead:
    """Change the project's details. 422 on `lead_id`: `not_member` or `account_inactive`."""
    return await ProjectService(session).update(ctx, project, body)


@router.put("/projects/{key}/classification", responses=ERRORS)
async def set_project_classification(
    project: Viewed, body: ClassificationUpdate, ctx: AuthzContextDep, session: SessionDep
) -> ProjectRead:
    """Set the project's classification level and categories (DL-81): raising needs
    `project.raise_classification`, lowering `project.lower_classification`. 422 on
    `export_control_confirmed` and `confirmed_member_ids`: `confirmation_required`,
    `members_changed`, or `confirmation_not_needed`."""
    return await ProjectService(session).set_classification(ctx, project, body)


@router.post("/projects/{key}/archive", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS)
async def archive_project(project: Archived, ctx: AuthzContextDep, session: SessionDep) -> None:
    """Archive the project: read-only until unarchived."""
    await ProjectService(session).archive(ctx, project)


@router.post("/projects/{key}/unarchive", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS)
async def unarchive_project(project: Unarchived, ctx: AuthzContextDep, session: SessionDep) -> None:
    """Unarchive the project."""
    await ProjectService(session).unarchive(ctx, project)


@router.get("/projects/{key}/members", responses=ERRORS)
async def list_project_members(
    project: Viewed, query: MemberQuery, ctx: AuthzContextDep, session: SessionDep
) -> Page[ProjectMemberRead]:
    """The project's explicit memberships, each row with the actions the caller may take on it."""
    return await ProjectService(session).list_members(ctx, project, query)


@router.get("/projects/{key}/member-candidates", responses=ERRORS)
async def project_member_candidates(
    project: MembersManaged, query: CandidateQuery, session: SessionDep
) -> Page[MemberCandidate]:
    """The picker: the org's members and the workspace's staff not yet on the project."""
    return await ProjectService(session).member_candidates(project, query)


@router.post("/projects/{key}/members", status_code=status.HTTP_201_CREATED, responses=ERRORS)
async def add_project_member(
    project: MembersManaged, body: ProjectMemberAdd, ctx: AuthzContextDep, session: SessionDep
) -> ProjectMemberRead:
    """Add someone by `user_id` (the picker; anyone else is a 404) or by `email` (422 on `email`:
    `already_member`, `no_account`, `account_inactive`, or `outside_org` unless `join_org`)."""
    return await ProjectService(session).add_member(ctx, project, body)


@router.post("/projects/{key}/members/new", status_code=status.HTTP_201_CREATED, responses=ERRORS)
async def create_project_member(
    project: MembersManaged, body: ProjectMemberCreate, ctx: AuthzContextDep, session: SessionDep
) -> ProjectMemberRead:
    """Create the account, its org membership, and the project membership in one step; the
    user must change the temporary password at their first sign-in."""
    return await ProjectService(session).create_member(ctx, project, body)


@router.patch("/projects/{key}/members/{user_id}", responses=ERRORS)
async def change_project_member_role(
    project: MembersManaged,
    user_id: uuid.UUID,
    body: ProjectMemberRoleUpdate,
    ctx: AuthzContextDep,
    session: SessionDep,
) -> ProjectMemberRead:
    """Change a member's role."""
    return await ProjectService(session).change_member_role(ctx, project, user_id, body.role)


@router.delete(
    "/projects/{key}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERRORS,
)
async def remove_project_member(
    project: MembersManaged, user_id: uuid.UUID, ctx: AuthzContextDep, session: SessionDep
) -> None:
    """Remove a member; removing the lead clears the project's lead."""
    await ProjectService(session).remove_member(ctx, project, user_id)


@router.get("/projects/{key}/access", responses=ERRORS)
async def project_access_review(project: AccessViewed, session: SessionDep) -> ProjectAccessReview:
    """Everyone who reaches the project, and why (design-doc §5, "Access review")."""
    return await ProjectService(session).access_review(project)


@router.get("/module-guidance", responses=ERRORS)
async def get_module_guidance(_user: SignedInUserDep) -> ModuleGuidance:
    """Which modules each project type recommends, a note per module, and which have shipped."""
    return module_guidance()
