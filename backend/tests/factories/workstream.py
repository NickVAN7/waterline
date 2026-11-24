from typing import ClassVar

from polyfactory import Use

from app.models.workstream import Workstream
from tests.factories import BaseFactory


class WorkstreamFactory(BaseFactory[Workstream]):
    """A live workstream with no lead (a test that needs one sets `lead_id`)."""

    __model__ = Workstream
    __set_as_default_factory_for_type__: ClassVar[bool] = True

    name = Use(lambda: f"Workstream {BaseFactory.__faker__.unique.random_int(1, 99_999)}")
    description = None
    rank = "a0"
    archived_at = None
