"""The `project` area (design-doc §1.1, §3; build plan, "The projects API", "The project members
API"; DL-76, DL-78)."""

import dataclasses
import uuid
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import cast

from pydantic import BaseModel
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.admin_event import JsonValue, apply_changes, change_details, log_admin_event
from app.audit.change_log import log_change
from app.authz.actions import Action
from app.authz.authorize import allowed_actions, ensure
from app.authz.context import AuthzContext, ProjectAccess
from app.authz.scoping import project_scope
from app.authz.target import Target, org_target, project_target
from app.core.errors import FieldError, ForbiddenError, NotFoundError, ValidationFailedError
from app.core.lists import Filter, FilterType, ListSpec, Page, fetch_page
from app.enums import (
    ActivityAction,
    ActivityEntityType,
    ActivityField,
    AuditAction,
    AuditEntityType,
    OrgRole,
    ProjectModule,
    ProjectRole,
    ProjectType,
    RestrictionCategory,
)
from app.models.org import Organization
from app.models.project import Project, ProjectMembership
from app.models.user import User
from app.repositories.project import ProjectRepository
from app.repositories.user import UserRepository
from app.rules.identifiers import normalize_project_key, project_key_problem
from app.rules.modules import ALL_MODULES, is_available, recommended_modules, seed_modules
from app.rules.restriction import Restriction, change
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
    RestrictionUpdate,
    TypeRecommendation,
)
from app.schemas.user import AccessReason
from app.schemas.workspace import SlugAvailability
from app.services.approval import ApprovalService
from app.services.my_work import PROJECTS, page_of
from app.services.org import OrgService
from app.services.roster import MemberRemoval, Roster, RosterSpec, register_on_member_removed
from app.services.user import (
    ORG_REASONS,
    PROJECT_REASONS,
    WORKSPACE_REASONS,
    access_kind,
    identifier_error,
    required_error,
)

# The entity a project endpoint loads, for routers (which never import models).
type ProjectEntity = Project


# My work's list, with archived projects on request (DL-181).
ORG_PROJECTS = dataclasses.replace(
    PROJECTS,
    name="OrgProject",
    archived_column=Project.archived_at,  # pyright: ignore[reportArgumentType]
)


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


def _enabled(modules: list[ProjectModule]) -> list[str]:
    """The modules as stored, without duplicates; one that hasn't shipped is a 422
    `module_unavailable` (design-doc §1.1, DL-136)."""
    if not all(is_available(m) for m in modules):
        raise ValidationFailedError.on(
            ("body", "enabled_modules"), "This module isn't available yet.", "module_unavailable"
        )
    return list(dict.fromkeys(m.value for m in modules))


_CONFIRMED = "export_control_confirmed"
_MEMBER_IDS = "confirmed_member_ids"


def _confirmation(
    values: BaseModel, *, needed: bool, members: set[uuid.UUID] | None = None
) -> dict[str, JsonValue]:
    """Check an export-control confirmation (design-doc §3.1; DL-81) and return it for the audit
    event. Where it's `needed`, `export_control_confirmed` must be true, and, when `members` is
    given, `confirmed_member_ids` must list exactly them; where it isn't, neither field may be
    sent. 422s: `confirmation_required`, `members_changed`, `confirmation_not_needed`."""
    sent = values.model_fields_set
    if not needed:
        errors = [
            FieldError(
                ("body", f),
                "No export-control confirmation is needed here.",
                "confirmation_not_needed",
            )
            for f in (_CONFIRMED, _MEMBER_IDS)
            if f in sent
        ]
        if errors:
            raise ValidationFailedError(errors)
        return {}
    errors: list[FieldError] = []
    if not getattr(values, _CONFIRMED):
        errors.append(
            FieldError(
                ("body", _CONFIRMED),
                "Confirm that the people involved are authorized for export-controlled data.",
                "confirmation_required",
            )
        )
    details: dict[str, JsonValue] = {_CONFIRMED: True}
    if members is not None:
        listed: list[uuid.UUID] | None = getattr(values, _MEMBER_IDS)
        if listed is None:
            errors.append(
                FieldError(
                    ("body", _MEMBER_IDS),
                    "List the project's members you confirm.",
                    "confirmation_required",
                )
            )
        elif set(listed) != members:
            errors.append(
                FieldError(
                    ("body", _MEMBER_IDS),
                    "The project's members have changed. Review them and confirm again.",
                    "members_changed",
                )
            )
        details[_MEMBER_IDS] = list[JsonValue](sorted(str(m) for m in members))
    if errors:
        raise ValidationFailedError(errors)
    return details


def _restriction(project: Project) -> Restriction:
    return Restriction(
        project.restriction_level,
        frozenset(RestrictionCategory(c) for c in project.restriction_categories),
    )


