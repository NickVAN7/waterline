"""`user` (design-doc §4, "Users")."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        """The user with exactly this email; callers lowercase it first (emails are stored
        lowercase)."""
        return await self.session.scalar(select(User).where(User.email == email))
