from sqlalchemy import URL

from app.core.db import create_engine, create_sessionmaker


def test_sessions_keep_objects_readable_after_commit() -> None:
    # Creating an engine doesn't connect, so no database is needed.
    engine = create_engine(URL.create("postgresql+psycopg", host="localhost", database="x"))

    assert create_sessionmaker(engine).kw["expire_on_commit"] is False
