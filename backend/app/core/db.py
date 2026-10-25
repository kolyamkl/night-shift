"""PostgreSQL access: connections, the immutable SQL migrations and the storage-key check.

No ORM: repositories write parameterized SQL with psycopg 3. Each repository call opens its own
short connection (the `with` block commits or rolls back), so a scan running in a worker thread
never shares a connection with the request that started it. Payloads are encrypted by the
PayloadCipher before they reach a query; there is no plaintext or in-memory fallback.
"""

import hashlib
from pathlib import Path
from typing import Self

import psycopg

from app.core.config import BACKEND_DIR, Settings
from app.core.crypto import PayloadCipher

MIGRATIONS_DIR = BACKEND_DIR / "migrations"
MIGRATION_LOCK = 873254011  # pg_advisory_xact_lock key: one app worker migrates at a time
CONNECT_TIMEOUT_SECONDS = 5
STATEMENT_TIMEOUT_MS = 10_000


class Database:
    def __init__(self, url: str, key: str) -> None:
        if not url or not key:
            raise RuntimeError("Set DATABASE_URL and VEIL_STORAGE_KEY. See docs/DATABASE.md.")
        self.url = url
        self.cipher = PayloadCipher(key)

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        return cls(settings.database_url, settings.storage_key.get_secret_value())

    def connect(self) -> psycopg.Connection:
        return psycopg.connect(self.url, connect_timeout=CONNECT_TIMEOUT_SECONDS,
                               options=f"-c statement_timeout={STATEMENT_TIMEOUT_MS}")

    def initialize(self, migrations: Path = MIGRATIONS_DIR) -> None:
        """Apply immutable SQL migrations atomically, serialized across app workers, then check that
        VEIL_STORAGE_KEY is the key this database was written with."""
        with self.connect() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK,))
            conn.execute("""CREATE TABLE IF NOT EXISTS veil_schema_migrations (
                version text PRIMARY KEY, checksum text NOT NULL,
                applied_at timestamptz NOT NULL DEFAULT now())""")
            for path in sorted(migrations.glob("*.sql")):
                sql = path.read_text()
                checksum = hashlib.sha256(sql.encode()).hexdigest()
                row = conn.execute("SELECT checksum FROM veil_schema_migrations WHERE version = %s",
                                   (path.name,)).fetchone()
                if row:
                    if row[0] != checksum:
                        raise RuntimeError(f"Applied migration changed: {path.name}")
                    continue
                conn.execute(sql.encode())  # a file of several statements: sent as one simple query
                conn.execute("INSERT INTO veil_schema_migrations (version, checksum) VALUES (%s, %s)",
                             (path.name, checksum))
            probe = conn.execute("SELECT key_probe FROM veil_storage_settings WHERE singleton").fetchone()
            if probe is None:
                conn.execute("INSERT INTO veil_storage_settings (key_probe) VALUES (%s)", (self.cipher.probe(),))
            elif not self.cipher.matches(probe[0]):
                raise RuntimeError("VEIL_STORAGE_KEY does not match this database. Restore the original key.")

    def healthy(self) -> None:
        """Raises psycopg.Error when the database cannot answer."""
        with self.connect() as conn:
            conn.execute("SELECT version FROM veil_schema_migrations LIMIT 1").fetchone()
