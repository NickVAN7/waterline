"""Requirements (design-doc §6; build plan, "Requirements")."""

import dataclasses
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import cast

from pydantic import BaseModel
from sqlalchemy import literal
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.change_log import log_change
from app.authz.actions import Action
from app.authz.authorize import allowed_actions, authorize, ensure
from app.authz.context import AuthzContext
from app.authz.target import Target, project_target
from app.core.base_model import check_version
from app.core.errors import ForbiddenError, NotFoundError, ValidationFailedError
from app.core.lists import Feed, Filter, FilterType, ListSpec, Page, fetch_feed, fetch_page
from app.enums import (
    ActivityAction,
    ActivityEntityType,
    ActivityField,
    ApprovalEntityType,
    DeletedChildren,
    NumberPrefix,
    RequirementStatus,
    RestrictionCategory,
    TrashItemType,
)
from app.models.approval import ApprovalRequest
from app.models.project import Project
from app.models.requirement import Requirement, RequirementRevision
from app.models.user import User
from app.repositories.activity import ActivityRepository
from app.repositories.approval import ApprovalRepository
from app.repositories.base import direct_update, write_ranks
from app.repositories.project import ProjectRepository
from app.repositories.requirement import RequirementRepository
from app.repositories.user import UserRepository
from app.rules.rank import place, rank_between
from app.rules.restriction import Restriction, effective, levels_below
from app.schemas.requirement import (
    RequirementAncestor,
    RequirementCreate,
    RequirementItem,
    RequirementMove,
    RequirementRead,
    RequirementRestrictionUpdate,
    RequirementTree,
    RequirementUpdate,
    RevisionItem,
    RevisionRead,
    TrashItem,
)
from app.services.approval import ApprovalService
from app.services.numbering import NumberingService
from app.services.project import (
    check_item_restriction,
    lift_items,
    register_on_restriction_changed,
    set_item_restriction,
)
from app.services.user import check_person, required_error
from app.services.workstream import WorkstreamService

type RequirementEntity = Requirement
type ApprovalRequestEntity = ApprovalRequest

# The ranked-view cap (DL-159; build plan, "API conventions").
TREE_CAP = 2_000

# The project's trash (design-doc §9): newest first; tasks and test cases join in Slices 3 and 5.
TRASH = ListSpec(
    name="TrashItem",
    id_column=Requirement.id,  # pyright: ignore[reportArgumentType]
    sorts={"deleted_at": Requirement.deleted_at},  # pyright: ignore[reportArgumentType]
    default_sort=("-deleted_at",),
    filters=(
        Filter(
            "type", literal(TrashItemType.REQUIREMENT.value), FilterType.ENUM, enum=TrashItemType
        ),
    ),
)

REVISIONS = ListSpec(
    name="RevisionItem",
    id_column=RequirementRevision.id,  # pyright: ignore[reportArgumentType]
    paging="cursor",
)


def _categories(requirement: Requirement) -> list[RestrictionCategory]:
    return [RestrictionCategory(c) for c in requirement.restriction_categories]


