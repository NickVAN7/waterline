from sqlalchemy import Column, MetaData, Table
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.core.base_model import NAMING_CONVENTION
from app.core.enums import enum_type
from tests.support.models import DocumentStatus


def create_sql() -> str:
    table = Table(
        "doc",
        MetaData(naming_convention=NAMING_CONVENTION),
        Column("status", enum_type(DocumentStatus, "status")),
    )
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))


def test_enum_is_a_varchar_not_a_native_postgres_enum() -> None:
    assert "status VARCHAR(64)" in create_sql()


def test_enum_gets_a_named_check_listing_the_values_not_the_names() -> None:
    assert "CONSTRAINT ck_doc_status CHECK (status IN ('draft', 'in_review'))" in create_sql()
