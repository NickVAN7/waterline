"""The `project` area (design-doc §1.1, §3; build plan, "The projects API", "The project members
API"; DL-76, DL-78)."""

import dataclasses
import uuid
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.admin_event import JsonValue, apply_changes, change_details, log_admin_event
from app.audit.change_log import log_change
from app.authz.actions import Action
from app.authz.authorize import allowed_actions, ensure
from app.authz.context import AuthzContext, ProjectAccess
from app.authz.scoping import project_scope
from app.authz.target import Target, org_target, project_target
from app.core.errors import FieldError, ForbiddenError, NotFoundError, ValidationFailedError
from app.core.lists import Page, fetch_page
from app.enums import (
    CONTENT_ITEM_CATEGORIES,
    ActivityAction,
    ActivityEntityType,
    ActivityField,
    AuditAction,
    AuditEntityType,
    ProjectModule,
    ProjectRole,
    ProjectType,
    RestrictionCategory,
    RestrictionLevel,
)
from app.models.org import Organization
from app.models.project import Project, ProjectMembership
from app.models.user import User
from app.repositories.base import direct_update, lock_stored_at
from app.repositories.project import ProjectRepository
from app.repositories.user import UserRepository
from app.rules.identifiers import normalize_project_key, project_key_problem
from app.rules.modules import ALL_MODULES, is_available, recommended_modules, seed_modules
from app.rules.restriction import Restriction, change, levels_below, needed_rights
from app.rules.task_types import task_types
from app.schemas.project import (
    ModuleGuidance,
    ModuleNote,
    ProjectAccessEntry,
    ProjectAccessReview,
    ProjectAccessUser,
    ProjectCreate,
    ProjectItem,
    ProjectRead,
    ProjectUpdate,
    RestrictionUpdate,
    TypeRecommendation,
)
from app.schemas.user import AccessReason
from app.schemas.workspace import SlugAvailability
from app.services.approval import ApprovalService
from app.services.my_work import PROJECTS, page_of
from app.services.roster import check_lead
from app.services.user import (
    ORG_REASONS,
    PROJECT_KEY_MESSAGES,
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


EXPORT_CONTROL_CONFIRMED = "export_control_confirmed"
_MEMBER_IDS = "confirmed_member_ids"


def export_control_confirmation(
    values: BaseModel,
    *,
    needed: bool,
    members: set[uuid.UUID] | None = None,
    under: tuple[str | int, ...] = ("body",),
) -> dict[str, JsonValue]:
    """Check an export-control confirmation (design-doc §3.1; DL-81) and return it for the audit
    event. Where it's `needed`, `export_control_confirmed` must be true, and, when `members` is
    given, `confirmed_member_ids` must list exactly them; where it isn't, neither field may be
    sent. 422s: `confirmation_required`, `members_changed`, `confirmation_not_needed`, on the
    fields `under` (an org add's project entry, `("body", "projects", 0)`)."""
    sent = values.model_fields_set
    if not needed:
        errors = [
            FieldError(
                (*under, f),
                "No export-control confirmation is needed here.",
                "confirmation_not_needed",
            )
            for f in (EXPORT_CONTROL_CONFIRMED, _MEMBER_IDS)
            if f in sent
        ]
        if errors:
            raise ValidationFailedError(errors)
        return {}
    errors: list[FieldError] = []
    if not getattr(values, EXPORT_CONTROL_CONFIRMED):
        errors.append(
            FieldError(
                (*under, EXPORT_CONTROL_CONFIRMED),
                "Confirm that the people involved are authorized for export-controlled data.",
                "confirmation_required",
            )
        )
    details: dict[str, JsonValue] = {EXPORT_CONTROL_CONFIRMED: True}
    if members is not None:
        listed: list[uuid.UUID] | None = getattr(values, _MEMBER_IDS)
        if listed is None:
            errors.append(
                FieldError(
                    (*under, _MEMBER_IDS),
                    "List the project's members you confirm.",
                    "confirmation_required",
                )
            )
        elif set(listed) != members:
            errors.append(
                FieldError(
                    (*under, _MEMBER_IDS),
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


def check_item_restriction(
    project: Project,
    level: RestrictionLevel | None,
    categories: frozenset[RestrictionCategory],
    *,
    noun: str,
    level_field: str,
    categories_field: str,
) -> None:
    """A content item's restriction (a requirement's, a task's): 422 for a level below the
    project's (`below_project`, DL-208) or `export_controlled` (`project_only`: it's set on the
    project)."""
    if level in levels_below(project.restriction_level):
        raise ValidationFailedError.on(
            ("body", level_field),
            f"A {noun} can't be restricted below its project.",
            "below_project",
        )
    if not categories <= set(CONTENT_ITEM_CATEGORIES):
        raise ValidationFailedError.on(
            ("body", categories_field),
            f"Export control is set on the project, not on a {noun}.",
            "project_only",
        )


async def lift_items(
    session: AsyncSession,
    model: Any,
    entity_type: ActivityEntityType,
    project: Project,
    actor_id: uuid.UUID,
) -> None:
    """A raised project lifts its live items of `model` stored below its new level to it, each
    logged as the raiser's change, without moving `updated_at` (DL-208 to DL-210): an item
    area's `on_restriction_changed` handler."""
    level = project.restriction_level
    for item_id, old in await lock_stored_at(session, model, project.id, levels_below(level)):
        await direct_update(
            session, model, item_id, {"restriction_level": level}, touch_updated_at=False
        )
        log_change(
            session,
            project_id=project.id,
            entity_type=entity_type,
            entity_id=item_id,
            action=ActivityAction.UPDATED,
            changed_by=actor_id,
            field=ActivityField.RESTRICTION_LEVEL,
            old=old,
            new=level,
        )


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
            *identifier_error(project_key_problem(key), field="key", messages=PROJECT_KEY_MESSAGES),
        ]
        if problems:
            raise ValidationFailedError(problems)
        first_admin_id = await self._first_admin(ctx, org, values.first_admin_id)
        restriction = Restriction(
            values.restriction_level, frozenset(values.restriction_categories)
        )
        # Created export-controlled: the first admin is its only explicit member (§3.1).
        export_controlled = RestrictionCategory.EXPORT_CONTROLLED in restriction.categories
        confirmation = export_control_confirmation(
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
                **({EXPORT_CONTROL_CONFIRMED: True} if confirmation else {}),
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
            task_types=list(task_types(project.type)),
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
                await check_lead(self.session, project.id, values.lead_id)
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
        for action in needed_rights(kind, raise_, lower):
            ensure(ctx, action, target)
        adds_export_control = RestrictionCategory.EXPORT_CONTROLLED in (
            new.categories - old.categories
        )
        confirmation = export_control_confirmation(
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
            if adds_export_control:
                # Inherited admins without a membership can no longer decide (design-doc §6.2).
                await ApprovalService(self.session).replace_lost_access(project, ctx.user_id)
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

    async def favorite(self, ctx: AuthzContext, project: Project) -> None:
        """Star the project for the caller; no audit event or activity entry (DL-304)."""
        await self.repository.add_favorite(ctx.user_id, project.id)

    async def unfavorite(self, ctx: AuthzContext, project: Project) -> None:
        """Unstar the project for the caller (DL-304)."""
        await self.repository.remove_favorite(ctx.user_id, project.id)

    async def unarchive(self, ctx: AuthzContext, project: Project) -> None:
        """`project_unarchived`; already unarchived changes and records nothing."""
        await self.repository.lock(project)
        if project.archived_at is None:
            return
        project.archived_at = None
        await self.session.flush()
        self._log(AuditAction.PROJECT_UNARCHIVED, ctx.user_id, project)

    # --- Access review (members are `ProjectMemberService`'s, S3-C0w) ----------------------

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
