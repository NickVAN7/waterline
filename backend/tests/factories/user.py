from typing import ClassVar

import anyio
from polyfactory import Use

from app.core.security import hash_password
from app.models.user import User
from tests.factories import BaseFactory, fake_slug

# Every factory user's password, for tests that sign in. Hashed once per run (Argon2id is slow),
# at import, before any event loop runs, with the app's own hasher, so a factory user's hash
# never looks outdated to sign-in.
FACTORY_PASSWORD = "correct horse battery staple"
FACTORY_PASSWORD_HASH = anyio.run(hash_password, FACTORY_PASSWORD)


def _username() -> str:
    faker = BaseFactory.__faker__
    return fake_slug(faker.first_name(), faker.last_name())


def _email() -> str:
    faker = BaseFactory.__faker__
    return f"{_username()}@{faker.domain_name()}".lower()


class UserFactory(BaseFactory[User]):
    __model__ = User
    __set_as_default_factory_for_type__: ClassVar[bool] = True

    email = Use(_email)
    username = Use(_username)
    name = Use(lambda: BaseFactory.__faker__.name())
    hashed_password = FACTORY_PASSWORD_HASH
