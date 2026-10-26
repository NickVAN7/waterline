"""The `my_work` read area (design-doc §11, "My work"): cross-project sections for the home page.
No tables; it reads through other areas' repositories and calls no service. The project list's
spec and rows live here so the project area (a higher layer) can share them."""

from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.context import AuthzContext
from app.authz.scoping import project_scope
from app.core.lists import Filter, FilterType, ListSpec, Page, PageResult, fetch_page
from app.enums import ProjectStatus, ProjectType
from app.models.project import Project
from app.repositories.project import ProjectRepository
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


class MyWorkService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def work(self, ctx: AuthzContext) -> MyWork:
        """Every section's first items and total, in one snapshot. Each section's query runs in
        a savepoint, so one that fails is returned as unavailable and the rest still show
        (backend/CLAUDE.md: the one sanctioned savepoint-and-continue)."""
        try:
            async with self.session.begin_nested():
                page = await self.projects(ctx, PROJECTS.query_model(limit=FIRST_ITEMS))
            projects = WorkSection[ProjectItem](available=True, items=page.items, total=page.total)
        except DBAPIError:
            projects = WorkSection[ProjectItem](available=False)
        return MyWork(sections=WorkSections(projects=projects))

    async def projects(self, ctx: AuthzContext, query: object) -> Page[ProjectItem]:
        """The projects the user can open, archived left out."""
        statement = ProjectRepository(self.session).visible(project_scope(ctx))
        statement = statement.where(Project.archived_at.is_(None))
        return page_of(ctx, await fetch_page(self.session, statement, PROJECTS, query))  # pyright: ignore[reportArgumentType] -- PROJECTS.query_model
