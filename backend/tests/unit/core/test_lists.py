"""The pure parts of the list helpers (app/core/lists.py): LIKE escaping and spec validation.
Everything else is tested over HTTP (tests/api/core/test_lists.py)."""

from collections.abc import Sequence
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import ColumnClause, column

from app.core.lists import (
    CustomFilter,
    Filter,
    FilterType,
    ListSpec,
    escape_like,
    order_by,
)


@pytest.mark.parametrize(
    ("text", "escaped"),
    [("plain", "plain"), ("50%", "50\\%"), ("a_b", "a\\_b"), ("c:\\dir", "c:\\\\dir")],
)
def test_like_wildcards_and_the_escape_character_are_escaped(text: str, escaped: str) -> None:
    assert escape_like(text) == escaped


def test_a_default_sort_outside_the_allowlist_is_a_programming_error() -> None:
    with pytest.raises(ValueError, match=r"default sort \['score'\]"):
        ListSpec(
            name="X",
            id_column=column("id"),
            sorts={"name": column("name")},
            default_sort=("-score",),
        )


SPEC = ListSpec(
    name="X",
    id_column=column("id"),
    sorts={"name": column("name"), "score": column("score")},
    default_sort=("name",),
)


def sql(columns: Sequence[object]) -> list[str]:
    return [str(clause) for clause in columns]


@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        (None, ["name ASC", "id ASC"]),
        ("-score", ["score DESC", "id ASC"]),
        ("score,-name", ["score ASC", "name DESC", "id ASC"]),
    ],
)
def test_order_by_ends_with_id_ascending(sort: str | None, expected: list[str]) -> None:
    # Rows tied on every sort key still have one order, so offsets never skip or repeat rows.
    assert sql(order_by(SPEC, sort)) == expected


def test_only_user_references_accept_me() -> None:
    spec = ListSpec(
        name="Y",
        id_column=column("id"),
        filters=(
            Filter("owner", column("owner_id"), FilterType.USER),
            Filter("parent", column("parent_id"), FilterType.REFERENCE),
        ),
    )

    assert spec.query_model.model_validate({"owner": ["me"]})
    with pytest.raises(ValidationError, match="parent"):
        spec.query_model.model_validate({"parent": ["me"]})


def test_the_sort_parameter_documents_the_default() -> None:
    description = SPEC.query_model.model_fields["sort"].description

    assert description is not None
    assert description.endswith("Default: name")


SECRET: ColumnClause[Any] = column("secret")
RESTRICTED = (Filter("secret", SECRET, FilterType.BOOLEAN, restricted=True),)


def test_a_restricted_field_cant_be_sortable() -> None:
    with pytest.raises(ValueError, match="restricted"):
        ListSpec(name="Z", id_column=column("id"), filters=RESTRICTED, sorts={"secret": SECRET})


def test_a_restricted_field_cant_be_searchable() -> None:
    with pytest.raises(ValueError, match="restricted"):
        ListSpec(name="Z", id_column=column("id"), filters=RESTRICTED, search=(SECRET,))


@pytest.mark.parametrize(
    "filters",
    [
        (Filter("limit", column("x"), FilterType.BOOLEAN),),  # a built-in parameter
        (Filter("q", column("x"), FilterType.BOOLEAN),),
        (
            Filter("score", column("x"), FilterType.NUMBER),
            Filter("score", column("y"), FilterType.NUMBER),
        ),
        (  # different filters, one generated name: `due__lt` twice
            Filter("due", column("x"), FilterType.DATE),
            CustomFilter("due__lt", str, lambda statement, _value: statement),
        ),
    ],
)
def test_clashing_parameter_names_are_a_programming_error(
    filters: tuple[Filter | CustomFilter, ...],
) -> None:
    with pytest.raises(ValueError, match="clash"):
        ListSpec(name="C", id_column=column("id"), filters=filters)
