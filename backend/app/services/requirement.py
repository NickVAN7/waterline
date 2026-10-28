"""Requirements (design-doc §6; build plan, "Requirements")."""

import uuid
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.change_log import log_change
from app.authz.actions import Action
from app.authz.authorize import allowed_actions, authorize, ensure
from app.authz.context import AuthzContext
from app.authz.target import Target, project_target
from app.core.base_model import check_version
from app.core.errors import NotFoundError, ValidationFailedError
from app.enums import (
    CONTENT_ITEM_CATEGORIES,
    ActivityAction,
    ActivityEntityType,
    ActivityField,
    NumberPrefix,
    RequirementStatus,
    RestrictionCategory,
    RestrictionLevel,
)
from app.models.project import Project
from app.models.requirement import Requirement, RequirementRevision
from app.models.user import User
from app.repositories.base import direct_update
from app.repositories.project import ProjectRepository
from app.repositories.requirement import RequirementRepository
from app.repositories.user import UserRepository
from app.rules.rank import rank_between
from app.rules.restriction import Restriction, change, levels_below
from app.schemas.requirement import (
    RequirementCreate,
    RequirementItem,
    RequirementMove,
    RequirementRead,
    RequirementRestrictionUpdate,
    RequirementTree,
    RequirementUpdate,
)
from app.services.numbering import NumberingService
from app.services.project import register_on_restriction_changed
from app.services.user import required_error

type RequirementEntity = Requirement

# The ranked-view cap (DL-159; build plan, "API conventions").
TREE_CAP = 2_000
# The rank length cap: a drop past it rewrites the gap's siblings (design-doc §6; DL-204).
RANK_MAX = 255


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

    async def _project(self, requirement: Requirement) -> Project:
        # A foreign key, so never None; the loader's project, an identity-map hit.
        return cast(Project, await self.session.get(Project, requirement.project_id))

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
        _check_restriction(
            project,
            values.restriction_level,
            categories,
            level_field="restriction_level",
            categories_field="restriction_categories",
        )
        # Checked before a number is taken; another project's requirement is a 404 (S2-plan,
        # threat model).
        if values.parent_id is not None and (
            await self.repository.get_in_project(project.id, values.parent_id) is None
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
        await self.repository.lock(requirement)
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
        # Locked and read again: the rights and the old values logged see a concurrent change.
        await self.repository.lock(requirement)
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
        await self.repository.lock(requirement)
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
        before = siblings[position - 1][1] if position > 0 else None
        after = siblings[position][1] if position < len(ids) else None
        rank = None if before is not None and before == after else rank_between(before, after)
        if rank is not None and len(rank) <= RANK_MAX:
            await direct_update(
                self.session,
                Requirement,
                requirement.id,
                {"rank": rank, "parent_requirement_id": parent_id},
                touch_updated_at=reparented,
            )
        else:
            # Fresh ranks in the same order: short again, and ties broken.
            order = [*ids[:position], requirement.id, *ids[position:]]
            fresh: str | None = None
            for id_ in order:
                fresh = rank_between(fresh, None)
                moved = id_ == requirement.id
                await direct_update(
                    self.session,
                    Requirement,
                    id_,
                    {"rank": fresh, "parent_requirement_id": parent_id}
                    if moved
                    else {"rank": fresh},
                    touch_updated_at=moved and reparented,
                )
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
            approved_at=requirement.approved_at,
            version=requirement.version,
            created_at=requirement.created_at,
            updated_at=requirement.updated_at,
            allowed_actions=allowed_actions(ctx, project_target(project, requirement)),
        )


async def _lift_requirements(session: AsyncSession, project: Project, actor_id: uuid.UUID) -> None:
    await RequirementService(session).lift_to_project(project, actor_id)


register_on_restriction_changed(_lift_requirements)
