"""Item history and the project activity feed, read from `activity_log` (design-doc §6.1
"History", §10; DL-147, DL-160)."""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import cast

from pydantic import BaseModel
from sqlalchemy import Date
from sqlalchemy import cast as cast_
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.context import AuthzContext
from app.core.lists import Feed, FeedResult, Filter, FilterType, ListSpec
from app.enums import (
    ActivityAction,
    ActivityEntityType,
    ActivityField,
    ApprovalEntityType,
    NumberPrefix,
)
from app.models.audit import ActivityLog
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.task import Task
from app.repositories.activity import ActivityRepository
from app.repositories.approval import ApprovalRepository
from app.repositories.phase import PhaseRepository
from app.repositories.requirement import RequirementRepository
from app.repositories.task import TaskRepository
from app.repositories.user import UserRepository
from app.repositories.workstream import WorkstreamRepository
from app.schemas.activity import ActivityEntry

ITEM_HISTORY = ListSpec(
    name="ActivityEntry",
    id_column=ActivityLog.id,  # pyright: ignore[reportArgumentType]
    paging="cursor",
)

# The project activity feed's declared filters (build plan, S3-C12). `changed_at` compares the
# UTC day of the change, as the other date filters compare a date.
PROJECT_FEED = ListSpec(
    name="ProjectActivity",
    id_column=ActivityLog.id,  # pyright: ignore[reportArgumentType]
    filters=(
        Filter("entity_type", ActivityLog.entity_type, FilterType.ENUM, enum=ActivityEntityType),
        Filter("actor", ActivityLog.changed_by, FilterType.USER),
        Filter("field", ActivityLog.field_changed, FilterType.ENUM, enum=ActivityField),
        Filter("changed_at", cast_(ActivityLog.changed_at, Date), FilterType.DATE),
    ),
    paging="cursor",
)

# Fields whose values are user IDs, so the entry names the users (design-doc §6.1 "History").
USER_FIELDS = frozenset(
    {
        ActivityField.ASSIGNEE_ID,
        ActivityField.REPORTER_ID,
        ActivityField.REVIEWER_ID,
        ActivityField.LEAD_ID,
        ActivityField.APPROVER_ID,
    }
)


@dataclass(frozen=True)
class _Named:
    """What an entry shows for an ID: a name, and whether it's still active (null: a revision)."""

    name: str
    is_active: bool | None


def _ids(entries: list[ActivityLog], field: ActivityField) -> set[uuid.UUID]:
    return {
        uuid.UUID(value)
        for entry in entries
        if entry.field_changed is field
        for value in (entry.old_value, entry.new_value)
        if value
    }


class ActivityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def requirement_history(
        self, requirement: Requirement, query: BaseModel
    ) -> Feed[ActivityEntry]:
        """The requirement's entries and its approval requests' (DL-388), newest first,
        cursor-paged, with every name resolved now, so a former member's name stays (DL-160)."""
        requests = ApprovalRepository(self.session).ids_for_entity(
            ApprovalEntityType.REQUIREMENT, requirement.id
        )
        page = await ActivityRepository(self.session).history(
            ActivityEntityType.REQUIREMENT, requirement.id, ITEM_HISTORY, query, requests=requests
        )
        return await self._feed(requirement.project_id, page)

    async def task_history(self, task: Task, query: BaseModel) -> Feed[ActivityEntry]:
        """The task's entries, newest first, named as a requirement's History."""
        page = await ActivityRepository(self.session).history(
            ActivityEntityType.TASK, task.id, ITEM_HISTORY, query
        )
        return await self._feed(task.project_id, page)

    async def project_feed(
        self, ctx: AuthzContext, project: Project, query: BaseModel
    ) -> Feed[ActivityEntry]:
        """Every entry of the project, newest first, filtered, each naming its item (the
        project activity feed; design-doc §10, DL-275, DL-276)."""
        page = await ActivityRepository(self.session).project_feed(
            project.id, PROJECT_FEED, query, ctx.user_id
        )
        return await self._feed(project.id, page)

    async def _feed(
        self, project_id: uuid.UUID, page: FeedResult[ActivityLog]
    ) -> Feed[ActivityEntry]:
        """The page's entries with every name resolved now, within this project only."""
        entries = page.items
        # The loader's project, an identity-map hit.
        project = cast(Project, await self.session.get(Project, project_id))
        user_ids = {entry.changed_by for entry in entries if entry.changed_by is not None}
        for field in USER_FIELDS:
            user_ids |= _ids(entries, field)
        users = await UserRepository(self.session).get_many(user_ids)
        named = {id_: _Named(user.name, user.is_active) for id_, user in users.items()}
        # Each entry's item, and the item a value or a link names (DL-416, DL-276): a
        # requirement or task by its display ID, deleted or not; a phase or workstream by its
        # name; an approval request by its requirement. All read within this project only.
        of = _entity_ids(entries)
        items = {entry.entity_id for entry in entries} | _item_values(entries)
        requests = await ApprovalRepository(self.session).entity_ids(
            project_id, of[ActivityEntityType.APPROVAL_REQUEST]
        )
        repository = RequirementRepository(self.session)
        requirements = await repository.get_many_in_project(
            project_id, items | set(requests.values())
        )
        prefix = f"{project.key}-{NumberPrefix.REQUIREMENT}"
        for id_, requirement in requirements.items():
            named[id_] = _Named(f"{prefix}-{requirement.number}", requirement.deleted_at is None)
        tasks = await TaskRepository(self.session).get_many_in_project(project_id, items)
        prefix = f"{project.key}-{NumberPrefix.TASK}"
        named |= {
            id_: _Named(f"{prefix}-{task.number}", task.deleted_at is None)
            for id_, task in tasks.items()
        }
        phases = await PhaseRepository(self.session).names(project_id, items)
        named |= {id_: _Named(name, True) for id_, name in phases.items()}
        # An archived workstream is still the one named; only a deleted item reads inactive.
        workstreams = await WorkstreamRepository(self.session).names(project_id, items)
        named |= {id_: _Named(name, True) for id_, name in workstreams.items()}
        named[project.id] = _Named(project.name, True)
        # Same project, deleted requirements included, so always named.
        named |= {request: named[requirement] for request, requirement in requests.items()}
        revisions = await repository.revision_numbers(
            of[ActivityEntityType.REQUIREMENT], _ids(entries, ActivityField.APPROVED_REVISION_ID)
        )
        named |= {id_: _Named(str(number), None) for id_, number in revisions.items()}
        return Feed[ActivityEntry](
            items=[_entry(entry, named) for entry in entries], next_cursor=page.next_cursor
        )


