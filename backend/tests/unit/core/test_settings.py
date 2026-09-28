import pytest

from app.core.settings import TEST_DATABASE_NAME, Settings, get_settings


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "postgres_user": "user",
        "postgres_password": "p@ss:word",
        "postgres_db": "waterline",
        **overrides,
    }
    return Settings(_env_file=None, **values)  # pyright: ignore[reportCallIssue]


@pytest.fixture(autouse=True)
def _no_ambient_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("POSTGRES_HOST", "POSTGRES_PORT", "API_DOCS_ENABLED"):
        monkeypatch.delenv(name, raising=False)


def test_database_url_uses_psycopg_async_driver_and_escapes_password() -> None:
    url = make_settings(postgres_host="db", postgres_port=6543).database_url()

    assert url.render_as_string(hide_password=False) == (
        "postgresql+psycopg://user:p%40ss%3Aword@db:6543/waterline"
    )


def test_test_database_url_points_at_the_test_database() -> None:
    assert make_settings().test_database_url().database == TEST_DATABASE_NAME


def test_host_and_port_default_to_local_postgres() -> None:
    url = make_settings().database_url()

    assert (url.host, url.port) == ("localhost", 5432)


def test_api_docs_are_off_unless_enabled() -> None:
    assert make_settings().api_docs_enabled is False


def test_password_is_not_shown_in_repr() -> None:
    assert "p@ss:word" not in repr(make_settings())


def test_settings_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_PORT", "6000")
    monkeypatch.setenv("API_DOCS_ENABLED", "true")

    settings = make_settings()

    assert (settings.postgres_port, settings.api_docs_enabled) == (6000, True)


def test_get_settings_reads_the_environment_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_USER", "from-env")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_DB", "envdb")
    get_settings.cache_clear()
    try:
        first = get_settings()

        assert first.postgres_user == "from-env"
        assert get_settings() is first
    finally:
        get_settings.cache_clear()
