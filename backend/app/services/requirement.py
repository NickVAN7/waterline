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
    CONTENT_ITEM_CATEGORIES,
    ActivityAction,
    ActivityEntityType,
    ActivityField,
    ApprovalEntityType,
    ApprovalRequestStatus,
    DeletedChildren,
    NumberPrefix,
    RequirementStatus,
    RestrictionCategory,
    RestrictionLevel,
    TrashItemType,
)
from app.models.approval import ApprovalRequest
from app.models.project import Project
from app.models.requirement import Requirement, RequirementRevision
from app.models.user import User
from app.repositories.activity import ActivityRepository
from app.repositories.approval import ApprovalRepository
from app.repositories.base import direct_update, get_by_id
from app.repositories.project import ProjectRepository
from app.repositories.requirement import RequirementRepository
from app.repositories.user import UserRepository
from app.rules.approval_policy import status_after_rejection
from app.rules.rank import rank_between
from app.rules.restriction import Restriction, change, levels_below
from app.schemas.approval import (
    ApprovalDecisionCreate,
    ApprovalRead,
    ApprovalRequestCreate,
    ApprovalRequestItem,
    ApprovalRequestRead,
)
from app.schemas.requirement import (
    RequirementApprove,
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
from app.services.approval import ApprovalService, register_on_approved, register_on_rejected
from app.services.numbering import NumberingService
from app.services.project import register_on_restriction_changed
from app.services.user import required_error

type RequirementEntity = Requirement
type ApprovalRequestEntity = ApprovalRequest

# The ranked-view cap (DL-159; build plan, "API conventions").
TREE_CAP = 2_000
# The rank length cap: a drop past it rewrites the gap's siblings (design-doc §6; DL-204).
RANK_MAX = 255

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

# A requirement's approval requests: newest first, offset-paged (DL-227).
APPROVAL_REQUESTS = ListSpec(
    name="ApprovalRequestItem",
    id_column=ApprovalRequest.id,  # pyright: ignore[reportArgumentType]
    sorts={"created_at": ApprovalRequest.created_at},  # pyright: ignore[reportArgumentType]
    default_sort=("-created_at",),
)


def _categories(requirement: Requirement) -> list[RestrictionCategory]:
    return [RestrictionCategory(c) for c in requirement.restriction_categories]


def _check_restriction(
    project: Project,
    level: RestrictionLevel | None,
    categories: frozenset[RestrictionCategory],
    *,
    level_field: str,
    categories_field: str,
) -> None:
    """422 for a level below the project's (`below_project`, DL-208) or `export_controlled`
    (`project_only`: it's set on the project)."""
    if level in levels_below(project.restriction_level):
        raise ValidationFailedError.on(
            ("body", level_field),
            "A requirement can't be restricted below its project.",
            "below_project",
        )
    if not categories <= set(CONTENT_ITEM_CATEGORIES):
        raise ValidationFailedError.on(
            ("body", categories_field),
            "Export control is set on the project, not on a requirement.",
            "project_only",
        )


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
        _check_restriction(
            project,
            values.restriction_level,
            categories,
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
        requirements here (422 `not_member` or `account_inactive`, DL-211). Logs `status`,
        `priority`, and `reporter_id`."""
        project = await self._project(requirement)
        target = project_target(project, requirement)
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
            await self._check_reporter(target, reporter_id)
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
        await self.session.flush()
        for field, old, new in logged:
            self._log(requirement, ctx.user_id, ActivityAction.UPDATED, field, old, new)
        return await self.read(ctx, requirement)

    async def _check_reporter(self, target: Target, user_id: uuid.UUID) -> None:
        """The new reporter may create requirements in the project (DL-211)."""
        users = UserRepository(self.session)
        # Held, so a removal or deactivation committing meanwhile waits for this one (TD-72).
        await users.hold_access(user_id)
        user = await users.get(user_id)
        if user is None or not authorize(
            await users.authz_context(user), Action.REQUIREMENT_CREATE, target
        ):
            raise ValidationFailedError.on(
                ("body", "reporter_id"),
                "The reporter must be able to create requirements in this project.",
                "not_member",
            )
        if not user.is_active:
            raise ValidationFailedError.on(
                ("body", "reporter_id"), "This account is deactivated.", "account_inactive"
            )

    async def set_restriction(
        self, ctx: AuthzContext, requirement: Requirement, values: RequirementRestrictionUpdate
    ) -> RequirementRead:
        """Replace the level and categories, without a version bump (DL-162, DL-168): a raise
        needs `requirement.raise_restriction`, a lower `requirement.lower_restriction`, a change
        that does neither either one. 422 on `level` (`below_project`) and `categories`
        (`project_only`). Logs each field that changed."""
        project = await self._project(requirement)
        target = project_target(project, requirement)
        # The project first, as a raise does, so the level checked stays true until commit
        # (TD-72); then the row, so the rights and the old values logged see a concurrent change.
        await ProjectRepository(self.session).hold(project)
        await self._lock_live(requirement)
        old = Restriction(requirement.restriction_level, frozenset(_categories(requirement)))
        new = Restriction(values.level, frozenset(values.categories))
        kind = change(old, new)
        raise_, lower = Action.REQUIREMENT_RAISE_RESTRICTION, Action.REQUIREMENT_LOWER_RESTRICTION
        needed = [a for a, does in ((raise_, kind.raises), (lower, kind.lowers)) if does]
        # Neither: either action will do, and lower is never granted without raise.
        for action in needed or [raise_]:
            ensure(ctx, action, target)
        _check_restriction(
            project, new.level, new.categories, level_field="level", categories_field="categories"
        )
        stored = sorted(new.categories)
        logged = [
            (field, before, after)
            for field, before, after in (
                (ActivityField.RESTRICTION_LEVEL, old.level, new.level),
                (ActivityField.RESTRICTION_CATEGORIES, _categories(requirement), stored),
            )
            if before != after
        ]
        if logged:
            await direct_update(
                self.session,
                Requirement,
                requirement.id,
                {"restriction_level": new.level, "restriction_categories": stored},
                touch_updated_at=True,
            )
        for field, before, after in logged:
            self._log(requirement, ctx.user_id, ActivityAction.UPDATED, field, before, after)
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
        await self.repository.lock_tree(project.id)
        await self._lock_live(requirement)
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
        before = siblings[position - 1][1] if position > 0 else None
        after = siblings[position][1] if position < len(siblings) else None
        ranks: list[str] = []
        if before is None or before != after:
            for _ in placed:
                ranks.append(rank_between(ranks[-1] if ranks else before, after))
        if ranks and len(ranks[-1]) <= RANK_MAX:
            updates = list(zip(placed, ranks, strict=True))
        else:
            # Fresh ranks in the same order: short again, and ties broken.
            ids = [id_ for id_, _ in siblings]
            fresh: str | None = None
            updates: list[tuple[uuid.UUID, str]] = []
            for id_ in [*ids[:position], *placed, *ids[position:]]:
                fresh = rank_between(fresh, None)
                updates.append((id_, fresh))
        for id_, rank in updates:
            moved = id_ in placed
            await direct_update(
                self.session,
                Requirement,
                id_,
                {"rank": rank, "parent_requirement_id": parent_id} if moved else {"rank": rank},
                touch_updated_at=moved and reparented,
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
        await self.repository.lock_tree(project.id)
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
        await self.repository.lock_tree(project.id)
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
                    allowed_actions=actions(row),
                )
                for row in rows
            ]
        )

    async def lift_to_project(self, project: Project, actor_id: uuid.UUID) -> None:
        """A raised project lifts its live requirements stored below its new level to it, each
        logged as the raiser's change, without moving `updated_at` (DL-208 to DL-210)."""
        level = project.restriction_level
        for requirement_id, old in await self.repository.lock_stored_at(
            project.id, levels_below(level)
        ):
            await direct_update(
                self.session,
                Requirement,
                requirement_id,
                {"restriction_level": level},
                touch_updated_at=False,
            )
            log_change(
                self.session,
                project_id=project.id,
                entity_type=ActivityEntityType.REQUIREMENT,
                entity_id=requirement_id,
                action=ActivityAction.UPDATED,
                changed_by=actor_id,
                field=ActivityField.RESTRICTION_LEVEL,
                old=old,
                new=level,
            )

    async def tree(self, project: Project) -> RequirementTree:
        """The project's requirements for the tree, up to the cap (DL-159)."""
        rows = await self.repository.ranked(project.id, TREE_CAP + 1)
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
        return RequirementRead(
            id=requirement.id,
            number=requirement.number,
            parent_id=requirement.parent_requirement_id,
            title=requirement.title,
            description_md=requirement.description_md,
            status=requirement.status,
            priority=requirement.priority,
            reporter_id=requirement.reporter_id,
            reporter_name=reporter.name,
            restriction_level=requirement.restriction_level,
            restriction_categories=_categories(requirement),
            current_revision_id=requirement.current_revision_id,
            approved_revision_id=requirement.approved_revision_id,
            can_delete_children=await self._can_delete_children(ctx, project, requirement),
            approved_at=requirement.approved_at,
            version=requirement.version,
            created_at=requirement.created_at,
            updated_at=requirement.updated_at,
            allowed_actions=allowed_actions(ctx, project_target(project, requirement)),
        )

    # --- Approval requests (design-doc §6.2; S2-C10) -------------------------------------------

    async def load_approval_request(
        self, request_id: uuid.UUID
    ) -> tuple[ApprovalRequest, Target] | None:
        """The request, as a target on its live requirement inside its project; None for a
        deleted requirement's (DL-228)."""
        loaded = await self._load_request(request_id)
        if loaded is None:
            return None
        request, requirement, project = loaded
        return request, project_target(project, requirement)

    async def _load_request(
        self, request_id: uuid.UUID
    ) -> tuple[ApprovalRequest, Requirement, Project] | None:
        request = await ApprovalRepository(self.session).get(request_id)
        if request is None or request.entity_type is not ApprovalEntityType.REQUIREMENT:
            return None
        requirement = await get_by_id(self.session, Requirement, request.entity_id)
        if requirement is None:
            return None
        return request, requirement, await self._project(requirement)

    async def load_approval_request_to_decide(
        self, request_id: uuid.UUID
    ) -> tuple[ApprovalRequest, Target] | None:
        """The request on a live requirement, as a target whose entity is the request with its
        rows, for `approval.decide`'s relationship (the named approver's own pending row)."""
        loaded = await self._load_request(request_id)
        if loaded is None:
            return None
        request, _, project = loaded
        return request, project_target(project, request)

    async def decide(
        self, ctx: AuthzContext, request: ApprovalRequest, body: ApprovalDecisionCreate
    ) -> ApprovalRequestRead:
        """The caller's decision on their own row (final, DL-195); 422 `not_pending` for a request
        that isn't pending (DL-230). The policy then completes or rejects the request (design-doc
        §6.2): completion runs the requirement's `on_approved` handler; a rejected re-open round
        moves it back to `draft`."""
        requirement, project = await self._request_entities(request)
        # Project, requirement, then request: the order a delete takes them, so neither waits on
        # the other in a cycle; the rule checked again under them.
        await ProjectRepository(self.session).hold(project)
        await self._lock_live(requirement)
        approvals = ApprovalService(self.session)
        request = await approvals.lock(request)
        ensure(ctx, Action.APPROVAL_DECIDE, project_target(project, request))
        await approvals.decide(request, ctx.user_id, body.decision, body.comment)
        return await self._read_approval_request(
            ctx, request.id, project_target(project, requirement)
        )

    async def approve(
        self, ctx: AuthzContext, requirement: Requirement, body: RequirementApprove
    ) -> RequirementRead:
        """Approve by hand (design-doc §5): the current revision, by the caller, now; a pending
        request cancelled. 409 on a stale `version` (DL-169)."""
        project = await self._project(requirement)
        await ProjectRepository(self.session).hold(project)
        await self._lock_live(requirement)
        target = project_target(project, requirement)
        ensure(ctx, Action.REQUIREMENT_APPROVE_MANUALLY, target)
        check_version(requirement, body.version)
        # A foreign key set at creation, so never None (design-doc §6.1).
        revision_id = cast(uuid.UUID, requirement.current_revision_id)
        self._record_approval(requirement, revision_id, ctx.user_id, RequirementStatus.APPROVED)
        await self.session.flush()
        await ApprovalService(self.session).cancel_pending(
            ApprovalEntityType.REQUIREMENT, [requirement.id], ctx.user_id
        )
        return await self.read(ctx, requirement)

    async def complete_approval(self, request: ApprovalRequest, approver_id: uuid.UUID) -> None:
        """A completed request (design-doc §6.2): its revision approved by the approver whose
        decision completed it, when it completed; only a `draft` requirement moves to `approved`
        (DL-148). The decision holds the requirement's lock."""
        requirement = cast(Requirement, await self.session.get(Requirement, request.entity_id))
        status = (
            RequirementStatus.APPROVED
            if requirement.status is RequirementStatus.DRAFT
            else requirement.status
        )
        revision_id = cast(uuid.UUID, request.requirement_revision_id)
        # Approved when the request completed (schema-doc `requirement`), the same instant.
        self._record_approval(
            requirement, revision_id, approver_id, status, at=cast(datetime, request.completed_at)
        )

    async def reject_approval(self, request: ApprovalRequest, actor_id: uuid.UUID) -> None:
        """A rejected request: a re-open round moves the requirement back to `draft`, logged;
        anything else changes nothing (DL-195)."""
        requirement = cast(Requirement, await self.session.get(Requirement, request.entity_id))
        old = requirement.status
        new = status_after_rejection(
            old, requirement.approved_revision_id, cast(uuid.UUID, request.requirement_revision_id)
        )
        if new is not old:
            requirement.status = new
            self._log(requirement, actor_id, ActivityAction.UPDATED, ActivityField.STATUS, old, new)

    def _record_approval(
        self,
        requirement: Requirement,
        revision_id: uuid.UUID,
        approved_by: uuid.UUID,
        status: RequirementStatus,
        *,
        at: datetime | None = None,
    ) -> None:
        """`approved_revision_id`, `approved_by`, and `approved_at`, and the status; the revision
        and the status logged when they change (§10), as `approved_by`."""
        changes = [
            (ActivityField.STATUS, requirement.status, status),
            (ActivityField.APPROVED_REVISION_ID, requirement.approved_revision_id, revision_id),
        ]
        requirement.status = status
        requirement.approved_revision_id = revision_id
        requirement.approved_by = approved_by
        requirement.approved_at = at or datetime.now(UTC)
        for field, old, new in changes:
            if old != new:
                self._log(requirement, approved_by, ActivityAction.UPDATED, field, old, new)

    async def request_approval(
        self, ctx: AuthzContext, requirement: Requirement, body: ApprovalRequestCreate
    ) -> ApprovalRequestRead:
        """A request bound to the current revision, one pending at a time (DL-225, DL-229),
        naming eligible approvers (DL-226); logged `created`."""
        if len(set(body.approver_ids)) < len(body.approver_ids):
            raise ValidationFailedError.on(
                ("body", "approver_ids"), "Name each approver once.", "duplicate"
            )
        # The project held first (the order every requirement path takes), so an archive or an
        # export-control change meanwhile waits, and the check runs again under it.
        project = await self._project(requirement)
        await ProjectRepository(self.session).hold(project)
        # Then the requirement, so two creates (or a create and a delete) take turns (DL-229).
        await self._lock_live(requirement)
        target = project_target(project, requirement)
        ensure(ctx, Action.APPROVAL_REQUEST_CREATE, target)
        for approver_id in body.approver_ids:
            await self._check_approver(target, approver_id)
        request = await ApprovalService(self.session).create(
            project_id=project.id,
            entity_type=ApprovalEntityType.REQUIREMENT,
            entity_id=requirement.id,
            requirement_revision_id=requirement.current_revision_id,
            approver_ids=body.approver_ids,
            note=body.note,
            actor_id=ctx.user_id,
        )
        return await self._read_approval_request(ctx, request.id, target)

    async def _check_approver(self, target: Target, user_id: uuid.UUID) -> None:
        """The approver has content access to the project (404 otherwise, as the member picker,
        design-doc §6.2) and is active (422 `account_inactive`, DL-226)."""
        users = UserRepository(self.session)
        # Held, so a removal or deactivation committing meanwhile waits for this one (TD-72).
        await users.hold_access(user_id)
        user = await users.get(user_id)
        if user is None or not authorize(
            await users.authz_context(user), Action.REQUIREMENT_VIEW, target
        ):
            raise NotFoundError
        if not user.is_active:
            raise ValidationFailedError.on(
                ("body", "approver_ids"), "This account is deactivated.", "account_inactive"
            )

    async def approval_requests(
        self, requirement: Requirement, query: BaseModel
    ) -> Page[ApprovalRequestItem]:
        """The requirement's approval requests, newest first (DL-227)."""
        page = await fetch_page(
            self.session,
            ApprovalRepository(self.session).for_entity(
                ApprovalEntityType.REQUIREMENT, requirement.id
            ),
            APPROVAL_REQUESTS,
            query,
        )
        return Page[ApprovalRequestItem](
            items=[_approval_request(row, requirement.current_revision_id) for row in page.items],
            total=page.total,
            limit=page.limit,
            offset=page.offset,
        )

    async def read_approval_request(
        self, ctx: AuthzContext, request: ApprovalRequest
    ) -> ApprovalRequestRead:
        """The request, with the actions the caller may take on it."""
        requirement, project = await self._request_entities(request)
        return await self._read_approval_request(
            ctx, request.id, project_target(project, requirement)
        )

    async def cancel_approval_request(
        self, ctx: AuthzContext, request: ApprovalRequest
    ) -> ApprovalRequestRead:
        """Cancel a pending request, logged (`status`); 422 `not_pending` otherwise (DL-228)."""
        requirement, project = await self._request_entities(request)
        # Held and checked again, as the create is: an export-control change meanwhile waits.
        await ProjectRepository(self.session).hold(project)
        target = project_target(project, requirement)
        ensure(ctx, Action.APPROVAL_REQUEST_CANCEL, target)
        await ApprovalService(self.session).cancel(request, ctx.user_id)
        return await self._read_approval_request(ctx, request.id, target)

    async def _request_entities(self, request: ApprovalRequest) -> tuple[Requirement, Project]:
        # The loader's requirement and project, identity-map hits.
        requirement = cast(Requirement, await self.session.get(Requirement, request.entity_id))
        return requirement, await self._project(requirement)

    async def _read_approval_request(
        self, ctx: AuthzContext, request_id: uuid.UUID, target: Target
    ) -> ApprovalRequestRead:
        # A foreign key's row the caller just loaded or wrote, so never None.
        request = cast(ApprovalRequest, await ApprovalRepository(self.session).get(request_id))
        actions = allowed_actions(ctx, target)
        if request.status is ApprovalRequestStatus.PENDING:
            # Decide's relationship needs the request (its rows), not the requirement (DL-233).
            if authorize(ctx, Action.APPROVAL_DECIDE, dataclasses.replace(target, entity=request)):
                actions = sorted([*actions, Action.APPROVAL_DECIDE])
        else:
            # Ruled out for good by its state (DL-231, DL-232).
            actions = [a for a in actions if a is not Action.APPROVAL_REQUEST_CANCEL]
        requirement = cast(Requirement, target.entity)
        return ApprovalRequestRead(
            **_approval_request(request, requirement.current_revision_id).model_dump(),
            allowed_actions=actions,
        )


def _approval_request(
    request: ApprovalRequest, current_revision_id: uuid.UUID | None
) -> ApprovalRequestItem:
    # A requirement's request is bound to a revision (the CHECK `requirement_revision`).
    revision = cast(RequirementRevision, request.requirement_revision)
    return ApprovalRequestItem(
        id=request.id,
        status=request.status,
        requirement_revision_id=revision.id,
        revision_number=revision.revision_number,
        note=request.note,
        requested_by_id=request.requested_by,
        requested_by_name=request.requester.name,
        requested_by_is_active=request.requester.is_active,
        created_at=request.created_at,
        completed_at=request.completed_at,
        newer_revision_exists=revision.id != current_revision_id,
        approvals=[
            ApprovalRead(
                id=row.id,
                approver_id=row.approver_id,
                approver_name=row.approver.name,
                approver_is_active=row.approver.is_active,
                decision=row.decision,
                comment=row.comment,
                decided_at=row.decided_at,
            )
            for row in request.approvals
        ],
    )


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
    await RequirementService(session).lift_to_project(project, actor_id)


register_on_restriction_changed(_lift_requirements)


async def _approved(session: AsyncSession, request: ApprovalRequest, actor_id: uuid.UUID) -> None:
    await RequirementService(session).complete_approval(request, actor_id)


async def _rejected(session: AsyncSession, request: ApprovalRequest, actor_id: uuid.UUID) -> None:
    await RequirementService(session).reject_approval(request, actor_id)


register_on_approved(ApprovalEntityType.REQUIREMENT, _approved)
register_on_rejected(ApprovalEntityType.REQUIREMENT, _rejected)
