"""A requirement's approval requests (design-doc §6.2): request, decide, approve by hand, cancel,
and read, with the requirement area's approved and rejected handlers. Split from
`requirement.py` (the handoff's Package 5 item 4, S3-C0w): a subclass, so its methods keep the
requirement service's locks, logging, and person check."""

import dataclasses
import uuid
from datetime import UTC, datetime
from typing import cast

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actions import Action
from app.authz.authorize import allowed_actions, authorize, ensure
from app.authz.context import AuthzContext
from app.authz.target import Target, project_target
from app.core.base_model import check_version
from app.core.errors import NotFoundError, ValidationFailedError
from app.core.lists import ListSpec, Page, fetch_page
from app.enums import (
    ActivityAction,
    ActivityField,
    ApprovalEntityType,
    ApprovalRequestStatus,
    RequirementStatus,
)
from app.models.approval import ApprovalRequest
from app.models.project import Project
from app.models.requirement import Requirement, RequirementRevision
from app.repositories.approval import ApprovalRepository
from app.repositories.base import get_by_id
from app.repositories.project import ProjectRepository
from app.rules.approval_policy import status_after_rejection
from app.schemas.approval import (
    ApprovalDecisionCreate,
    ApprovalRead,
    ApprovalRequestCreate,
    ApprovalRequestItem,
    ApprovalRequestRead,
)
from app.schemas.requirement import (
    RequirementApprove,
    RequirementRead,
)
from app.services.approval import ApprovalService, register_on_approved, register_on_rejected
from app.services.requirement import RequirementService

# A requirement's approval requests: newest first, offset-paged (DL-227).
APPROVAL_REQUESTS = ListSpec(
    name="ApprovalRequestItem",
    id_column=ApprovalRequest.id,  # pyright: ignore[reportArgumentType]
    sorts={"created_at": ApprovalRequest.created_at},  # pyright: ignore[reportArgumentType]
    default_sort=("-created_at",),
)


