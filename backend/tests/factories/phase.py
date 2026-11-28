from typing import ClassVar

from polyfactory import Use

from app.enums import PhaseStatus
from app.models.phase import Phase
from tests.factories import BaseFactory


class PhaseFactory(BaseFactory[Phase]):
    """A planned phase with no dates or baseline."""

    __model__ = Phase
    __set_as_default_factory_for_type__: ClassVar[bool] = True

    name = Use(lambda: f"Phase {BaseFactory.__faker__.unique.random_int(1, 99_999)}")
    description = None
    # Any key sorts; a test that orders phases sets each rank.
    rank = "a0"
    start_date = None
    end_date = None
    baseline_start = None
    baseline_end = None
    status = PhaseStatus.PLANNED
