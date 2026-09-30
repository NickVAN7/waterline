"""Write the API's OpenAPI schema to `backend/openapi.json`, the input to the frontend's generated
client (`wl gen-client`). With `--check`, fail instead if the file is out of date (`wl check`).

The schema comes from the code, never a running server: no database, `.env`, or network needed.

    python -m app.openapi_export [--check]
"""

import argparse
import json
import sys
from pathlib import Path

from app.core.settings import Settings
from app.main import create_app

OPENAPI_FILE = Path(__file__).resolve().parents[1] / "openapi.json"


def export_settings() -> Settings:
    """Placeholder settings: the schema doesn't depend on them, but the app factory needs some.
    Built on each call, never from `.env`; the engine they describe is never connected."""
    return Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        postgres_user="openapi-export",
        postgres_password="openapi-export",  # noqa: S106 -- a placeholder, never used to connect
        postgres_db="openapi-export",
    )


def render_schema() -> str:
    """The schema as the file holds it: stable key order, two-space indent, final newline."""
    schema = create_app(export_settings()).openapi()
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None, *, path: Path = OPENAPI_FILE) -> int:
    parser = argparse.ArgumentParser(description="Export the OpenAPI schema.")
    parser.add_argument("--check", action="store_true", help="fail if the file is out of date")
    args = parser.parse_args(argv)
    schema = render_schema()
    if args.check:
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current != schema:
            print(  # noqa: T201
                f"{path.name} is out of date with the API: run `uv run wl gen-client` and commit "
                "the result.",
                file=sys.stderr,
            )
            return 1
        return 0
    path.write_text(schema, encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover -- the module's command-line entry
    sys.exit(main())
