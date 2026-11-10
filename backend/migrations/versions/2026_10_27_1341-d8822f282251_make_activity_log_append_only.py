"""make activity_log append-only

Revision ID: d8822f282251
Revises: 73c3d988de78
Create Date: 2026-10-27 13:41:52.739577

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8822f282251"
down_revision: str | Sequence[str] | None = "73c3d988de78"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Written by hand: autogenerate doesn't see functions or triggers. A copy of audit_event's
# (schema-doc `activity_log`, "Append-only"; DL-193). TRUNCATE is a separate trigger event, so
# test cleanup still works.


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE FUNCTION activity_log_append_only() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'activity_log is append-only: % is not allowed', TG_OP
                USING ERRCODE = 'restrict_violation';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER tr_activity_log_append_only
        BEFORE UPDATE OR DELETE ON activity_log
        FOR EACH ROW EXECUTE FUNCTION activity_log_append_only()
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER tr_activity_log_append_only ON activity_log")
    op.execute("DROP FUNCTION activity_log_append_only()")
