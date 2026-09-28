"""The base model's columns and naming convention, against real Postgres."""

from datetime import datetime

import pytest
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.support.models import Gadget, Widget

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("support_tables")]


async def test_id_is_known_before_flush_and_stored_as_given(session: AsyncSession) -> None:
    widget = Widget(name="a")
    before_flush = widget.id

    session.add(widget)
    await session.flush()

    stored = await session.scalar(text("SELECT id FROM support_widget"))
    assert stored == before_flush


async def test_timestamps_are_timestamptz(session: AsyncSession) -> None:
    rows = await session.execute(
        text(
            "SELECT column_name, data_type FROM information_schema.columns"
            " WHERE table_name = 'support_widget'"
            " AND column_name IN ('created_at', 'updated_at')"
        )
    )

    assert dict(rows.all()) == {
        "created_at": "timestamp with time zone",
        "updated_at": "timestamp with time zone",
    }


async def test_timestamps_are_set_by_the_database_and_readable_after_commit(
    session: AsyncSession,
) -> None:
    widget = Widget(name="a")
    session.add(widget)
    await session.commit()

    # Readable without a lazy load: eager_defaults + expire_on_commit=False.
    assert isinstance(widget.created_at, datetime)
    assert widget.created_at.tzinfo is not None
    assert widget.updated_at == widget.created_at


async def test_updated_at_moves_on_update_and_created_at_does_not(session: AsyncSession) -> None:
    widget = Widget(name="a")
    session.add(widget)
    await session.flush()
    # now() is fixed within a transaction, so backdate the row to see updated_at move.
    await session.execute(
        update(Widget)
        .where(Widget.id == widget.id)
        .values(
            created_at=text("now() - interval '1 day'"),
            updated_at=text("now() - interval '1 day'"),
        )
        .execution_options(synchronize_session=False)
    )
    await session.refresh(widget)
    created = widget.created_at

    widget.quantity = 5
    await session.flush()

    assert widget.created_at == created
    assert widget.updated_at > created


async def test_constraints_follow_the_naming_convention(session: AsyncSession) -> None:
    constraints = await session.scalars(
        text(
            "SELECT conname FROM pg_constraint"
            " WHERE conrelid IN ('support_widget'::regclass, 'support_gadget'::regclass)"
            " AND contype <> 'n'"  # Postgres 18+ also lists NOT NULL as constraints
        )
    )
    indexes = await session.scalars(
        text("SELECT indexname FROM pg_indexes WHERE tablename = 'support_widget'")
    )

    assert set(constraints.all()) == {
        "pk_support_widget",
        "uq_support_widget_name",
        "ck_support_widget_quantity_not_negative",
        "pk_support_gadget",
        "fk_support_gadget_widget_id_support_widget",
    }
    assert set(indexes.all()) == {
        "pk_support_widget",
        "uq_support_widget_name",
        "ix_support_widget_quantity",
    }


async def test_child_can_reference_parent_id_before_the_parent_is_flushed(
    session: AsyncSession,
) -> None:
    widget = Widget(name="a")
    gadget = Gadget(widget_id=widget.id)  # the parent's id is known before any flush

    session.add(widget)
    await session.flush()
    session.add(gadget)
    await session.flush()

    assert await session.scalar(text("SELECT count(*) FROM support_gadget")) == 1
