"""rename classification to restriction and drop unshipped modules

Revision ID: a24383c924aa
Revises: 950169fd7ea9
Create Date: 2026-10-23 08:39:12.435389

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a24383c924aa"
down_revision: str | Sequence[str] | None = "950169fd7ea9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Written by hand: autogenerate sees the rename as a drop and an add, which loses the data, and
# doesn't see CHECK changes. DL-134 (the rename, `restricted` removed) and DL-136 (no project
# keeps a module that hasn't shipped).

# `audit_event.action`'s values, but for the one being renamed.
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
    "project_member_added",
    "project_member_role_changed",
    "project_member_removed",
)
_OLD_ACTION = "project_classification_changed"
_NEW_ACTION = "project_restriction_changed"


def _action_check(renamed: str) -> str:
    return "action IN (" + ", ".join(f"'{a}'" for a in (*_ACTIONS, renamed)) + ")"


def _rewrite_audit_actions(old: str, new: str) -> None:
    """Rename the action on existing `audit_event` rows (dev data only, DL-134), the append-only
    trigger off for this statement alone."""
    op.drop_constraint(op.f("ck_audit_event_action"), "audit_event", type_="check")
    op.execute("ALTER TABLE audit_event DISABLE TRIGGER tr_audit_event_append_only")
    op.execute(
        sa.text("UPDATE audit_event SET action = :new WHERE action = :old").bindparams(
            new=new, old=old
        )
    )
    op.execute("ALTER TABLE audit_event ENABLE TRIGGER tr_audit_event_append_only")
    op.create_check_constraint(op.f("ck_audit_event_action"), "audit_event", _action_check(new))


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(op.f("ck_project_classification_level"), "project", type_="check")
    op.execute(
        "UPDATE project SET classification_level = 'confidential'"
        " WHERE classification_level = 'restricted'"
    )
    op.alter_column("project", "classification_level", new_column_name="restriction_level")
    op.alter_column(
        "project", "classification_categories", new_column_name="restriction_categories"
    )
    op.create_check_constraint(
        op.f("ck_project_restriction_level"),
        "project",
        "restriction_level IN ('internal', 'confidential')",
    )
    # Postgres rewrites the CHECK's column reference itself; only the name changes.
    op.execute(
        "ALTER TABLE project RENAME CONSTRAINT ck_project_classification_categories"
        " TO ck_project_restriction_categories"
    )
    _rewrite_audit_actions(_OLD_ACTION, _NEW_ACTION)
    op.execute(
        "UPDATE project"
        " SET enabled_modules = array_remove(array_remove(enabled_modules, 'sprints'), 'github')"
    )


def downgrade() -> None:
    """Downgrade schema. The modules removed and the `restricted` levels mapped to
    `confidential` can't be told apart afterwards, so only the schema comes back."""
    _rewrite_audit_actions(_NEW_ACTION, _OLD_ACTION)
    op.execute(
        "ALTER TABLE project RENAME CONSTRAINT ck_project_restriction_categories"
        " TO ck_project_classification_categories"
    )
    op.drop_constraint(op.f("ck_project_restriction_level"), "project", type_="check")
    op.alter_column(
        "project", "restriction_categories", new_column_name="classification_categories"
    )
    op.alter_column("project", "restriction_level", new_column_name="classification_level")
    op.create_check_constraint(
        op.f("ck_project_classification_level"),
        "project",
        "classification_level IN ('internal', 'confidential', 'restricted')",
    )
