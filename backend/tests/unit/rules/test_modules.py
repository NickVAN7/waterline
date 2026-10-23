"""Project modules (design-doc §1.1, "Project types & modules", the module table; build plan,
"Projects (§1.1, §3)": seeding and module guidance, DL-76; DL-136).

- Seeding: a new project gets only its type's default modules that have shipped ("A module can be
  enabled only once it has shipped", v1 and v2 modules alike, DL-136). None has yet, so every
  type, software included, seeds no modules ("every project created before Slice 4 starts with no
  modules").
- Recommended: the type's defaults from the table, v2 modules included, still listed while not
  available.
- Available: whether the module's slice has shipped; none has yet (`sprints` ships in Slice 4,
  `github` in Slice 7).
"""

import pytest

from app.enums import ProjectModule, ProjectType
from app.rules import modules
from app.rules.modules import is_available, recommended_modules, seed_modules


@pytest.mark.parametrize(
    ("project_type", "expected"),
    [
        # `sprints` and `github` haven't shipped (Slices 4 and 7): seeding skips them (DL-136).
        (ProjectType.SOFTWARE, []),
        # The erp defaults are all v2: seeding skips them (design-doc §1.1).
        (ProjectType.ERP, []),
        (ProjectType.GENERAL, []),
    ],
)
def test_a_new_project_is_seeded_with_its_types_shipped_defaults_only(
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
    """No module's slice has shipped yet (design-doc §1.1, DL-136), so the UI shows every one as
    a disabled checkbox with "Not available yet"."""
    assert is_available(module) is False


# --- Once a module ships (design-doc §1.1, DL-136) ----------------------------------------------


@pytest.fixture
def github_shipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """`github` shipped and `sprints` not: each module's slice adds its name to `_SHIPPED`, the
    one place in the backend (design-doc §1.1)."""
    monkeypatch.setattr(modules, "_SHIPPED", frozenset({"github"}))


@pytest.mark.parametrize(
    ("project_type", "expected"),
    [
        # A shipped default is seeded; `sprints`, not yet shipped, is still skipped.
        (ProjectType.SOFTWARE, [ProjectModule.GITHUB]),
        # `github` isn't an erp or general default.
        (ProjectType.ERP, []),
        (ProjectType.GENERAL, []),
    ],
)
@pytest.mark.usefixtures("github_shipped")
def test_a_new_project_is_seeded_with_its_types_defaults_that_have_shipped(
    project_type: ProjectType, expected: list[ProjectModule]
) -> None:
    assert seed_modules(project_type) == expected


@pytest.mark.usefixtures("github_shipped")
def test_a_shipped_module_is_available() -> None:
    assert is_available("github") is True
