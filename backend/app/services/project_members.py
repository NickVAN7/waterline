"""Project membership (build plan, "The projects API"; design-doc §4, §5): the members list, the
pickers, adds (one person, an org add's projects step, DL-379), role changes, and removals, with
the project area's member-removed handler. Split from `project.py` (the handoff's Package 5 item
4, S3-C0w): a subclass, so its methods keep the project service's logging and locks."""

import dataclasses
import uuid
from typing import cast

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.admin_event import JsonValue
from app.authz.actions import Action
from app.authz.authorize import ensure
from app.authz.context import AuthzContext
from app.authz.target import project_target
from app.core.errors import ForbiddenError, NotFoundError, ValidationFailedError
from app.core.lists import Filter, FilterType, ListSpec, Page, fetch_page
from app.enums import (
    ActivityField,
    AuditAction,
    AuditEntityType,
    OrgRole,
    ProjectRole,
)
from app.models.org import Organization
from app.models.project import Project, ProjectMembership
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.org import MemberAdd, MemberCreate, MemberProjectAdd, MemberRead
from app.schemas.project import (
    MemberCandidate,
    MemberProject,
    ProjectMemberAdd,
    ProjectMemberCreate,
    ProjectMemberRead,
)
from app.services.approval import ApprovalService
from app.services.org import OrgService
from app.services.project import (
    EXPORT_CONTROL_CONFIRMED,
    ProjectService,
    export_control_confirmation,
)
from app.services.roster import MemberRemoval, Roster, RosterSpec, register_on_member_removed
from app.services.workstream import WorkstreamService

PROJECT_MEMBERS = ListSpec(
    name="ProjectMember",
    id_column=ProjectMembership.id,  # pyright: ignore[reportArgumentType]
    sorts={"name": User.name, "email": User.email},  # pyright: ignore[reportArgumentType]
    default_sort=("name",),
    filters=(Filter("role", ProjectMembership.role, FilterType.ENUM, enum=ProjectRole),),  # pyright: ignore[reportArgumentType]
    active_column=User.is_active,  # pyright: ignore[reportArgumentType]
)
MEMBER_CANDIDATES = ListSpec(
    name="MemberCandidate",
    id_column=User.id,  # pyright: ignore[reportArgumentType]
    sorts={"name": User.name},  # pyright: ignore[reportArgumentType]
    default_sort=("name",),
    search=(User.name, User.email, User.username),  # pyright: ignore[reportArgumentType]
)

MEMBER_PROJECTS = ListSpec(
    name="MemberProject",
    id_column=Project.id,  # pyright: ignore[reportArgumentType]
    sorts={"name": Project.name},  # pyright: ignore[reportArgumentType]
    default_sort=("name",),
)


@dataclasses.dataclass(frozen=True)
class _OrgAddProject:
    """An org add's project (DL-379), locked: its entry's index, its role, its confirmation."""

    index: int
    project: Project
    role: ProjectRole
    confirmation: dict[str, JsonValue]


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


