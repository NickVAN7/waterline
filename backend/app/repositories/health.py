from sqlalchemy import text

from app.core.db import SessionMaker


class HealthRepository:
    """Pings the database on its own short-lived session, outside any request transaction, so a
    dropped connection is reported as unavailable rather than failing the request's commit."""

    def __init__(self, sessionmaker: SessionMaker) -> None:
        self.sessionmaker = sessionmaker

    async def ping(self) -> None:
        """Round-trip to the database; raises if it can't be reached."""
        async with self.sessionmaker() as session:
            await session.execute(text("SELECT 1"))