class RequirementService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = RequirementRepository(session)

    async def load(self, key: str, number: int) -> tuple[Requirement, Target] | None:
        """The requirement `number` in project `key`, as a target inside its project."""
        project = await ProjectRepository(self.session).get_by_key(key)
        if project is None:
            return None
        requirement = await self.repository.get_by_number(project.id, number)
        return None if requirement is None else (requirement, project_target(project, requirement))

    async def load_deleted(self, key: str, number: int) -> tuple[Requirement, Target] | None:
        """The requirement `number` in project `key` if it's in the trash, as a target inside its
        project."""
        project = await ProjectRepository(self.session).get_by_key(key)
        if project is None:
            return None
        requirement = await self.repository.get_deleted_by_number(project.id, number)
        return None if requirement is None else (requirement, project_target(project, requirement))

    async def _project(self, requirement: Requirement) -> Project:
        # A foreign key, so never None; the loader's project, an identity-map hit.
        return cast(Project, await self.session.get(Project, requirement.project_id))

    async def _current_context(self, ctx: AuthzContext) -> AuthzContext:
        """The caller's authorization context loaded again, for a check made under locks a
        change to their access takes first."""
        user = await self.session.get_one(User, ctx.user_id, populate_existing=True)
        if not user.is_active:
            # Deactivated meanwhile: no access at all, as `ApprovalService` counts it.
            raise NotFoundError
        return await UserRepository(self.session).authz_context(user)

    async def _lock_live(self, requirement: Requirement) -> None:
        """Lock the row and read it again; one deleted meanwhile is a 404."""
        await self.repository.lock(requirement)
        if requirement.deleted_at is not None:
            raise NotFoundError

    def _log(
        self,
        requirement: Requirement,
        actor_id: uuid.UUID,
        action: ActivityAction,
        field: ActivityField | None = None,
        old: object = None,
        new: object = None,
    ) -> None:
        log_change(
            self.session,
            project_id=requirement.project_id,
            entity_type=ActivityEntityType.REQUIREMENT,
            entity_id=requirement.id,
            action=action,
            changed_by=actor_id,
            field=field,
            old=old,
            new=new,
        )

    async def create(
        self, ctx: AuthzContext, project: Project, values: RequirementCreate
    ) -> RequirementRead:
        """A new requirement in `project`: the next `RQ` number, `draft`, reported by the
        caller, at the bottom of its siblings, with revision 1, at `version` 1 (design-doc §6,
        §6.1; DL-207). 404 for a `parent_id` outside the project; 422 on `title` (`missing`),
        `restriction_level` (`below_project`), and `restriction_categories` (`project_only`)."""
        problems = required_error(values.title, field="title")
        if problems:
            raise ValidationFailedError(problems)
        categories = frozenset(values.restriction_categories)
        # Held, so a raise committing meanwhile can't leave the item below the level (TD-72).
        await ProjectRepository(self.session).hold(project)
        # Checked again on the held row: an archive or export-control change that committed
        # while this waited takes the right away.
        ensure(ctx, Action.REQUIREMENT_CREATE, project_target(project))
        check_item_restriction(
            project,
            values.restriction_level,
            categories,
            noun="requirement",
            level_field="restriction_level",
            categories_field="restriction_categories",
        )
        # Checked before a number is taken; another project's requirement is a 404 (S2-plan,
        # threat model).
        # Held, so a delete of the parent can't commit under the new child (TD-71).
        if values.parent_id is not None and (
            await self.repository.get_in_project(project.id, values.parent_id, hold=True) is None
        ):
            raise NotFoundError
        title = values.title.strip()
        requirement = Requirement(
            project_id=project.id,
            number=await NumberingService(self.session).allocate_number(
                project, NumberPrefix.REQUIREMENT
            ),
            parent_requirement_id=values.parent_id,
            reporter_id=ctx.user_id,
            title=title,
            description_md=values.description_md,
            priority=values.priority,
            rank=rank_between(
                await self.repository.last_sibling_rank(project.id, values.parent_id), None
            ),
            restriction_level=values.restriction_level,
            restriction_categories=sorted(categories),
        )
        self.session.add(requirement)
        # The foreign keys are circular: the requirement goes in first, then revision 1.
        await self.session.flush()
        revision = RequirementRevision(
            requirement_id=requirement.id,
            revision_number=1,
            title=title,
            description_md=values.description_md,
            created_by=ctx.user_id,
        )
        self.session.add(revision)
        await self.session.flush()
        # Not an edit, so no version bump: a new requirement starts at 1 (DL-207, DL-210).
        await direct_update(
            self.session,
            Requirement,
            requirement.id,
            {"current_revision_id": revision.id},
            touch_updated_at=False,
        )
        self._log(requirement, ctx.user_id, ActivityAction.CREATED)
        return await self.read(ctx, requirement)

    async def update(
        self, ctx: AuthzContext, requirement: Requirement, values: RequirementUpdate
    ) -> RequirementRead:
        """Change the fields sent (design-doc §5, §6.1). 409 on a stale `version`. A changed
        title or description makes the next revision, with `change_note`. `status` `approved`:
        403 without `requirement.approve_manually`, else 422 `use_approve` (DL-161). A changed
        `reporter_id` needs `requirement.reassign_reporter`, and someone who may create
        requirements here (422 `not_member` or `account_inactive`, DL-211). A newly set
        `workstream_id` is a live workstream of the project (404 outside it, 422 `archived`).
        Logs `status`, `priority`, `reporter_id`, and `workstream_id`."""
        project = await self._project(requirement)
        # Held, then read: the target sees what a restriction change committed meanwhile
        # (TD-74). Project, then requirement, as every requirement path takes them, so a member
        # removal holding the project (and completing a request on this requirement) finishes
        # first.
        await ProjectRepository(self.session).hold(project)
        target = project_target(project, requirement)
        # Checked again on the held row, as a create is.
        ensure(ctx, Action.REQUIREMENT_UPDATE, target)
        if values.status is RequirementStatus.APPROVED:
            ensure(ctx, Action.REQUIREMENT_APPROVE_MANUALLY, target)
            raise ValidationFailedError.on(
                ("body", "status"), "Approve the requirement with Approve.", "use_approve"
            )
        # Locked and read again, so the version check and the old values logged see what a
        # concurrent edit committed, and two edits never both take the next revision number.
        await self._lock_live(requirement)
        check_version(requirement, values.version)
        reporter_id = values.reporter_id
        if reporter_id is not None and reporter_id != requirement.reporter_id:
            ensure(ctx, Action.REQUIREMENT_REASSIGN_REPORTER, target)
            await check_person(
                self.session,
                target,
                reporter_id,
                Action.REQUIREMENT_CREATE,
                "reporter_id",
                ValidationFailedError.on(
                    ("body", "reporter_id"),
                    "The reporter must be able to create requirements in this project.",
                    "not_member",
                ),
            )
        else:
            reporter_id = None
        if values.title is not None and (problems := required_error(values.title, field="title")):
            raise ValidationFailedError(problems)
        title = requirement.title if values.title is None else values.title.strip()
        description = (
            requirement.description_md if values.description_md is None else values.description_md
        )
        if (title, description) != (requirement.title, requirement.description_md):
            revision = RequirementRevision(
                requirement_id=requirement.id,
                revision_number=await self.repository.revision_number(
                    cast(uuid.UUID, requirement.current_revision_id)
                )
                + 1,
                title=title,
                description_md=description,
                change_note=values.change_note,
                created_by=ctx.user_id,
            )
            self.session.add(revision)
            await self.session.flush()
            requirement.title = title
            requirement.description_md = description
            requirement.current_revision_id = revision.id
        logged: list[tuple[ActivityField, object, object]] = []
        for field, new in (
            (ActivityField.STATUS, values.status),
            (ActivityField.PRIORITY, values.priority),
            (ActivityField.REPORTER_ID, reporter_id),
        ):
            old = getattr(requirement, field.value)
            if new is not None and new != old:
                setattr(requirement, field.value, new)
                logged.append((field, old, new))
        # Nullable: null clears it.
        old_workstream = requirement.workstream_id
        if "workstream_id" in values.model_fields_set and values.workstream_id != old_workstream:
            if values.workstream_id is not None:
                await WorkstreamService(self.session).assignable(project.id, values.workstream_id)
            requirement.workstream_id = values.workstream_id
            logged.append((ActivityField.WORKSTREAM_ID, old_workstream, values.workstream_id))
        await self.session.flush()
        for field, old, new in logged:
            self._log(requirement, ctx.user_id, ActivityAction.UPDATED, field, old, new)
        return await self.read(ctx, requirement)

    async def set_restriction(
        self, ctx: AuthzContext, requirement: Requirement, values: RequirementRestrictionUpdate
    ) -> RequirementRead:
        """Replace the level and categories, without a version bump (DL-162, DL-168): a raise
        needs `requirement.raise_restriction`, a lower `requirement.lower_restriction`, a change
        that does neither either one. 422 on `level` (`below_project`) and `categories`
        (`project_only`). Logs each field that changed."""
        project = await self._project(requirement)
        # The project first, as a raise does, so the level checked stays true until commit
        # (TD-72); then the row, so the rights and the old values logged see a concurrent change.
        await ProjectRepository(self.session).hold(project)
        await self._lock_live(requirement)
        # Built on the held rows: an archive or export-control change meanwhile is seen (TD-80).
        await set_item_restriction(
            self.session,
            ctx,
            project,
            requirement,
            Restriction(values.level, frozenset(values.categories)),
            entity_type=ActivityEntityType.REQUIREMENT,
            raise_action=Action.REQUIREMENT_RAISE_RESTRICTION,
            lower_action=Action.REQUIREMENT_LOWER_RESTRICTION,
            noun="requirement",
        )
        return await self.read(ctx, requirement)

    async def move(
        self, ctx: AuthzContext, requirement: Requirement, values: RequirementMove
    ) -> RequirementRead:
        """Put the requirement under `parent_id` (null: the top level), just after `after_id` or
        just before `before_id` among its siblings, or at the bottom (design-doc §6). 404 for a
        parent outside the project; 422 on `parent_id` (`cycle`: itself or a descendant), on
        `after_id` or `before_id` (`not_sibling`: not another child of that parent), and on
        `before_id` with both (`conflict`). A drop with no rank between its neighbors (a tie, or
        past 255 characters) rewrites the ranks of that parent's children in order (DL-204).
        No `version` bump; a parent change is logged and moves `updated_at`, a reorder doesn't."""
        if values.after_id is not None and values.before_id is not None:
            raise ValidationFailedError.on(
                ("body", "before_id"), "Give after_id or before_id, not both.", "conflict"
            )
        project = await self._project(requirement)
        # Moves in a project run one at a time, so two at once can't make a cycle neither saw.
        # The tree first, then the row: a new parent's foreign-key check waits on that parent's
        # row, which another move may hold.
        await self.repository.lock_tree(project)
        await self._lock_live(requirement)
        # Checked again under the tree lock, which reads the project again (TD-80).
        ensure(ctx, Action.REQUIREMENT_UPDATE, project_target(project, requirement))
        parent_id, old_parent_id = values.parent_id, requirement.parent_requirement_id
        reparented = parent_id != old_parent_id
        if parent_id is not None:
            if await self.repository.get_in_project(project.id, parent_id) is None:
                raise NotFoundError
            if await self.repository.is_in_ancestry(requirement.id, of=parent_id):
                raise ValidationFailedError.on(
                    ("body", "parent_id"),
                    "A requirement can't move under itself or one of its children.",
                    "cycle",
                )
        siblings = await self.repository.siblings(project.id, parent_id, excluding=requirement.id)
        ids = [id_ for id_, _ in siblings]
        position = len(ids)
        for field, anchor, offset in (
            ("after_id", values.after_id, 1),
            ("before_id", values.before_id, 0),
        ):
            if anchor is None:
                continue
            if anchor not in ids:
                raise ValidationFailedError.on(
                    ("body", field), "That requirement isn't a sibling here.", "not_sibling"
                )
            position = ids.index(anchor) + offset
        await self._place([requirement.id], parent_id, siblings, position, reparented=reparented)
        if reparented:
            self._log(
                requirement,
                ctx.user_id,
                ActivityAction.UPDATED,
                ActivityField.PARENT_REQUIREMENT_ID,
                old_parent_id,
                parent_id,
            )
        return await self.read(ctx, requirement)

    async def _place(
        self,
        placed: list[uuid.UUID],
        parent_id: uuid.UUID | None,
        siblings: list[tuple[uuid.UUID, str]],
        position: int,
        *,
        reparented: bool,
    ) -> None:
        """Put `placed`, in order, under `parent_id` at `position` among `siblings` (`(id, rank)`
        in order). With no room between the neighbors (a tie, or past 255 characters), the
        parent's children are rewritten in order (DL-204, DL-213, DL-218). No `version` bump; a
        placed item's `updated_at` moves when `reparented`."""
        writes = place(siblings, placed, position)
        moved = set(placed)
        for id_, rank in writes:
            if id_ in moved:
                await direct_update(
                    self.session,
                    Requirement,
                    id_,
                    {"rank": rank, "parent_requirement_id": parent_id},
                    touch_updated_at=reparented,
                )
        # The rest of a rewrite in one statement (DL-345, TD-73).
        await write_ranks(
            self.session, Requirement, [(id_, rank) for id_, rank in writes if id_ not in moved]
        )

    async def _subtree(
        self, requirement: Requirement, *, deleted_at: datetime | None = None
    ) -> list[Requirement]:
        """The requirement's descendants, locked a level at a time (live ones, or with
        `deleted_at`, those deleted with it), so a child created under one meanwhile is seen."""
        found: list[Requirement] = []
        level = [requirement.id]
        while level:
            children = await self.repository.lock_children(level, deleted_at=deleted_at)
            found += children
            level = [child.id for child in children]
        return found

    def _ensure_each(
        self, ctx: AuthzContext, project: Project, action: Action, items: list[Requirement]
    ) -> None:
        """403 unless the caller may take `action` on every item: a delete or restore never
        reaches what the caller couldn't act on directly (DL-221)."""
        if not all(authorize(ctx, action, project_target(project, item)) for item in items):
            raise ForbiddenError

    async def delete(
        self, ctx: AuthzContext, requirement: Requirement, children: DeletedChildren
    ) -> None:
        """Move the requirement to the trash (design-doc §9): its children promoted to its
        parent, in its place (DL-217), or its whole subtree deleted with it, 403 if the caller
        may not delete each one (DL-221). Every deleted one's pending approval request is
        cancelled (DL-224). One `deleted_at` for all, each logged."""
        project = await self._project(requirement)
        await self.repository.lock_tree(project)
        await self._lock_live(requirement)
        # Checked again on the locked row: a reporter change or an approval that committed while
        # this waited can take the right away.
        ensure(ctx, Action.REQUIREMENT_DELETE, project_target(project, requirement))
        if children is DeletedChildren.DELETE:
            deleted = [requirement, *await self._subtree(requirement)]
            self._ensure_each(ctx, project, Action.REQUIREMENT_DELETE, deleted[1:])
        else:
            deleted = [requirement]
            promoted = await self.repository.lock_children([requirement.id])
            if promoted:
                parent_id = requirement.parent_requirement_id
                siblings = await self.repository.siblings(
                    project.id, parent_id, excluding=requirement.id
                )
                place = (requirement.rank, requirement.id)
                position = sum(1 for id_, rank in siblings if (rank, id_) < place)
                await self._place(
                    [child.id for child in promoted], parent_id, siblings, position, reparented=True
                )
                for child in promoted:
                    self._log(
                        child,
                        ctx.user_id,
                        ActivityAction.UPDATED,
                        ActivityField.PARENT_REQUIREMENT_ID,
                        requirement.id,
                        parent_id,
                    )
        # One moment for the whole subtree, which a restore brings back together (DL-146).
        now = datetime.now(UTC)
        for item in deleted:
            item.deleted_at = now
        await self.session.flush()
        for item in deleted:
            self._log(item, ctx.user_id, ActivityAction.DELETED)
        await ApprovalService(self.session).cancel_pending(
            ApprovalEntityType.REQUIREMENT, [item.id for item in deleted], ctx.user_id
        )

    async def restore(self, ctx: AuthzContext, requirement: Requirement) -> RequirementRead:
        """Bring the requirement back from the trash with the descendants deleted with it, 403
        if the caller may not restore each one (DL-146, DL-221); at the bottom of the top level
        if its parent is still in the trash (DL-217). One stored below the project's level is
        raised to it (DL-209). Each logged."""
        project = await self._project(requirement)
        await self.repository.lock_tree(project)
        await self.repository.lock(requirement)
        deleted_at = requirement.deleted_at
        if deleted_at is None:
            # Restored meanwhile.
            raise NotFoundError
        # Checked again on the locked row, as a delete is.
        ensure(ctx, Action.REQUIREMENT_RESTORE, project_target(project, requirement))
        restored = [requirement, *await self._subtree(requirement, deleted_at=deleted_at)]
        self._ensure_each(ctx, project, Action.REQUIREMENT_RESTORE, restored[1:])
        parent_id = requirement.parent_requirement_id
        if (
            parent_id is not None
            and await self.repository.get_in_project(project.id, parent_id) is None
        ):
            siblings = await self.repository.siblings(project.id, None, excluding=requirement.id)
            await self._place([requirement.id], None, siblings, len(siblings), reparented=True)
            self._log(
                requirement,
                ctx.user_id,
                ActivityAction.UPDATED,
                ActivityField.PARENT_REQUIREMENT_ID,
                parent_id,
                None,
            )
        below = levels_below(project.restriction_level)
        for item in restored:
            item.deleted_at = None
        await self.session.flush()
        for item in restored:
            old_level = item.restriction_level
            lifted = old_level in below
            if lifted:
                await direct_update(
                    self.session,
                    Requirement,
                    item.id,
                    {"restriction_level": project.restriction_level},
                    touch_updated_at=False,
                )
            self._log(item, ctx.user_id, ActivityAction.RESTORED)
            if lifted:
                self._log(
                    item,
                    ctx.user_id,
                    ActivityAction.UPDATED,
                    ActivityField.RESTRICTION_LEVEL,
                    old_level,
                    project.restriction_level,
                )
        return await self.read(ctx, requirement)

    async def trash(self, ctx: AuthzContext, project: Project, query: BaseModel) -> Page[TrashItem]:
        """The project's deleted items the caller could restore, each by its own rule (DL-220):
        everything for project admins, the reporter's own never-approved ones for members. A
        row carries `requirement.restore` only when the whole restore would pass (DL-222)."""
        # Who could restore, archived or not: an archived project lists the same rows (DL-220).
        live = dataclasses.replace(project_target(project), archived=False)
        empty = False
        if authorize(ctx, Action.REQUIREMENT_RESTORE, live):
            reporter_id = None
        else:
            # A project member's own never-approved one (DL-219): nothing for anyone else.
            own = Requirement(reporter_id=ctx.user_id, approved_revision_id=None)
            reporter_id = ctx.user_id
            empty = not authorize(
                ctx, Action.REQUIREMENT_RESTORE, dataclasses.replace(live, entity=own)
            )
        page = await fetch_page(
            self.session,
            self.repository.trash(project.id, reporter_id, empty=empty),
            TRASH,
            query,
        )
        rows: list[Requirement] = page.items
        with_them: dict[uuid.UUID, list[Requirement]] = defaultdict(list)
        for root, item in await self.repository.deleted_with(rows) if rows else []:
            with_them[root].append(item)
        deleters = await ActivityRepository(self.session).last_deleters(
            ActivityEntityType.REQUIREMENT, [row.id for row in rows]
        )
        users = await UserRepository(self.session).get_many(
            {user_id for user_id in deleters.values() if user_id is not None}
        )

        def deleter(row: Requirement) -> User | None:
            user_id = deleters.get(row.id)
            return None if user_id is None else users.get(user_id)

        def actions(row: Requirement) -> list[Action]:
            allowed = allowed_actions(ctx, project_target(project, row))
            if Action.REQUIREMENT_RESTORE in allowed and not all(
                authorize(ctx, Action.REQUIREMENT_RESTORE, project_target(project, item))
                for item in with_them[row.id]
            ):
                allowed.remove(Action.REQUIREMENT_RESTORE)
            return allowed

        return page.with_items(
            [
                TrashItem(
                    type=TrashItemType.REQUIREMENT,
                    id=row.id,
                    number=row.number,
                    title=row.title,
                    deleted_at=cast(datetime, row.deleted_at),
                    deleted_by_id=deleters.get(row.id),
                    deleted_by_name=user.name if (user := deleter(row)) else None,
                    deleted_by_is_active=user.is_active if user else None,
                    allowed_actions=actions(row),
                )
                for row in rows
            ]
        )

    async def tree(self, project: Project) -> RequirementTree:
        """The project's requirements for the tree, up to the cap (DL-159)."""
        rows = await self.repository.ranked(project.id, TREE_CAP + 1)
        awaiting = await ApprovalRepository(self.session).pending_entity_ids(
            project.id, ApprovalEntityType.REQUIREMENT
        )
        return RequirementTree(
            items=[
                RequirementItem(
                    id=r.id,
                    number=r.number,
                    parent_id=r.parent_requirement_id,
                    title=r.title,
                    status=r.status,
                    priority=r.priority,
                    restriction_level=r.restriction_level,
                    restriction_categories=_categories(r),
                    current_revision_id=r.current_revision_id,
                    approved_revision_id=r.approved_revision_id,
                    awaiting_approval=r.id in awaiting,
                )
                for r in rows[:TREE_CAP]
            ],
            truncated=len(rows) > TREE_CAP,
        )

    async def _can_delete_children(
        self, ctx: AuthzContext, project: Project, requirement: Requirement
    ) -> bool:
        """Whether the caller may delete the requirement with its whole subtree (DL-222)."""
        target = project_target(project, requirement)
        if requirement.deleted_at is not None or not authorize(
            ctx, Action.REQUIREMENT_DELETE, target
        ):
            return False
        return all(
            authorize(ctx, Action.REQUIREMENT_DELETE, project_target(project, item))
            for item in await self.repository.live_descendants(requirement.id)
        )

    async def revisions(self, requirement: Requirement, query: BaseModel) -> Feed[RevisionItem]:
        """The requirement's revisions, newest first, cursor-paged (append-only, design-doc
        §6.1)."""
        page = await fetch_feed(
            self.session, self.repository.revisions(requirement.id), REVISIONS, query
        )
        return Feed[RevisionItem](
            items=[_revision(row) for row in page.items],
            next_cursor=page.next_cursor,
        )

    async def revision(self, requirement: Requirement, revision_number: int) -> RevisionRead:
        """One revision with its snapshot; a number the requirement doesn't have is a 404."""
        row = await self.repository.revision(requirement.id, revision_number)
        if row is None:
            raise NotFoundError
        return RevisionRead(**_revision(row).model_dump(), description_md=row.description_md)

    async def read(self, ctx: AuthzContext, requirement: Requirement) -> RequirementRead:
        """The requirement, with the actions the caller may take on it."""
        project = await self._project(requirement)
        # A foreign key, so never None.
        reporter = cast(User, await self.session.get(User, requirement.reporter_id))
        applies = effective(
            Restriction(requirement.restriction_level, frozenset(_categories(requirement))),
            Restriction(
                project.restriction_level,
                frozenset(RestrictionCategory(c) for c in project.restriction_categories),
            ),
        )
        return RequirementRead(
            id=requirement.id,
            number=requirement.number,
            parent_id=requirement.parent_requirement_id,
            title=requirement.title,
            description_md=requirement.description_md,
            status=requirement.status,
            priority=requirement.priority,
            workstream_id=requirement.workstream_id,
            reporter_id=requirement.reporter_id,
            reporter_name=reporter.name,
            reporter_is_active=reporter.is_active,
            restriction_level=requirement.restriction_level,
            restriction_categories=_categories(requirement),
            effective_restriction_level=applies.level,
            effective_restriction_categories=sorted(applies.categories),
            current_revision_id=requirement.current_revision_id,
            approved_revision_id=requirement.approved_revision_id,
            approved_revision_number=await self._revision_number(requirement.approved_revision_id),
            has_children=await self.repository.has_children(requirement.id),
            can_delete_children=await self._can_delete_children(ctx, project, requirement),
            approved_at=requirement.approved_at,
            version=requirement.version,
            created_at=requirement.created_at,
            updated_at=requirement.updated_at,
            allowed_actions=allowed_actions(ctx, project_target(project, requirement)),
            ancestors=[
                RequirementAncestor(number=number, title=title)
                for number, title in await self.repository.ancestors(requirement)
            ],
        )

    async def _revision_number(self, revision_id: uuid.UUID | None) -> int | None:
        if revision_id is None:
            return None
        # A foreign key's row, so never None.
        revision = cast(
            RequirementRevision, await self.session.get(RequirementRevision, revision_id)
        )
        return revision.revision_number


def _revision(row: RequirementRevision) -> RevisionItem:
    return RevisionItem(
        id=row.id,
        revision_number=row.revision_number,
        title=row.title,
        change_note=row.change_note,
        created_by_id=row.created_by,
        created_by_name=row.creator.name,
        created_by_is_active=row.creator.is_active,
        created_at=row.created_at,
    )


async def _lift_requirements(session: AsyncSession, project: Project, actor_id: uuid.UUID) -> None:
    await lift_items(session, Requirement, ActivityEntityType.REQUIREMENT, project, actor_id)


register_on_restriction_changed(_lift_requirements)
