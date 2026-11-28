"""A review copy's own test databases (DL-392), dropped when the copy is discarded:
`python -m tests.support.review_databases drop <name>`, run from `backend/` (`wl discard-copy`).
The standing test database is never dropped."""

import re
import sys

from sqlalchemy import create_engine, text

from app.core.settings import TEST_DATABASE_NAME, Settings

COPY = re.compile(r"waterline_test_[0-9a-f]{8}")


def drop(name: str, settings: Settings) -> list[str]:
    """Drops `name` and every database named after it (its workers' copies, `<name>_gw<n>`, and
    scratch databases a killed run left, `<name>_scratch_<hex>`); returns what it dropped."""
    if not COPY.fullmatch(name):
        raise ValueError(f"{name!r} isn't a review copy's test database (waterline_test_<8 hex>)")
    admin = create_engine(
        settings.database_url(database=TEST_DATABASE_NAME), isolation_level="AUTOCOMMIT"
    )
    try:
        with admin.connect() as connection:
            names = (
                connection.execute(
                    text(
                        "SELECT datname FROM pg_database"
                        " WHERE datname = :n OR datname LIKE :w ORDER BY 1"
                    ),
                    {"n": name, "w": name.replace("_", r"\_") + r"\_%"},
                )
                .scalars()
                .all()
            )
            for database in names:  # a name from pg_database, checked above; never user text
                connection.execute(text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
    finally:
        admin.dispose()
    return list(names)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "drop":
        sys.stderr.write("usage: python -m tests.support.review_databases drop <name>\n")
        return 2
    try:
        dropped = drop(argv[1], Settings())  # pyright: ignore[reportCallIssue]
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    sys.stdout.write(f"dropped: {', '.join(dropped) or 'nothing (already gone)'}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover -- the entry point; main() is tested directly
    sys.exit(main(sys.argv[1:]))
