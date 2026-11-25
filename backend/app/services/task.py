"""Tasks (design-doc §5, §6 "Task"; build plan, S3-C5). Layer 4: calls numbering, phase,
workstream, and project (its restriction rules and the raise's handler)."""

import uuid
from datetime import UTC, datetime
from typing import cast

from pydantic import BaseModel
from sqlalchemy import case
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.change_log import log_change
from app.authz.actions import Action
from app.authz.authorize import allowed_actions, authorize, ensure
from app.authz.context import AuthzContext
from app.authz.target import Target, project_target
from app.core.base_model import check_version
from app.core.errors import ForbiddenError, NotFoundError, ValidationFailedError
from app.core.lists import Filter, FilterType, ListSpec, fetch_ranked
from app.enums import (
    ActivityAction,
    ActivityEntityType,
    ActivityField,
    LinkedTasks,
    NumberPrefix,
    Priority,
    RestrictionCategory,
    TaskStatus,
    TaskType,
)
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.user import User
from app.repositories.base import write_ranks
from app.repositories.project import ProjectRepository
from app.repositories.requirement import RequirementRepository
from app.repositories.task import TaskRepository
from app.repositories.user import UserRepository
from app.rules.branch_name import branch_name
from app.rules.rank import place, rank_between
from app.rules.restriction import Restriction, effective
from app.rules.task_transitions import TaskPeople, allowed_transitions, may_transition
from app.rules.task_types import task_types
from app.schemas.task import (
    TaskCreate,
    TaskItem,
    TaskList,
    TaskMove,
    TaskRead,
    TaskRestrictionUpdate,
    TaskUpdate,
)
from app.services.numbering import NumberingService
from app.services.ordering import anchor_position
from app.services.phase import PhaseService
from app.services.project import (
    check_item_restriction,
    lift_items,
    lift_restored,
    register_on_restriction_changed,
    set_item_restriction,
)
from app.services.user import check_person, required_error
from app.services.workstream import WorkstreamService

type TaskEntity = Task

# The ranked-view cap (DL-159), as the requirement tree's.
LIST_CAP = 2_000

# Priority sorts by importance, not by its stored text.
_PRIORITY_ORDER = case({p.value: index for index, p in enumerate(Priority)}, value=Task.priority)

# The backlog's and board's one list (Q2): filters and display sorts decided Nov 24, 2026 (R2).
TASKS = ListSpec(
    name="TaskItem",
    id_column=Task.id,  # pyright: ignore[reportArgumentType]
    sorts={
        "rank": Task.rank,  # pyright: ignore[reportArgumentType]
        "number": Task.number,  # pyright: ignore[reportArgumentType]
        "priority": _PRIORITY_ORDER,
        "due_date": Task.due_date,  # pyright: ignore[reportArgumentType]
        "updated_at": Task.updated_at,  # pyright: ignore[reportArgumentType]
    },
    default_sort=("rank",),
    filters=(
        Filter("status", Task.status, FilterType.ENUM, enum=TaskStatus),
        Filter("type", Task.type, FilterType.ENUM, enum=TaskType),
        Filter("priority", Task.priority, FilterType.ENUM, enum=Priority),
        Filter("assignee", Task.assignee_id, FilterType.USER),
        Filter("reviewer", Task.reviewer_id, FilterType.USER),
        Filter("workstream", Task.workstream_id, FilterType.REFERENCE),
        Filter("phase", Task.phase_id, FilterType.REFERENCE),
        Filter("requirement", Task.requirement_id, FilterType.REFERENCE),
    ),
    paging="ranked",
)


# Design-doc §10's logged task fields; title, description, type, and time taken aren't.
LOGGED = frozenset(
    {
        "status",
        "assignee_id",
        "reporter_id",
        "reviewer_id",
        "phase_id",
        "workstream_id",
        "priority",
        "severity",
        "start_date",
        "due_date",
        "requirement_id",
        "time_estimate",
    }
)


