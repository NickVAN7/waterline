"""Project modules (design-doc §1.1, "Project types & modules"): which modules a project type
seeds and recommends, and which have shipped (module guidance, DL-76). Pure."""

from app.enums import ProjectModule, ProjectType

# Every module in design-doc §1.1's table, v2 included: guidance lists them all, though only
# `ProjectModule`'s (the v1 modules) may be enabled.
ALL_MODULES: tuple[str, ...] = (
    "sprints",
    "github",
    "raid",
    "status_reports",
    "budget",
    "data_migration",
    "cutover",
)


# Design-doc §1.1's "Default on for" column.
_DEFAULTS: dict[ProjectType, tuple[str, ...]] = {
    ProjectType.SOFTWARE: ("sprints", "github"),
    ProjectType.ERP: ("raid", "status_reports", "budget", "data_migration", "cutover"),
    ProjectType.GENERAL: (),
}
# Each module's slice adds it here when it ships (design-doc §1.1: one place in the backend).
_SHIPPED: frozenset[str] = frozenset()


def seed_modules(project_type: ProjectType) -> list[ProjectModule]:
    """The modules a new project of this type starts with: its defaults that may be enabled."""
    allowed = {module.value for module in ProjectModule}
    return [ProjectModule(m) for m in _DEFAULTS[project_type] if m in allowed]


def recommended_modules(project_type: ProjectType) -> list[str]:
    """The modules design-doc §1.1 turns on by default for this type, v2 included."""
    return list(_DEFAULTS[project_type])


def is_available(module: str) -> bool:
    """Whether the module's slice has shipped, so its features work (none have yet)."""
    return module in _SHIPPED
