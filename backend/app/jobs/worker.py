"""Worker entry point: `python -m app.jobs.worker` (the Compose `worker` service from S0-C7).

The worker is the only process that opens a procrastinate connection pool, and the only
importer of the job modules.
"""

import asyncio
import logging

import procrastinate
from sqlalchemy import URL

from app.core.settings import get_settings
from app.jobs.app import jobs_app


def conninfo(url: URL) -> str:
    """A libpq connection string for procrastinate, from the app's SQLAlchemy URL."""
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def register_jobs() -> procrastinate.App:
    """Import every job module, registering its jobs on `jobs_app`."""
    import app.jobs.tasks  # noqa: F401  # pyright: ignore[reportUnusedImport]

    return jobs_app


async def run_worker(
    database_url: URL, *, wait: bool = True, install_signal_handlers: bool = True
) -> None:
    """Process jobs until stopped (or, with wait=False, until the queue is empty)."""
    worker_app = register_jobs()
    connector = procrastinate.PsycopgConnector(conninfo=conninfo(database_url))
    with worker_app.replace_connector(connector):
        async with worker_app.open_async():
            await worker_app.run_worker_async(
                wait=wait, install_signal_handlers=install_signal_handlers
            )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker(get_settings().database_url()))


if __name__ == "__main__":  # pragma: no cover -- the module's command-line entry
    main()
