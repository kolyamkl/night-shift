import os
import uuid

import pymupdf
import pytest

from app.core.db import Database
from app.main import app
from app.modules.documents.repository import DocumentRepository

# The test database persists between runs, so its test key must be stable too.
TEST_KEY = os.environ.get("VEIL_STORAGE_KEY") or "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


@pytest.fixture
def postgres_store(monkeypatch):
    """Integration tests use only an explicitly configured, separate database. The app's lifespan
    gets this database instead of the one in DATABASE_URL."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL/API integration tests.")
    if url == os.environ.get("DATABASE_URL"):
        pytest.fail("TEST_DATABASE_URL must be separate from DATABASE_URL")
    suffix = uuid.uuid4().hex
    owner_id = uuid.uuid4().hex

    class TestStore(DocumentRepository):
        """The documents repository with this test's user as the default owner."""

        test_suffix = suffix
        test_owner = owner_id
        test_key = TEST_KEY

        def connect(self):
            return self.db.connect()

        def create(self, doc, *, owner_id=owner_id):
            return super().create(doc, owner_id=owner_id)

        def get(self, doc_id, *, owner_id=owner_id):
            return super().get(doc_id, owner_id=owner_id)

        def save_result(self, doc_id, result, revision, *, owner_id=owner_id):
            return super().save_result(doc_id, result, revision, owner_id=owner_id)

        def delete(self, doc_id, *, owner_id=owner_id):
            return super().delete(doc_id, owner_id=owner_id)

    db = Database(url, TEST_KEY)
    db.initialize()
    store = TestStore(db)
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO veil_users (user_id, email, password_hash) VALUES (%s, %s, %s)",
            (owner_id, f"storage-{suffix}@example.test", "unused-test-hash"),
        )
    monkeypatch.setattr(Database, "from_settings", classmethod(lambda cls, settings: db))
    yield store
    with db.connect() as conn:
        conn.execute("DELETE FROM veil_users WHERE email LIKE %s", (f"%-{suffix}@example.test",))


@pytest.fixture
def settings(monkeypatch):
    """Change the app's settings for one test: settings(samples_dir=..., cookie_secure=True)."""

    def override(**changes):
        monkeypatch.setattr(app.state, "settings", app.state.settings.model_copy(update=changes))

    return override


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
    return make_pdf(
        [
            [
                "Tenancy agreement",
                "",
                "Tenant: Raj Patel",
                "Address: 12 Oak Road, Leeds LS6 2AB",
                "",
                "Rent: 950 pounds per month",
            ],
            ["Signed by Raj Patel", "Sort code 20-45-77, account no 31926819"],
        ]
    )
