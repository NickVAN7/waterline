from typing import Literal

from pydantic import BaseModel


class HealthRead(BaseModel):
    """A healthy response. When the database is unreachable the endpoint returns 503 with the
    standard error body instead (`service_unavailable`)."""

    status: Literal["ok"]
    database: Literal["ok"]
