"""Workstreams (design-doc §6, "Workstream"; build plan, S3-C4). Layer 3: calls the roster's lead
rule (layer 1b) and no other service. Not logged in the activity feed (design-doc §10)."""

import uuid
from datetime import UTC, datetime
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.admin_event import apply_changes
from app.authz.authorize import allowed_actions
from app.authz.context import AuthzContext
from app.authz.target import Target, project_target
from app.core.errors import NotFoundError, ValidationFailedError
from app.models.project import Project
from app.models.user import User
from app.models.workstream import Workstream
from app.repositories.base import write_ranks
from app.repositories.project import ProjectRepository
from app.repositories.user import UserRepository
from app.repositories.workstream import WorkstreamRepository
from app.rules.rank import place, rank_between
from app.schemas.move import ItemMove
from app.schemas.workstream import (
    WorkstreamCreate,
    WorkstreamItem,
    WorkstreamList,
    WorkstreamRead,
    WorkstreamUpdate,
)
from app.services.ordering import anchor_position
from app.services.roster import check_lead
from app.services.user import required_error

type WorkstreamEntity = Workstream

# The ranked-view cap (DL-159), as the requirement tree's.
LIST_CAP = 2_000


def _item(workstream: Workstream, leads: dict[uuid.UUID, User]) -> WorkstreamItem:
    lead = leads.get(workstream.lead_id) if workstream.lead_id else None
    return WorkstreamItem(
        id=workstream.id,
        name=workstream.name,
        description=workstream.description,
        lead_id=workstream.lead_id,
        lead_name=lead.name if lead else None,
        lead_is_active=lead.is_active if lead else None,
        archived=workstream.archived_at is not None,
    )


