"""The task types a project offers (design-doc §6, Task; DL-352): software projects offer
feature, bug, chore, and spike; ERP and general projects offer all seven, in `TaskType`'s order."""

import pytest

from app.enums import ProjectType, TaskType
from app.rules.task_types import task_types

ALL_SEVEN = (
    TaskType.FEATURE,
    TaskType.BUG,
    TaskType.CHORE,
    TaskType.SPIKE,
    TaskType.CONFIG,
    TaskType.DATA,
    TaskType.TRAINING,
)


def test_a_software_project_offers_feature_bug_chore_and_spike() -> None:
    assert task_types(ProjectType.SOFTWARE) == (
        TaskType.FEATURE,
        TaskType.BUG,
        TaskType.CHORE,
        TaskType.SPIKE,
    )


@pytest.mark.parametrize("project_type", [ProjectType.ERP, ProjectType.GENERAL])
def test_erp_and_general_projects_offer_all_seven(project_type: ProjectType) -> None:
    assert task_types(project_type) == ALL_SEVEN


@pytest.mark.parametrize("task_type", [TaskType.CONFIG, TaskType.DATA, TaskType.TRAINING])
def test_a_software_project_does_not_offer_the_erp_types(task_type: TaskType) -> None:
    assert task_type not in task_types(ProjectType.SOFTWARE)
