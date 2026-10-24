"""Users, their server-side sessions and the per-client login throttle. Session tokens are stored hashed."""

import hashlib
import secrets

import psycopg

from ..core.errors import Conflict
from ..db.database import Database

SESSION_SECONDS = 7 * 24 * 60 * 60
ATTEMPTS_PER_MINUTE = 30


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class EmailTaken(Conflict):
    detail = "An account with this email already exists. Log in instead."


class AccountRepository:
    def __init__(self, db: Database):
        self._db = db

    def user_for_session(self, token: str) -> dict | None:
        with self._db.connect() as conn:
            row = conn.execute("""SELECT u.user_id, u.email FROM veil_sessions s
                JOIN veil_users u USING (user_id)
                WHERE s.token_hash = %s AND s.expires_at > now()""", (token_hash(token),)).fetchone()
        return {"id": row[0], "email": row[1]} if row else None

    def count_attempt(self, client: str) -> int:
        """Attempts by this client in the current one-minute window, this one included."""
        with self._db.connect() as conn:
            conn.execute("DELETE FROM veil_auth_limits WHERE reset_at < now() - interval '1 day'")
            row = conn.execute("""INSERT INTO veil_auth_limits (bucket, attempts, reset_at)
                VALUES (%s, 1, now() + interval '1 minute') ON CONFLICT (bucket) DO UPDATE SET
                attempts = CASE WHEN veil_auth_limits.reset_at <= now() THEN 1 ELSE veil_auth_limits.attempts + 1 END,
                reset_at = CASE WHEN veil_auth_limits.reset_at <= now() THEN now() + interval '1 minute'
                           ELSE veil_auth_limits.reset_at END RETURNING attempts""", (token_hash(client),)).fetchone()
        return row[0]

    def create_user(self, user_id: str, email: str, password_hash: str, replaces: str | None) -> str:
        """The new user's first session token. Raises EmailTaken."""
        try:
            with self._db.connect() as conn:
                conn.execute("INSERT INTO veil_users (user_id, email, password_hash) VALUES (%s, %s, %s)",
                             (user_id, email, password_hash))
                return self._new_session(conn, user_id, replaces)
        except psycopg.errors.UniqueViolation:
            raise EmailTaken() from None

    def find_by_email(self, email: str) -> tuple[str, str, str] | None:
        """(user_id, email, password_hash), or None."""
        with self._db.connect() as conn:
            return conn.execute("SELECT user_id, email, password_hash FROM veil_users WHERE email = %s",
                                (email,)).fetchone()

    def open_session(self, user_id: str, replaces: str | None, new_hash: str | None = None) -> str:
        """A new session token, ending the session it replaces; new_hash upgrades the stored password hash."""
        with self._db.connect() as conn:
            if new_hash:
                conn.execute("UPDATE veil_users SET password_hash = %s WHERE user_id = %s", (new_hash, user_id))
            return self._new_session(conn, user_id, replaces)

    def close_session(self, token: str) -> None:
        with self._db.connect() as conn:
            conn.execute("DELETE FROM veil_sessions WHERE token_hash = %s", (token_hash(token),))

    @staticmethod
    def _new_session(conn, user_id: str, replaces: str | None) -> str:
        token = secrets.token_urlsafe(32)
        if replaces:
            conn.execute("DELETE FROM veil_sessions WHERE token_hash = %s", (token_hash(replaces),))
        conn.execute("DELETE FROM veil_sessions WHERE expires_at <= now()")
        conn.execute("""INSERT INTO veil_sessions (token_hash, user_id, expires_at)
            VALUES (%s, %s, now() + %s * interval '1 second')""", (token_hash(token), user_id, SESSION_SECONDS))
        return token
