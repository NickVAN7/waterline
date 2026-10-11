"""The `project` area (design-doc §1.1, §3; build plan, "The projects API", DL-76)."""

import dataclasses
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.admin_event import JsonValue, change_details, log_admin_event
from app.authz.actions import Action
from app.authz.authorize import allowed_actions, ensure
from app.authz.context import AuthzContext, ProjectAccess
from app.authz.scoping import project_scope
from app.authz.target import Target, org_target, project_target
from app.core.errors import FieldError, ForbiddenError, NotFoundError, ValidationFailedError
from app.core.lists import Page, fetch_page
from app.enums import (
    AuditAction,
    AuditEntityType,
    ProjectModule,
    ProjectRole,
    ProjectType,
)
from app.models.org import Organization
from app.models.project import Project, ProjectMembership
from app.repositories.project import ProjectRepository
from app.repositories.user import UserRepository
from app.rules.identifiers import normalize_project_key, project_key_problem
from app.rules.modules import ALL_MODULES, is_available, recommended_modules, seed_modules
from app.schemas.project import (
    ModuleGuidance,
    ModuleNote,
    ProjectCreate,
    ProjectItem,
    ProjectRead,
    ProjectUpdate,
    TypeRecommendation,
)
from app.schemas.workspace import SlugAvailability
from app.services.my_work import PROJECTS, page_of
from app.services.user import identifier_error, required_error

# The entity a project endpoint loads, for routers (which never import models).
type ProjectEntity = Project


class OrgProjectQuery(PROJECTS.query_model):  # pyright: ignore[reportGeneralTypeIssues, reportUntypedBaseClass] -- built by ListSpec
    """The org's project list also takes `include_archived` (FastAPI reads a query model only as
    an endpoint's sole query parameter)."""

    include_archived: bool = False


# A best-practice note per module (design-doc §1.1, "UI guidance on module choice").
_NOTES = {
    "sprints": "Sprints suit a build phase; phases and milestones drive the overall plan.",
    "github": "GitHub linking is only useful when the project's work lands in a repository.",
    "raid": "ERP implementations: keep a RAID log from day one; steering committees expect one.",
    "status_reports": "Publish a RAG snapshot on a fixed cadence so trends are visible.",
    "budget": "Track actuals against the baseline monthly, before variances grow.",
    "data_migration": "Plan load cycles early; reconciliation takes longer than the loads.",
    "cutover": "Rehearse the cutover runbook at least once, timed, before go-live.",
}


def module_guidance() -> ModuleGuidance:
    """Which modules each type recommends, a note per module, and which have shipped (DL-76)."""
    return ModuleGuidance(
        modules=[
            ModuleNote(module=m, note=_NOTES[m], available=is_available(m)) for m in ALL_MODULES
        ],
        types=[TypeRecommendation(type=t, recommended=recommended_modules(t)) for t in ProjectType],
    )


def _distinct(modules: list[ProjectModule]) -> list[str]:
    return list(dict.fromkeys(m.value for m in modules))


