"""Every job named in task_names.py is registered, with no defer-time options on its decorator.

`enqueue.py` defers by name. In the API process the job isn't registered, so procrastinate
ignores decorator options such as `queue=`, `priority=`, `lock=`, and `queueing_lock=` there,
while the worker would apply them: set them only in `enqueue.py`.
"""

from typing import Any

import pytest

from app.jobs import task_names
from app.jobs.worker import register_jobs

NAMES = sorted(
    value for key, value in vars(task_names).items() if key.isupper() and isinstance(value, str)
)


def registered_task(name: str) -> Any:
    return register_jobs().tasks[name]  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType] -- procrastinate's Task generics


@pytest.mark.parametrize("name", NAMES)
def test_job_is_registered_under_its_name(name: str) -> None:
    assert registered_task(name).name == name


@pytest.mark.parametrize("name", NAMES)
def test_job_decorator_sets_no_defer_time_options(name: str) -> None:
    task = registered_task(name)

    assert (task.queue, task.priority, task.lock, task.queueing_lock) == ("default", 0, None, None)
