import pytest
from sqlalchemy import URL

from app.core.settings import Settings
from app.jobs import worker


def test_conninfo_is_a_libpq_url_with_the_password_escaped() -> None:
    url = URL.create(
        "postgresql+psycopg", username="u", password="p@ss:w", host="db", port=5433, database="w"
    )

    assert worker.conninfo(url) == "postgresql://u:p%40ss%3Aw@db:5433/w"


def test_main_runs_a_worker_for_the_configured_database(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    started: list[URL] = []

    async def fake_run_worker(database_url: URL) -> None:
        started.append(database_url)

    monkeypatch.setattr(worker, "run_worker", fake_run_worker)
    monkeypatch.setattr(worker, "get_settings", lambda: settings)

    worker.main()

    assert started == [settings.database_url()]
