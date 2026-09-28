"""A trivial job for checking the queue end to end."""

import logging

from app.jobs import task_names
from app.jobs.app import jobs_app

logger = logging.getLogger(__name__)


@jobs_app.task(name=task_names.PING)
async def ping(message: str) -> None:
    logger.info("ping: %s", message)
