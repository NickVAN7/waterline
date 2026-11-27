"""add project get_started_hidden

Revision ID: c3f1e7a2d915
Revises: b644f1a775f5
Create Date: 2026-11-26 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f1e7a2d915"
down_revision: str | Sequence[str] | None = "b644f1a775f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOT NULL is safe on existing rows: the server default fills them.
    op.add_column(
        "project",
        sa.Column(
            "get_started_hidden", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("project", "get_started_hidden")
