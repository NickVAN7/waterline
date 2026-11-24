"""Phases (design-doc §6, "Phase"; build plan, S3-C3). Layer 3: calls no other service."""

import uuid
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.admin_event import apply_changes
from app.audit.change_log import log_change
from app.authz.authorize import allowed_actions
from app.authz.context import AuthzContext
from app.authz.target import Target, project_target
from app.core.errors import NotFoundError, ValidationFailedError
from app.enums import ActivityAction, ActivityEntityType, ActivityField
from app.models.phase import Phase
from app.models.project import Project
from app.repositories.base import write_ranks
from app.repositories.phase import PhaseRepository
from app.repositories.project import ProjectRepository
from app.rules.rank import place, rank_between
from app.schemas.move import ItemMove
from app.schemas.phase import PhaseCreate, PhaseItem, PhaseList, PhaseRead, PhaseUpdate
from app.services.ordering import anchor_position
from app.services.user import required_error

type PhaseEntity = Phase

# The ranked-view cap (DL-159), as the requirement tree's.
LIST_CAP = 2_000
# The fields design-doc §10 logs for a phase; name and description aren't.
LOGGED = (
    ActivityField.STATUS,
    ActivityField.START_DATE,
    ActivityField.END_DATE,
    ActivityField.BASELINE_START,
    ActivityField.BASELINE_END,
)


def _item(phase: Phase) -> PhaseItem:
    return PhaseItem(
        id=phase.id,
        name=phase.name,
        description=phase.description,
        start_date=phase.start_date,
        end_date=phase.end_date,
        baseline_start=phase.baseline_start,
        baseline_end=phase.baseline_end,
        status=phase.status,
    )


class PhaseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = PhaseRepository(session)

    async def load(self, key: str, phase_id: uuid.UUID) -> tuple[Phase, Target] | None:
        """The phase in project `key`, as a target inside its project; another project's phase
        is None (a 404)."""
        project = await ProjectRepository(self.session).get_by_key(key)
        if project is None:
            return None
        phase = await self.repository.get_in_project(project.id, phase_id)
        return None if phase is None else (phase, project_target(project, phase))

    async def assignable(self, project_id: uuid.UUID, phase_id: uuid.UUID) -> Phase:
        """The phase an item in the project is newly given, held until commit so a delete
        waits: 404 outside the project."""
        phase = await self.repository.get_in_project(project_id, phase_id, hold=True)
        if phase is None:
            raise NotFoundError
        return phase

    async def _project(self, phase: Phase) -> Project:
        # A foreign key, so never None; the loader's project, an identity-map hit.
        return cast(Project, await self.session.get(Project, phase.project_id))

    def _log(
        self,
        phase: Phase,
        actor_id: uuid.UUID,
        action: ActivityAction,
        field: ActivityField | None = None,
        old: object = None,
        new: object = None,
    ) -> None:
        log_change(
            self.session,
            project_id=phase.project_id,
            entity_type=ActivityEntityType.PHASE,
            entity_id=phase.id,
            action=action,
            changed_by=actor_id,
            field=field,
            old=old,
            new=new,
        )

    async def list(self, project: Project) -> PhaseList:
        rows = await self.repository.ranked(project.id, LIST_CAP + 1)
        return PhaseList(
            items=[_item(row) for row in rows[:LIST_CAP]], truncated=len(rows) > LIST_CAP
        )

    async def read(self, ctx: AuthzContext, phase: Phase) -> PhaseRead:
        project = await self._project(phase)
        return PhaseRead(
            **_item(phase).model_dump(),
            created_at=phase.created_at,
            updated_at=phase.updated_at,
            allowed_actions=allowed_actions(ctx, project_target(project, phase)),
        )

    async def create(self, ctx: AuthzContext, project: Project, values: PhaseCreate) -> PhaseRead:
        """A new phase at the bottom of the project's phases, logged `created`. 422 on `name`
        (`missing`, `taken`) and on `end_date` before `start_date` (`ck_phase_dates`)."""
        if errors := required_error(values.name, field="name"):
            raise ValidationFailedError(errors)
        phase = Phase(
            project_id=project.id,
            **values.model_dump(exclude={"name"}),
            name=values.name.strip(),
            # Two creates at once may tie: `(rank, id)` orders them, a later move rewrites.
            rank=rank_between(await self.repository.last_rank(project.id), None),
        )
        self.session.add(phase)
        await self.session.flush()
        self._log(phase, ctx.user_id, ActivityAction.CREATED)
        return await self.read(ctx, phase)

    async def update(self, ctx: AuthzContext, phase: Phase, values: PhaseUpdate) -> PhaseRead:
        """Change the fields sent; status, dates, and baselines logged (design-doc §10). 422 on
        `name` (`missing`, `taken`) and on `end_date` before `start_date`."""
        sent = values.model_fields_set
        changes: dict[str, object] = {}
        if values.name is not None:
            if errors := required_error(values.name, field="name"):
                raise ValidationFailedError(errors)
            changes["name"] = values.name.strip()
        if values.status is not None:
            changes["status"] = values.status
        # Nullable: null clears them.
        for field in ("description", "start_date", "end_date", "baseline_start", "baseline_end"):
            if field in sent:
                changes[field] = getattr(values, field)
        if not await self.repository.lock(phase):
            raise NotFoundError
        changed = await apply_changes(self.session, phase, changes)
        for field in LOGGED:
            if field.value in changed:
                old, new = changed[field.value]
                self._log(phase, ctx.user_id, ActivityAction.UPDATED, field, old, new)
        return await self.read(ctx, phase)

    async def delete(self, ctx: AuthzContext, phase: Phase) -> None:
        """Delete the phase for good, logged `deleted`: only while no task names it, one in the
        trash too (422 `in_use`; design-doc §9)."""
        if not await self.repository.lock(phase):
            raise NotFoundError
        if await self.repository.is_referenced(phase.id):
            raise ValidationFailedError.on(
                ("path", "phase_id"),
                "Tasks are in this phase, some maybe in the trash. Move them out of it first.",
                "in_use",
            )
        self._log(phase, ctx.user_id, ActivityAction.DELETED)
        await self.session.delete(phase)
        await self.session.flush()

    async def move(self, ctx: AuthzContext, phase: Phase, values: ItemMove) -> PhaseRead:
        """Put the phase just after `after_id` or just before `before_id`, or at the bottom.
        422 on `after_id` or `before_id` (`not_found`: not another phase of the project) and on
        `before_id` with both (`conflict`). A drop with no rank between its neighbors (a tie, or
        past 255 characters) rewrites the project's phase order. Not logged (design-doc §10)."""
        project = await self._project(phase)
        # Moves in a project run one at a time, so two can't compute ranks from the same order.
        await ProjectRepository(self.session).lock_order(project)
        if not await self.repository.lock(phase):
            raise NotFoundError
        others = await self.repository.others(project.id, excluding=phase.id)
        position = anchor_position([id_ for id_, _ in others], values, noun="phase")
        await write_ranks(self.session, Phase, place(others, [phase.id], position))
        return await self.read(ctx, phase)
