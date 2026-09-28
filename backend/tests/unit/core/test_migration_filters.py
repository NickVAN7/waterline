import pytest

from app.core.migration_filters import include_object


@pytest.mark.parametrize(
    ("name", "type_", "included"),
    [
        ("procrastinate_jobs", "table", False),
        ("procrastinate_jobs_queue_name_idx_v1", "index", False),
        ("task", "table", True),
        ("ix_task_project_id", "index", True),
        (None, "unique_constraint", True),
    ],
)
def test_only_procrastinate_objects_are_excluded(
    name: str | None, type_: str, included: bool
) -> None:
    assert include_object(None, name, type_, True, None) is included
