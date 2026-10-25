"""Email/password accounts and revocable, server-side sessions.

Passwords are hashed with Argon2id. A login for an unknown email still verifies against a dummy hash,
so both failures take the same time and give the same answer. Sign-in attempts are limited to 30 a
minute per client address (the socket's address, never an X-Forwarded-For header).
"""

import uuid
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.errors import ConflictError, TooManyRequestsError, UnauthorizedError
from app.core.security import new_token, token_hash
from app.modules.auth.repository import AuthRepository, EmailTaken, NewSession
from app.modules.auth.schemas import Credentials, User

MAX_ATTEMPTS_PER_MINUTE = 30
LOGIN_FAILED = "Email or password is incorrect."

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(new_token())


@dataclass(frozen=True)
class SignedIn:
    user: User
    token: str  # the new session cookie value


class AuthService:
    def __init__(self, repo: AuthRepository) -> None:
        self.repo = repo

    def user_for_token(self, token: str | None) -> User:
        if token and len(token) <= 128:
            found = self.repo.user_for_session(token_hash(token))
            if found:
                return User(id=found[0], email=found[1])
        raise UnauthorizedError("Please log in to continue.")

    def throttle(self, client: str) -> None:
        if self.repo.count_attempt(token_hash(client)) > MAX_ATTEMPTS_PER_MINUTE:
            raise TooManyRequestsError("Too many attempts. Please wait a minute.", headers={"Retry-After": "60"})

    def register(self, body: Credentials, client: str, old_token: str | None) -> SignedIn:
        self.throttle(client)
        user_id = uuid.uuid4().hex
        token = new_token()
        try:
            self.repo.create_user(user_id, body.email, hasher.hash(body.password), self._session(token, old_token))
        except EmailTaken:
            raise ConflictError("An account with this email already exists. Log in instead.") from None
        return SignedIn(User(id=user_id, email=body.email), token)

    def login(self, body: Credentials, client: str, old_token: str | None) -> SignedIn:
        self.throttle(client)
        stored = self.repo.find_user(body.email)
        try:
            hasher.verify(stored.password_hash if stored else DUMMY_HASH, body.password)
        except (VerificationError, InvalidHashError):
            raise UnauthorizedError(LOGIN_FAILED) from None
        if stored is None:
            raise UnauthorizedError(LOGIN_FAILED)
        rehashed = hasher.hash(body.password) if hasher.check_needs_rehash(stored.password_hash) else None
        token = new_token()
        self.repo.start_session(stored.user_id, self._session(token, old_token), rehashed)
        return SignedIn(User(id=stored.user_id, email=stored.email), token)

    def logout(self, token: str | None) -> None:
        if token:
            self.repo.end_session(token_hash(token))

    @staticmethod
    def _session(token: str, old_token: str | None) -> NewSession:
        return NewSession(token_hash(token), token_hash(old_token) if old_token else None)
