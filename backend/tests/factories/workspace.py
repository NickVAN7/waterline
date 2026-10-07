from typing import ClassVar

from polyfactory import Use

from app.enums import WorkspaceRole
from app.models.workspace import Workspace, WorkspaceMembership
from tests.factories import BaseFactory, fake_slug


class WorkspaceFactory(BaseFactory[Workspace]):
    __model__ = Workspace
    __set_as_default_factory_for_type__: ClassVar[bool] = True

    name = Use(lambda: BaseFactory.__faker__.company())
    slug = Use(lambda: fake_slug(BaseFactory.__faker__.company()))


class WorkspaceMembershipFactory(BaseFactory[WorkspaceMembership]):
    __model__ = WorkspaceMembership
    __set_as_default_factory_for_type__: ClassVar[bool] = True

    role = WorkspaceRole.MEMBER
