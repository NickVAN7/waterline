"""`session` (schema-doc; design-doc §4, "Sessions"), owned by the `auth` area."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.core.constraint_errors import internal_only
from app.models.user import User

# A `User-Agent` longer than this is cut, not refused (schema-doc `session`).
USER_AGENT_MAX_LENGTH = 512


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
    # The sign-in request's `User-Agent`, for the session list (DL-242, DL-299).
    user_agent: Mapped[str | None] = mapped_column(String(USER_AGENT_MAX_LENGTH))
    expires_at: Mapped[datetime]

    user: Mapped[User] = relationship(lazy="raise")
