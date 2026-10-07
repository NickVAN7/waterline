"""`audit_event` constraints and defaults (schema-doc, `audit_event`)."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent
from tests.factories.audit_event import AuditEventFactory

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    ("update", "constraint"),
    [
        ("UPDATE audit_event SET action = 'user_deleted' WHERE id = :id", "ck_audit_event_action"),
        (
            "UPDATE audit_event SET entity_type = 'task' WHERE id = :id",
            "ck_audit_event_entity_type",
        ),
    ],
)
async def test_audit_enum_value_outside_the_enum_is_rejected(
    session: AsyncSession, update: str, constraint: str
) -> None:
    event = await AuditEventFactory.create_async()

    with pytest.raises(IntegrityError, match=constraint):
        await session.execute(text(update), {"id": event.id})


async def test_occurred_at_is_set_by_the_database(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO audit_event (id, action, details)"
            " VALUES (gen_random_uuid(), 'user_created', '{}')"
        )
    )

    occurred_at, now = (await session.execute(select(AuditEvent.occurred_at, text("now()")))).one()
    assert occurred_at == now
