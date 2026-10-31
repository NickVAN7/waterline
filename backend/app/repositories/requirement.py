"""Requirements (schema-doc "Requirements"; design-doc §6)."""

import uuid
from collections.abc import Collection
from datetime import datetime
from typing import cast

from sqlalchemy import Select, exists, false, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.base_model import INCLUDE_DELETED
from app.enums import RestrictionLevel
from app.models.project import Project
from app.models.requirement import Requirement, RequirementRevision


class RequirementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_number(self, project_id: uuid.UUID, number: int) -> Requirement | None:
        """The project's requirement with this number; a deleted one is hidden (design-doc §9)."""
        return await self.session.scalar(
            select(Requirement).where(
                Requirement.project_id == project_id, Requirement.number == number
            )
        )

    async def get_deleted_by_number(self, project_id: uuid.UUID, number: int) -> Requirement | None:
        """The project's requirement with this number if it's in the trash (design-doc §9)."""
        return await self.session.scalar(
            select(Requirement)
            .where(
                Requirement.project_id == project_id,
                Requirement.number == number,
                Requirement.deleted_at.is_not(None),
            )
            .execution_options(**{INCLUDE_DELETED: True})
        )

    async def get_in_project(
        self, project_id: uuid.UUID, requirement_id: uuid.UUID, *, hold: bool = False
    ) -> Requirement | None:
        """The requirement with this ID if it's in the project; a deleted one is hidden. With
        `hold`, it's held `FOR SHARE` until the transaction ends, so a delete waits (TD-71)."""
        statement = select(Requirement).where(
            Requirement.project_id == project_id, Requirement.id == requirement_id
        )
        return await self.session.scalar(
            statement.with_for_update(read=True) if hold else statement
        )

    async def last_sibling_rank(
        self, project_id: uuid.UUID, parent_id: uuid.UUID | None
    ) -> str | None:
        """The rank of the last of the parent's children (top level with None), if any."""
        return await self.session.scalar(
            select(Requirement.rank)
            .where(
                Requirement.project_id == project_id,
                Requirement.parent_requirement_id.is_(None)
                if parent_id is None
                else Requirement.parent_requirement_id == parent_id,
            )
            .order_by(Requirement.rank.desc())
            .limit(1)
        )

    async def ranked(self, project_id: uuid.UUID, limit: int) -> list[Requirement]:
        """The project's requirements in `(rank, id)` order, at most `limit`."""
        rows = await self.session.scalars(
            select(Requirement)
            .where(Requirement.project_id == project_id)
            .order_by(Requirement.rank, Requirement.id)
            .limit(limit)
        )
        return list(rows)

    async def lock(self, requirement: Requirement) -> None:
        """Re-read the requirement's row, in the trash or not, and hold it until the transaction
        ends; the caller checks `deleted_at`, which a delete or restore may have changed."""
        await self.session.execute(
            select(Requirement)
            .where(Requirement.id == requirement.id)
            .with_for_update()
            .execution_options(populate_existing=True, **{INCLUDE_DELETED: True})
        )

    async def lock_children(
        self, parent_ids: Collection[uuid.UUID], *, deleted_at: datetime | None = None
    ) -> list[Requirement]:
        """The parents' live children (or, with `deleted_at`, those deleted at that moment),
        locked, in `(rank, id)` order. Locking a level before reading the next means a child
        created under a locked row is either seen or waits (its parent is held `FOR SHARE`)."""
        return list(
            await self.session.scalars(
                select(Requirement)
                .where(
                    Requirement.parent_requirement_id.in_(parent_ids),
                    Requirement.deleted_at.is_(None)
                    if deleted_at is None
                    else Requirement.deleted_at == deleted_at,
                )
                .order_by(Requirement.rank, Requirement.id)
                .with_for_update()
                .execution_options(populate_existing=True, **{INCLUDE_DELETED: True})
            )
        )

    async def live_descendants(self, requirement_id: uuid.UUID) -> list[Requirement]:
        """Every live requirement below this one (a recursive query, never Python recursion)."""
        chain = (
            select(Requirement.id)
            .where(Requirement.parent_requirement_id == requirement_id)
            .cte(recursive=True)
        )
        chain = chain.union_all(
            select(Requirement.id).join(chain, Requirement.parent_requirement_id == chain.c.id)
        )
        return list(
            await self.session.scalars(
                select(Requirement).join(chain, Requirement.id == chain.c.id)
            )
        )

    async def deleted_with(
        self, roots: Collection[Requirement]
    ) -> list[tuple[uuid.UUID, Requirement]]:
        """For each requirement in the trash, the descendants deleted in the same action (the
        same `deleted_at`, design-doc §9), as `(root id, descendant)`."""
        chain = (
            select(Requirement.id.label("root"), Requirement.id, Requirement.deleted_at)
            .where(Requirement.id.in_([r.id for r in roots]))
            .cte(recursive=True)
        )
        chain = chain.union_all(
            select(chain.c.root, Requirement.id, Requirement.deleted_at).join(
                chain,
                (Requirement.parent_requirement_id == chain.c.id)
                & (Requirement.deleted_at == chain.c.deleted_at),
            )
        )
        rows = await self.session.execute(
            select(chain.c.root, Requirement)
            .join(Requirement, Requirement.id == chain.c.id)
            .where(chain.c.id != chain.c.root)
            .execution_options(**{INCLUDE_DELETED: True})
        )
        return [(root, requirement) for root, requirement in rows]

    def trash(
        self, project_id: uuid.UUID, reporter_id: uuid.UUID | None, *, empty: bool = False
    ) -> Select[Requirement]:
        """The project's requirements in the trash; with `reporter_id`, only that reporter's
        never-approved ones (design-doc §9: each user sees what they may restore); with `empty`,
        none, still paged as asked."""
        statement = select(Requirement).where(
            Requirement.project_id == project_id, Requirement.deleted_at.is_not(None)
        )
        if empty:
            statement = statement.where(false())
        if reporter_id is not None:
            statement = statement.where(
                Requirement.reporter_id == reporter_id, Requirement.approved_revision_id.is_(None)
            )
        return statement.execution_options(**{INCLUDE_DELETED: True})

    def revisions(self, requirement_id: uuid.UUID) -> Select[RequirementRevision]:
        """The requirement's revisions, with their authors (the feed orders them)."""
        return (
            select(RequirementRevision)
            .where(RequirementRevision.requirement_id == requirement_id)
            .options(joinedload(RequirementRevision.creator))
        )

    async def revision(
        self, requirement_id: uuid.UUID, revision_number: int
    ) -> RequirementRevision | None:
        """The requirement's revision `revision_number`, with its author."""
        return await self.session.scalar(
            self.revisions(requirement_id).where(
                RequirementRevision.revision_number == revision_number
            )
        )

    async def revision_number(self, revision_id: uuid.UUID) -> int:
        """The number of a revision that exists (the current one)."""
        number = await self.session.scalar(
            select(RequirementRevision.revision_number).where(RequirementRevision.id == revision_id)
        )
        return cast(int, number)

    async def lock_stored_at(
        self, project_id: uuid.UUID, levels: Collection[RestrictionLevel]
    ) -> list[tuple[uuid.UUID, RestrictionLevel]]:
        """The project's live requirements stored at one of `levels`, locked, in id order (so
        two raises lock rows in the same order)."""
        rows = await self.session.execute(
            select(Requirement.id, Requirement.restriction_level)
            .where(Requirement.project_id == project_id, Requirement.restriction_level.in_(levels))
            .order_by(Requirement.id)
            .with_for_update()
        )
        return [(id_, RestrictionLevel(level)) for id_, level in rows]

    async def siblings(
        self, project_id: uuid.UUID, parent_id: uuid.UUID | None, *, excluding: uuid.UUID
    ) -> list[tuple[uuid.UUID, str]]:
        """The parent's other children (top level with None), `(id, rank)` in `(rank, id)`
        order."""
        rows = await self.session.execute(
            select(Requirement.id, Requirement.rank)
            .where(
                Requirement.project_id == project_id,
                Requirement.parent_requirement_id.is_(None)
                if parent_id is None
                else Requirement.parent_requirement_id == parent_id,
                Requirement.id != excluding,
            )
            .order_by(Requirement.rank, Requirement.id)
        )
        return [(id_, rank) for id_, rank in rows]

    async def is_in_ancestry(self, requirement_id: uuid.UUID, of: uuid.UUID) -> bool:
        """Whether `requirement_id` is `of` or one of its ancestors (a recursive query, so the
        depth a user can build never reaches Python's recursion limit)."""
        chain = (
            select(Requirement.id, Requirement.parent_requirement_id)
            .where(Requirement.id == of)
            .cte(recursive=True)
        )
        chain = chain.union_all(
            select(Requirement.id, Requirement.parent_requirement_id).join(
                chain, Requirement.id == chain.c.parent_requirement_id
            )
        )
        return bool(await self.session.scalar(select(exists().where(chain.c.id == requirement_id))))

    async def lock_tree(self, project_id: uuid.UUID) -> None:
        """Hold the project's requirement tree until the transaction ends, so moves in it run one
        at a time. `FOR NO KEY UPDATE` on the project row: creates' foreign-key checks
        (`FOR KEY SHARE`) still pass."""
        await self.session.execute(
            select(Project.id).where(Project.id == project_id).with_for_update(key_share=True)
        )
