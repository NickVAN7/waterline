from typing import Literal

from pydantic import BaseModel

type Status = Literal["ok", "unavailable"]


class HealthRead(BaseModel):
    status: Status
    database: Status
