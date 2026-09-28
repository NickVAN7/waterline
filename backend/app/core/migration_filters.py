"""What Alembic autogenerate compares (used by migrations/env.py).

procrastinate's tables are created by our migrations from procrastinate's own SQL, but aren't
modeled in the ORM, so autogenerate must ignore them rather than propose dropping them.
"""

from typing import Any

PROCRASTINATE_PREFIX = "procrastinate_"


def include_object(
    obj: Any, name: str | None, type_: str, reflected: bool, compare_to: Any
) -> bool:
    return not (name or "").startswith(PROCRASTINATE_PREFIX)
