"""Dropping a review copy's own test databases (tests/support/review_databases.py, DL-392): its
own and its workers' copies, never another copy's, never the standing test database."""

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text

from app.core.settings import TEST_DATABASE_NAME, Settings
from tests.support import review_databases


def existing(settings: Settings, prefix: str) -> list[str]:
    admin = create_engine(settings.database_url(database=TEST_DATABASE_NAME))
    try:
        with admin.connect() as connection:
            return list(
                connection.execute(
                    text("SELECT datname FROM pg_database WHERE datname LIKE :p ORDER BY 1"),
                    {"p": f"{prefix}%"},
                ).scalars()
            )
    finally:
        admin.dispose()


@pytest.fixture
def copies(settings: Settings) -> Iterator[tuple[str, str]]:
    """A copy's database with two workers' copies and a scratch database a killed run left, and
    another copy's beside it."""
    name, other = (f"waterline_test_{uuid.uuid4().hex[:8]}" for _ in range(2))
    admin = create_engine(
        settings.database_url(database=TEST_DATABASE_NAME), isolation_level="AUTOCOMMIT"
    )
    try:
        with admin.connect() as connection:
            for database in (name, f"{name}_gw0", f"{name}_gw1", f"{name}_scratch_ab12", other):
                connection.execute(text(f'CREATE DATABASE "{database}"'))
        yield name, other
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{other}" WITH (FORCE)'))
    finally:
        admin.dispose()


def test_a_copys_databases_are_dropped_and_no_other(
    settings: Settings, copies: tuple[str, str]
) -> None:
    name, other = copies

    dropped = review_databases.drop(name, settings)

    assert dropped == [name, f"{name}_gw0", f"{name}_gw1", f"{name}_scratch_ab12"]
    assert existing(settings, name) == []
    assert existing(settings, other) == [other]


@pytest.mark.parametrize(
    "name", [TEST_DATABASE_NAME, "waterline", "waterline_test_%", "waterline_test_ab"]
)
def test_only_a_copys_name_is_dropped(settings: Settings, name: str) -> None:
    with pytest.raises(ValueError, match="isn't a review copy's test database"):
        review_databases.drop(name, settings)


def test_the_command_drops_reports_and_refuses(
    copies: tuple[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    name, _ = copies

    assert review_databases.main(["drop", name]) == 0
    assert (
        capsys.readouterr().out == f"dropped: {name}, {name}_gw0, {name}_gw1, {name}_scratch_ab12\n"
    )
    assert review_databases.main(["drop", name]) == 0
    assert "nothing (already gone)" in capsys.readouterr().out
    assert review_databases.main(["drop", TEST_DATABASE_NAME]) == 2
    assert review_databases.main([]) == 2
