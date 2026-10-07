"""`audit_event` constraints, defaults, and append-only guard (schema-doc, `audit_event`;
design-doc §10.1)."""

from typing import cast

import psycopg
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AuditAction
from app.models.audit_event import AuditEvent
from tests.factories.audit_event import AuditEventFactory

pytestmark = pytest.mark.anyio


# Rows can't be updated (see below), so the enum CHECKs are tested on INSERT.
@pytest.mark.parametrize(
    ("action", "entity_type", "constraint"),
    [
        ("user_deleted", None, "ck_audit_event_action"),
        ("user_created", "task", "ck_audit_event_entity_type"),
    ],
)
async def test_audit_enum_value_outside_the_enum_is_rejected(
    session: AsyncSession, action: str, entity_type: str | None, constraint: str
) -> None:
    with pytest.raises(IntegrityError, match=constraint):
        await session.execute(
            text(
                "INSERT INTO audit_event (id, action, entity_type, details)"
                " VALUES (gen_random_uuid(), :action, :entity_type, '{}')"
            ),
            {"action": action, "entity_type": entity_type},
        )


async def test_occurred_at_is_set_by_the_database(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO audit_event (id, action, details)"
            " VALUES (gen_random_uuid(), 'user_created', '{}')"
        )
    )

    occurred_at, now = (await session.execute(select(AuditEvent.occurred_at, text("now()")))).one()
    assert occurred_at == now


# --- Append-only (owner decision, Oct 7, 2026) ---------------------------------------------------


async def test_an_event_cannot_be_updated(session: AsyncSession) -> None:
    event = await AuditEventFactory.create_async(action=AuditAction.USER_CREATED)

    with pytest.raises(IntegrityError, match="audit_event is append-only: UPDATE") as raised:
        await session.execute(
            text("UPDATE audit_event SET action = 'user_deactivated' WHERE id = :id"),
            {"id": event.id},
        )
    # The SQLSTATE the schema doc commits to: restrict_violation.
    assert cast(psycopg.Error, raised.value.orig).sqlstate == "23001"


async def test_an_event_cannot_be_edited_through_the_orm(session: AsyncSession) -> None:
    event = await AuditEventFactory.create_async(details={"role": "member"})

    event.details = {"role": "owner"}
    with pytest.raises(IntegrityError, match="audit_event is append-only: UPDATE"):
        await session.flush()


async def test_an_event_cannot_be_deleted(session: AsyncSession) -> None:
    event = await AuditEventFactory.create_async()

    with pytest.raises(IntegrityError, match="audit_event is append-only: DELETE"):
        await session.execute(text("DELETE FROM audit_event WHERE id = :id"), {"id": event.id})


async def test_events_can_still_be_added(session: AsyncSession) -> None:
    await AuditEventFactory.create_async()
    await AuditEventFactory.create_async()

    assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 2