def _not_member(field: str, what: str) -> ValidationFailedError:
    noun = field.removesuffix("_id")
    return ValidationFailedError.on(("body", field), f"The {noun} {what}.", "not_member")


def _categories(task: Task) -> list[RestrictionCategory]:
    return [RestrictionCategory(c) for c in task.restriction_categories]


def _person(
    users: dict[uuid.UUID, User], user_id: uuid.UUID | None
) -> tuple[str | None, bool | None]:
    """The person's name and whether their account is active, or None with nobody."""
    user = users.get(user_id) if user_id else None
    return (user.name, user.is_active) if user else (None, None)


def _item(task: Task, users: dict[uuid.UUID, User]) -> TaskItem:
    assignee, reviewer = _person(users, task.assignee_id), _person(users, task.reviewer_id)
    return TaskItem(
        id=task.id,
        number=task.number,
        title=task.title,
        type=task.type,
        status=task.status,
        priority=task.priority,
        severity=task.severity,
        assignee_id=task.assignee_id,
        assignee_name=assignee[0],
        assignee_is_active=assignee[1],
        reviewer_id=task.reviewer_id,
        reviewer_name=reviewer[0],
        reviewer_is_active=reviewer[1],
        requirement_id=task.requirement_id,
        phase_id=task.phase_id,
        workstream_id=task.workstream_id,
        due_date=task.due_date,
        restriction_level=task.restriction_level,
        restriction_categories=_categories(task),
    )