class RequirementApprovalService(RequirementService):
    async def load_approval_request(
        self, request_id: uuid.UUID
    ) -> tuple[ApprovalRequest, Target] | None:
        """The request, as a target on its live requirement inside its project; None for a
        deleted requirement's (DL-228)."""
        loaded = await self._load_request(request_id)
        if loaded is None:
            return None
        request, requirement, project = loaded
        return request, project_target(project, requirement)

    async def _load_request(
        self, request_id: uuid.UUID
    ) -> tuple[ApprovalRequest, Requirement, Project] | None:
        request = await ApprovalRepository(self.session).get(request_id)
        if request is None or request.entity_type is not ApprovalEntityType.REQUIREMENT:
            return None
        requirement = await get_by_id(self.session, Requirement, request.entity_id)
        if requirement is None:
            return None
        return request, requirement, await self._project(requirement)

    async def load_approval_request_to_decide(
        self, request_id: uuid.UUID
    ) -> tuple[ApprovalRequest, Target] | None:
        """The request on a live requirement, as a target whose entity is the request with its
        rows, for `approval.decide`'s relationship (the named approver's own pending row)."""
        loaded = await self._load_request(request_id)
        if loaded is None:
            return None
        request, _, project = loaded
        return request, project_target(project, request)

    async def decide(
        self, ctx: AuthzContext, request: ApprovalRequest, body: ApprovalDecisionCreate
    ) -> ApprovalRequestRead:
        """The caller's decision on their own row (final, DL-195); 422 `not_pending` for a request
        that isn't pending (DL-230). The policy then completes or rejects the request (design-doc
        §6.2): completion runs the requirement's `on_approved` handler; a rejected re-open round
        moves it back to `draft`."""
        requirement, project = await self._request_entities(request)
        # Project, requirement, then request: the order a delete takes them, so neither waits on
        # the other in a cycle; the rule checked again under them.
        await ProjectRepository(self.session).hold(project)
        await self._lock_live(requirement)
        approvals = ApprovalService(self.session)
        request = await approvals.lock(request)
        # The caller's access read again, whole: a removal, role change, revocation, or
        # deactivation takes the project's lock first, so one that committed while this waited,
        # leaving their row pending, is seen (TD-82).
        ctx = await self._current_context(ctx)
        ensure(ctx, Action.APPROVAL_DECIDE, project_target(project, request))
        await approvals.decide(request, ctx.user_id, body.decision, body.comment)
        return await self._read_approval_request(
            ctx, request.id, project_target(project, requirement)
        )

    async def approve(
        self, ctx: AuthzContext, requirement: Requirement, body: RequirementApprove
    ) -> RequirementRead:
        """Approve by hand (design-doc §5): the current revision, by the caller, now; a pending
        request cancelled. 409 on a stale `version` (DL-169)."""
        project = await self._project(requirement)
        await ProjectRepository(self.session).hold(project)
        await self._lock_live(requirement)
        target = project_target(project, requirement)
        ensure(ctx, Action.REQUIREMENT_APPROVE_MANUALLY, target)
        check_version(requirement, body.version)
        # A foreign key set at creation, so never None (design-doc §6.1).
        revision_id = cast(uuid.UUID, requirement.current_revision_id)
        self._record_approval(requirement, revision_id, ctx.user_id, RequirementStatus.APPROVED)
        await self.session.flush()
        await ApprovalService(self.session).cancel_pending(
            ApprovalEntityType.REQUIREMENT, [requirement.id], ctx.user_id
        )
        return await self.read(ctx, requirement)

    async def complete_approval(self, request: ApprovalRequest, approver_id: uuid.UUID) -> None:
        """A completed request (design-doc §6.2): its revision approved by the approver whose
        decision completed it, when it completed; only a `draft` requirement moves to `approved`
        (DL-148). The decision holds the requirement's lock; a replacement holds the project's,
        which every requirement write takes first."""
        requirement = cast(Requirement, await self.session.get(Requirement, request.entity_id))
        status = (
            RequirementStatus.APPROVED
            if requirement.status is RequirementStatus.DRAFT
            else requirement.status
        )
        revision_id = cast(uuid.UUID, request.requirement_revision_id)
        # Approved when the request completed (schema-doc `requirement`), the same instant.
        self._record_approval(
            requirement, revision_id, approver_id, status, at=cast(datetime, request.completed_at)
        )

    async def reject_approval(self, request: ApprovalRequest, actor_id: uuid.UUID) -> None:
        """A rejected request: a re-open round moves the requirement back to `draft`, logged;
        anything else changes nothing (DL-195)."""
        requirement = cast(Requirement, await self.session.get(Requirement, request.entity_id))
        old = requirement.status
        new = status_after_rejection(
            old, requirement.approved_revision_id, cast(uuid.UUID, request.requirement_revision_id)
        )
        if new is not old:
            requirement.status = new
            self._log(requirement, actor_id, ActivityAction.UPDATED, ActivityField.STATUS, old, new)

    def _record_approval(
        self,
        requirement: Requirement,
        revision_id: uuid.UUID,
        approved_by: uuid.UUID,
        status: RequirementStatus,
        *,
        at: datetime | None = None,
    ) -> None:
        """`approved_revision_id`, `approved_by`, and `approved_at`, and the status; the revision
        and the status logged when they change (§10), as `approved_by`."""
        changes = [
            (ActivityField.STATUS, requirement.status, status),
            (ActivityField.APPROVED_REVISION_ID, requirement.approved_revision_id, revision_id),
        ]
        requirement.status = status
        requirement.approved_revision_id = revision_id
        requirement.approved_by = approved_by
        requirement.approved_at = at or datetime.now(UTC)
        for field, old, new in changes:
            if old != new:
                self._log(requirement, approved_by, ActivityAction.UPDATED, field, old, new)

    async def request_approval(
        self, ctx: AuthzContext, requirement: Requirement, body: ApprovalRequestCreate
    ) -> ApprovalRequestRead:
        """A request bound to the current revision, one pending at a time (DL-225, DL-229),
        naming eligible approvers (DL-226); logged `created`."""
        if len(set(body.approver_ids)) < len(body.approver_ids):
            raise ValidationFailedError.on(
                ("body", "approver_ids"), "Name each approver once.", "duplicate"
            )
        # The project held first (the order every requirement path takes), so an archive or an
        # export-control change meanwhile waits, and the check runs again under it.
        project = await self._project(requirement)
        await ProjectRepository(self.session).hold(project)
        # Then the requirement, so two creates (or a create and a delete) take turns (DL-229).
        await self._lock_live(requirement)
        target = project_target(project, requirement)
        ensure(ctx, Action.APPROVAL_REQUEST_CREATE, target)
        for approver_id in body.approver_ids:
            await self._check_person(
                target, approver_id, Action.REQUIREMENT_VIEW, "approver_ids", NotFoundError()
            )
        request = await ApprovalService(self.session).create(
            project_id=project.id,
            entity_type=ApprovalEntityType.REQUIREMENT,
            entity_id=requirement.id,
            requirement_revision_id=requirement.current_revision_id,
            approver_ids=body.approver_ids,
            note=body.note,
            actor_id=ctx.user_id,
        )
        return await self._read_approval_request(ctx, request.id, target)

    async def approval_requests(
        self, requirement: Requirement, query: BaseModel
    ) -> Page[ApprovalRequestItem]:
        """The requirement's approval requests, newest first (DL-227)."""
        page = await fetch_page(
            self.session,
            ApprovalRepository(self.session).for_entity(
                ApprovalEntityType.REQUIREMENT, requirement.id
            ),
            APPROVAL_REQUESTS,
            query,
        )
        flagged = await ApprovalService(self.session).flagged(
            await self._project(requirement), page.items
        )
        return Page[ApprovalRequestItem](
            items=[
                _approval_request(row, requirement.current_revision_id, row.id in flagged)
                for row in page.items
            ],
            total=page.total,
            limit=page.limit,
            offset=page.offset,
        )

    async def read_approval_request(
        self, ctx: AuthzContext, request: ApprovalRequest
    ) -> ApprovalRequestRead:
        """The request, with the actions the caller may take on it."""
        requirement, project = await self._request_entities(request)
        return await self._read_approval_request(
            ctx, request.id, project_target(project, requirement)
        )

    async def cancel_approval_request(
        self, ctx: AuthzContext, request: ApprovalRequest
    ) -> ApprovalRequestRead:
        """Cancel a pending request, logged (`status`); 422 `not_pending` otherwise (DL-228)."""
        requirement, project = await self._request_entities(request)
        # Held and checked again, as the create is: an export-control change meanwhile waits.
        await ProjectRepository(self.session).hold(project)
        target = project_target(project, requirement)
        ensure(ctx, Action.APPROVAL_REQUEST_CANCEL, target)
        await ApprovalService(self.session).cancel(request, ctx.user_id)
        return await self._read_approval_request(ctx, request.id, target)

    async def _request_entities(self, request: ApprovalRequest) -> tuple[Requirement, Project]:
        # The loader's requirement and project, identity-map hits.
        requirement = cast(Requirement, await self.session.get(Requirement, request.entity_id))
        return requirement, await self._project(requirement)

    async def _read_approval_request(
        self, ctx: AuthzContext, request_id: uuid.UUID, target: Target
    ) -> ApprovalRequestRead:
        # A foreign key's row the caller just loaded or wrote, so never None.
        request = cast(ApprovalRequest, await ApprovalRepository(self.session).get(request_id))
        # The request's own actions only: the requirement's are on the requirement (S2-C22).
        actions = [a for a in allowed_actions(ctx, target) if a is Action.APPROVAL_REQUEST_CANCEL]
        if request.status is ApprovalRequestStatus.PENDING:
            # Decide's relationship needs the request (its rows), not the requirement (DL-233).
            if authorize(ctx, Action.APPROVAL_DECIDE, dataclasses.replace(target, entity=request)):
                actions = sorted([*actions, Action.APPROVAL_DECIDE])
        else:
            # Ruled out for good by its state (DL-231, DL-232).
            actions = [a for a in actions if a is not Action.APPROVAL_REQUEST_CANCEL]
        requirement = cast(Requirement, target.entity)
        flagged = await ApprovalService(self.session).flagged(
            await self._project(requirement), [request]
        )
        return ApprovalRequestRead(
            **_approval_request(
                request, requirement.current_revision_id, request.id in flagged
            ).model_dump(),
            allowed_actions=actions,
        )


