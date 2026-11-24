"""A move in a flat ranked list (phases, workstreams, tasks; design-doc §6, "Manual ordering")."""

import uuid

from pydantic import BaseModel


class ItemMove(BaseModel):
    """`POST …/{id}/move`: just after `after_id` or just before `before_id`, or with neither at
    the bottom."""

    after_id: uuid.UUID | None = None
    before_id: uuid.UUID | None = None