class TaskService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = TaskRepository(session)

    async def load(self, key: str, number: int) -> tuple[Task, Target] | None:
        """The task `number` in project `key`, as a target inside its project."""
        project = await ProjectRepository(self.session).get_by_key(key)
        if project is None:
            return None
        task = await self.repository.get_by_number(project.id, number)
        return None if task is None else (task, project_target(project, task))

    async def load_deleted(self, key: str, number: int) -> tuple[Task, Target] | None:
        """The task `number` in project `key` if it's in the trash, as a target inside its
        project."""
        project = await ProjectRepository(self.session).get_by_key(key)
        if project is None:
            return None
        task = await self.repository.get_deleted_by_number(project.id, number)
        return None if task is None else (task, project_target(project, task))

    async def _project(self, task: Task) -> Project:
        # A foreign key, so never None; the loader's project, an identity-map hit.
        return cast(Project, await self.session.get(Project, task.project_id))

    async def _people(self, tasks: list[Task]) -> dict[uuid.UUID, User]:
        return await UserRepository(self.session).get_many(
            {
                user_id
                for task in tasks
                for user_id in (task.assignee_id, task.reviewer_id, task.reporter_id)
                if user_id is not None
            }
        )

    async def create(self, ctx: AuthzContext, project: Project, values: TaskCreate) -> TaskRead:
        """A new task in `project`: the next `TA` number, `todo`, reported by the caller, at the
        bottom of the project's order, logged `created`. 404 for a requirement (live), phase,
        or workstream outside the project; 422 on `title` (`missing`), `type` (`not_offered`),
        `workstream_id` (`archived`), `restriction_level` (`below_project`), and
        `restriction_categories` (`project_only`)."""
        if problems := required_error(values.title, field="title"):
            raise ValidationFailedError(problems)
        if values.type not in task_types(project.type):
            raise ValidationFailedError.on(
                ("body", "type"), "This project doesn't offer that task type.", "not_offered"
            )
        categories = frozenset(values.restriction_categories)
        # Held, so a raise committing meanwhile can't leave the item below the level (TD-72).
        await ProjectRepository(self.session).hold(project)
        # Checked again on the held row: an archive or export-control change that committed
        # while this waited takes the right away.
        ensure(ctx, Action.TASK_CREATE, project_target(project))
        check_item_restriction(
            project,
            values.restriction_level,
            categories,
            noun="task",
            level_field="restriction_level",
            categories_field="restriction_categories",
        )
        # Each held until commit, so a delete (or an archive) can't commit under the new task.
        if values.requirement_id is not None and (
            await RequirementRepository(self.session).get_in_project(
                project.id, values.requirement_id, hold=True
            )
            is None
        ):
            raise NotFoundError
        if values.phase_id is not None:
            await PhaseService(self.session).assignable(project.id, values.phase_id)
        if values.workstream_id is not None:
            await WorkstreamService(self.session).assignable(project.id, values.workstream_id)
        task = Task(
            project_id=project.id,
            number=await NumberingService(self.session).allocate_number(project, NumberPrefix.TASK),
            requirement_id=values.requirement_id,
            type=values.type,
            title=values.title.strip(),
            description_md=values.description_md,
            priority=values.priority,
            severity=values.severity,
            reporter_id=ctx.user_id,
            phase_id=values.phase_id,
            workstream_id=values.workstream_id,
            # Two creates at once may tie: `(rank, id)` orders them, a later move rewrites.
            rank=rank_between(await self.repository.last_rank(project.id), None),
            restriction_level=values.restriction_level,
            restriction_categories=sorted(categories),
        )
        self.session.add(task)
        await self.session.flush()
        log_change(
            self.session,
            project_id=project.id,
            entity_type=ActivityEntityType.TASK,
            entity_id=task.id,
            action=ActivityAction.CREATED,
            changed_by=ctx.user_id,
        )
        return await self.read(ctx, task)

    async def _lock_live(self, task: Task) -> None:
        """Lock the row and read it again; one deleted meanwhile is a 404."""
        await self.repository.lock(task)
        if task.deleted_at is not None:
            raise NotFoundError

    async def update(self, ctx: AuthzContext, task: Task, values: TaskUpdate) -> TaskRead:
        """Change the fields sent (design-doc §5, §6). 409 on a stale `version`; 403 for a
        status move the table denies (judged on the people stored before), or a reporter change
        without `task.reassign_reporter`; 404 for a requirement, phase, or workstream outside
        the project; 422 on `title` (`missing`), `type` (`not_offered`), `assignee_id`,
        `reviewer_id`, `reporter_id` (`not_member`, `account_inactive`), `time_estimate` and
        `time_taken` (0 to 9,999,999.99, DL-411), and `workstream_id` (`archived`). Logs
        design-doc §10's fields."""
        project = await self._project(task)
        # Held, then read: the target sees what a restriction or archive committed meanwhile,
        # project then task, as a requirement's edit (TD-74).
        await ProjectRepository(self.session).hold(project)
        target = project_target(project, task)
        ensure(ctx, Action.TASK_UPDATE, target)
        # Held until commit, so a delete can't commit under the new link; before the task's row,
        # as a requirement's delete takes them (the requirement, then its tasks), so the two
        # can't deadlock.
        requirement = (
            None
            if values.requirement_id is None
            else await RequirementRepository(self.session).get_in_project(
                project.id, values.requirement_id, hold=True
            )
        )
        # Locked and read again, so the version check, the transition, and the old values logged
        # see what a concurrent edit committed.
        await self._lock_live(task)
        check_version(task, values.version)
        sent = values.model_fields_set
        changes: dict[str, object] = {}

        def changed(field: str) -> bool:
            return field in sent and getattr(values, field) != getattr(task, field)

        if values.title is not None:
            if problems := required_error(values.title, field="title"):
                raise ValidationFailedError(problems)
            changes["title"] = values.title.strip()
        if values.description_md is not None:
            changes["description_md"] = values.description_md
        if values.type is not None and values.type != task.type:
            if values.type not in task_types(project.type):
                raise ValidationFailedError.on(
                    ("body", "type"), "This project doesn't offer that task type.", "not_offered"
                )
            changes["type"] = values.type
        if values.status is not None and values.status != task.status:
            if not may_transition(
                task.status,
                values.status,
                actor_id=ctx.user_id,
                people=TaskPeople(task.assignee_id, task.reviewer_id),
                is_project_admin=authorize(ctx, Action.TASK_REASSIGN_REPORTER, target),
            ):
                raise ForbiddenError
            changes["status"] = values.status
        if values.priority is not None:
            changes["priority"] = values.priority
        # Nullable: null clears them.
        for field in ("severity", "start_date", "due_date", "time_estimate", "time_taken"):
            if field in sent:
                changes[field] = getattr(values, field)
        for field in ("assignee_id", "reviewer_id"):
            new = getattr(values, field)
            if changed(field):
                if new is not None:
                    await check_person(
                        self.session,
                        target,
                        new,
                        Action.TASK_UPDATE,
                        field,
                        _not_member(field, "must be able to update tasks in this project"),
                    )
                changes[field] = new
        # Null on a field that can't be empty is no change, as a requirement's (DL-411).
        if values.reporter_id is not None and values.reporter_id != task.reporter_id:
            ensure(ctx, Action.TASK_REASSIGN_REPORTER, target)
            await check_person(
                self.session,
                target,
                values.reporter_id,
                Action.TASK_CREATE,
                "reporter_id",
                _not_member("reporter_id", "must be able to create tasks in this project"),
            )
            changes["reporter_id"] = values.reporter_id
        if changed("requirement_id"):
            if values.requirement_id is not None and requirement is None:
                raise NotFoundError
            changes["requirement_id"] = values.requirement_id
        if changed("phase_id"):
            if values.phase_id is not None:
                await PhaseService(self.session).assignable(project.id, values.phase_id)
            changes["phase_id"] = values.phase_id
        if changed("workstream_id"):
            if values.workstream_id is not None:
                await WorkstreamService(self.session).assignable(project.id, values.workstream_id)
            changes["workstream_id"] = values.workstream_id
        logged: list[tuple[ActivityField, object, object]] = []
        for field, new in changes.items():
            old = getattr(task, field)
            if new == old:
                continue
            setattr(task, field, new)
            if field in LOGGED:
                logged.append((ActivityField(field), old, new))
        await self.session.flush()
        for field, old, new in logged:
            log_change(
                self.session,
                project_id=project.id,
                entity_type=ActivityEntityType.TASK,
                entity_id=task.id,
                action=ActivityAction.UPDATED,
                changed_by=ctx.user_id,
                field=field,
                old=old,
                new=new,
            )
        return await self.read(ctx, task)

    async def move(self, ctx: AuthzContext, task: Task, values: TaskMove) -> TaskRead:
        """Put the task just after `after_id` or just before `before_id` in the project's one
        order, or at the bottom, and with `status` move it to that column too (design-doc §6).
        The transition is checked first (403, nothing saved); 422 on `after_id` or `before_id`
        (`not_found`) and on both (`conflict`). A drop with no rank between its neighbors (a
        tie, or past 255 characters) rewrites the project's whole task order in one statement
        (DL-345). The rank write bumps no `version`; a status change is an edit (logged)."""
        project = await self._project(task)
        # Moves in a project run one at a time, under the tree's lock (DL-345), then the row.
        await ProjectRepository(self.session).lock_order(project)
        await self._lock_live(task)
        target = project_target(project, task)
        # Checked again under the lock, which reads the project again (TD-80).
        ensure(ctx, Action.TASK_UPDATE, target)
        old_status = task.status
        # Staying in the same column is no transition.
        new_status = values.status if values.status is not old_status else None
        if new_status is not None and not may_transition(
            old_status,
            new_status,
            actor_id=ctx.user_id,
            people=TaskPeople(task.assignee_id, task.reviewer_id),
            is_project_admin=authorize(ctx, Action.TASK_REASSIGN_REPORTER, target),
        ):
            raise ForbiddenError
        others = await self.repository.others(project.id, excluding=task.id)
        position = anchor_position([id_ for id_, _ in others], values, noun="task")
        await write_ranks(self.session, Task, place(others, [task.id], position))
        if new_status is not None:
            task.status = new_status
            await self.session.flush()
            log_change(
                self.session,
                project_id=project.id,
                entity_type=ActivityEntityType.TASK,
                entity_id=task.id,
                action=ActivityAction.UPDATED,
                changed_by=ctx.user_id,
                field=ActivityField.STATUS,
                old=old_status,
                new=new_status,
            )
        return await self.read(ctx, task)

    def _log(self, task: Task, actor_id: uuid.UUID, action: ActivityAction) -> None:
        log_change(
            self.session,
            project_id=task.project_id,
            entity_type=ActivityEntityType.TASK,
            entity_id=task.id,
            action=action,
            changed_by=actor_id,
        )

    async def delete(self, ctx: AuthzContext, task: Task) -> None:
        """Move the task to the trash (design-doc §9): its subtasks stay in place, hidden with
        it. Logged."""
        project = await self._project(task)
        # Held, then the row, as an edit: the rights checked see an archive or a reporter change
        # that committed while this waited.
        await ProjectRepository(self.session).hold(project)
        await self._lock_live(task)
        ensure(ctx, Action.TASK_DELETE, project_target(project, task))
        task.deleted_at = datetime.now(UTC)
        await self.session.flush()
        self._log(task, ctx.user_id, ActivityAction.DELETED)

    async def restore(self, ctx: AuthzContext, task: Task) -> TaskRead:
        """Bring the task back from the trash with its subtasks, in its old place in the order;
        one stored below the project's level is raised to it (DL-209). 404 for one restored
        meanwhile. Logged."""
        project = await self._project(task)
        await ProjectRepository(self.session).hold(project)
        await self.repository.lock(task)
        if task.deleted_at is None:
            raise NotFoundError
        ensure(ctx, Action.TASK_RESTORE, project_target(project, task))
        task.deleted_at = None
        await self.session.flush()
        self._log(task, ctx.user_id, ActivityAction.RESTORED)
        await lift_restored(self.session, Task, ActivityEntityType.TASK, project, task, ctx.user_id)
        return await self.read(ctx, task)

    async def leave_requirements(
        self,
        ctx: AuthzContext,
        project: Project,
        requirement_ids: list[uuid.UUID],
        choice: LinkedTasks,
        deleted_at: datetime,
    ) -> list[tuple[uuid.UUID, uuid.UUID]]:
        """The live tasks linked to requirements being deleted (design-doc §9): detached, each
        logged `unlinked`, or deleted with them at their `deleted_at`, each logged, 403 and
        nothing changed if the caller may not delete each one directly. Returns each detached
        `(task id, requirement id)`, for the requirement's side of the log. The caller holds the
        requirements' rows, which come before their tasks'."""
        tasks = await self.repository.linked(requirement_ids, lock=True)
        if choice is LinkedTasks.DELETE:
            if not all(
                authorize(ctx, Action.TASK_DELETE, project_target(project, t)) for t in tasks
            ):
                raise ForbiddenError
            for task in tasks:
                task.deleted_at = deleted_at
            await self.session.flush()
            for task in tasks:
                self._log(task, ctx.user_id, ActivityAction.DELETED)
            return []
        detached = [(task.id, cast(uuid.UUID, task.requirement_id)) for task in tasks]
        for task in tasks:
            task.requirement_id = None
        await self.session.flush()
        for task_id, requirement_id in detached:
            log_change(
                self.session,
                project_id=project.id,
                entity_type=ActivityEntityType.TASK,
                entity_id=task_id,
                action=ActivityAction.UNLINKED,
                changed_by=ctx.user_id,
                old=requirement_id,
            )
        return detached

    async def set_restriction(
        self, ctx: AuthzContext, task: Task, values: TaskRestrictionUpdate
    ) -> TaskRead:
        """Replace the level and categories, without a version bump (DL-162, DL-168): a raise
        needs `task.raise_restriction`, a lower `task.lower_restriction` (403). 422 on `level`
        (`below_project`) and `categories` (`project_only`). Logs each field that changed."""
        project = await self._project(task)
        # The project first, as a raise does, so the level checked stays true until commit
        # (TD-72); then the row, so the rights and the old values logged see a concurrent change.
        await ProjectRepository(self.session).hold(project)
        await self._lock_live(task)
        await set_item_restriction(
            self.session,
            ctx,
            project,
            task,
            Restriction(values.level, frozenset(values.categories)),
            entity_type=ActivityEntityType.TASK,
            raise_action=Action.TASK_RAISE_RESTRICTION,
            lower_action=Action.TASK_LOWER_RESTRICTION,
            noun="task",
        )
        return await self.read(ctx, task)

    async def read(self, ctx: AuthzContext, task: Task) -> TaskRead:
        project = await self._project(task)
        target = project_target(project, task)
        users = await self._people([task])
        reporter = _person(users, task.reporter_id)
        done, total = await self.repository.subtask_counts(task.id)
        applies = effective(
            Restriction(task.restriction_level, frozenset(_categories(task))),
            Restriction(
                project.restriction_level,
                frozenset(RestrictionCategory(c) for c in project.restriction_categories),
            ),
        )
        transitions = (
            allowed_transitions(
                task.status,
                actor_id=ctx.user_id,
                people=TaskPeople(task.assignee_id, task.reviewer_id),
                # A project admin as the admin content actions count one (owner, Nov 24, 2026).
                is_project_admin=authorize(ctx, Action.TASK_REASSIGN_REPORTER, target),
            )
            if authorize(ctx, Action.TASK_UPDATE, target)
            else frozenset[TaskStatus]()
        )
        return TaskRead(
            **_item(task, users).model_dump(),
            description_md=task.description_md,
            reporter_id=task.reporter_id,
            # A foreign key, so the reporter is always there.
            reporter_name=cast(str, reporter[0]),
            reporter_is_active=cast(bool, reporter[1]),
            start_date=task.start_date,
            time_estimate=task.time_estimate,
            time_taken=task.time_taken,
            effective_restriction_level=applies.level,
            effective_restriction_categories=sorted(applies.categories),
            subtasks_done=done,
            subtasks_total=total,
            branch_name=branch_name(f"{project.key}-{NumberPrefix.TASK}-{task.number}", task.title),
            version=task.version,
            created_at=task.created_at,
            updated_at=task.updated_at,
            allowed_actions=allowed_actions(ctx, target),
            allowed_transitions=[s for s in TaskStatus if s in transitions],
        )

    async def list(self, ctx: AuthzContext, project: Project, query: BaseModel) -> TaskList:
        """The project's tasks matching the declared filters, in the requested order (rank by
        default), up to the cap (DL-159, DL-351)."""
        rows, truncated = await fetch_ranked(
            self.session,
            self.repository.in_project(project.id),
            TASKS,
            query,
            LIST_CAP,
            current_user_id=ctx.user_id,
        )
        users = await self._people(rows)
        return TaskList(items=[_item(row, users) for row in rows], truncated=truncated)

    async def for_requirement(self, ctx: AuthzContext, requirement: Requirement) -> TaskList:
        """The requirement's live tasks, as the backlog's rows and in its order, up to the cap
        (its page and the approver's review, DL-196); none for a caller who may not view
        tasks."""
        # A foreign key, so never None; the loader's project, an identity-map hit.
        project = cast(Project, await self.session.get(Project, requirement.project_id))
        if not authorize(ctx, Action.TASK_VIEW, project_target(project)):
            return TaskList(items=[], truncated=False)
        rows = await self.repository.for_requirement(requirement.id, LIST_CAP + 1)
        users = await self._people(rows[:LIST_CAP])
        return TaskList(
            items=[_item(row, users) for row in rows[:LIST_CAP]], truncated=len(rows) > LIST_CAP
        )


async def _lift_tasks(session: AsyncSession, project: Project, actor_id: uuid.UUID) -> None:
    await lift_items(session, Task, ActivityEntityType.TASK, project, actor_id)


register_on_restriction_changed(_lift_tasks)
