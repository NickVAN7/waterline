"""add session user agent and signed out other sessions

Revision ID: d8cd57d53e43
Revises: d8822f282251
Create Date: 2026-11-06 11:54:03.105455

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8cd57d53e43"
down_revision: str | Sequence[str] | None = "d8822f282251"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# The actions before this migration (DL-300 adds `signed_out_other_sessions`).
_ACTIONS = (
    "workspace_created",
    "user_created",
    "user_deactivated",
    "user_reactivated",
    "password_reset",
    "password_changed",
    "signed_out_everywhere",
    "user_updated",
    "system_admin_granted",
    "system_admin_revoked",
    "workspace_updated",
    "workspace_member_added",
    "workspace_member_role_changed",
    "workspace_member_removed",
    "org_created",
    "org_updated",
    "org_member_added",
    "org_member_role_changed",
    "org_member_removed",
    "project_created",
    "project_updated",
    "project_archived",
    "project_unarchived",
    "project_restriction_changed",
    "project_member_added",
    "project_member_role_changed",
    "project_member_removed",
)
_NEW_ACTION = "signed_out_other_sessions"


def _set_actions(actions: tuple[str, ...]) -> None:
    op.drop_constraint(op.f("ck_audit_event_action"), "audit_event", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_event_action"),
        "audit_event",
        "action IN (" + ", ".join(f"'{a}'" for a in actions) + ")",
    )


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("session", sa.Column("user_agent", sa.String(length=512), nullable=True))
    _set_actions((*_ACTIONS, _NEW_ACTION))


def downgrade() -> None:
    """Downgrade schema. The new action's events can't be kept under the old CHECK, so the
    downgrade fails while any exist (the table is append-only)."""
    _set_actions(_ACTIONS)
    op.drop_column("session", "user_agent")
