"""`audit_event` (schema-doc "Audit"; design-doc §10.1). Only `log_admin_event()` writes it;
rows are append-only."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel
from app.core.enums import enum_type
from app.enums import AuditAction, AuditEntityType
from app.models.org import Organization
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace


class AuditEvent(BaseModel):
    __tablename__ = "audit_event"
    __table_args__ = (
        # Feeds page by id (UUIDv7, creation order), per scope.
        Index(None, "workspace_id", "id"),
        Index(None, "organization_id", "id"),
        Index(None, "project_id", "id"),
        Index(None, "target_user_id", "id"),
    )

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(Workspace.id))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(Organization.id))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(Project.id))
    action: Mapped[AuditAction] = mapped_column(enum_type(AuditAction, "action"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(User.id))
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(User.id))
    entity_type: Mapped[AuditEntityType | None] = mapped_column(
        enum_type(AuditEntityType, "entity_type")
    )
    entity_id: Mapped[uuid.UUID | None]
    details: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # The transaction's start time, as for created_at; log_admin_event() never sets it.
    occurred_at: Mapped[datetime] = mapped_column(server_default=func.now())
