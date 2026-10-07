"""Admin and security events (design-doc §10.1; schema-doc `audit_event`).

`log_admin_event()` is the only writer of `audit_event`. It adds the row to the caller's session
and never commits or flushes, so the event commits or rolls back with the change it records; a
change is never saved without its record, and vice versa. The database rejects any later edit
or delete (append-only trigger).
"""

import re
import uuid
from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AuditAction, AuditEntityType
from app.models.audit_event import AuditEvent

type JsonValue = str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None

# Never stored in an event, at any depth (design-doc §10.1: "never passwords, hashes, or
# tokens"). Matched against `details` keys, which name what a value is: a defense against
# carelessness, not a scanner. A secret under an innocent key (`{"value": token}`) gets through,
# so callers never put one in `details` at all.
_SECRET_KEY = re.compile(r"password|hash|token|secret", re.IGNORECASE)


class SecretInDetailsError(ValueError):
    """`details` has a key that looks like a password, hash, token, or secret."""


def _secret_keys(value: JsonValue, path: str = "") -> list[str]:
    if isinstance(value, dict):
        found: list[str] = []
        for key, item in value.items():
            here = f"{path}.{key}" if path else key
            # A secret is text (or holds text): a flag such as `must_change_password: true` is fine.
            if _SECRET_KEY.search(key) and isinstance(item, str | list | dict):
                found.append(here)
            found.extend(_secret_keys(item, here))
        return found
    if isinstance(value, list):
        return [
            key
            for index, item in enumerate(value)
            for key in _secret_keys(item, f"{path}[{index}]")
        ]
    return []


def log_admin_event(
    session: AsyncSession,
    *,
    action: AuditAction,
    actor_id: uuid.UUID | None,
    workspace_id: uuid.UUID | None,
    organization_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    target_user_id: uuid.UUID | None = None,
    entity_type: AuditEntityType | None = None,
    entity_id: uuid.UUID | None = None,
    details: Mapping[str, JsonValue] | None = None,
) -> AuditEvent:
    """Record an admin or security event in the request's transaction (no commit, no flush).

    `actor_id` is None only when an app CLI command acted. `workspace_id` is None only for
    instance-level events (system-admin grants and revocations). Scope the event as design-doc
    §10.1 says: the org when the actor acted as that org's owner/admin, the project for project
    events. `occurred_at` is the database's (the transaction's start time).

    Raises `SecretInDetailsError` if a `details` key names a password, hash, token, or secret.
    """
    payload: dict[str, JsonValue] = dict(details or {})
    secrets = _secret_keys(payload)
    if secrets:
        raise SecretInDetailsError(
            f"audit event details must not hold passwords, hashes, or tokens: {secrets}"
        )
    event = AuditEvent(
        action=action,
        actor_id=actor_id,
        workspace_id=workspace_id,
        organization_id=organization_id,
        project_id=project_id,
        target_user_id=target_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        details=payload,
    )
    session.add(event)
    return event
