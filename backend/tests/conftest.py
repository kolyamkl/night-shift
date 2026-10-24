import os
import uuid

import pymupdf
import pytest

from app.db.database import Database
from app.repositories import Storage
from app.repositories.documents import DocumentRepository

TEST_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


def storage_key() -> str:
    return os.environ.get("VEIL_STORAGE_KEY") or TEST_KEY


@pytest.fixture
def postgres_store(monkeypatch):
    """Integration tests use only an explicitly configured, separate database. The fixture is the app's
    Storage, whose document calls default to a fresh test owner."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL/API integration tests.")
    if url == os.environ.get("DATABASE_URL"):
        pytest.fail("TEST_DATABASE_URL must be separate from DATABASE_URL")
    # The test database persists between runs, so its test key must be stable too.
    suffix = uuid.uuid4().hex
    owner_id = uuid.uuid4().hex

    class TestDocuments(DocumentRepository):
        def create(self, doc, *, owner_id=owner_id):
            return super().create(doc, owner_id=owner_id)

        def get(self, doc_id, *, owner_id=owner_id):
            return super().get(doc_id, owner_id=owner_id)

        def save_result(self, doc_id, result, revision, *, owner_id=owner_id):
            return super().save_result(doc_id, result, revision, owner_id=owner_id)

        def delete(self, doc_id, *, owner_id=owner_id):
            return super().delete(doc_id, owner_id=owner_id)

    class TestStorage(Storage):
        test_suffix = suffix
        test_owner = owner_id

        def __init__(self, db):
            super().__init__(db)
            self.documents = TestDocuments(db)

    store = TestStorage(Database(url, storage_key()))
    store.db.migrate()
    with store.db.connect() as conn:
        conn.execute("INSERT INTO veil_users (user_id, email, password_hash) VALUES (%s, %s, %s)",
                     (owner_id, f"storage-{suffix}@example.test", "unused-test-hash"))
    monkeypatch.setattr(Storage, "from_env", classmethod(lambda cls: store))
    yield store
    with store.db.connect() as conn:
        conn.execute("DELETE FROM veil_users WHERE email LIKE %s", (f"%-{suffix}@example.test",))
    store.db.close()


def make_pdf(lines_per_page: list[list[str]]) -> bytes:
    """A small real PDF: each inner list is one page, each string one line of text."""
    doc = pymupdf.open()
    for lines in lines_per_page:
        page = doc.new_page()
        y = 72
        for line in lines:
            if line == "":
                y += 30  # blank line: a new text block
                continue
            page.insert_text((72, y), line, fontsize=11)
            y += 16
    return doc.tobytes()


@pytest.fixture
def tenancy_pdf() -> bytes:
    return make_pdf([
        ["Tenancy agreement", "", "Tenant: Raj Patel", "Address: 12 Oak Road, Leeds LS6 2AB", "",
         "Rent: 950 pounds per month"],
        ["Signed by Raj Patel", "Sort code 20-45-77, account no 31926819"],
    ])