class WorkstreamService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = WorkstreamRepository(session)

    async def load(self, key: str, workstream_id: uuid.UUID) -> tuple[Workstream, Target] | None:
        """The workstream in project `key`, as a target inside its project; another project's
        is None (a 404)."""
        project = await ProjectRepository(self.session).get_by_key(key)
        if project is None:
            return None
        workstream = await self.repository.get_in_project(project.id, workstream_id)
        return None if workstream is None else (workstream, project_target(project, workstream))

    async def assignable(self, project_id: uuid.UUID, workstream_id: uuid.UUID) -> Workstream:
        """The workstream an item in the project is newly given, held until commit so an archive
        waits: 404 outside the project, 422 `archived` on `workstream_id` when archived (it's
        hidden from pickers; an item keeps one it already has)."""
        workstream = await self.repository.get_in_project(project_id, workstream_id, hold=True)
        if workstream is None:
            raise NotFoundError
        if workstream.archived_at is not None:
            raise ValidationFailedError.on(
                ("body", "workstream_id"), "This workstream is archived.", "archived"
            )
        return workstream

    async def clear_lead(self, project_id: uuid.UUID, user_id: uuid.UUID) -> list[uuid.UUID]:
        """A removed member leads none of the project's workstreams any more: the IDs cleared
        (the project lead's rule)."""
        return await self.repository.clear_lead(project_id, user_id)

    async def _project(self, workstream: Workstream) -> Project:
        # A foreign key, so never None; the loader's project, an identity-map hit.
        return cast(Project, await self.session.get(Project, workstream.project_id))

    async def _leads(self, rows: list[Workstream]) -> dict[uuid.UUID, User]:
        return await UserRepository(self.session).get_many(
            {row.lead_id for row in rows if row.lead_id is not None}
        )

    async def list(self, project: Project, *, include_archived: bool) -> WorkstreamList:
        rows = await self.repository.ranked(
            project.id, LIST_CAP + 1, include_archived=include_archived
        )
        leads = await self._leads(rows)
        return WorkstreamList(
            items=[_item(row, leads) for row in rows[:LIST_CAP]], truncated=len(rows) > LIST_CAP
        )

    async def read(self, ctx: AuthzContext, workstream: Workstream) -> WorkstreamRead:
        project = await self._project(workstream)
        return WorkstreamRead(
            **_item(workstream, await self._leads([workstream])).model_dump(),
            created_at=workstream.created_at,
            updated_at=workstream.updated_at,
            allowed_actions=allowed_actions(ctx, project_target(project, workstream)),
        )

    async def create(
        self, ctx: AuthzContext, project: Project, values: WorkstreamCreate
    ) -> WorkstreamRead:
        """A new workstream at the bottom of the project's. 422 on `name` (`missing`, `taken`)
        and on `lead_id` (`not_member`, `account_inactive`)."""
        if errors := required_error(values.name, field="name"):
            raise ValidationFailedError(errors)
        if values.lead_id is not None:
            # Held first: a member removal locks the project, so it can't commit between the
            # check and the insert and leave a non-member leading (it clears the leads it removes).
            await ProjectRepository(self.session).hold(project)
            await check_lead(self.session, project.id, values.lead_id)
        workstream = Workstream(
            project_id=project.id,
            name=values.name.strip(),
            description=values.description,
            lead_id=values.lead_id,
            # Two creates at once may tie: `(rank, id)` orders them, a later move rewrites.
            rank=rank_between(await self.repository.last_rank(project.id), None),
        )
        self.session.add(workstream)
        await self.session.flush()
        return await self.read(ctx, workstream)

    async def update(
        self, ctx: AuthzContext, workstream: Workstream, values: WorkstreamUpdate
    ) -> WorkstreamRead:
        """Change the fields sent; null clears the description or the lead. 422 on `name`
        (`missing`, `taken`) and on a newly named `lead_id` (`not_member`, `account_inactive`)."""
        sent = values.model_fields_set
        changes: dict[str, object] = {}
        if values.name is not None:
            if errors := required_error(values.name, field="name"):
                raise ValidationFailedError(errors)
            changes["name"] = values.name.strip()
        if "description" in sent:
            changes["description"] = values.description
        if "lead_id" in sent:
            project = await self._project(workstream)
            # The project first (projects are locked first), then the row read again under its
            # lock, so "unchanged" is judged on what's committed (backend/CLAUDE.md).
            await ProjectRepository(self.session).hold(project)
            await self.session.refresh(workstream, with_for_update={"key_share": True})
            if values.lead_id != workstream.lead_id:
                if values.lead_id is not None:
                    await check_lead(self.session, project.id, values.lead_id)
                changes["lead_id"] = values.lead_id
        await apply_changes(self.session, workstream, changes)
        return await self.read(ctx, workstream)

    async def archive(self, ctx: AuthzContext, workstream: Workstream) -> WorkstreamRead:
        """Hidden from pickers, still shown on its items; archiving an archived one changes
        nothing."""
        # Locked and read again: an archive that committed meanwhile keeps its time.
        await self.session.refresh(workstream, with_for_update={"key_share": True})
        if workstream.archived_at is None:
            workstream.archived_at = datetime.now(UTC)
            await self.session.flush()
        return await self.read(ctx, workstream)

    async def unarchive(self, ctx: AuthzContext, workstream: Workstream) -> WorkstreamRead:
        await apply_changes(self.session, workstream, {"archived_at": None})
        return await self.read(ctx, workstream)

    async def move(
        self, ctx: AuthzContext, workstream: Workstream, values: ItemMove
    ) -> WorkstreamRead:
        """Put the workstream just after `after_id` or just before `before_id`, or at the bottom,
        among all of the project's, archived included. 422 on `after_id` or `before_id`
        (`not_found`: not another of the project's) and on `before_id` with both
        (`conflict`)."""
        project = await self._project(workstream)
        # Moves in a project run one at a time, so two can't compute ranks from the same order.
        await ProjectRepository(self.session).lock_order(project)
        others = await self.repository.others(project.id, excluding=workstream.id)
        position = anchor_position([id_ for id_, _ in others], values, noun="workstream")
        await write_ranks(self.session, Workstream, place(others, [workstream.id], position))
        return await self.read(ctx, workstream)
