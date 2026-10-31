"""The `my_work` read area (design-doc §11, "My work"): cross-project sections for the home page.
No tables; it reads through other areas' repositories and calls no service. The project list's
spec and rows live here so the project area (a higher layer) can share them."""

from collections.abc import Awaitable
from typing import cast

from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.context import AuthzContext
from app.authz.scoping import content_scope, project_scope
from app.core.lists import Filter, FilterType, ListSpec, Page, PageResult, fetch_page
from app.enums import ProjectStatus, ProjectType
from app.models.approval import Approval, ApprovalRequest
from app.models.project import Project
from app.models.requirement import RequirementRevision
from app.repositories.approval import ApprovalRepository
from app.repositories.project import ProjectRepository
from app.schemas.approval import ApprovalWorkItem
from app.schemas.project import INHERITED_ADMIN, MyWork, ProjectItem, WorkSection, WorkSections

PROJECTS = ListSpec(
    name="Project",
    id_column=Project.id,  # pyright: ignore[reportArgumentType]
    sorts={"name": Project.name, "key": Project.key},  # pyright: ignore[reportArgumentType]
    default_sort=("name",),
    filters=(
        Filter("status", Project.status, FilterType.ENUM, enum=ProjectStatus),  # pyright: ignore[reportArgumentType]
        Filter("type", Project.type, FilterType.ENUM, enum=ProjectType),  # pyright: ignore[reportArgumentType]
    ),
)
APPROVALS = ListSpec(
    name="MyApproval",
    id_column=Approval.id,  # pyright: ignore[reportArgumentType]
    sorts={"requested_at": ApprovalRequest.created_at},  # pyright: ignore[reportArgumentType]
    default_sort=("requested_at",),
)
FIRST_ITEMS = 10  # each section's items in `GET /api/me/work` (DL-76)


def item(ctx: AuthzContext, project: Project) -> ProjectItem:
    """A project in a list; its org and lead are loaded. A project the user sees without a
    membership is one they administer by inheritance (`project_scope`)."""
    membership = ctx.projects.get(project.id)
    return ProjectItem(
        id=project.id,
        key=project.key,
        name=project.name,
        type=project.type,
        status=project.status,
        lead_id=project.lead_id,
        lead_name=project.lead.name if project.lead else None,
        organization_id=project.organization_id,
        organization_slug=project.organization.slug,
        organization_name=project.organization.name,
        my_access=membership.role if membership else INHERITED_ADMIN,
    )


def page_of(ctx: AuthzContext, page: PageResult[Project]) -> Page[ProjectItem]:
    """A page of projects as list rows."""
    return page.with_items([item(ctx, p) for p in page.items])


def approval_item(row: Approval) -> ApprovalWorkItem:
    """A pending approval as My work shows it (DL-236); its request, revision, requirement,
    requester, and project with org are loaded."""
    request = row.approval_request
    # The repository joins on the revision, so a listed request always has one.
    revision = cast(RequirementRevision, request.requirement_revision)
    return ApprovalWorkItem(
        request_id=request.id,
        requested_at=request.created_at,
        requested_by_id=request.requested_by,
        requested_by_name=request.requester.name,
        note=request.note,
        entity_type=request.entity_type,
        entity_number=revision.requirement.number,
        title=revision.title,
        revision_number=revision.revision_number,
        project_key=request.project.key,
        project_name=request.project.name,
        organization_slug=request.project.organization.slug,
    )


class MyWorkService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def work(self, ctx: AuthzContext) -> MyWork:
        """Every section's first items and total, in one snapshot. Each section's query runs in
        a savepoint, so one that fails is returned as unavailable and the rest still show
        (backend/CLAUDE.md: the one sanctioned savepoint-and-continue)."""
        return MyWork(
            sections=WorkSections(
                projects=await self._section(
                    self.projects(ctx, PROJECTS.query_model(limit=FIRST_ITEMS))
                ),
                approvals=await self._section(
                    self.approvals(ctx, APPROVALS.query_model(limit=FIRST_ITEMS))
                ),
            )
        )

    async def _section[T](self, read: Awaitable[Page[T]]) -> WorkSection[T]:
        """One section's first page, in its own savepoint: a failed query is `available` false."""
        try:
            async with self.session.begin_nested():
                page = await read
        except DBAPIError:
            return WorkSection[T](available=False)
        return WorkSection[T](available=True, items=page.items, total=page.total)

    async def projects(self, ctx: AuthzContext, query: object) -> Page[ProjectItem]:
        """The projects the user can open, archived left out."""
        statement = ProjectRepository(self.session).visible(project_scope(ctx))
        statement = statement.where(Project.archived_at.is_(None))
        return page_of(ctx, await fetch_page(self.session, statement, PROJECTS, query))  # pyright: ignore[reportArgumentType] -- PROJECTS.query_model

    async def approvals(self, ctx: AuthzContext, query: object) -> Page[ApprovalWorkItem]:
        """The caller's pending approvals in projects whose content they can see, oldest request
        first (DL-236)."""
        statement = ApprovalRepository(self.session).pending_for(ctx.user_id, content_scope(ctx))
        page = await fetch_page(self.session, statement, APPROVALS, query)  # pyright: ignore[reportArgumentType] -- APPROVALS.query_model
        return page.with_items([approval_item(row) for row in page.items])