def _approval_request(
    request: ApprovalRequest, current_revision_id: uuid.UUID | None, flagged: bool
) -> ApprovalRequestItem:
    # A requirement's request is bound to a revision (the CHECK `requirement_revision`).
    revision = cast(RequirementRevision, request.requirement_revision)
    return ApprovalRequestItem(
        id=request.id,
        status=request.status,
        requirement_revision_id=revision.id,
        revision_number=revision.revision_number,
        note=request.note,
        requested_by_id=request.requested_by,
        requested_by_name=request.requester.name,
        requested_by_is_active=request.requester.is_active,
        created_at=request.created_at,
        completed_at=request.completed_at,
        newer_revision_exists=revision.id != current_revision_id,
        flagged=flagged,
        approvals=[
            ApprovalRead(
                id=row.id,
                approver_id=row.approver_id,
                approver_name=row.approver.name,
                approver_email=row.approver.email,
                approver_is_active=row.approver.is_active,
                decision=row.decision,
                comment=row.comment,
                decided_at=row.decided_at,
            )
            for row in request.approvals
        ],
    )


async def _approved(session: AsyncSession, request: ApprovalRequest, actor_id: uuid.UUID) -> None:
    await RequirementApprovalService(session).complete_approval(request, actor_id)


async def _rejected(session: AsyncSession, request: ApprovalRequest, actor_id: uuid.UUID) -> None:
    await RequirementApprovalService(session).reject_approval(request, actor_id)


register_on_approved(ApprovalEntityType.REQUIREMENT, _approved)
register_on_rejected(ApprovalEntityType.REQUIREMENT, _rejected)
