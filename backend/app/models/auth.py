"""`session` (schema-doc; design-doc §4, "Sessions"), owned by the `auth` area."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.core.constraint_errors import internal_only
from app.models.user import User


class UserSession(BaseModel):
    """A signed-in browser session. Named `UserSession` so it never shadows SQLAlchemy's
    `Session`; the table is `session`."""

    __tablename__ = "session"
    # A hash of 32 random bytes: a clash would be a bug, never a user's doing.
    __table_args__ = (
        UniqueConstraint("token_hash", info=internal_only()),
        # Account actions delete all of a user's sessions (DL-34).
        Index(None, "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(User.id))
    token_hash: Mapped[str]
    last_seen_at: Mapped[datetime]
    expires_at: Mapped[datetime]

    user: Mapped[User] = relationship(lazy="raise")
