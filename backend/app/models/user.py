"""`user` (schema-doc "Users, Tenancy & Auth"; design-doc §4, "Users")."""

from sqlalchemy import CheckConstraint, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class User(BaseModel):
    __tablename__ = "user"
    __table_args__ = (
        UniqueConstraint("email"),
        UniqueConstraint("username"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    email: Mapped[str]
    username: Mapped[str]
    name: Mapped[str]
    hashed_password: Mapped[str]
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    is_system_admin: Mapped[bool] = mapped_column(server_default=text("false"))
    must_change_password: Mapped[bool] = mapped_column(server_default=text("false"))
