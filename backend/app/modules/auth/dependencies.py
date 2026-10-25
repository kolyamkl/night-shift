"""The signed-in user, as a dependency every document route takes."""

from typing import Annotated

from fastapi import Depends, Request

from app.dependencies import DatabaseDep
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import User
from app.modules.auth.service import AuthService

COOKIE = "veil_session"


def get_auth_service(db: DatabaseDep) -> AuthService:
    return AuthService(AuthRepository(db))


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def current_user(request: Request, auth: AuthServiceDep) -> User:
    """The session cookie's user, or 401."""
    return auth.user_for_token(request.cookies.get(COOKIE))


CurrentUser = Annotated[User, Depends(current_user)]
