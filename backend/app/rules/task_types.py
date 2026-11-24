"""The task types a project offers (design-doc §6, Task; DL-352)."""

from app.enums import ProjectType, TaskType

_SOFTWARE = frozenset({TaskType.FEATURE, TaskType.BUG, TaskType.CHORE, TaskType.SPIKE})


def task_types(project_type: ProjectType) -> tuple[TaskType, ...]:
    """The task types a project of `project_type` offers, in `TaskType`'s order: software the
    four, ERP and general all seven."""
    if project_type is ProjectType.SOFTWARE:
        return tuple(t for t in TaskType if t in _SOFTWARE)
    return tuple(TaskType)
