"""make audit_event append-only

Revision ID: de363d1a3629
Revises: 2674631cba1a
Create Date: 2026-10-07 12:25:57.469977

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "de363d1a3629"
down_revision: str | Sequence[str] | None = "2674631cba1a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Written by hand: autogenerate doesn't see functions or triggers (schema-doc `audit_event`,
# "Append-only"; owner decision, Oct 7, 2026). TRUNCATE is a separate trigger event, so test
# cleanup still works.


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE FUNCTION audit_event_append_only() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_event is append-only: % is not allowed', TG_OP
                USING ERRCODE = 'restrict_violation';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER tr_audit_event_append_only
        BEFORE UPDATE OR DELETE ON audit_event
        FOR EACH ROW EXECUTE FUNCTION audit_event_append_only()
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER tr_audit_event_append_only ON audit_event")
    op.execute("DROP FUNCTION audit_event_append_only()")
