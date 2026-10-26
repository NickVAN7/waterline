"""`activity_log` constraints and defaults (schema-doc `activity_log`; design-doc §10)."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ActivityAction, ActivityField
from app.models.audit import ActivityLog
from tests.factories.audit import ActivityLogFactory

pytestmark = pytest.mark.anyio


async def test_an_update_entry_names_the_field_it_changed(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="ck_activity_log_updated_has_field"):
        await ActivityLogFactory.create_async(action=ActivityAction.UPDATED, field_changed=None)


async def test_an_update_entry_with_its_field_is_stored(session: AsyncSession) -> None:
    await ActivityLogFactory.create_async(
        action=ActivityAction.UPDATED,
        field_changed=ActivityField.STATUS,
        old_value="draft",
        new_value="in_progress",
    )

    assert await session.scalar(text("SELECT count(*) FROM activity_log")) == 1


@pytest.mark.parametrize(
    "action",
    [
        ActivityAction.CREATED,
        ActivityAction.DELETED,
        ActivityAction.RESTORED,
        ActivityAction.LINKED,
        ActivityAction.UNLINKED,
    ],
)
async def test_other_entries_need_no_field(session: AsyncSession, action: ActivityAction) -> None:
    await ActivityLogFactory.create_async(action=action, field_changed=None)

    assert await session.scalar(text("SELECT count(*) FROM activity_log")) == 1


async def test_changed_at_is_set_by_the_database(session: AsyncSession) -> None:
    await ActivityLogFactory.create_async()

    changed_at, now = (await session.execute(select(ActivityLog.changed_at, text("now()")))).one()
    assert changed_at == now


@pytest.mark.parametrize(
    ("update", "constraint"),
    [
        (
            "UPDATE activity_log SET entity_type = 'sprint' WHERE id = :id",
            "ck_activity_log_entity_type",
        ),
        ("UPDATE activity_log SET action = 'moved' WHERE id = :id", "ck_activity_log_action"),
        (
            "UPDATE activity_log SET action = 'updated', field_changed = 'title' WHERE id = :id",
            "ck_activity_log_field_changed",
        ),
    ],
)
async def test_activity_enum_value_outside_the_enum_is_rejected(
    session: AsyncSession, update: str, constraint: str
) -> None:
    entry = await ActivityLogFactory.create_async()

    with pytest.raises(IntegrityError, match=constraint):
        await session.execute(text(update), {"id": entry.id})
