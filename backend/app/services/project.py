"""The `project` area (design-doc §1.1, §3; build plan, "The projects API", "The project members
API"; DL-76, DL-78)."""

import dataclasses
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.admin_event import JsonValue, change_details, log_admin_event
from app.authz.actions import Action
from app.authz.authorize import allowed_actions, ensure
from app.authz.context import AuthzContext, ProjectAccess
from app.authz.scoping import project_scope
from app.authz.target import Target, org_target, project_target
from app.core.errors import FieldError, ForbiddenError, NotFoundError, ValidationFailedError
from app.core.lists import Filter, FilterType, ListSpec, Page, fetch_page
from app.enums import (
    AuditAction,
    AuditEntityType,
    OrgRole,
    ProjectModule,
    ProjectRole,
    ProjectType,
)
from app.models.org import Organization
from app.models.project import Project, ProjectMembership
from app.models.user import User
from app.repositories.project import ProjectRepository
from app.repositories.user import UserRepository
from app.rules.identifiers import normalize_project_key, project_key_problem
from app.rules.modules import ALL_MODULES, is_available, recommended_modules, seed_modules
from app.schemas.org import MemberCreate
from app.schemas.project import (
    MemberCandidate,
    ModuleGuidance,
    ModuleNote,
    ProjectAccessEntry,
    ProjectAccessReview,
    ProjectAccessUser,
    ProjectCreate,
    ProjectItem,
    ProjectMemberAdd,
    ProjectMemberCreate,
    ProjectMemberRead,
    ProjectRead,
    ProjectUpdate,
    TypeRecommendation,
)
from app.schemas.user import AccessReason
from app.schemas.workspace import SlugAvailability
from app.services.my_work import PROJECTS, page_of
from app.services.org import OrgService
from app.services.roster import MemberRemoval, Roster, RosterSpec, register_on_member_removed
from app.services.user import (
    ORG_REASONS,
    PROJECT_REASONS,
    WORKSPACE_REASONS,
    identifier_error,
    required_error,
)

# The entity a project endpoint loads, for routers (which never import models).
type ProjectEntity = Project


class OrgProjectQuery(PROJECTS.query_model):  # pyright: ignore[reportGeneralTypeIssues, reportUntypedBaseClass] -- built by ListSpec
    """The org's project list also takes `include_archived` (FastAPI reads a query model only as
    an endpoint's sole query parameter)."""

    include_archived: bool = False


PROJECT_MEMBERS = ListSpec(
    name="ProjectMember",
    id_column=ProjectMembership.id,  # pyright: ignore[reportArgumentType]
    sorts={"name": User.name, "email": User.email},  # pyright: ignore[reportArgumentType]
    default_sort=("name",),
    filters=(Filter("role", ProjectMembership.role, FilterType.ENUM, enum=ProjectRole),),  # pyright: ignore[reportArgumentType]
)
MEMBER_CANDIDATES = ListSpec(
    name="MemberCandidate",
    id_column=User.id,  # pyright: ignore[reportArgumentType]
    sorts={"name": User.name},  # pyright: ignore[reportArgumentType]
    default_sort=("name",),
    search=(User.name, User.email, User.username),  # pyright: ignore[reportArgumentType]
)

