"""`activity_log` constraints and defaults (schema-doc `activity_log`; design-doc §10)."""

from typing import cast

import psycopg
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


# Each copies a valid entry with one value outside its enum: an UPDATE would hit the append-only
# trigger before the CHECK (DL-193).
_COPY = (
    "INSERT INTO activity_log (id, project_id, entity_type, entity_id, action, field_changed) "
    "SELECT gen_random_uuid(), project_id, {entity_type}, entity_id, {action}, {field} "
    "FROM activity_log WHERE id = :id"
)


@pytest.mark.parametrize(
    ("insert", "constraint"),
    [
        (
            _COPY.format(entity_type="'sprint'", action="action", field="field_changed"),
            "ck_activity_log_entity_type",
        ),
        (
            _COPY.format(entity_type="entity_type", action="'moved'", field="field_changed"),
            "ck_activity_log_action",
        ),
        (
            _COPY.format(entity_type="entity_type", action="'updated'", field="'title'"),
            "ck_activity_log_field_changed",
        ),
    ],
)
async def test_activity_enum_value_outside_the_enum_is_rejected(
    session: AsyncSession, insert: str, constraint: str
) -> None:
    entry = await ActivityLogFactory.create_async()

    with pytest.raises(IntegrityError, match=constraint):
        await session.execute(text(insert), {"id": entry.id})


# --- Append-only (DL-193) -------------------------------------------------------------------------


async def test_an_entry_cannot_be_updated(session: AsyncSession) -> None:
    entry = await ActivityLogFactory.create_async(action=ActivityAction.CREATED)

    with pytest.raises(IntegrityError, match="activity_log is append-only: UPDATE") as raised:
        await session.execute(
            text("UPDATE activity_log SET action = 'deleted' WHERE id = :id"), {"id": entry.id}
        )
    # The SQLSTATE the schema doc commits to, as for audit_event: restrict_violation.
    assert cast(psycopg.Error, raised.value.orig).sqlstate == "23001"


async def test_an_entry_cannot_be_edited_through_the_orm(session: AsyncSession) -> None:
    entry = await ActivityLogFactory.create_async(
        action=ActivityAction.UPDATED, field_changed=ActivityField.STATUS, new_value="draft"
    )

    entry.new_value = "approved"
    with pytest.raises(IntegrityError, match="activity_log is append-only: UPDATE"):
        await session.flush()


async def test_an_entry_cannot_be_deleted(session: AsyncSession) -> None:
    entry = await ActivityLogFactory.create_async()

    with pytest.raises(IntegrityError, match="activity_log is append-only: DELETE"):
        await session.execute(text("DELETE FROM activity_log WHERE id = :id"), {"id": entry.id})
