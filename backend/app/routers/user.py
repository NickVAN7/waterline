"""Account actions, profile edits, and the per-person access review (build plan, "The account
API", DL-72)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.authz.actions import Action
from app.core.db import SessionDep
from app.core.errors import ErrorBody
from app.routers.deps import (
    AuthServiceDep,
    AuthzContextDep,
    SignedInUserDep,
    authorized,
    load_user,
)
from app.schemas.auth import MeUser
from app.schemas.user import AccessReview, OwnProfileUpdate, PasswordReset, UserRow, UserUpdate
from app.services.user import UserEntity, UserService

router = APIRouter(tags=["user"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorBody}
    for code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    )
}

Managed = Annotated[UserEntity, Depends(authorized(load_user, Action.USER_MANAGE))]
AccessViewed = Annotated[
    UserEntity, Depends(authorized(load_user, Action.USER_VIEW_ACCESS, hide_denial=True))
]


@router.post(
    "/users/{user_id}/deactivate", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS
)
async def deactivate_user(subject: Managed, ctx: AuthzContextDep, auth: AuthServiceDep) -> None:
    """Deactivate the account and end its sessions. 422 on `user_id`: `last_system_admin`, or
    `last_owner` for the last active owner of the workspace or an org."""
    await auth.deactivate(ctx, subject)


@router.post(
    "/users/{user_id}/reactivate", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS
)
async def reactivate_user(subject: Managed, ctx: AuthzContextDep, session: SessionDep) -> None:
    """Let a deactivated account sign in again."""
    await UserService(session).reactivate(ctx, subject)


@router.post(
    "/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS
)
async def reset_password(
    subject: Managed, body: PasswordReset, ctx: AuthzContextDep, auth: AuthServiceDep
) -> None:
    """Set a temporary password the user must change at next sign-in, and end their sessions.
    403 on one's own account (use change password); 422 on `password` for the policy's
    problems."""
    await auth.reset_password(ctx, subject, body.password)


@router.post(
    "/users/{user_id}/sign-out-everywhere",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,
)
async def sign_out_everywhere(subject: Managed, ctx: AuthzContextDep, auth: AuthServiceDep) -> None:
    """End every session of the user."""
    await auth.sign_out_everywhere(ctx, subject)


@router.patch("/users/{user_id}", responses=_ERRORS)
async def update_user(
    subject: Managed, body: UserUpdate, ctx: AuthzContextDep, session: SessionDep
) -> UserRow:
    """Change the user's email, name, or username; an email change ends their sessions. 422:
    `taken`, the username rule's problems, or `own_email` on one's own email."""
    return await UserService(session).update(ctx, subject, body)


@router.patch("/me", responses=_ERRORS)
async def update_own_profile(
    user: SignedInUserDep, body: OwnProfileUpdate, session: SessionDep
) -> MeUser:
    """Change one's own name or username. 422: `taken`, or the username rule's problems."""
    return await UserService(session).update_own(user, body)


@router.get("/users/{user_id}/access", responses=_ERRORS)
async def access_review(subject: AccessViewed, session: SessionDep) -> AccessReview:
    """Every org and project the person can reach, and why (design-doc §5, "Access review")."""
    return await UserService(session).access_review(subject)
