"""add requirement, approval, and activity log tables (S2-C1)

Revision ID: 73c3d988de78
Revises: a24383c924aa
Create Date: 2026-10-26 18:00:33.581629

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "73c3d988de78"
down_revision: str | Sequence[str] | None = "a24383c924aa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "activity_log",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column(
            "entity_type",
            sa.Enum(
                "requirement",
                "task",
                "testcase",
                "phase",
                "milestone",
                "approval_request",
                "test_result",
                "project",
                name="entity_type",
                native_enum=False,
                create_constraint=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "created",
                "updated",
                "deleted",
                "restored",
                "linked",
                "unlinked",
                name="action",
                native_enum=False,
                create_constraint=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column(
            "field_changed",
            sa.Enum(
                "status",
                "assignee_id",
                "reporter_id",
                "reviewer_id",
                "sprint_id",
                "milestone_id",
                "phase_id",
                "workstream_id",
                "priority",
                "severity",
                "start_date",
                "end_date",
                "due_date",
                "target_date",
                "baseline_start",
                "baseline_end",
                "baseline_date",
                "requirement_id",
                "parent_requirement_id",
                "time_estimate",
                "approved_revision_id",
                "approver_id",
                "restriction_level",
                "restriction_categories",
                "lead_id",
                "actual_result",
                name="field_changed",
                native_enum=False,
                create_constraint=False,
                length=64,
            ),
            nullable=True,
        ),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.Uuid(), nullable=True),
        sa.Column(
            "changed_at",
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
            "action <> 'updated' OR field_changed IS NOT NULL",
            name=op.f("ck_activity_log_updated_has_field"),
        ),
        sa.CheckConstraint(
            "action IN ('created', 'updated', 'deleted', 'restored', 'linked', 'unlinked')",
            name=op.f("ck_activity_log_action"),
        ),
        sa.CheckConstraint(
            (
                "entity_type IN ('requirement', 'task', 'testcase', 'phase', 'milestone', "
                "'approval_request', 'test_result', 'project')"
            ),
            name=op.f("ck_activity_log_entity_type"),
        ),
        sa.CheckConstraint(
            (
                "field_changed IN ('status', 'assignee_id', 'reporter_id', 'reviewer_id', "
                "'sprint_id', 'milestone_id', 'phase_id', 'workstream_id', 'priority', 'severity', "
                "'start_date', 'end_date', 'due_date', 'target_date', 'baseline_start', "
                "'baseline_end', 'baseline_date', 'requirement_id', 'parent_requirement_id', "
                "'time_estimate', 'approved_revision_id', 'approver_id', 'restriction_level', "
                "'restriction_categories', 'lead_id', 'actual_result')"
            ),
            name=op.f("ck_activity_log_field_changed"),
        ),
        sa.ForeignKeyConstraint(
            ["changed_by"], ["user.id"], name=op.f("fk_activity_log_changed_by_user")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_activity_log_project_id_project")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_activity_log")),
    )
    op.create_index(
        op.f("ix_activity_log_entity_type_entity_id_id"),
        "activity_log",
        ["entity_type", "entity_id", "id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_activity_log_project_id_id"), "activity_log", ["project_id", "id"], unique=False
    )
    op.create_table(
        "requirement",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("parent_requirement_id", sa.Uuid(), nullable=True),
        sa.Column("reporter_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description_md", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "approved",
                "in_progress",
                "done",
                "rejected",
                "deferred",
                name="status",
                native_enum=False,
                create_constraint=False,
                length=64,
            ),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum(
                "critical",
                "high",
                "medium",
                "low",
                name="priority",
                native_enum=False,
                create_constraint=False,
                length=64,
            ),
            server_default="medium",
            nullable=False,
        ),
        sa.Column("rank", sa.String(), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=True),
        sa.Column("approved_revision_id", sa.Uuid(), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "restriction_level",
            sa.Enum(
                "internal",
                "confidential",
                name="restriction_level",
                native_enum=False,
                create_constraint=False,
                length=64,
            ),
            nullable=True,
        ),
        sa.Column(
            "restriction_categories",
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
            "priority IN ('critical', 'high', 'medium', 'low')",
            name=op.f("ck_requirement_priority"),
        ),
        sa.CheckConstraint(
            "restriction_categories <@ ARRAY['financial', 'proprietary', 'pii']::text[]",
            name=op.f("ck_requirement_restriction_categories"),
        ),
        sa.CheckConstraint(
            "restriction_level IN ('internal', 'confidential')",
            name=op.f("ck_requirement_restriction_level"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'in_progress', 'done', 'rejected', 'deferred')",
            name=op.f("ck_requirement_status"),
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"], ["user.id"], name=op.f("fk_requirement_approved_by_user")
        ),
        sa.ForeignKeyConstraint(
            ["parent_requirement_id"],
            ["requirement.id"],
            name=op.f("fk_requirement_parent_requirement_id_requirement"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_requirement_project_id_project")
        ),
        sa.ForeignKeyConstraint(
            ["reporter_id"], ["user.id"], name=op.f("fk_requirement_reporter_id_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_requirement")),
        sa.UniqueConstraint("project_id", "number", name=op.f("uq_requirement_project_id_number")),
    )
    op.create_index(
        op.f("ix_requirement_parent_requirement_id"),
        "requirement",
        ["parent_requirement_id"],
        unique=False,
    )
    op.create_table(
        "requirement_revision",
        sa.Column("requirement_id", sa.Uuid(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description_md", sa.Text(), nullable=False),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
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
            ["created_by"], ["user.id"], name=op.f("fk_requirement_revision_created_by_user")
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id"],
            ["requirement.id"],
            name=op.f("fk_requirement_revision_requirement_id_requirement"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_requirement_revision")),
        sa.UniqueConstraint(
            "requirement_id",
            "revision_number",
            name=op.f("uq_requirement_revision_requirement_id_revision_number"),
        ),
    )
    # requirement's revision FKs are circular with requirement_revision.requirement_id, so they
    # go on once both tables exist (schema-doc `requirement`).
    op.create_foreign_key(
        op.f("fk_requirement_current_revision_id_requirement_revision"),
        "requirement",
        "requirement_revision",
        ["current_revision_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_requirement_approved_revision_id_requirement_revision"),
        "requirement",
        "requirement_revision",
        ["approved_revision_id"],
        ["id"],
    )
    op.create_table(
        "approval_request",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column(
            "entity_type",
            sa.Enum(
                "requirement",
                "milestone",
                "test_run",
                name="entity_type",
                native_enum=False,
                create_constraint=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_revision_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "approved",
                "rejected",
                "cancelled",
                name="status",
                native_enum=False,
                create_constraint=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            "entity_type <> 'requirement' OR requirement_revision_id IS NOT NULL",
            name=op.f("ck_approval_request_requirement_revision"),
        ),
        sa.CheckConstraint(
            "entity_type IN ('requirement', 'milestone', 'test_run')",
            name=op.f("ck_approval_request_entity_type"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name=op.f("ck_approval_request_status"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_approval_request_project_id_project")
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["user.id"], name=op.f("fk_approval_request_requested_by_user")
        ),
        sa.ForeignKeyConstraint(
            ["requirement_revision_id"],
            ["requirement_revision.id"],
            name="fk_approval_request_requirement_revision_id",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approval_request")),
    )
    op.create_index(
        op.f("ix_approval_request_entity_type_entity_id"),
        "approval_request",
        ["entity_type", "entity_id"],
        unique=True,
        postgresql_where="status = 'pending'",
    )
    op.create_index(
        op.f("ix_approval_request_entity_type_entity_id_created_at"),
        "approval_request",
        ["entity_type", "entity_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_request_project_id_status"),
        "approval_request",
        ["project_id", "status"],
        unique=False,
    )
    op.create_table(
        "approval",
        sa.Column("approval_request_id", sa.Uuid(), nullable=False),
        sa.Column("approver_id", sa.Uuid(), nullable=False),
        sa.Column(
            "decision",
            sa.Enum(
                "pending",
                "approved",
                "rejected",
                "replaced",
                name="decision",
                native_enum=False,
                create_constraint=False,
                length=64,
            ),
            nullable=False,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
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
            "decision IN ('pending', 'approved', 'rejected', 'replaced')",
            name=op.f("ck_approval_decision"),
        ),
        sa.ForeignKeyConstraint(
            ["approval_request_id"],
            ["approval_request.id"],
            name=op.f("fk_approval_approval_request_id_approval_request"),
        ),
        sa.ForeignKeyConstraint(
            ["approver_id"], ["user.id"], name=op.f("fk_approval_approver_id_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approval")),
        sa.UniqueConstraint(
            "approval_request_id",
            "approver_id",
            name=op.f("uq_approval_approval_request_id_approver_id"),
        ),
    )
    op.create_index(
        op.f("ix_approval_approver_id_decision"),
        "approval",
        ["approver_id", "decision"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_approval_approver_id_decision"), table_name="approval")
    op.drop_table("approval")
    op.drop_index(op.f("ix_approval_request_project_id_status"), table_name="approval_request")
    op.drop_index(
        op.f("ix_approval_request_entity_type_entity_id_created_at"), table_name="approval_request"
    )
    op.drop_index(
        op.f("ix_approval_request_entity_type_entity_id"),
        table_name="approval_request",
        postgresql_where="status = 'pending'",
    )
    op.drop_table("approval_request")
    op.drop_constraint(
        op.f("fk_requirement_approved_revision_id_requirement_revision"),
        "requirement",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_requirement_current_revision_id_requirement_revision"),
        "requirement",
        type_="foreignkey",
    )
    op.drop_table("requirement_revision")
    op.drop_index(op.f("ix_requirement_parent_requirement_id"), table_name="requirement")
    op.drop_table("requirement")
    op.drop_index(op.f("ix_activity_log_project_id_id"), table_name="activity_log")
    op.drop_index(op.f("ix_activity_log_entity_type_entity_id_id"), table_name="activity_log")
    op.drop_table("activity_log")