class ProjectMemberService(ProjectService):
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
        member change (design-doc §5). Lock order: the project, then the person's org and staff
        rows (an add's `org_member_or_staff`), then its memberships, as a removal "with their
        projects" takes them (DL-235)."""
        await self.repository.lock(project)
        if project.archived_at is not None:
            raise ForbiddenError

    async def _lock_for_add(
        self, project: Project, payload: ProjectMemberAdd | ProjectMemberCreate
    ) -> dict[str, JsonValue]:
        """Lock the live project for a member add, then check the export-control confirmation
        against what it is now (a restriction change holds the same lock; DL-81)."""
        await self._lock_live(project)
        return export_control_confirmation(
            payload, needed=project_target(project).export_controlled
        )

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
        # The project before the person's org and staff rows (DL-235); the checks keep DL-78's
        # order, the export-control confirmation last.
        await self._lock_live(project)
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
                # A second add of the same person, waiting on the project, then hits the unique
                # constraint: `already_member` on `email` (DL-80).
                return export_control_confirmation(
                    payload, needed=project_target(project).export_controlled
                )

            return await roster.add(ctx, payload.email, payload.role, admit=admit)
        # Exactly one of the two was sent (checked above), so here it's `user_id`.
        user_id = cast(uuid.UUID, payload.user_id)
        if not await self.repository.org_member_or_staff(org, user_id):
            raise NotFoundError
        confirmation = export_control_confirmation(
            payload, needed=project_target(project).export_controlled
        )
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

    async def member_projects(self, org: Organization, query: object) -> Page[MemberProject]:
        """An org add's projects step (Q12g, DL-379): the org's live projects. Whoever may add
        org members (`org_member.manage`) administers every one of them, so none is filtered out
        here; the add still authorizes each."""
        page = await fetch_page(
            self.session,
            self.repository.live_in_org(org.id),
            MEMBER_PROJECTS,
            query,  # pyright: ignore[reportArgumentType] -- MEMBER_PROJECTS.query_model
        )
        return page.with_items(
            [
                MemberProject(
                    id=p.id,
                    key=p.key,
                    name=p.name,
                    export_controlled=project_target(p).export_controlled,
                )
                for p in page.items
            ]
        )

    async def add_org_member(
        self, ctx: AuthzContext, org: Organization, payload: MemberAdd
    ) -> MemberRead:
        """An org add (by email) and, with `projects`, a membership on each of them, all or
        nothing in the one request (Q12g, DL-379): the org's service adds the org member, then
        this one each project's, each its own `project_member_added`."""
        projects = await self._lock_projects_for_org_add(ctx, org, payload.projects)
        row = await OrgService(self.session).add_member(ctx, org, payload.email, payload.role)
        await self._add_to_projects(ctx, row.user_id, projects)
        return row

    async def create_org_member(
        self, ctx: AuthzContext, org: Organization, payload: MemberCreate
    ) -> MemberRead:
        """As `add_org_member`, creating the account first (`user_created`)."""
        projects = await self._lock_projects_for_org_add(ctx, org, payload.projects)
        row = await OrgService(self.session).create_member(ctx, org, payload)
        await self._add_to_projects(ctx, row.user_id, projects)
        return row

    async def _lock_projects_for_org_add(
        self, ctx: AuthzContext, org: Organization, entries: list[MemberProjectAdd]
    ) -> list[_OrgAddProject]:
        """Each entry's project, locked live, in ID order, before the person's rows (DL-235),
        with its export-control confirmation checked under the lock (DL-81); one query to read
        them, one to lock them. A project sent twice is a 422 `duplicate`; one outside the org, or
        one the caller can't see, a 404 before any lock; one they may not add members to, or
        archived, a 403."""
        index_of: dict[uuid.UUID, int] = {}
        for index, entry in enumerate(entries):
            if entry.project_id in index_of:
                raise ValidationFailedError.on(
                    ("body", "projects", index, "project_id"),
                    "This project is listed twice.",
                    "duplicate",
                )
            index_of[entry.project_id] = index
        found = {p.id: p for p in await self.repository.in_org(org.id, index_of)}
        for entry in entries:
            project = found.get(entry.project_id)
            if project is None:
                raise NotFoundError
            # As DL-379 asks: today `org_member.manage`, which the route requires, carries this
            # on every project in the org (actions.py), so it refuses no one yet.
            ensure(ctx, Action.PROJECT_MEMBER_MANAGE, project_target(project))
        locked: list[_OrgAddProject] = []
        for project in await self.repository.lock_all(index_of):
            # Archived since it was read: a member change is denied (design-doc §5).
            if project.archived_at is not None:
                raise ForbiddenError
            index = index_of[project.id]
            confirmation = export_control_confirmation(
                entries[index],
                needed=project_target(project).export_controlled,
                under=("body", "projects", index),
            )
            locked.append(_OrgAddProject(index, project, entries[index].role, confirmation))
        return locked

    async def _add_to_projects(
        self, ctx: AuthzContext, user_id: uuid.UUID, projects: list[_OrgAddProject]
    ) -> None:
        """Each membership; one the person already holds (workspace staff can be on a project
        outside its org) is a 422 `already_member` on its entry."""
        if not projects:
            return
        user = cast(User, await UserRepository(self.session).get(user_id))  # just added
        for add in projects:
            await self._members(add.project).add_user(
                ctx,
                user,
                add.role,
                loc=("body", "projects", add.index, "project_id"),
                details=add.confirmation,
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
        new = MemberCreate(
            **payload.model_dump(exclude={"role", EXPORT_CONTROL_CONFIRMED}), role=OrgRole.MEMBER
        )
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
        """Remove a member (`project_member_removed`); removing the lead clears `lead_id`, and
        their pending approvals are replaced if that took their access (design-doc §6.2)."""
        await self._lock_live(project)
        membership = await self.repository.membership(project.id, user_id, lock=True)
        if membership is None:
            raise NotFoundError
        await self._remove(membership, project, ctx.user_id)
        await ApprovalService(self.session).replace_lost_access(project, ctx.user_id)

    async def _remove(
        self,
        membership: ProjectMembership,
        project: Project,
        actor_id: uuid.UUID,
        *,
        via: AuditAction | None = None,
    ) -> None:
        """Delete the membership and, if it was the lead's, clear `lead_id` in the same
        transaction (`lead_cleared`), and the workstream leads it held
        (`workstream_leads_cleared`); `via`, the org or staff removal that removed it."""
        details: dict[str, JsonValue] = {"role": membership.role.value}
        await self.session.delete(membership)
        if project.lead_id == membership.user_id:
            project.lead_id = None
            details["lead_cleared"] = True
            self._log_change(project, ActivityField.LEAD_ID, actor_id, membership.user_id, None)
        # The project lead's rule holds for workstream leads too (S3-C4).
        if cleared := await WorkstreamService(self.session).clear_lead(
            project.id, membership.user_id
        ):
            details["workstream_leads_cleared"] = [str(id_) for id_ in cleared]
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


async def _remove_with_projects(session: AsyncSession, removal: MemberRemoval) -> None:
    await ProjectMemberService(session).remove_with_projects(removal)


register_on_member_removed(_remove_with_projects)