def _field(field: str, message: str, type_: str) -> ValidationFailedError:
    return ValidationFailedError([FieldError(("body", field), message, type_)])


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ProjectRepository(session)

    async def load(self, key: str) -> tuple[Project, Target] | None:
        project = await self.repository.get_by_key(key)
        return None if project is None else (project, project_target(project))

    def _log(
        self,
        action: AuditAction,
        ctx: AuthzContext,
        project: Project,
        *,
        target_user_id: uuid.UUID | None = None,
        details: Mapping[str, JsonValue] | None = None,
    ) -> None:
        log_admin_event(
            self.session,
            action=action,
            actor_id=ctx.user_id,
            workspace_id=project.workspace_id,
            organization_id=project.organization_id,
            project_id=project.id,
            target_user_id=target_user_id,
            entity_type=AuditEntityType.PROJECT,
            entity_id=project.id,
            details=details,
        )

    async def _first_admin(
        self, ctx: AuthzContext, org: Organization, first_admin_id: uuid.UUID | None
    ) -> uuid.UUID:
        """The caller, or the named first admin: naming someone else needs
        `project.assign_first_admin` (403), and they must be an org member or staff (404) with an
        active account (422)."""
        if first_admin_id is None or first_admin_id == ctx.user_id:
            return ctx.user_id
        ensure(ctx, Action.PROJECT_ASSIGN_FIRST_ADMIN, org_target(org))
        if not await self.repository.org_member_or_staff(org, first_admin_id):
            raise NotFoundError
        user = await UserRepository(self.session).get(first_admin_id)
        if user is None or not user.is_active:
            raise _field("first_admin_id", "This account is deactivated.", "account_inactive")
        return first_admin_id

    async def create(
        self, ctx: AuthzContext, org: Organization, values: ProjectCreate
    ) -> ProjectRead:
        """A new project: its first admin gets an explicit admin membership and becomes the lead
        (`project_created`, `project_member_added`)."""
        key = normalize_project_key(values.key.strip())
        # A taken key is the unique constraint's 422 `taken` on `key`.
        problems = [
            *required_error(values.name, field="name"),
            *identifier_error(project_key_problem(key), field="key"),
        ]
        if problems:
            raise ValidationFailedError(problems)
        first_admin_id = await self._first_admin(ctx, org, values.first_admin_id)
        modules = (
            values.enabled_modules
            if values.enabled_modules is not None
            else seed_modules(values.type)
        )
        project = Project(
            organization_id=org.id,
            workspace_id=org.workspace_id,
            key=key,
            name=values.name.strip(),
            description=values.description,
            type=values.type,
            enabled_modules=_distinct(modules),
            lead_id=first_admin_id,
        )
        self.session.add(project)
        await self.session.flush()
        self.session.add(
            ProjectMembership(project_id=project.id, user_id=first_admin_id, role=ProjectRole.ADMIN)
        )
        await self.session.flush()
        self._log(AuditAction.PROJECT_CREATED, ctx, project)
        self._log(
            AuditAction.PROJECT_MEMBER_ADDED,
            ctx,
            project,
            target_user_id=first_admin_id,
            details={"role": ProjectRole.ADMIN.value},
        )
        if first_admin_id == ctx.user_id:
            # The context predates the new membership: count it for the response's actions.
            access = ProjectAccess(ProjectRole.ADMIN, org.id, org.workspace_id)
            ctx = dataclasses.replace(ctx, projects={**ctx.projects, project.id: access})
        return self.read(ctx, project)

    async def list_in_org(
        self, ctx: AuthzContext, org: Organization, query: OrgProjectQuery
    ) -> Page[ProjectItem]:
        """The org's projects the caller can open; archived ones only with `include_archived`."""
        statement = self.repository.visible(
            project_scope(ctx), include_archived=query.include_archived
        ).where(Project.organization_id == org.id)
        return page_of(await fetch_page(self.session, statement, PROJECTS, query))  # pyright: ignore[reportArgumentType] -- the query model

    async def key_availability(self, org: Organization, key: str) -> SlugAvailability:
        """Whether `key`, uppercased as create does, could be a new project's key."""
        key = normalize_project_key(key.strip())
        problem = project_key_problem(key)
        taken = problem is None and await self.repository.key_taken(org.workspace_id, key)
        return SlugAvailability.of(problem.value if problem else None, taken=taken)

    def read(self, ctx: AuthzContext, project: Project) -> ProjectRead:
        return ProjectRead(
            id=project.id,
            organization_id=project.organization_id,
            key=project.key,
            name=project.name,
            description=project.description,
            type=project.type,
            status=project.status,
            lead_id=project.lead_id,
            enabled_modules=[ProjectModule(m) for m in project.enabled_modules],
            archived=project.archived_at is not None,
            # Each module's has-data hook arrives with its slice; none holds data yet.
            modules_holding_data=[],
            allowed_actions=allowed_actions(ctx, project_target(project)),
        )

    async def update(
        self, ctx: AuthzContext, project: Project, values: ProjectUpdate
    ) -> ProjectRead:
        """Change the project's details (`project_updated`, the changed fields). The lead must
        hold a membership (422 `not_member`) and be active when newly named (`account_inactive`);
        null clears it."""
        # Locked and read again: two edits at once compare against what the other committed, and
        # an archive that committed meanwhile still denies the edit (design-doc §5).
        await self.repository.lock(project)
        if project.archived_at is not None:
            raise ForbiddenError
        sent = values.model_fields_set
        changes: dict[str, object] = {}
        if values.name is not None:
            if errors := required_error(values.name, field="name"):
                raise ValidationFailedError(errors)
            changes["name"] = values.name.strip()
        for field in ("description", "type", "status"):
            if field in sent and (field == "description" or getattr(values, field) is not None):
                changes[field] = getattr(values, field)
        if values.enabled_modules is not None:
            changes["enabled_modules"] = _distinct(values.enabled_modules)
        if "lead_id" in sent and values.lead_id != project.lead_id:
            if values.lead_id is not None:
                await self._check_lead(project, values.lead_id)
            changes["lead_id"] = values.lead_id
        changed = {
            key: (getattr(project, key), new)
            for key, new in changes.items()
            if getattr(project, key) != new
        }
        if changed:
            for key, (_, new) in changed.items():
                setattr(project, key, new)
            await self.session.flush()
            self._log(
                AuditAction.PROJECT_UPDATED,
                ctx,
                project,
                details=change_details(_json(changed)),
            )
        return self.read(ctx, project)

    async def _check_lead(self, project: Project, lead_id: uuid.UUID) -> None:
        if not await self.repository.is_member(project.id, lead_id):
            raise _field("lead_id", "The lead must be a member of the project.", "not_member")
        user = await UserRepository(self.session).get(lead_id)
        if user is None or not user.is_active:
            raise _field("lead_id", "This account is deactivated.", "account_inactive")

    async def archive(self, ctx: AuthzContext, project: Project) -> None:
        """Read-only until unarchived (`project_archived`). An archived project can't be archived
        again: `authorize()` denies it as a mutation on an archived project (403)."""
        # Locked and read again: an archive that committed meanwhile leaves nothing to record.
        await self.repository.lock(project)
        if project.archived_at is not None:
            return
        project.archived_at = datetime.now(UTC)
        await self.session.flush()
        self._log(AuditAction.PROJECT_ARCHIVED, ctx, project)

    async def unarchive(self, ctx: AuthzContext, project: Project) -> None:
        """`project_unarchived`; already unarchived changes and records nothing."""
        await self.repository.lock(project)
        if project.archived_at is None:
            return
        project.archived_at = None
        await self.session.flush()
        self._log(AuditAction.PROJECT_UNARCHIVED, ctx, project)


def _json(changed: dict[str, tuple[object, object]]) -> dict[str, tuple[str, str]]:
    """Old and new values as JSON for the event: enums by value, IDs as text."""

    def plain(value: object) -> object:
        if isinstance(value, uuid.UUID):
            return str(value)
        return getattr(value, "value", value)

    return {key: (plain(old), plain(new)) for key, (old, new) in changed.items()}  # pyright: ignore[reportReturnType] -- JSON values
