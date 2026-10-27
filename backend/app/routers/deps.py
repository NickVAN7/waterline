"""Dependencies shared by routers: settings, the auth service, the signed-in user, the
authorization context, and load-and-authorize (`authorized`)."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import Cookie, Depends, Request, status

from app.authz.authorize import authorize, ensure, module_enabled
from app.authz.context import AuthzContext
from app.authz.target import Target, org_target, workspace_target
from app.core.db import SessionDep
from app.core.errors import ErrorBody, NotFoundError
from app.core.settings import Settings
from app.enums import ProjectModule
from app.services.auth import AuthService, SignedInUser
from app.services.org import OrgEntity, OrgService
from app.services.project import ProjectEntity, ProjectService
from app.services.requirement import RequirementEntity, RequirementService
from app.services.user import UserEntity, UserService
from app.services.workspace import WorkspaceEntity, WorkspaceService

# `__Host-`: the browser only accepts it with `Secure`, `Path=/`, and no `Domain` (design-doc
# §4, "Slice 1 security checklist").
SESSION_COOKIE = "__Host-session"

# The error responses the area routers document on each endpoint (the OpenAPI `responses`).
ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorBody}
    for code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    )
}


def get_settings_from_app(request: Request) -> Settings:
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(get_settings_from_app)]


def get_auth_service(session: SessionDep, settings: SettingsDep) -> AuthService:
    return AuthService(session, settings)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]

# The raw session token from the cookie, if sent. Not in the OpenAPI schema's parameters: the
# browser sends it, never the client code.
SessionTokenDep = Annotated[str | None, Cookie(alias=SESSION_COOKIE, include_in_schema=False)]


async def get_signed_in_user(auth: AuthServiceDep, token: SessionTokenDep = None) -> SignedInUser:
    """The user of the request's session; 401 `not_authenticated` without a live one, 403
    `password_change_required` while they must change their password. Every endpoint that
    needs a user takes this one."""
    return await auth.authenticate(token)


SignedInUserDep = Annotated[SignedInUser, Depends(get_signed_in_user)]


async def get_user_pending_password_change(
    auth: AuthServiceDep, token: SessionTokenDep = None
) -> SignedInUser:
    """As `get_signed_in_user`, but lets through a user who must change their password: only
    for `GET /api/auth/me` and change-password (design-doc §4, "Forced change")."""
    return await auth.authenticate(token, allow_pending_password_change=True)


UserPendingPasswordChangeDep = Annotated[SignedInUser, Depends(get_user_pending_password_change)]


async def get_authz_context(user: SignedInUserDep, auth: AuthServiceDep) -> AuthzContext:
    """The signed-in user's authorization context, loaded once per request (FastAPI caches a
    dependency's result within a request)."""
    return await auth.authz_context(user)


AuthzContextDep = Annotated[AuthzContext, Depends(get_authz_context)]


def authorized[E](
    loader: Callable[..., Awaitable[tuple[E, Target] | None]],
    action: str,
    *,
    module: ProjectModule | None = None,
    hide_denial: bool = False,
) -> Callable[..., Awaitable[E]]:
    """A dependency that loads an entity and authorizes `action` on it in one step, so an
    endpoint can't get the entity without the check (design-doc §5).

    `loader` is itself a dependency (it takes the path parameters and the session) and returns
    the entity with its `Target`, or None when there's no such entity. A missing entity, or one
    the user can't see, is a 404; one they see but may not act on, a 403. With `module`, the
    target's project must have that module enabled, else 404, checked before `authorize()`.
    With `hide_denial`, every denial is a 404, even on a target the user sees (the per-person
    access review, DL-72).
    """

    # `ctx` first: FastAPI resolves dependencies in order, so the user is authenticated before
    # the loader queries anything.
    async def dependency(
        ctx: AuthzContextDep, loaded: Annotated[tuple[E, Target] | None, Depends(loader)]
    ) -> E:
        if loaded is None:
            raise NotFoundError
        entity, target = loaded
        if module is not None and not module_enabled(target, module):
            raise NotFoundError
        if hide_denial and not authorize(ctx, action, target):
            raise NotFoundError
        ensure(ctx, action, target)
        return entity

    return dependency


# --- Loaders for `authorized` -------------------------------------------------------------


async def load_workspace(
    workspace_id: uuid.UUID, session: SessionDep
) -> tuple[WorkspaceEntity, Target] | None:
    workspace = await WorkspaceService(session).get(workspace_id)
    return None if workspace is None else (workspace, workspace_target(workspace))


async def load_org(org_id: uuid.UUID, session: SessionDep) -> tuple[OrgEntity, Target] | None:
    org = await OrgService(session).get(org_id)
    return None if org is None else (org, org_target(org))


async def load_user(user_id: uuid.UUID, session: SessionDep) -> tuple[UserEntity, Target] | None:
    return await UserService(session).load(user_id)


async def load_project(key: str, session: SessionDep) -> tuple[ProjectEntity, Target] | None:
    return await ProjectService(session).load(key)


async def load_requirement(
    key: str, number: int, session: SessionDep
) -> tuple[RequirementEntity, Target] | None:
    return await RequirementService(session).load(key, number)
