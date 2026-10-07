from datetime import UTC, datetime, timedelta
from typing import ClassVar

from polyfactory import Use

from app.core.security import generate_token, hash_token
from app.models.auth import UserSession
from tests.factories import BaseFactory


class UserSessionFactory(BaseFactory[UserSession]):
    __model__ = UserSession
    __set_as_default_factory_for_type__: ClassVar[bool] = True

    token_hash = Use(lambda: hash_token(generate_token()))
    last_seen_at = Use(lambda: datetime.now(UTC))
    expires_at = Use(lambda: datetime.now(UTC) + timedelta(days=7))
