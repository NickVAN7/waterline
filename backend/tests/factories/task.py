from typing import ClassVar

from polyfactory import Use

from app.enums import Priority, TaskStatus, TaskType
from app.models.task import Subtask, Task
from tests.factories import BaseFactory


def _title() -> str:
    return BaseFactory.__faker__.sentence(nb_words=5).rstrip(".")


class TaskFactory(BaseFactory[Task]):
    """A to-do feature, medium priority, unassigned, with no requirement, phase, or workstream
    (a test that needs one sets its id), no dates or times, no restriction."""

    __model__ = Task
    __set_as_default_factory_for_type__: ClassVar[bool] = True

    # Numbers come from the numbering service in the app; a test that depends on one sets it.
    number = Use(lambda: BaseFactory.__faker__.unique.random_int(1, 99_999))
    type = TaskType.FEATURE
    title = Use(_title)
    description_md = Use(lambda: BaseFactory.__faker__.paragraph())
    status = TaskStatus.TODO
    priority = Priority.MEDIUM
    severity = None
    start_date = None
    due_date = None
    # Any key sorts; a test that orders tasks sets each rank.
    rank = "a0"
    time_estimate = None
    time_taken = None
    restriction_level = None
    deleted_at = None


class SubtaskFactory(BaseFactory[Subtask]):
    __model__ = Subtask
    __set_as_default_factory_for_type__: ClassVar[bool] = True

    # From the task's counter in the app; a test that depends on one sets it.
    number = Use(lambda: BaseFactory.__faker__.unique.random_int(1, 99_999))
    title = Use(_title)
    description = ""
    rank = "a0"
