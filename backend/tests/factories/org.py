from typing import ClassVar

from polyfactory import Use

from app.enums import OrgRole
from app.models.org import Membership, Organization
from tests.factories import BaseFactory, fake_slug


class OrganizationFactory(BaseFactory[Organization]):
    __model__ = Organization
    __set_as_default_factory_for_type__: ClassVar[bool] = True

    name = Use(lambda: BaseFactory.__faker__.company())
    slug = Use(lambda: fake_slug(BaseFactory.__faker__.company()))


class MembershipFactory(BaseFactory[Membership]):
    __model__ = Membership
    __set_as_default_factory_for_type__: ClassVar[bool] = True

    role = OrgRole.MEMBER
