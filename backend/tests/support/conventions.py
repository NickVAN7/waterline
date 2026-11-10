"""Checks that every mapped model follows the model conventions (backend/CLAUDE.md, "Models")."""

from sqlalchemy.orm import registry

from app.core.base_model import RestrictionMixin

# The restrictable tables (schema-doc, conventions: "Restriction"), each from its own slice.
RESTRICTABLE_TABLES = frozenset({"project", "requirement", "task", "testcase"})


def relationships_that_can_lazy_load(models: registry) -> list[str]:
    """Relationships not declared `lazy="raise"`: touching one unloaded would emit SQL, which
    async sessions can't do (and which hides missing eager loads)."""
    return sorted(
        f"{mapper.class_.__name__}.{rel.key}"
        for mapper in models.mappers
        for rel in mapper.relationships
        if rel.lazy != "raise"
    )


def mappers_without_eager_defaults(models: registry) -> list[str]:
    """Models whose `__mapper_args__` dropped `eager_defaults=True`. SQLAlchemy's default,
    "auto", fetches server-set values after an INSERT but not after an UPDATE, so `updated_at`
    couldn't be read after an update without a lazy load (which fails in async code)."""
    return sorted(
        mapper.class_.__name__ for mapper in models.mappers if mapper.eager_defaults is not True
    )


def versioned_tables_without_version_checks(models: registry) -> list[str]:
    """Models with a `version` column that the mapper doesn't use for optimistic locking (e.g.
    `VersionMixin` listed after `TimestampMixin`, whose `__mapper_args__` then wins)."""
    return sorted(
        mapper.class_.__name__
        for mapper in models.mappers
        if "version" in mapper.columns and mapper.version_id_col is None
    )


def restrictable_models_without_the_mixin(models: registry) -> list[str]:
    """Models of a restrictable table, or with a `restriction_*` column, that don't use
    `RestrictionMixin` (design-doc §3.1): their columns would drift from the shared ones."""
    return sorted(
        mapper.class_.__name__
        for mapper in models.mappers
        if (
            mapper.persist_selectable.name in RESTRICTABLE_TABLES  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
            or any(key.startswith("restriction_") for key in mapper.columns.keys())  # noqa: SIM118
        )
        and not issubclass(mapper.class_, RestrictionMixin)
    )
