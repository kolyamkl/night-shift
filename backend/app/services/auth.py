"""Email/password accounts with Argon2id hashes and revocable server-side sessions."""

import secrets
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from ..core.errors import TooManyAttempts, Unauthorized
from ..repositories.accounts import ATTEMPTS_PER_MINUTE, AccountRepository

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))  # verified against for unknown emails, so timing matches
WRONG_LOGIN = "Email or password is incorrect."


class AuthService:
    def __init__(self, accounts: AccountRepository):
        self._accounts = accounts

    def user_for(self, token: str | None) -> dict:
        if token and len(token) <= 128:
            user = self._accounts.user_for_session(token)
            if user:
                return user
        raise Unauthorized()

    def throttle(self, client: str) -> None:
        if self._accounts.count_attempt(client) > ATTEMPTS_PER_MINUTE:
            raise TooManyAttempts()

    def register(self, email: str, password: str, old_token: str | None) -> tuple[dict, str]:
        user_id = uuid.uuid4().hex
        token = self._accounts.create_user(user_id, email, hasher.hash(password), old_token)
        return {"id": user_id, "email": email}, token

    def login(self, email: str, password: str, old_token: str | None) -> tuple[dict, str]:
        row = self._accounts.find_by_email(email)
        try:
            hasher.verify(row[2] if row else DUMMY_HASH, password)
        except (VerificationError, InvalidHashError):
            raise Unauthorized(WRONG_LOGIN) from None
        if row is None:
            raise Unauthorized(WRONG_LOGIN)
        user_id, stored_email, stored_hash = row
        new_hash = hasher.hash(password) if hasher.check_needs_rehash(stored_hash) else None
        return {"id": user_id, "email": stored_email}, self._accounts.open_session(user_id, old_token, new_hash)

    def logout(self, token: str | None) -> None:
        if token:
            self._accounts.close_session(token)
