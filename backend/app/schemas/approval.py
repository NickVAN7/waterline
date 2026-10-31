"""Approval requests (design-doc §6.2; build plan, S2-C10)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.authz.actions import Action
from app.enums import ApprovalDecision, ApprovalEntityType, ApprovalRequestStatus
from app.schemas.limits import APPROVAL_NOTE_MAX, APPROVERS_MAX


class ApprovalRequestCreate(BaseModel):
    """A request bound to the requirement's current revision. `approver_ids`: 1 to 50 distinct
    users with access to the project (a repeat is a 422 `duplicate`, someone without access a
    404, a deactivated one a 422 `account_inactive`; DL-226)."""

    approver_ids: list[uuid.UUID] = Field(min_length=1, max_length=APPROVERS_MAX)
    note: str | None = Field(default=None, max_length=APPROVAL_NOTE_MAX)


class ApprovalDecisionCreate(BaseModel):
    """The caller's decision on their own row (design-doc §6.2): final (DL-195). A comment is
    optional, rejecting included (DL-196: the UI asks to confirm without one)."""

    decision: Literal[ApprovalDecision.APPROVED, ApprovalDecision.REJECTED]
    comment: str | None = Field(default=None, max_length=APPROVAL_NOTE_MAX)


class ApprovalRead(BaseModel):
    """One approver's row; `approver_is_active` false shows the "Deactivated" badge."""

    id: uuid.UUID
    approver_id: uuid.UUID
    approver_name: str
    approver_is_active: bool
    decision: ApprovalDecision
    comment: str | None
    decided_at: datetime | None


class ApprovalRequestItem(BaseModel):
    """A request on the requirement's list, newest first (DL-227), with its approvers."""

    id: uuid.UUID
    status: ApprovalRequestStatus
    requirement_revision_id: uuid.UUID
    revision_number: int
    note: str | None
    requested_by_id: uuid.UUID
    requested_by_name: str
    requested_by_is_active: bool
    created_at: datetime
    completed_at: datetime | None
    # The UI warns approvers when the requirement has a newer revision (design-doc §6.2, "Stale
    # requests").
    newer_revision_exists: bool
    approvals: list[ApprovalRead]


class ApprovalRequestRead(ApprovalRequestItem):
    """One request, with the actions the caller may take on it."""

    allowed_actions: list[Action]


class ApprovalWorkItem(BaseModel):
    """One of the caller's pending approvals, in My work (design-doc §11; DL-236): `title` and
    `revision_number` are the revision under approval's, whatever the requirement is now."""

    request_id: uuid.UUID
    requested_at: datetime
    requested_by_id: uuid.UUID
    requested_by_name: str
    note: str | None
    entity_type: ApprovalEntityType
    entity_number: int
    title: str
    revision_number: int
    project_key: str
    project_name: str
    organization_slug: str
