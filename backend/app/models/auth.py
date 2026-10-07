"""`session` (schema-doc; design-doc §4, "Sessions"), owned by the `auth` area."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.models.user import User


class UserSession(BaseModel):
    """A signed-in browser session. Named `UserSession` so it never shadows SQLAlchemy's
    `Session`; the table is `session`."""

    __tablename__ = "session"
    __table_args__ = (UniqueConstraint("token_hash"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(User.id))
    token_hash: Mapped[str]
    last_seen_at: Mapped[datetime]
    expires_at: Mapped[datetime]

    user: Mapped[User] = relationship(lazy="raise")
