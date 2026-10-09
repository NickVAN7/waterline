from typing import Any

from fastapi import APIRouter, Response, status

from app.core.errors import ErrorBody
from app.routers.deps import (
    SESSION_COOKIE,
    AuthServiceDep,
    SessionTokenDep,
    SettingsDep,
    SignedInUserDep,
)
from app.schemas.auth import MeRead, SignInRequest

router = APIRouter(prefix="/auth", tags=["auth"])

_UNAUTHENTICATED: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorBody}
}


@router.post(
    "/sign-in",
    responses={**_UNAUTHENTICATED, status.HTTP_403_FORBIDDEN: {"model": ErrorBody}},
)
async def sign_in(
    body: SignInRequest, response: Response, auth: AuthServiceDep, settings: SettingsDep
) -> MeRead:
    """Start a new session and set its cookie. 401 `invalid_credentials` for an unknown email
    or a wrong password; 403 `account_inactive` for a deactivated account."""
    signed_in = await auth.sign_in(body.email, body.password)
    # The same attributes in every environment, dev and test included (build plan,
    # implementation decision 9).
    response.set_cookie(
        SESSION_COOKIE,
        signed_in.token,
        max_age=int(settings.session_lifetime.total_seconds()),
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    return signed_in.me


@router.post("/sign-out", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out(response: Response, auth: AuthServiceDep, token: SessionTokenDep = None) -> None:
    """End the request's session, if any, and clear its cookie."""
    await auth.sign_out(token)
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax")


@router.get("/me", responses=_UNAUTHENTICATED)
async def get_me(user: SignedInUserDep, auth: AuthServiceDep) -> MeRead:
    """The signed-in user. 401 `not_authenticated` without a live session."""
    return await auth.me(user)