def _item_values(entries: list[ActivityLog]) -> set[uuid.UUID]:
    """The item IDs the entries' values hold: an item field's, and a link's other side."""
    return {
        uuid.UUID(value)
        for entry in entries
        if entry.field_changed in ITEM_FIELDS or entry.action in LINK_ACTIONS
        for value in (entry.old_value, entry.new_value)
        if value
    }


def _entity_ids(entries: list[ActivityLog]) -> defaultdict[ActivityEntityType, set[uuid.UUID]]:
    of: defaultdict[ActivityEntityType, set[uuid.UUID]] = defaultdict(set)
    for entry in entries:
        of[entry.entity_type].add(entry.entity_id)
    return of


# Fields whose values are the project's items (DL-276, DL-416; TD-132).
ITEM_FIELDS = frozenset(
    {
        ActivityField.PARENT_REQUIREMENT_ID,
        ActivityField.REQUIREMENT_ID,
        ActivityField.PHASE_ID,
        ActivityField.WORKSTREAM_ID,
    }
)
# A link's values hold the other item's ID (design-doc §10; TD-134).
LINK_ACTIONS = frozenset({ActivityAction.LINKED, ActivityAction.UNLINKED})

# The fields whose values the entry names (DL-147, DL-276).
NAMED_FIELDS = USER_FIELDS | ITEM_FIELDS | {ActivityField.APPROVED_REVISION_ID}


def _entry(entry: ActivityLog, named: dict[uuid.UUID, _Named]) -> ActivityEntry:
    def look_up(value: uuid.UUID | str | None) -> _Named | None:
        return None if value is None else named.get(uuid.UUID(str(value)))

    actor = look_up(entry.changed_by)
    item = look_up(entry.entity_id)
    names_values = entry.field_changed in NAMED_FIELDS or entry.action in LINK_ACTIONS
    old = look_up(entry.old_value) if names_values else None
    new = look_up(entry.new_value) if names_values else None
    return ActivityEntry(
        id=entry.id,
        entity_type=entry.entity_type,
        entity_id=entry.entity_id,
        entity_name=item.name if item else None,
        # A hard-deleted item (a phase) is gone, so it reads as deleted.
        entity_is_active=bool(item and item.is_active),
        action=entry.action,
        field_changed=entry.field_changed,
        old_value=entry.old_value,
        new_value=entry.new_value,
        changed_at=entry.changed_at,
        changed_by_id=entry.changed_by,
        changed_by_name=actor.name if actor else None,
        changed_by_is_active=actor.is_active if actor else None,
        old_value_name=old.name if old else None,
        old_value_is_active=old.is_active if old else None,
        new_value_name=new.name if new else None,
        new_value_is_active=new.is_active if new else None,
    )
