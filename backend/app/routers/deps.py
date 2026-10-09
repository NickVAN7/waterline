"""Dependencies shared by routers: settings, the auth service, and the signed-in user."""

from typing import Annotated

from fastapi import Cookie, Depends, Request

from app.core.db import SessionDep
from app.core.settings import Settings
from app.services.auth import AuthService, SignedInUser

# `__Host-`: the browser only accepts it with `Secure`, `Path=/`, and no `Domain` (design-doc
# §4, "Slice 1 security checklist").
SESSION_COOKIE = "__Host-session"


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
    """The user of the request's session; 401 `not_authenticated` without a live one."""
    return await auth.authenticate(token)


SignedInUserDep = Annotated[SignedInUser, Depends(get_signed_in_user)]
