import uuid

from app.core.base_model import NAMING_CONVENTION, TYPE_ANNOTATION_MAP, Base, BaseModel
from tests.support.models import Widget


def test_app_base_uses_the_naming_convention_and_type_map() -> None:
    assert dict(Base.metadata.naming_convention) == NAMING_CONVENTION
    assert Base.type_annotation_map is TYPE_ANNOTATION_MAP


def test_base_model_is_abstract_with_the_shared_columns() -> None:
    assert BaseModel.__abstract__ is True
    assert {"id", "created_at", "updated_at"} <= set(dir(BaseModel))


def test_id_is_a_uuid7_assigned_at_construction() -> None:
    widget = Widget(name="a")

    assert isinstance(widget.id, uuid.UUID)
    assert widget.id.version == 7


def test_explicit_id_is_kept() -> None:
    chosen = uuid.uuid7()

    assert Widget(name="a", id=chosen).id == chosen


def test_ids_sort_by_creation_order() -> None:
    ids = [Widget(name=str(n)).id for n in range(500)]

    assert sorted(ids) == ids
