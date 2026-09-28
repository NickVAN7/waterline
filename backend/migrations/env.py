"""Alembic environment (async). The database URL comes from app settings; tests pass their own
URL through `config.attributes["url"]`."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import URL
from sqlalchemy.engine import Connection

import app.models  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers every model
from app.core.base_model import Base
from app.core.db import create_engine
from app.core.migration_filters import include_object
from app.core.settings import get_settings

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def database_url() -> URL:
    url: URL | None = config.attributes.get("url")
    return url if url is not None else get_settings().database_url()


def configure(**kwargs: object) -> None:
    context.configure(
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
        **kwargs,  # pyright: ignore[reportArgumentType]
    )


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it (`alembic upgrade head --sql`)."""
    configure(url=database_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_engine(database_url())
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
