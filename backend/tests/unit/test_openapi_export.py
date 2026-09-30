"""`python -m app.openapi_export`: the file the frontend client is generated from, and the
freshness check `wl check` runs on it (build-plan.md, "API foundations")."""

import json
from pathlib import Path

import pytest

from app.openapi_export import main

ENV_VARS = ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "API_DOCS_ENABLED")


@pytest.fixture(autouse=True)
def _no_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """The export must work with no `.env` or database settings (e.g. in CI's lint job)."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_export_writes_the_api_routes_under_api(tmp_path: Path) -> None:
    path = tmp_path / "openapi.json"

    assert main([], path=path) == 0

    schema = json.loads(path.read_text())
    assert schema["info"]["title"] == "Waterline"
    assert "/api/health" in schema["paths"]


def test_export_is_written_with_a_final_newline(tmp_path: Path) -> None:
    path = tmp_path / "openapi.json"

    main([], path=path)

    assert path.read_text().endswith("}\n")


def test_check_passes_when_the_file_matches_the_code(tmp_path: Path) -> None:
    path = tmp_path / "openapi.json"
    main([], path=path)

    assert main(["--check"], path=path) == 0


def test_check_fails_and_leaves_the_file_alone_when_it_is_out_of_date(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "openapi.json"
    path.write_text('{"paths": {}}\n')

    assert main(["--check"], path=path) == 1

    assert path.read_text() == '{"paths": {}}\n'
    assert "run `uv run wl gen-client`" in capsys.readouterr().err


def test_check_fails_when_the_file_is_missing(tmp_path: Path) -> None:
    assert main(["--check"], path=tmp_path / "openapi.json") == 1
