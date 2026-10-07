from typing import ClassVar

from app.models.numbering import ProjectCounter
from tests.factories import BaseFactory


class ProjectCounterFactory(BaseFactory[ProjectCounter]):
    __model__ = ProjectCounter
    __set_as_default_factory_for_type__: ClassVar[bool] = True
    # The composite key is (project_id, prefix): prefix must be set here, and project_id comes
    # from the `project` relationship (foreign keys are never generated).
    __set_primary_key__: ClassVar[bool] = True

    prefix = "TA"
    # The state after the first allocation: the lazy upsert inserts 2 once number 1 is handed
    # out (schema-doc `project_counter`), so a stored row never holds 1.
    next_value = 2
