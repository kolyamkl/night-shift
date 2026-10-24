"""/api/auth: register, log in, who am I, log out."""

from fastapi import APIRouter, Request, Response

from ...repositories.accounts import SESSION_SECONDS
from ..deps import COOKIE, Auth, ConfigDep, User
from ..schemas import Credentials

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _client(request: Request) -> str:
    # The actual peer (Caddy passes the real IP and uvicorn trusts only its proxy headers), not an
    # arbitrary X-Forwarded-For from the browser.
    return request.client.host if request.client else "unknown"


def _set_cookie(response: Response, request: Request, token: str, secure: bool) -> None:
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, path="/", httponly=True, samesite="lax",
                        secure=request.url.scheme == "https" or secure)


@router.post("/register", status_code=201)
def register(body: Credentials, request: Request, response: Response, auth: Auth, config: ConfigDep) -> dict:
    auth.throttle(_client(request))
    user, token = auth.register(body.email, body.password, request.cookies.get(COOKIE))
    _set_cookie(response, request, token, config.cookie_secure)
    return user


@router.post("/login")
def login(body: Credentials, request: Request, response: Response, auth: Auth, config: ConfigDep) -> dict:
    auth.throttle(_client(request))
    user, token = auth.login(body.email, body.password, request.cookies.get(COOKIE))
    _set_cookie(response, request, token, config.cookie_secure)
    return user


@router.get("/me")
def me(user: User) -> dict:
    return user


@router.post("/logout")
def logout(request: Request, response: Response, auth: Auth) -> dict:
    auth.logout(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="lax")
    return {"ok": True}
