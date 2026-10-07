"""add tenancy, project, and audit tables

Revision ID: 2674631cba1a
Revises: 65cb8ec68b54
Create Date: 2026-10-07 10:55:27.731864

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "2674631cba1a"
down_revision: str | Sequence[str] | None = "65cb8ec68b54"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Reviewed by hand (migration skill). Enum columns use create_constraint=False: each enum's
    # CHECK is the named `ck_<table>_<column>` constraint listed with its table, so it isn't
    # created twice (autogenerate also emitted copies under ad-hoc names, which were removed).
    op.create_table(
        "user",
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_system_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "must_change_password", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_user_email_lowercase")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user")),
        sa.UniqueConstraint("email", name=op.f("uq_user_email")),
        sa.UniqueConstraint("username", name=op.f("uq_user_username")),
    )
    op.create_table(
        "workspace",
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace")),
        sa.UniqueConstraint("slug", name=op.f("uq_workspace_slug")),
    )
    op.create_table(
        "organization",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspace.id"], name=op.f("fk_organization_workspace_id_workspace")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organization")),
        sa.UniqueConstraint("id", "workspace_id", name=op.f("uq_organization_id_workspace_id")),
        sa.UniqueConstraint("workspace_id", "slug", name=op.f("uq_organization_workspace_id_slug")),
    )
    op.create_index(
        op.f("ix_organization_workspace_id"), "organization", ["workspace_id"], unique=False
    )
    op.create_table(
        "session",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], name=op.f("fk_session_user_id_user")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_session")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_session_token_hash")),
    )
    op.create_table(
        "workspace_membership",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "owner",
                "admin",
                "member",
                name="role",
                native_enum=False,
                create_constraint=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'member')", name=op.f("ck_workspace_membership_role")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name=op.f("fk_workspace_membership_user_id_user")
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspace.id"],
            name=op.f("fk_workspace_membership_workspace_id_workspace"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_membership")),
        sa.UniqueConstraint(
            "workspace_id", "user_id", name=op.f("uq_workspace_membership_workspace_id_user_id")
        ),
    )
    op.create_index(
        op.f("ix_workspace_membership_user_id"), "workspace_membership", ["user_id"], unique=False
    )
    op.create_table(
        "membership",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "owner",
                "admin",
                "member",
                name="role",
                native_enum=False,
                create_constraint=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('owner', 'admin', 'member')", name=op.f("ck_membership_role")),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_membership_organization_id_organization"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], name=op.f("fk_membership_user_id_user")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_membership")),
        sa.UniqueConstraint(
            "user_id", "organization_id", name=op.f("uq_membership_user_id_organization_id")
        ),
    )
    op.create_table(
        "project",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "type",
            sa.Enum(
                "software",
                "erp",
                "general",
                name="type",
                native_enum=False,
                create_constraint=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "planning",
                "active",
                "on_hold",
                "completed",
                "cancelled",
                name="status",
                native_enum=False,
                create_constraint=False,
                length=64,
            ),
            server_default="planning",
            nullable=False,
        ),
        sa.Column("lead_id", sa.Uuid(), nullable=True),
        sa.Column("enabled_modules", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "classification_level",
            sa.Enum(
                "internal",
                "confidential",
                "restricted",
                name="classification_level",
                native_enum=False,
                create_constraint=False,
                length=64,
            ),
            nullable=True,
        ),
        sa.Column(
            "classification_categories",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "classification_categories <@ ARRAY['financial', 'proprietary', 'pii', "
                "'export_controlled']::text[]"
            ),
            name=op.f("ck_project_classification_categories"),
        ),
        sa.CheckConstraint(
            "classification_level IN ('internal', 'confidential', 'restricted')",
            name=op.f("ck_project_classification_level"),
        ),
        sa.CheckConstraint(
            "enabled_modules <@ ARRAY['sprints', 'github']::text[]",
            name=op.f("ck_project_enabled_modules"),
        ),
        sa.CheckConstraint(
            "status IN ('planning', 'active', 'on_hold', 'completed', 'cancelled')",
            name=op.f("ck_project_status"),
        ),
        sa.CheckConstraint("type IN ('software', 'erp', 'general')", name=op.f("ck_project_type")),
        sa.ForeignKeyConstraint(["lead_id"], ["user.id"], name=op.f("fk_project_lead_id_user")),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["organization.id", "organization.workspace_id"],
            name=op.f("fk_project_organization_id_organization"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project")),
        sa.UniqueConstraint("workspace_id", "key", name=op.f("uq_project_workspace_id_key")),
    )
    op.create_table(
        "audit_event",
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column(
            "action",
            sa.Enum(
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
                "project_classification_changed",
                "project_member_added",
                "project_member_role_changed",
                "project_member_removed",
                name="action",
                native_enum=False,
                create_constraint=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("target_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "entity_type",
            sa.Enum(
                "workspace",
                "organization",
                "project",
                "user",
                name="entity_type",
                native_enum=False,
                create_constraint=False,
                length=64,
            ),
            nullable=True,
        ),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "action IN ('workspace_created', 'user_created', 'user_deactivated', "
                "'user_reactivated', 'password_reset', 'password_changed', "
                "'signed_out_everywhere', 'user_updated', 'system_admin_granted', "
                "'system_admin_revoked', 'workspace_updated', 'workspace_member_added', "
                "'workspace_member_role_changed', "
                "'workspace_member_removed', 'org_created', 'org_updated', 'org_member_added', "
                "'org_member_role_changed', 'org_member_removed', 'project_created', "
                "'project_updated', 'project_archived', 'project_unarchived', "
                "'project_classification_changed', 'project_member_added', "
                "'project_member_role_changed', 'project_member_removed')"
            ),
            name=op.f("ck_audit_event_action"),
        ),
        sa.CheckConstraint(
            "entity_type IN ('workspace', 'organization', 'project', 'user')",
            name=op.f("ck_audit_event_entity_type"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["user.id"], name=op.f("fk_audit_event_actor_id_user")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_audit_event_organization_id_organization"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_audit_event_project_id_project")
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"], ["user.id"], name=op.f("fk_audit_event_target_user_id_user")
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspace.id"], name=op.f("fk_audit_event_workspace_id_workspace")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_event")),
    )
    op.create_index(
        op.f("ix_audit_event_organization_id_id"),
        "audit_event",
        ["organization_id", "id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_event_project_id_id"), "audit_event", ["project_id", "id"], unique=False
    )
    op.create_index(
        op.f("ix_audit_event_target_user_id_id"),
        "audit_event",
        ["target_user_id", "id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_event_workspace_id_id"), "audit_event", ["workspace_id", "id"], unique=False
    )
    op.create_table(
        "project_counter",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("prefix", sa.String(), nullable=False),
        sa.Column("next_value", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_project_counter_project_id_project")
        ),
        sa.PrimaryKeyConstraint("project_id", "prefix", name=op.f("pk_project_counter")),
    )
    op.create_table(
        "project_membership",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "admin",
                "member",
                "viewer",
                name="role",
                native_enum=False,
                create_constraint=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('admin', 'member', 'viewer')", name=op.f("ck_project_membership_role")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_project_membership_project_id_project")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name=op.f("fk_project_membership_user_id_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_membership")),
        sa.UniqueConstraint(
            "project_id", "user_id", name=op.f("uq_project_membership_project_id_user_id")
        ),
    )
    op.create_index(
        op.f("ix_project_membership_user_id"), "project_membership", ["user_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_project_membership_user_id"), table_name="project_membership")
    op.drop_table("project_membership")
    op.drop_table("project_counter")
    op.drop_index(op.f("ix_audit_event_workspace_id_id"), table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_target_user_id_id"), table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_project_id_id"), table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_organization_id_id"), table_name="audit_event")
    op.drop_table("audit_event")
    op.drop_table("project")
    op.drop_table("membership")
    op.drop_index(op.f("ix_workspace_membership_user_id"), table_name="workspace_membership")
    op.drop_table("workspace_membership")
    op.drop_table("session")
    op.drop_index(op.f("ix_organization_workspace_id"), table_name="organization")
    op.drop_table("organization")
    op.drop_table("workspace")
    op.drop_table("user")
