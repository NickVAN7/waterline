"""`user` (schema-doc "Users, Tenancy & Auth"; design-doc §4, "Users")."""

from sqlalchemy import CheckConstraint, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel
from app.core.constraint_errors import user_error


class User(BaseModel):
    __tablename__ = "user"
    __table_args__ = (
        UniqueConstraint(
            "email", info=user_error("email", "taken", "This email is already in use.")
        ),
        UniqueConstraint(
            "username", info=user_error("username", "taken", "This username is taken.")
        ),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    email: Mapped[str]
    username: Mapped[str]
    name: Mapped[str]
    hashed_password: Mapped[str]
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    is_system_admin: Mapped[bool] = mapped_column(server_default=text("false"))
    must_change_password: Mapped[bool] = mapped_column(server_default=text("false"))
