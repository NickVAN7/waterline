from typing import ClassVar

from polyfactory import Use

from app.enums import ProjectModule, ProjectRole, ProjectType
from app.models.project import Project, ProjectMembership
from tests.factories import BaseFactory


def _key() -> str:
    """3 to 6 uppercase letters and digits, starting with a letter (design-doc §3)."""
    faker = BaseFactory.__faker__
    return faker.random_uppercase_letter() + faker.bothify("??#").upper()


class ProjectFactory(BaseFactory[Project]):
    """A software project with its default modules, unclassified, unarchived, and no lead (the
    lead must hold a project membership, so a test that needs one sets both)."""

    __model__ = Project
    __set_as_default_factory_for_type__: ClassVar[bool] = True

    key = Use(_key)
    name = Use(lambda: BaseFactory.__faker__.catch_phrase())
    description = None
    type = ProjectType.SOFTWARE
    enabled_modules = Use(lambda: [ProjectModule.SPRINTS.value, ProjectModule.GITHUB.value])
    lead = None
    archived_at = None
    classification_level = None


class ProjectMembershipFactory(BaseFactory[ProjectMembership]):
    __model__ = ProjectMembership
    __set_as_default_factory_for_type__: ClassVar[bool] = True

    role = ProjectRole.MEMBER
