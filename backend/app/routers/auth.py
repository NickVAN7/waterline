from typing import Any

from fastapi import APIRouter, Response, status

from app.core.errors import ErrorBody
from app.core.settings import Settings
from app.routers.deps import (
    SESSION_COOKIE,
    AuthServiceDep,
    SessionTokenDep,
    SettingsDep,
    UserPendingPasswordChangeDep,
)
from app.schemas.auth import ChangePasswordRequest, MeRead, SignInRequest

router = APIRouter(prefix="/auth", tags=["auth"])

_UNAUTHENTICATED: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorBody}
}


@router.post(
    "/sign-in",
    responses={**_UNAUTHENTICATED, status.HTTP_403_FORBIDDEN: {"model": ErrorBody}},
)
async def sign_in(
    body: SignInRequest,
    response: Response,
    auth: AuthServiceDep,
    settings: SettingsDep,
    token: SessionTokenDep = None,
) -> MeRead:
    """Start a new session and set its cookie, ending the session the browser sent, if any. 401
    `invalid_credentials` for an unknown email or a wrong password; 403 `account_inactive` for a
    deactivated account."""
    signed_in = await auth.sign_in(body.email, body.password, old_token=token)
    _set_session_cookie(response, signed_in.token, settings)
    return signed_in.me


@router.post("/sign-out", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out(response: Response, auth: AuthServiceDep, token: SessionTokenDep = None) -> None:
    """End the request's session, if any, and clear its cookie."""
    await auth.sign_out(token)
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax")


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**_UNAUTHENTICATED, status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorBody}},
)
async def change_password(
    body: ChangePasswordRequest,
    response: Response,
    user: UserPendingPasswordChangeDep,
    auth: AuthServiceDep,
    settings: SettingsDep,
    token: SessionTokenDep = None,
) -> None:
    """Change your own password, which clears a forced change. The session gets a new token
    (a new cookie) and your other sessions end. 422 on `current_password` (`incorrect`) or on
    `new_password` (the password policy: `too_short`, `too_long`, `same_as_email`,
    `same_as_username`, `same_as_current`)."""
    # The dependency found a live session, so the cookie is there.
    new_token = await auth.change_password(
        user, token or "", body.current_password, body.new_password
    )
    _set_session_cookie(response, new_token, settings)


@router.get("/me", responses=_UNAUTHENTICATED)
async def get_me(user: UserPendingPasswordChangeDep, auth: AuthServiceDep) -> MeRead:
    """The signed-in user. 401 `not_authenticated` without a live session."""
    return await auth.me(user)


def _set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    # The same attributes in every environment, dev and test included (build plan,
    # implementation decision 9).
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(settings.session_lifetime.total_seconds()),
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )
