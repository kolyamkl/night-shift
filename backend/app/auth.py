"""Email/password accounts and revocable, server-side cookie sessions."""

import hashlib
import os
import re
import secrets
import uuid
from typing import Annotated

import psycopg
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

router = APIRouter(prefix="/api/auth")
COOKIE = "veil_session"
SESSION_SECONDS = 7 * 24 * 60 * 60
hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128, repr=False)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address.")
        return value


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(request: Request) -> dict:
    token = request.cookies.get(COOKIE)
    if token and len(token) <= 128:
        with request.app.state.store.connect() as conn:
            row = conn.execute("""SELECT u.user_id, u.email FROM veil_sessions s
                JOIN veil_users u USING (user_id)
                WHERE s.token_hash = %s AND s.expires_at > now()""", (token_hash(token),)).fetchone()
        if row:
            return {"id": row[0], "email": row[1]}
    raise HTTPException(401, "Please log in to continue.")


User = Annotated[dict, Depends(current_user)]


def throttle(request: Request):
    # Use the actual client, not an untrusted X-Forwarded-For header.
    bucket = token_hash(request.client.host if request.client else "unknown")
    with request.app.state.store.connect() as conn:
        conn.execute("DELETE FROM veil_auth_limits WHERE reset_at < now() - interval '1 day'")
        row = conn.execute("""INSERT INTO veil_auth_limits (bucket, attempts, reset_at)
            VALUES (%s, 1, now() + interval '1 minute') ON CONFLICT (bucket) DO UPDATE SET
            attempts = CASE WHEN veil_auth_limits.reset_at <= now() THEN 1 ELSE veil_auth_limits.attempts + 1 END,
            reset_at = CASE WHEN veil_auth_limits.reset_at <= now() THEN now() + interval '1 minute'
                       ELSE veil_auth_limits.reset_at END RETURNING attempts""", (bucket,)).fetchone()
    if row[0] > 30:
        raise HTTPException(429, "Too many attempts. Please wait a minute.", headers={"Retry-After": "60"})


def new_session(conn, request: Request, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    old = request.cookies.get(COOKIE)
    if old:
        conn.execute("DELETE FROM veil_sessions WHERE token_hash = %s", (token_hash(old),))
    conn.execute("DELETE FROM veil_sessions WHERE expires_at <= now()")
    conn.execute("""INSERT INTO veil_sessions (token_hash, user_id, expires_at)
        VALUES (%s, %s, now() + %s * interval '1 second')""", (token_hash(token), user_id, SESSION_SECONDS))
    return token


def set_cookie(response: Response, request: Request, token: str):
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, path="/", httponly=True,
                        samesite="lax", secure=request.url.scheme == "https" or
                        os.environ.get("VEIL_COOKIE_SECURE", "false").lower() == "true")


@router.post("/register", status_code=201)
def register(body: Credentials, request: Request, response: Response) -> dict:
    throttle(request)
    user_id = uuid.uuid4().hex
    password_hash = hasher.hash(body.password)
    try:
        with request.app.state.store.connect() as conn:
            conn.execute("INSERT INTO veil_users (user_id, email, password_hash) VALUES (%s, %s, %s)",
                         (user_id, body.email, password_hash))
            token = new_session(conn, request, user_id)
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "An account with this email already exists. Log in instead.") from None
    set_cookie(response, request, token)
    return {"id": user_id, "email": body.email}


@router.post("/login")
def login(body: Credentials, request: Request, response: Response) -> dict:
    throttle(request)
    with request.app.state.store.connect() as conn:
        row = conn.execute("SELECT user_id, email, password_hash FROM veil_users WHERE email = %s",
                           (body.email,)).fetchone()
    try:
        hasher.verify(row[2] if row else DUMMY_HASH, body.password)
    except (VerificationError, InvalidHashError):
        raise HTTPException(401, "Email or password is incorrect.") from None
    if row is None:
        raise HTTPException(401, "Email or password is incorrect.")
    with request.app.state.store.connect() as conn:
        if hasher.check_needs_rehash(row[2]):
            conn.execute("UPDATE veil_users SET password_hash = %s WHERE user_id = %s",
                         (hasher.hash(body.password), row[0]))
        token = new_session(conn, request, row[0])
    set_cookie(response, request, token)
    return {"id": row[0], "email": row[1]}


@router.get("/me")
def me(user: User) -> dict:
    return user


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(COOKIE)
    if token:
        with request.app.state.store.connect() as conn:
            conn.execute("DELETE FROM veil_sessions WHERE token_hash = %s", (token_hash(token),))
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="lax")
    return {"ok": True}
