from typing import ClassVar

from polyfactory import Use

from app.enums import Priority, RequirementStatus
from app.models.requirement import Requirement, RequirementRevision
from tests.factories import BaseFactory


def _title() -> str:
    return BaseFactory.__faker__.sentence(nb_words=6).rstrip(".")


def _description() -> str:
    """The shape the type templates give (DL-149): a summary, then acceptance criteria."""
    faker = BaseFactory.__faker__
    return f"{faker.paragraph()}\n\n## Acceptance Criteria\n\n- {faker.sentence()}\n"


class RequirementFactory(BaseFactory[Requirement]):
    """A top-level draft with no revision yet (`current_revision_id` null: the service creates
    revision 1 with it, so a test that needs one builds it with `RequirementRevisionFactory`
    and sets it), no restriction, never approved."""

    __model__ = Requirement
    __set_as_default_factory_for_type__: ClassVar[bool] = True

    # Numbers come from the numbering service in the app; a test that depends on one sets it.
    number = Use(lambda: BaseFactory.__faker__.unique.random_int(1, 99_999))
    title = Use(_title)
    description_md = Use(_description)
    status = RequirementStatus.DRAFT
    priority = Priority.MEDIUM
    # Any key sorts; a test that orders siblings sets each rank.
    rank = "a0"
    restriction_level = None
    approved_at = None
    deleted_at = None


class RequirementRevisionFactory(BaseFactory[RequirementRevision]):
    __model__ = RequirementRevision
    __set_as_default_factory_for_type__: ClassVar[bool] = True

    revision_number = 1
    title = Use(_title)
    description_md = Use(_description)
    change_note = None
