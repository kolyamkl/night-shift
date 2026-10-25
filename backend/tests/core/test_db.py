"""Every migration applies to an empty database, twice without harm (a fresh deploy and a restart)."""

import uuid

import psycopg
import pytest

from app.core.db import MIGRATIONS_DIR, Database


@pytest.fixture
def empty_schema(postgres_store):
    schema = f"fresh_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(postgres_store.db.url, autocommit=True) as conn:
        conn.execute(f'CREATE SCHEMA "{schema}"')
    yield schema
    with psycopg.connect(postgres_store.db.url, autocommit=True) as conn:
        conn.execute(f'DROP SCHEMA "{schema}" CASCADE')


def test_migrations_apply_to_an_empty_database(postgres_store, empty_schema):
    class FreshDatabase(Database):
        def connect(self):
            return psycopg.connect(self.url, options=f"-c search_path={empty_schema}")

    db = FreshDatabase(postgres_store.db.url, postgres_store.test_key)
    db.initialize()
    db.initialize()
    with db.connect() as conn:
        applied = [row[0] for row in conn.execute("SELECT version FROM veil_schema_migrations ORDER BY 1")]
    assert applied == sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    db.healthy()