# A project has no owner role: the roster's add, list, and lock order only (DL-71).
_MEMBER_ROSTER = RosterSpec(
    owner=None,
    admin=ProjectRole.ADMIN,
    member=ProjectRole.MEMBER,
    manage=Action.PROJECT_MEMBER_MANAGE,
    manage_admins=None,
    added=AuditAction.PROJECT_MEMBER_ADDED,
    role_changed=AuditAction.PROJECT_MEMBER_ROLE_CHANGED,
    removed=AuditAction.PROJECT_MEMBER_REMOVED,
    entity_type=AuditEntityType.PROJECT,
    already_member="This person is already a member of the project.",
)


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
        actor_id: uuid.UUID,
        project: Project,
        *,
        target_user_id: uuid.UUID | None = None,
        details: Mapping[str, JsonValue] | None = None,
    ) -> None:
        log_admin_event(
            self.session,
            action=action,
            actor_id=actor_id,
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
        active account (422). Either way the first admin's org or staff row is held until the
        create commits, so a removal "with their projects" can't miss the new project (S1-C12
        review); a caller removed meanwhile is a 404. A system admin may hold neither."""
        if first_admin_id is None or first_admin_id == ctx.user_id:
            if not ctx.is_system_admin and not await self.repository.org_member_or_staff(
                org, ctx.user_id
            ):
                raise NotFoundError
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
        self._log(AuditAction.PROJECT_CREATED, ctx.user_id, project)
        self._log(
            AuditAction.PROJECT_MEMBER_ADDED,
            ctx.user_id,
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
                ctx.user_id,
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
        self._log(AuditAction.PROJECT_ARCHIVED, ctx.user_id, project)

    async def unarchive(self, ctx: AuthzContext, project: Project) -> None:
        """`project_unarchived`; already unarchived changes and records nothing."""
        await self.repository.lock(project)
        if project.archived_at is None:
            return
        project.archived_at = None
        await self.session.flush()
        self._log(AuditAction.PROJECT_UNARCHIVED, ctx.user_id, project)

    # --- Members (the project members API, DL-78; the roster's add, DL-71) -----------------

    def _members(
        self, project: Project
    ) -> Roster[ProjectMembership, ProjectRole, ProjectMemberRead]:
        return Roster(
            self.session,
            _MEMBER_ROSTER,
            self.repository,
            scope_id=project.id,
            target=project_target(project),
            new_membership=lambda user_id, role: ProjectMembership(
                project_id=project.id, user_id=user_id, role=role
            ),
            row_model=ProjectMemberRead,
        )

    async def _lock_live(self, project: Project) -> None:
        """Lock the project, then re-read it: an archive that committed meanwhile still denies a
        member change (design-doc §5). Lock order: the person's org and staff rows (an add's
        `org_member_or_staff`), then the project, then its memberships, as a removal "with their
        projects" takes them."""
        await self.repository.lock(project)
        if project.archived_at is not None:
            raise ForbiddenError

    async def list_members(
        self, ctx: AuthzContext, project: Project, query: object
    ) -> Page[ProjectMemberRead]:
        return await self._members(project).list(ctx, PROJECT_MEMBERS, query)

    async def member_candidates(self, project: Project, query: object) -> Page[MemberCandidate]:
        """The picker: the org's active members and the workspace's staff not yet on it."""
        page = await fetch_page(
            self.session,
            self.repository.candidates(project),
            MEMBER_CANDIDATES,
            query,  # pyright: ignore[reportArgumentType] -- MEMBER_CANDIDATES.query_model
        )
        return Page[MemberCandidate](
            items=[
                MemberCandidate(user_id=u.id, email=u.email, username=u.username, name=u.name)
                for u in page.items
            ],
            total=page.total,
            limit=page.limit,
            offset=page.offset,
        )

    async def add_member(
        self, ctx: AuthzContext, project: Project, payload: ProjectMemberAdd
    ) -> ProjectMemberRead:
        """Add someone by `user_id` (the picker) or `email` (email first), in DL-78's order of
        checks; `join_org` adds an account from outside the org and the staff to the org too."""
        if (payload.user_id is None) == (payload.email is None):
            raise ValidationFailedError(
                [FieldError(("body",), "Send exactly one of user_id or email.", "one_parameter")]
            )
        # The project's org exists: a foreign key.
        org = cast(Organization, await OrgService(self.session).get(project.organization_id))
        roster = self._members(project)
        if payload.email is not None:

            async def admit(user: User) -> None:
                if not await self.repository.org_member_or_staff(org, user.id):
                    if not payload.join_org:
                        raise _field(
                            "email",
                            "This person isn't in the organization. Confirm to add them to it too.",
                            "outside_org",
                        )
                    await OrgService(self.session).add_member(ctx, org, user.email, OrgRole.MEMBER)
                # A second add of the same person, waiting here, then hits the unique constraint:
                # `already_member` on `email` (DL-80).
                await self._lock_live(project)

            return await roster.add(ctx, payload.email, payload.role, admit=admit)
        # Exactly one of the two was sent (checked above), so here it's `user_id`.
        user_id = cast(uuid.UUID, payload.user_id)
        if not await self.repository.org_member_or_staff(org, user_id):
            raise NotFoundError
        await self._lock_live(project)
        if await self.repository.membership(project.id, user_id):
            raise _field("user_id", _MEMBER_ROSTER.already_member, "already_member")
        # An org member or staff member has an account.
        user = cast(User, await UserRepository(self.session).get(user_id))
        if not user.is_active:
            raise _field("user_id", "This account is deactivated.", "account_inactive")
        return await roster.add_user(ctx, user, payload.role, loc=("body", "user_id"))

    async def create_member(
        self, ctx: AuthzContext, project: Project, payload: ProjectMemberCreate
    ) -> ProjectMemberRead:
        """Create the account and its org membership through the org service, then the project
        membership through the roster (`user_created`, `org_member_added`,
        `project_member_added`)."""
        await self._lock_live(project)
        orgs = OrgService(self.session)
        org = cast(Organization, await orgs.get(project.organization_id))  # a foreign key
        new = MemberCreate(**payload.model_dump(exclude={"role"}), role=OrgRole.MEMBER)
        row = await orgs.create_member(ctx, org, new)
        user = cast(User, await UserRepository(self.session).get(row.user_id))  # just created
        return await self._members(project).add_user(ctx, user, payload.role)

    async def change_member_role(
        self, ctx: AuthzContext, project: Project, user_id: uuid.UUID, role: ProjectRole
    ) -> ProjectMemberRead:
        """Change a member's role (`project_member_role_changed`); the role already held changes
        and records nothing. No last-admin guard (DL-71)."""
        await self._lock_live(project)
        membership = await self.repository.membership(project.id, user_id, lock=True)
        if membership is None:
            raise NotFoundError
        old = membership.role
        if old != role:
            membership.role = role
            await self.session.flush()
            self._log(
                AuditAction.PROJECT_MEMBER_ROLE_CHANGED,
                ctx.user_id,
                project,
                target_user_id=user_id,
                details={"old_role": old.value, "new_role": role.value},
            )
        return self._members(project).row(ctx, membership)

    async def remove_member(self, ctx: AuthzContext, project: Project, user_id: uuid.UUID) -> None:
        """Remove a member (`project_member_removed`); removing the lead clears `lead_id`."""
        await self._lock_live(project)
        membership = await self.repository.membership(project.id, user_id, lock=True)
        if membership is None:
            raise NotFoundError
        await self._remove(membership, project, ctx.user_id)

    async def _remove(
        self,
        membership: ProjectMembership,
        project: Project,
        actor_id: uuid.UUID,
        *,
        via: AuditAction | None = None,
    ) -> None:
        """Delete the membership and, if it was the lead's, clear `lead_id` in the same
        transaction (`lead_cleared`); `via`, the org or staff removal that removed it."""
        details: dict[str, JsonValue] = {"role": membership.role.value}
        await self.session.delete(membership)
        if project.lead_id == membership.user_id:
            project.lead_id = None
            details["lead_cleared"] = True
        if via is not None:
            details["via"] = via.value
        await self.session.flush()
        self._log(
            AuditAction.PROJECT_MEMBER_REMOVED,
            actor_id,
            project,
            target_user_id=membership.user_id,
            details=details,
        )

    async def remove_with_projects(self, removal: MemberRemoval) -> None:
        """An org or staff removal "with their projects" (the roster's `on_member_removed`):
        the person's memberships on the org's projects, or the workspace's, archived included,
        each removed as above, the remover as actor."""
        staff = removal.organization_id is None
        via = AuditAction.WORKSPACE_MEMBER_REMOVED if staff else AuditAction.ORG_MEMBER_REMOVED
        memberships = await self.repository.memberships_in(
            removal.user_id,
            organization_id=removal.organization_id,
            workspace_id=removal.workspace_id,
        )
        for membership in memberships:
            await self._remove(membership, membership.project, removal.actor_id, via=via)

    async def access_review(self, project: Project) -> ProjectAccessReview:
        """Everyone who reaches the project, and why (design-doc §5): an explicit role, or
        inherited admin through the system-admin flag, a workspace role, or an org role.
        Sorted by name."""
        seen = await self.repository.reachers(project)
        users: dict[uuid.UUID, User] = {}
        roles: dict[uuid.UUID, ProjectRole] = {}
        reasons: dict[uuid.UUID, set[AccessReason]] = {}

        def reach(user: User, reason: AccessReason) -> None:
            users[user.id] = user
            reasons.setdefault(user.id, set()).add(reason)

        for user, role in seen.members:
            roles[user.id] = role
            reach(user, PROJECT_REASONS[role])
        for user in seen.system_admins:
            reach(user, AccessReason.SYSTEM_ADMIN)
        for user, workspace_role in seen.workspace_admins:
            reach(user, WORKSPACE_REASONS[workspace_role])
        for user, org_role in seen.org_admins:
            reach(user, ORG_REASONS[org_role])
        order = list(AccessReason)
        return ProjectAccessReview(
            people=[
                ProjectAccessEntry(
                    user=ProjectAccessUser(
                        id=u.id,
                        email=u.email,
                        username=u.username,
                        name=u.name,
                        is_active=u.is_active,
                    ),
                    role=roles.get(u.id),
                    reasons=sorted(reasons[u.id], key=order.index),
                )
                for u in sorted(users.values(), key=lambda u: (u.name, u.id))
            ]
        )


def _json(changed: dict[str, tuple[object, object]]) -> dict[str, tuple[str, str]]:
    """Old and new values as JSON for the event: enums by value, IDs as text."""

    def plain(value: object) -> object:
        if isinstance(value, uuid.UUID):
            return str(value)
        return getattr(value, "value", value)

    return {key: (plain(old), plain(new)) for key, (old, new) in changed.items()}  # pyright: ignore[reportReturnType] -- JSON values


async def _remove_with_projects(session: AsyncSession, removal: MemberRemoval) -> None:
    await ProjectService(session).remove_with_projects(removal)


register_on_member_removed(_remove_with_projects)
