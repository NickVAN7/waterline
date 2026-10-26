"""`approval_request` and `approval` (schema-doc "Approvals"; design-doc §6.2)."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.core.constraint_errors import internal_only
from app.core.enums import enum_type
from app.enums import ApprovalDecision, ApprovalEntityType, ApprovalRequestStatus
from app.models.project import Project
from app.models.requirement import RequirementRevision
from app.models.user import User


class ApprovalRequest(BaseModel):
    __tablename__ = "approval_request"
    __table_args__ = (
        CheckConstraint(
            "entity_type <> 'requirement' OR requirement_revision_id IS NOT NULL",
            name="requirement_revision",
        ),
        # One pending request per entity.
        Index(
            None,
            "entity_type",
            "entity_id",
            unique=True,
            postgresql_where="status = 'pending'",
            # The request endpoints (S2-C10) check first; a clash here is a bug until then.
            info=internal_only(),
        ),
        Index(None, "entity_type", "entity_id", "created_at"),
        # A project's pending requests (DL-192).
        Index(None, "project_id", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(Project.id))
    entity_type: Mapped[ApprovalEntityType] = mapped_column(
        enum_type(ApprovalEntityType, "entity_type")
    )
    # Polymorphic, no FK: the service verifies the entity.
    entity_id: Mapped[uuid.UUID]
    # Named by hand: the convention's name is over Postgres's 63 characters.
    requirement_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(RequirementRevision.id, name="fk_approval_request_requirement_revision_id")
    )
    status: Mapped[ApprovalRequestStatus] = mapped_column(
        enum_type(ApprovalRequestStatus, "status")
    )
    note: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(User.id))
    completed_at: Mapped[datetime | None]

    project: Mapped[Project] = relationship(lazy="raise")
    requester: Mapped[User] = relationship(lazy="raise")


class Approval(BaseModel):
    __tablename__ = "approval"
    __table_args__ = (
        UniqueConstraint(
            "approval_request_id",
            "approver_id",
            info=internal_only(),
        ),
        # "My pending approvals".
        Index(None, "approver_id", "decision"),
    )

    approval_request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(ApprovalRequest.id))
    approver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(User.id))
    decision: Mapped[ApprovalDecision] = mapped_column(enum_type(ApprovalDecision, "decision"))
    comment: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None]

    approval_request: Mapped[ApprovalRequest] = relationship(lazy="raise")
    approver: Mapped[User] = relationship(lazy="raise")
