"""The `workspace` area: `workspace` and `workspace_membership` (build plan, "Feature map")."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.admin_event import log_admin_event
from app.core.errors import FieldError, ForbiddenError, ValidationFailedError
from app.core.security import hash_password
from app.enums import AuditAction, AuditEntityType, WorkspaceRole
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from app.repositories.workspace import WorkspaceRepository
from app.rules.identifiers import slug_problem, username_problem
from app.services.user import UserService, identifier_error, password_errors


class WorkspaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def seed(
        self,
        *,
        workspace_name: str,
        workspace_slug: str,
        email: str,
        username: str,
        name: str,
        password: str,
    ) -> tuple[Workspace, User]:
        """Create the workspace and its first system admin, who is its owner (the seed command,
        `wl seed`; design-doc §4, "Tenancy"). No actor: it runs from the app CLI. 403
        `workspace_exists` when there is already a workspace; 422 for an invalid value, every
        field's problems at once."""
        repository = WorkspaceRepository(self.session)
        if await repository.any_exists():
            raise ForbiddenError("A workspace already exists.", code="workspace_exists")
        email = email.strip().lower()
        problems = [
            *_required(workspace_name, "workspace_name"),
            *identifier_error(slug_problem(workspace_slug), field="workspace_slug"),
            *_email_problem(email),
            *identifier_error(username_problem(username), field="username"),
            *_required(name, "name"),
            *password_errors(
                password, email=email, username=username, same_as_current=False, field="password"
            ),
        ]
        if problems:
            raise ValidationFailedError(problems)

        workspace = Workspace(name=workspace_name.strip(), slug=workspace_slug)
        self.session.add(workspace)
        await self.session.flush()
        user = await UserService(self.session).create(
            email=email,
            username=username,
            name=name.strip(),
            password_hash=await hash_password(password),
            is_system_admin=True,
        )
        self.session.add(
            WorkspaceMembership(
                workspace_id=workspace.id, user_id=user.id, role=WorkspaceRole.OWNER
            )
        )
        await self.session.flush()

        log_admin_event(
            self.session,
            action=AuditAction.WORKSPACE_CREATED,
            actor_id=None,
            workspace_id=workspace.id,
            entity_type=AuditEntityType.WORKSPACE,
            entity_id=workspace.id,
            details={"name": workspace.name, "slug": workspace.slug},
        )
        log_admin_event(
            self.session,
            action=AuditAction.USER_CREATED,
            actor_id=None,
            workspace_id=workspace.id,
            target_user_id=user.id,
        )
        log_admin_event(
            self.session,
            action=AuditAction.SYSTEM_ADMIN_GRANTED,
            actor_id=None,
            workspace_id=None,  # instance-level
            target_user_id=user.id,
        )
        log_admin_event(
            self.session,
            action=AuditAction.WORKSPACE_MEMBER_ADDED,
            actor_id=None,
            workspace_id=workspace.id,
            target_user_id=user.id,
            entity_type=AuditEntityType.WORKSPACE,
            entity_id=workspace.id,
            details={"role": WorkspaceRole.OWNER.value},
        )
        return workspace, user


def _required(value: str, field: str) -> list[FieldError]:
    if value.strip():
        return []
    return [FieldError(("body", field), "This is required.", "missing")]


def _email_problem(email: str) -> list[FieldError]:
    # Only the shape a typo breaks: a real check needs a verification email (design-doc §4).
    local, at, domain = email.partition("@")
    if at and local and "." in domain and " " not in email:
        return []
    return [FieldError(("body", "email"), "Enter an email address.", "invalid_email")]