def _stored(categories: frozenset[RestrictionCategory]) -> list[str]:
    """Categories as stored: in `RestrictionCategory` order, no duplicates."""
    return [c.value for c in RestrictionCategory if c in categories]


def _restriction_json(restriction: Restriction) -> dict[str, JsonValue]:
    level = restriction.level
    return {
        "restriction_level": level.value if level else None,
        "restriction_categories": list[JsonValue](_stored(restriction.categories)),
    }


type RestrictionChangedHandler = Callable[[AsyncSession, Project, uuid.UUID], Awaitable[None]]

# Registered by the item areas (requirements, S2-C6), which this module never imports: each lifts
# its live items stored below the project's new level (DL-208, DL-209).
_ON_RESTRICTION_CHANGED: list[RestrictionChangedHandler] = []


def register_on_restriction_changed(handler: RestrictionChangedHandler) -> None:
    _ON_RESTRICTION_CHANGED.append(handler)


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
            raise ValidationFailedError.on(
                ("body", "first_admin_id"), "This account is deactivated.", "account_inactive"
            )
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
        restriction = Restriction(
            values.restriction_level, frozenset(values.restriction_categories)
        )
        # Created export-controlled: the first admin is its only explicit member (§3.1).
        export_controlled = RestrictionCategory.EXPORT_CONTROLLED in restriction.categories
        confirmation = _confirmation(
            values,
            needed=export_controlled,
            members={first_admin_id} if export_controlled else None,
        )
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
            enabled_modules=_enabled(modules),
            lead_id=first_admin_id,
            restriction_level=restriction.level,
            restriction_categories=_stored(restriction.categories),
        )
        self.session.add(project)
        await self.session.flush()
        self.session.add(
            ProjectMembership(project_id=project.id, user_id=first_admin_id, role=ProjectRole.ADMIN)
        )
        await self.session.flush()
        self._log(
            AuditAction.PROJECT_CREATED,
            ctx.user_id,
            project,
            details={**_restriction_json(restriction), **confirmation},
        )
        self._log(
            AuditAction.PROJECT_MEMBER_ADDED,
            ctx.user_id,
            project,
            target_user_id=first_admin_id,
            # As every add to an export-controlled project records it (DL-81).
            details={
                "role": ProjectRole.ADMIN.value,
                **({_CONFIRMED: True} if confirmation else {}),
            },
        )
        if first_admin_id == ctx.user_id:
            # The context predates the new membership: count it for the response's actions.
            access = ProjectAccess(ProjectRole.ADMIN, org.id, org.workspace_id)
            ctx = dataclasses.replace(ctx, projects={**ctx.projects, project.id: access})
        return await self.read(ctx, project)

    async def list_in_org(
        self, ctx: AuthzContext, org: Organization, query: object
    ) -> Page[ProjectItem]:
        """The org's projects the caller can open; archived ones with `include_archived`, or
        alone with `archived_only`."""
        statement = self.repository.visible(project_scope(ctx)).where(
            Project.organization_id == org.id
        )
        return page_of(ctx, await fetch_page(self.session, statement, ORG_PROJECTS, query))  # pyright: ignore[reportArgumentType] -- the query model

    async def key_availability(self, org: Organization, key: str) -> SlugAvailability:
        """Whether `key`, uppercased as create does, could be a new project's key."""
        key = normalize_project_key(key.strip())
        problem = project_key_problem(key)
        taken = problem is None and await self.repository.key_taken(org.workspace_id, key)
        return SlugAvailability.of(problem.value if problem else None, taken=taken)

    async def read(self, ctx: AuthzContext, project: Project) -> ProjectRead:
        # By id, not `project.lead`: right after a create or a lead change too (DL-111).
        lead = await UserRepository(self.session).get(project.lead_id) if project.lead_id else None
        return ProjectRead(
            id=project.id,
            organization_id=project.organization_id,
            key=project.key,
            name=project.name,
            description=project.description,
            type=project.type,
            status=project.status,
            lead_id=project.lead_id,
            lead_name=lead.name if lead else None,
            lead_is_active=lead.is_active if lead else None,
            enabled_modules=[ProjectModule(m) for m in project.enabled_modules],
            archived=project.archived_at is not None,
            restriction_level=project.restriction_level,
            restriction_categories=[RestrictionCategory(c) for c in project.restriction_categories],
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
            changes["enabled_modules"] = _enabled(values.enabled_modules)
        if "lead_id" in sent and values.lead_id != project.lead_id:
            if values.lead_id is not None:
                await self._check_lead(project, values.lead_id)
            changes["lead_id"] = values.lead_id
        # apply_changes re-reads under its own lock; the one above covers the checks before it.
        if changed := await apply_changes(self.session, project, changes):
            self._log(
                AuditAction.PROJECT_UPDATED,
                ctx.user_id,
                project,
                details=change_details(_json(changed)),
            )
            # The activity feed shows these two (design-doc §10); the rest are audit events only.
            for field in (ActivityField.STATUS, ActivityField.LEAD_ID):
                if field.value in changed:
                    old, new = changed[field.value]
                    self._log_change(project, field, ctx.user_id, old, new)
        return await self.read(ctx, project)

    def _log_change(
        self,
        project: Project,
        field: ActivityField,
        actor_id: uuid.UUID,
        old: object,
        new: object,
    ) -> None:
        log_change(
            self.session,
            project_id=project.id,
            entity_type=ActivityEntityType.PROJECT,
            entity_id=project.id,
            action=ActivityAction.UPDATED,
            changed_by=actor_id,
            field=field,
            old=old,
            new=new,
        )

    async def _with_current_role(self, ctx: AuthzContext, project: Project) -> AuthzContext:
        """`ctx` with the caller's role on `project` read again, for a check made under the
        project's lock."""
        projects = {k: v for k, v in ctx.projects.items() if k != project.id}
        membership = await self.repository.membership(project.id, ctx.user_id)
        if membership is not None:
            projects[project.id] = ProjectAccess(
                membership.role,
                project.organization_id,
                project.workspace_id,
                project.archived_at is not None,
            )
        return dataclasses.replace(ctx, projects=projects)

    async def set_restriction(
        self, ctx: AuthzContext, project: Project, values: RestrictionUpdate
    ) -> ProjectRead:
        """Replace the level and categories (`project_restriction_changed`; DL-81): a raise
        needs `project.raise_restriction`, a lower `project.lower_restriction`, a change
        that does neither (the restriction already held included, which records nothing)
        either one. Adding `export_controlled` needs the confirmation, against the explicit
        members as they commit."""
        # Locked and read again: the rights, the "nothing to change" check, and the confirmed
        # members all see what a concurrent change or member add committed (design-doc §5).
        await self.repository.lock(project)
        # The caller's own role too: a removal takes the project's lock first, so one that
        # committed while this waited is seen, and a removed explicit admin can't lower (owner
        # decision, S1-C13 security review).
        ctx = await self._with_current_role(ctx, project)
        target = project_target(project)
        old = _restriction(project)
        new = Restriction(values.level, frozenset(values.categories))
        kind = change(old, new)
        raise_, lower = Action.PROJECT_RAISE_RESTRICTION, Action.PROJECT_LOWER_RESTRICTION
        needed = [a for a, does in ((raise_, kind.raises), (lower, kind.lowers)) if does]
        # Neither: either action will do, and lower is never granted without raise (DL-82).
        for action in needed or [raise_]:
            ensure(ctx, action, target)
        adds_export_control = RestrictionCategory.EXPORT_CONTROLLED in (
            new.categories - old.categories
        )
        confirmation = _confirmation(
            values,
            needed=adds_export_control,
            members=await self.repository.member_ids(project.id) if adds_export_control else None,
        )
        if new != old:
            project.restriction_level = new.level
            project.restriction_categories = _stored(new.categories)
            await self.session.flush()
            # Each lifts only what's now below the floor, so a lower lifts nothing (DL-208).
            for handler in _ON_RESTRICTION_CHANGED:
                await handler(self.session, project, ctx.user_id)
            self._log(
                AuditAction.PROJECT_RESTRICTION_CHANGED,
                ctx.user_id,
                project,
                details={
                    "old": _restriction_json(old),
                    "new": _restriction_json(new),
                    **confirmation,
                },
            )
        return await self.read(ctx, project)

    async def _check_lead(self, project: Project, lead_id: uuid.UUID) -> None:
        if not await self.repository.is_member(project.id, lead_id):
            raise ValidationFailedError.on(
                ("body", "lead_id"), "The lead must be a member of the project.", "not_member"
            )
        user = await UserRepository(self.session).get(lead_id)
        if user is None or not user.is_active:
            raise ValidationFailedError.on(
                ("body", "lead_id"), "This account is deactivated.", "account_inactive"
            )

    async def archive(self, ctx: AuthzContext, project: Project) -> None:
        """Read-only until unarchived (`project_archived`); its pending approval requests are
        cancelled, each logged (DL-194). An archived project can't be archived again:
        `authorize()` denies it as a mutation on an archived project (403)."""
        # Locked and read again: an archive that committed meanwhile leaves nothing to record.
        await self.repository.lock(project)
        if project.archived_at is not None:
            return
        project.archived_at = datetime.now(UTC)
        await self.session.flush()
        self._log(AuditAction.PROJECT_ARCHIVED, ctx.user_id, project)
        await ApprovalService(self.session).cancel_pending_in_project(project.id, ctx.user_id)

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

    async def _lock_for_add(
        self, project: Project, payload: ProjectMemberAdd | ProjectMemberCreate
    ) -> dict[str, JsonValue]:
        """Lock the live project for a member add, then check the export-control confirmation
        against what it is now (a restriction change holds the same lock; DL-81)."""
        await self._lock_live(project)
        return _confirmation(payload, needed=project_target(project).export_controlled)

    async def list_members(
        self, ctx: AuthzContext, project: Project, query: object
    ) -> Page[ProjectMemberRead]:
        return await self._members(project).list(ctx, PROJECT_MEMBERS, query)

    async def first_admin_candidates(
        self, org: Organization, query: object
    ) -> Page[MemberCandidate]:
        """The create dialog's picker: the org's active members and the workspace's active staff
        (DL-152). The caller holds `project.assign_first_admin`."""
        return await self._candidates(
            self.repository.first_admin_candidates(org.id, org.workspace_id), query
        )

    async def member_candidates(self, project: Project, query: object) -> Page[MemberCandidate]:
        """The picker: the org's active members and the workspace's staff not yet on it."""
        return await self._candidates(self.repository.candidates(project), query)

    async def _candidates(self, people: Select[User], query: object) -> Page[MemberCandidate]:
        page = await fetch_page(
            self.session,
            people,
            MEMBER_CANDIDATES,
            query,  # pyright: ignore[reportArgumentType] -- MEMBER_CANDIDATES.query_model
        )
        return page.with_items(
            [
                MemberCandidate(user_id=u.id, email=u.email, username=u.username, name=u.name)
                for u in page.items
            ]
        )

    async def add_member(
        self, ctx: AuthzContext, project: Project, payload: ProjectMemberAdd
    ) -> ProjectMemberRead:
        """Add someone by `user_id` (the picker) or `email` (email first), in DL-78's order of
        checks; `join_org` adds an account from outside the org and the staff to the org too."""
        if (payload.user_id is None) == (payload.email is None):
            raise ValidationFailedError.on(
                ("body",), "Send exactly one of user_id or email.", "one_parameter"
            )
        # The project's org exists: a foreign key.
        org = cast(Organization, await OrgService(self.session).get(project.organization_id))
        roster = self._members(project)
        if payload.email is not None:

            async def admit(user: User) -> dict[str, JsonValue]:
                if not await self.repository.org_member_or_staff(org, user.id):
                    if not payload.join_org:
                        raise ValidationFailedError.on(
                            ("body", "email"),
                            "This person isn't in the organization. Confirm to add them to it too.",
                            "outside_org",
                        )
                    await OrgService(self.session).add_member(ctx, org, user.email, OrgRole.MEMBER)
                # A second add of the same person, waiting here, then hits the unique constraint:
                # `already_member` on `email` (DL-80).
                return await self._lock_for_add(project, payload)

            return await roster.add(ctx, payload.email, payload.role, admit=admit)
        # Exactly one of the two was sent (checked above), so here it's `user_id`.
        user_id = cast(uuid.UUID, payload.user_id)
        if not await self.repository.org_member_or_staff(org, user_id):
            raise NotFoundError
        confirmation = await self._lock_for_add(project, payload)
        if await self.repository.membership(project.id, user_id):
            raise ValidationFailedError.on(
                ("body", "user_id"), _MEMBER_ROSTER.already_member, "already_member"
            )
        # An org member or staff member has an account.
        user = cast(User, await UserRepository(self.session).get(user_id))
        if not user.is_active:
            raise ValidationFailedError.on(
                ("body", "user_id"), "This account is deactivated.", "account_inactive"
            )
        return await roster.add_user(
            ctx, user, payload.role, loc=("body", "user_id"), details=confirmation
        )

    async def create_member(
        self, ctx: AuthzContext, project: Project, payload: ProjectMemberCreate
    ) -> ProjectMemberRead:
        """Create the account and its org membership through the org service, then the project
        membership through the roster (`user_created`, `org_member_added`,
        `project_member_added`)."""
        confirmation = await self._lock_for_add(project, payload)
        orgs = OrgService(self.session)
        org = cast(Organization, await orgs.get(project.organization_id))  # a foreign key
        new = MemberCreate(**payload.model_dump(exclude={"role", _CONFIRMED}), role=OrgRole.MEMBER)
        row = await orgs.create_member(ctx, org, new)
        user = cast(User, await UserRepository(self.session).get(row.user_id))  # just created
        return await self._members(project).add_user(ctx, user, payload.role, details=confirmation)

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
            self._log_change(project, ActivityField.LEAD_ID, actor_id, membership.user_id, None)
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
        export_controlled = project_target(project).export_controlled
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
                    access=access_kind(export_controlled, explicit=u.id in roles),
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
