"""`session` (design-doc §4, "Sessions"). Only the auth service calls this."""

import uuid
from datetime import timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager
from sqlalchemy.orm.attributes import set_committed_value

from app.models.auth import UserSession
from app.models.user import User


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_session(
        self, user_id: uuid.UUID, token_hash: str, lifetime: timedelta
    ) -> UserSession:
        """A new session row, timed by the database clock: seen now, ending `lifetime` from
        now at the latest."""
        row = UserSession(
            user_id=user_id,
            token_hash=token_hash,
            last_seen_at=func.now(),
            expires_at=func.now() + lifetime,
        )
        self.session.add(row)
        await self.session.flush()
        # Attributes set to SQL expressions are expired by the flush; load them now, since a
        # lazy load later would fail.
        await self.session.refresh(row, ["last_seen_at", "expires_at"])
        return row

    async def find_live(self, token_hash: str, idle_timeout: timedelta) -> UserSession | None:
        """The session with this token hash, with its user loaded, if it's within its lifetime,
        was seen within `idle_timeout`, and its user is active; otherwise None."""
        return await self.session.scalar(
            select(UserSession)
            .join(UserSession.user)
            .options(contains_eager(UserSession.user))
            .where(
                UserSession.token_hash == token_hash,
                UserSession.expires_at > func.now(),
                UserSession.last_seen_at > func.now() - idle_timeout,
                User.is_active,
            )
        )

    async def touch(self, row: UserSession, interval: timedelta) -> None:
        """Set `last_seen_at` to now if it's older than `interval` (so it's written at most
        that often), keeping the loaded row in step."""
        result = await self.session.execute(
            update(UserSession)
            .where(UserSession.id == row.id, UserSession.last_seen_at < func.now() - interval)
            .values(last_seen_at=func.now())
            .returning(UserSession.last_seen_at, UserSession.updated_at)
            .execution_options(synchronize_session=False)
        )
        written = result.one_or_none()
        if written is not None:
            set_committed_value(row, "last_seen_at", written.last_seen_at)
            set_committed_value(row, "updated_at", written.updated_at)

    async def get_by_token_hash(self, token_hash: str) -> UserSession | None:
        return await self.session.scalar(
            select(UserSession).where(UserSession.token_hash == token_hash)
        )

    async def replace_token(self, row: UserSession, token_hash: str) -> None:
        """Give the session a new token (its times stay as they are)."""
        row.token_hash = token_hash
        await self.session.flush()

    async def delete_by_token_hash(self, token_hash: str) -> None:
        await self.session.execute(delete(UserSession).where(UserSession.token_hash == token_hash))

    async def delete_others(self, user_id: uuid.UUID, keep_id: uuid.UUID) -> None:
        """Delete every session of the user except `keep_id`."""
        await self.session.execute(
            delete(UserSession).where(UserSession.user_id == user_id, UserSession.id != keep_id)
        )
