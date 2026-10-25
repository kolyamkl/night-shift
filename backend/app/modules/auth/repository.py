"""Accounts, sessions and sign-in attempts in PostgreSQL. Queries only: no hashing, no HTTP.

Session tokens are stored as SHA-256 hashes (core.security.token_hash), never as tokens.
"""

from dataclasses import dataclass

import psycopg

from app.core.db import Database

SESSION_SECONDS = 7 * 24 * 60 * 60


@dataclass(frozen=True)
class StoredUser:
    user_id: str
    email: str
    password_hash: str


@dataclass(frozen=True)
class NewSession:
    token_hash: str
    replaces: str | None  # hash of the session cookie the browser sent, ended when this one starts


class EmailTaken(Exception):
    pass


class AuthRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def user_for_session(self, token_hash: str) -> tuple[str, str] | None:
        """(user_id, email) of an unexpired session."""
        with self.db.connect() as conn:
            row = conn.execute("""SELECT u.user_id, u.email FROM veil_sessions s
                JOIN veil_users u USING (user_id)
                WHERE s.token_hash = %s AND s.expires_at > now()""", (token_hash,)).fetchone()
        return (row[0], row[1]) if row else None

    def count_attempt(self, bucket: str) -> int:
        """Count one sign-in attempt in a one-minute window and return the window's count."""
        with self.db.connect() as conn:
            conn.execute("DELETE FROM veil_auth_limits WHERE reset_at < now() - interval '1 day'")
            row = conn.execute("""INSERT INTO veil_auth_limits (bucket, attempts, reset_at)
                VALUES (%s, 1, now() + interval '1 minute') ON CONFLICT (bucket) DO UPDATE SET
                attempts = CASE WHEN veil_auth_limits.reset_at <= now() THEN 1 ELSE veil_auth_limits.attempts + 1 END,
                reset_at = CASE WHEN veil_auth_limits.reset_at <= now() THEN now() + interval '1 minute'
                           ELSE veil_auth_limits.reset_at END RETURNING attempts""", (bucket,)).fetchone()
        assert row is not None  # noqa: S101 - INSERT ... RETURNING always returns the row
        return int(row[0])

    def create_user(self, user_id: str, email: str, password_hash: str, session: NewSession) -> None:
        """Create the account and its first session in one transaction. Raises EmailTaken."""
        try:
            with self.db.connect() as conn:
                conn.execute("INSERT INTO veil_users (user_id, email, password_hash) VALUES (%s, %s, %s)",
                             (user_id, email, password_hash))
                self._start_session(conn, user_id, session)
        except psycopg.errors.UniqueViolation:
            raise EmailTaken from None

    def find_user(self, email: str) -> StoredUser | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT user_id, email, password_hash FROM veil_users WHERE email = %s",
                               (email,)).fetchone()
        return StoredUser(*row) if row else None

    def start_session(self, user_id: str, session: NewSession, new_password_hash: str | None = None) -> None:
        """Start a session, first storing a rehashed password if the hash parameters changed."""
        with self.db.connect() as conn:
            if new_password_hash is not None:
                conn.execute("UPDATE veil_users SET password_hash = %s WHERE user_id = %s",
                             (new_password_hash, user_id))
            self._start_session(conn, user_id, session)

    def end_session(self, token_hash: str) -> None:
        with self.db.connect() as conn:
            conn.execute("DELETE FROM veil_sessions WHERE token_hash = %s", (token_hash,))

    @staticmethod
    def _start_session(conn: psycopg.Connection, user_id: str, session: NewSession) -> None:
        if session.replaces:
            conn.execute("DELETE FROM veil_sessions WHERE token_hash = %s", (session.replaces,))
        conn.execute("DELETE FROM veil_sessions WHERE expires_at <= now()")
        conn.execute("""INSERT INTO veil_sessions (token_hash, user_id, expires_at)
            VALUES (%s, %s, now() + %s * interval '1 second')""", (session.token_hash, user_id, SESSION_SECONDS))
