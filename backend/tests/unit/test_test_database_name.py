"""The test database's name (tests/conftest.py, DL-392): `waterline_test`, or a review copy's
own from `WATERLINE_TEST_DATABASE`, and never anything else."""

import pytest
from pydantic import SecretStr

from tests.conftest import HarnessSettings


def settings() -> HarnessSettings:
    """Read from the environment only: a developer's `.env` can't change what these expect."""
    return HarnessSettings(
        postgres_user="u",
        postgres_password=SecretStr("p"),
        postgres_db="waterline",
        _env_file=None,  # pyright: ignore[reportCallIssue]
    )


def test_the_default_is_the_standing_test_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WATERLINE_TEST_DATABASE", raising=False)

    assert settings().test_database_url().database == "waterline_test"


def test_a_review_copy_names_its_own_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WATERLINE_TEST_DATABASE", "waterline_test_3fa9c1d2")

    assert settings().test_database_url().database == "waterline_test_3fa9c1d2"


@pytest.mark.parametrize(
    "name",
    [
        "waterline",
        "waterline_dev",
        "postgres",
        "waterline_test_",
        "waterline_test_A1",
        "x_waterline_test",
    ],
)
def test_any_other_name_is_refused(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WATERLINE_TEST_DATABASE", name)

    with pytest.raises(pytest.UsageError, match="only ever run against a test database"):
        settings().test_database_url()
