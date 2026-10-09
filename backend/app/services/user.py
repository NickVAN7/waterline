"""The `user` area: the only writer of the `user` table (build plan, "Feature map")."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def set_password_hash(self, user: User, password_hash: str) -> None:
        """Store a new hash for the user's current password (sign-in's upgrade of a hash made
        with older Argon2 parameters). The caller has verified the password."""
        user.hashed_password = password_hash
        await self.session.flush()
