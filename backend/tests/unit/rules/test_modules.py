"""Project modules (design-doc §1.1, "Project types & modules", the module table; build plan,
"Projects (§1.1, §3)": seeding and module guidance, DL-76).

- Seeding: a new project gets its type's default modules that may be enabled (the v1 ones), so a
  software project starts with `sprints` and `github`, and an `erp` or `general` one with none.
- Recommended: the type's defaults from the table, v2 modules included.
- Available: whether the module's slice has shipped; none has yet (`sprints` and `github` are
  "not yet", build plan "Module guidance"; the v2 modules can't be enabled until they ship).
"""

import pytest

from app.enums import ProjectType
from app.rules.modules import is_available, recommended_modules, seed_modules


@pytest.mark.parametrize(
    ("project_type", "expected"),
    [
        (ProjectType.SOFTWARE, ["github", "sprints"]),
        # The erp defaults are all v2: seeding skips them (design-doc §1.1).
        (ProjectType.ERP, []),
        (ProjectType.GENERAL, []),
    ],
)
def test_a_new_project_is_seeded_with_its_types_v1_defaults_only(
    project_type: ProjectType, expected: list[str]
) -> None:
    assert sorted(seed_modules(project_type)) == expected


@pytest.mark.parametrize(
    ("project_type", "expected"),
    [
        (ProjectType.SOFTWARE, ["github", "sprints"]),
        # Still recommended while not yet available (design-doc §1.1).
        (ProjectType.ERP, ["budget", "cutover", "data_migration", "raid", "status_reports"]),
        (ProjectType.GENERAL, []),
    ],
)
def test_each_type_recommends_its_default_modules_v2_included(
    project_type: ProjectType, expected: list[str]
) -> None:
    assert sorted(recommended_modules(project_type)) == expected


@pytest.mark.parametrize(
    "module", ["sprints", "github", "raid", "status_reports", "budget", "data_migration", "cutover"]
)
def test_no_module_is_available_yet(module: str) -> None:
    """No module's slice has shipped in Slice 1, so the UI greys every one out."""
    assert is_available(module) is False
