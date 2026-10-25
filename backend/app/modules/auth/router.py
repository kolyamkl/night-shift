"""/api/auth: register, log in, who am I, log out. The session is an HttpOnly, SameSite=Lax cookie."""

from fastapi import APIRouter, Request, Response

from app.dependencies import SettingsDep
from app.modules.auth.dependencies import COOKIE, AuthServiceDep, CurrentUser
from app.modules.auth.repository import SESSION_SECONDS
from app.modules.auth.schemas import Credentials, LoggedOut, User

router = APIRouter(prefix="/api/auth")


def _client(request: Request) -> str:
    # The actual client, not an untrusted X-Forwarded-For header.
    return request.client.host if request.client else "unknown"


def _set_cookie(response: Response, request: Request, token: str, secure: bool) -> None:
    response.set_cookie(
        COOKIE,
        token,
        max_age=SESSION_SECONDS,
        path="/",
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https" or secure,
    )


@router.post("/register", status_code=201)
def register(
    body: Credentials, request: Request, response: Response, auth: AuthServiceDep, settings: SettingsDep
) -> User:
    signed_in = auth.register(body, _client(request), request.cookies.get(COOKIE))
    _set_cookie(response, request, signed_in.token, settings.cookie_secure)
    return signed_in.user


@router.post("/login")
def login(body: Credentials, request: Request, response: Response, auth: AuthServiceDep, settings: SettingsDep) -> User:
    signed_in = auth.login(body, _client(request), request.cookies.get(COOKIE))
    _set_cookie(response, request, signed_in.token, settings.cookie_secure)
    return signed_in.user


@router.get("/me")
def me(user: CurrentUser) -> User:
    return user


@router.post("/logout")
def logout(request: Request, response: Response, auth: AuthServiceDep) -> LoggedOut:
    auth.logout(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="lax")
    return LoggedOut()
