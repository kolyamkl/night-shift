"""PostgreSQL access: a connection pool shared by every request and scan, migrations, and the key check."""

import hashlib
import os
import threading
from contextlib import contextmanager
from pathlib import Path

from cryptography.fernet import InvalidToken
from psycopg_pool import ConnectionPool

from .crypto import Envelope

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
MIGRATION_LOCK = 873254011  # pg_advisory_xact_lock id: one app worker migrates at a time
KEY_PROBE = b"veil-storage-v1"


class Database:
    def __init__(self, url: str, key: str, *, pool_min: int = 1, pool_max: int = 10):
        if not url or not key:
            raise RuntimeError("Set DATABASE_URL and VEIL_STORAGE_KEY. See docs/DATABASE.md.")
        self.url = url
        self.envelope = Envelope(key)
        self._sizes = (pool_min, max(pool_min, pool_max))
        self._pool: ConnectionPool | None = None
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls) -> "Database":
        return cls(os.environ.get("DATABASE_URL", ""), os.environ.get("VEIL_STORAGE_KEY", ""),
                   pool_max=int(os.environ.get("VEIL_DB_POOL_MAX") or 10))

    def _get_pool(self) -> ConnectionPool:
        # Opened on first use and again after close(), so a restarted app (or test client) reuses this object.
        with self._lock:
            if self._pool is None:
                self._pool = ConnectionPool(
                    self.url, min_size=self._sizes[0], max_size=self._sizes[1], open=True, timeout=10,
                    kwargs={"connect_timeout": 5, "options": "-c statement_timeout=10000"},
                    check=ConnectionPool.check_connection, name="veil")
            return self._pool

    @contextmanager
    def connect(self):
        """One pooled connection for one transaction: committed on success, rolled back on error."""
        with self._get_pool().connection() as conn:
            yield conn

    def close(self) -> None:
        with self._lock:
            pool, self._pool = self._pool, None
        if pool is not None:
            pool.close()

    def migrate(self) -> None:
        """Apply immutable SQL migrations atomically, serialized across app workers, then check the key."""
        with self.connect() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK,))
            conn.execute("""CREATE TABLE IF NOT EXISTS veil_schema_migrations (
                version text PRIMARY KEY, checksum text NOT NULL,
                applied_at timestamptz NOT NULL DEFAULT now())""")
            for path in sorted(MIGRATIONS.glob("*.sql")):
                sql = path.read_text()
                checksum = hashlib.sha256(sql.encode()).hexdigest()
                row = conn.execute("SELECT checksum FROM veil_schema_migrations WHERE version = %s",
                                   (path.name,)).fetchone()
                if row:
                    if row[0] != checksum:
                        raise RuntimeError(f"Applied migration changed: {path.name}")
                    continue
                conn.execute(sql)
                conn.execute("INSERT INTO veil_schema_migrations (version, checksum) VALUES (%s, %s)",
                             (path.name, checksum))
            probe = conn.execute("SELECT key_probe FROM veil_storage_settings WHERE singleton").fetchone()
            if probe:
                try:
                    valid = self.envelope.decrypt(probe[0]) == KEY_PROBE
                except InvalidToken:
                    valid = False
                if not valid:
                    raise RuntimeError("VEIL_STORAGE_KEY does not match this database. Restore the original key.")
            else:
                conn.execute("INSERT INTO veil_storage_settings (key_probe) VALUES (%s)",
                             (self.envelope.encrypt(KEY_PROBE),))

    def healthy(self) -> None:
        with self.connect() as conn:
            conn.execute("SELECT version FROM veil_schema_migrations LIMIT 1").fetchone()
