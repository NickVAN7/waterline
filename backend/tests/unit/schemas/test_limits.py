"""The length limits on request fields (DL-143; schema-doc): each field takes its limit and
refuses one character more, so a missing or wrong `max_length` fails here."""

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas.org import OrgCreate, OrgUpdate
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.schemas.user import OwnProfileUpdate, UserUpdate
from app.schemas.workspace import NewUser, WorkspaceUpdate

NEW_USER: dict[str, Any] = {
    "email": "ann@example.com",
    "username": "ann",
    "password": "Correct-horse-1",
}
NEW_PROJECT: dict[str, Any] = {"key": "PAY", "type": "software"}

CASES: list[tuple[type[BaseModel], str, int, dict[str, Any]]] = [
    (OrgCreate, "name", 100, {"slug": "bolt"}),
    (OrgUpdate, "name", 100, {}),
    (WorkspaceUpdate, "name", 100, {}),
    (NewUser, "name", 100, NEW_USER),
    (UserUpdate, "name", 100, {}),
    (OwnProfileUpdate, "name", 100, {}),
    (ProjectCreate, "name", 100, NEW_PROJECT),
    (ProjectCreate, "description", 2_000, {"name": "Payments", **NEW_PROJECT}),
    (ProjectUpdate, "name", 100, {}),
    (ProjectUpdate, "description", 2_000, {}),
]
IDS = [f"{schema.__name__}.{field}" for schema, field, _, _ in CASES]


@pytest.mark.parametrize(("schema", "field", "limit", "others"), CASES, ids=IDS)
def test_a_field_takes_its_limit(
    schema: type[BaseModel], field: str, limit: int, others: dict[str, Any]
) -> None:
    assert getattr(schema(**others, **{field: "x" * limit}), field) == "x" * limit


@pytest.mark.parametrize(("schema", "field", "limit", "others"), CASES, ids=IDS)
def test_a_field_refuses_one_character_more(
    schema: type[BaseModel], field: str, limit: int, others: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError, match="string_too_long"):
        schema(**others, **{field: "x" * (limit + 1)})
