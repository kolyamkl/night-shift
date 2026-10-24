import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from threading import Barrier

import pytest
from conftest import storage_key
from cryptography.fernet import Fernet
from evalkit.redact import restore

from app.core.errors import MissingDocument, StaleRevision
from app.db.database import Database
from app.domain.extract import extract_pdf, extract_text
from app.domain.pipeline import T1Result, rebuild, run_pipeline
from app.repositories import Storage


def detector(_text):
    return T1Result([{"text": "Raj Patel", "type": "PERSON"}], "mreq_test", None)


def test_reconnect_preserves_pdf_vault_layout_and_review_edits(postgres_store, tenancy_pdf):
    doc = extract_pdf(tenancy_pdf, "private-lease.pdf")
    postgres_store.documents.create(doc)
    result = run_pipeline(doc, detector)
    result = rebuild(doc, result, hide={"950 pounds": "CUSTOM"}, unhide={"20-45-77"})
    assert postgres_store.documents.save_result(doc.doc_id, result, 0) == 1
    # A new object opens fresh database connections and loads everything from disk.
    fresh = Storage(Database(postgres_store.db.url, storage_key()))
    fresh.db.migrate()
    saved = fresh.documents.get(doc.doc_id, owner_id=postgres_store.test_owner)
    assert asdict(saved.document) == asdict(doc)
    assert asdict(saved.result) == asdict(result)
    assert restore("Tenant [PERSON_1]", saved.result.vault)[0] == "Tenant Raj Patel"
    assert saved.revision == 1


def test_database_payloads_do_not_contain_original_text_or_vault(postgres_store):
    doc = extract_text("Raj Patel secret CL-20931", "Raj Patel.txt")
    postgres_store.documents.create(doc)
    postgres_store.documents.save_result(doc.doc_id, run_pipeline(doc, detector), 0)
    with postgres_store.db.connect() as conn:
        row = conn.execute("""SELECT d.payload, r.payload FROM veil_documents d
            JOIN veil_redactions r USING (doc_id) WHERE doc_id = %s""", (doc.doc_id,)).fetchone()
    for value in row:
        assert b"Raj Patel" not in bytes(value)
        assert b"CL-20931" not in bytes(value)
    assert postgres_store.documents.get(doc.doc_id).document.text == doc.text


def test_wrong_key_fails_before_any_write(postgres_store):
    wrong = Database(postgres_store.db.url, Fernet.generate_key().decode())
    with pytest.raises(RuntimeError, match="does not match"):
        wrong.migrate()
    wrong.close()


def test_concurrent_results_cannot_silently_overwrite_each_other(postgres_store):
    doc = extract_text("Raj Patel")
    postgres_store.documents.create(doc)
    barrier = Barrier(2)

    def save(value):
        saved = postgres_store.documents.get(doc.doc_id)
        result = run_pipeline(doc, detector)
        result = rebuild(doc, result, hide={"Raj Patel": value})
        barrier.wait(timeout=5)
        try:
            postgres_store.documents.save_result(doc.doc_id, result, saved.revision)
            return value
        except StaleRevision:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, ["PERSON", "CUSTOM"]))
    winners = [r for r in results if r is not None]
    assert len(winners) == 1
    assert postgres_store.documents.get(doc.doc_id).result.hidden == {"Raj Patel": winners[0]}
    assert postgres_store.documents.get(doc.doc_id).revision == 1


def test_delete_cascades_and_late_scan_cannot_resurrect_document(postgres_store):
    doc = extract_text("Raj Patel")
    postgres_store.documents.create(doc)
    result = run_pipeline(doc, detector)
    postgres_store.documents.save_result(doc.doc_id, result, 0)
    postgres_store.documents.delete(doc.doc_id)
    with postgres_store.db.connect() as conn:
        assert conn.execute("SELECT 1 FROM veil_redactions WHERE doc_id = %s", (doc.doc_id,)).fetchone() is None
    with pytest.raises(MissingDocument):
        postgres_store.documents.get(doc.doc_id)
    with pytest.raises(MissingDocument):
        postgres_store.documents.save_result(doc.doc_id, result, 1)


def test_migrations_are_idempotent(postgres_store):
    postgres_store.db.migrate()
    postgres_store.db.migrate()
    with postgres_store.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM veil_schema_migrations").fetchone()[0] == 3


def test_configuration_fails_closed():
    with pytest.raises(RuntimeError, match="Set DATABASE_URL"):
        Database("", "")
    with pytest.raises(RuntimeError, match="Fernet key"):
        Database("postgresql://example", "bad")


def test_scan_reservations_supersede_across_store_instances(postgres_store):
    doc = extract_text("Raj Patel")
    postgres_store.documents.create(doc)
    owner = postgres_store.test_owner
    second = Storage(Database(postgres_store.db.url, storage_key()))
    old = postgres_store.documents.begin_scan(doc.doc_id, owner_id=owner)
    new = second.documents.begin_scan(doc.doc_id, owner_id=owner)
    assert new.revision > old.revision
    assert not postgres_store.documents.is_current(doc.doc_id, old.revision, owner_id=owner)
    assert second.documents.is_current(doc.doc_id, new.revision, owner_id=owner)
    result = run_pipeline(doc, detector, plan="evalkit")
    with pytest.raises(StaleRevision):
        postgres_store.documents.save_result(doc.doc_id, result, old.revision)
    second.documents.save_result(doc.doc_id, result, new.revision, owner_id=owner)
    assert postgres_store.documents.get(doc.doc_id).result.plan == "evalkit"


def test_legacy_snapshot_loads_without_stream_metadata(postgres_store):
    doc = extract_text("Raj Patel")
    postgres_store.documents.create(doc)
    original = run_pipeline(doc, detector)
    legacy = asdict(original)
    legacy["unhidden"] = []
    for key in ("plan", "chunk_values"):
        legacy.pop(key)
    for chunk in legacy["chunks"]:
        for key in ("index", "status", "latency_ms"):
            chunk.pop(key)
    with postgres_store.db.connect() as conn:
        conn.execute("INSERT INTO veil_redactions (doc_id, payload) VALUES (%s, %s)",
                     (doc.doc_id, postgres_store.db.envelope.seal(doc.doc_id, "result", legacy)))
    saved = postgres_store.documents.get(doc.doc_id).result
    assert saved.redacted_text == original.redacted_text
    assert saved.chunks[0].index == 0 and saved.chunks[0].status == "ok"
    assert saved.plan == "" and saved.chunk_values == []


def test_rows_saved_before_the_summary_column_still_list(postgres_store, tenancy_pdf):
    pdf = extract_pdf(tenancy_pdf, "synthetic-lease.pdf")
    note = extract_text("Raj Patel", "synthetic-note.txt")
    postgres_store.documents.create(pdf)
    postgres_store.documents.create(note)
    result = run_pipeline(pdf, detector)
    postgres_store.documents.save_result(pdf.doc_id, result, 0)
    owner = postgres_store.test_owner
    # What migration 003 leaves on older rows; status 'new' with a result is a scan saved by the
    # previous release while a deploy overlapped, after the migration ran.
    with postgres_store.db.connect() as conn:
        conn.execute("UPDATE veil_documents SET meta = NULL, status = 'new' WHERE owner_id = %s", (owner,))
    expected = {pdf.doc_id: ("synthetic-lease.pdf", "pdf", 2, len(result.spans), True, "review"),
                note.doc_id: ("synthetic-note.txt", "text", 0, None, False, "new")}
    for _ in range(2):  # the first listing fills the summaries, the second reads them
        listed = {d["doc_id"]: (d["filename"], d["kind"], d["pages"], d["changes"], d["has_result"], d["status"])
                  for d in postgres_store.documents.list_documents(owner_id=owner)}
        assert listed == expected
        assert postgres_store.documents.get(pdf.doc_id).status == "review"
        with postgres_store.db.connect() as conn:
            assert conn.execute("SELECT count(*) FROM veil_documents WHERE owner_id = %s AND meta IS NULL",
                                (owner,)).fetchone()[0] == 0
    # A result saved while the summary is still missing is counted when the row is first listed.
    with postgres_store.db.connect() as conn:
        conn.execute("UPDATE veil_documents SET meta = NULL WHERE doc_id = %s", (pdf.doc_id,))
    more = rebuild(pdf, result, hide={"950 pounds": "CUSTOM"})
    postgres_store.documents.save_result(pdf.doc_id, more, 1)
    listed = {d["doc_id"]: d for d in postgres_store.documents.list_documents(owner_id=owner)}
    assert listed[pdf.doc_id]["changes"] == len(more.spans) == len(result.spans) + 1


def test_listing_stops_at_200_documents(postgres_store):
    owner = postgres_store.test_owner
    ids = [uuid.uuid4().hex for _ in range(201)]
    rows = [(i, b"unused", owner, postgres_store.db.envelope.seal(i, "meta", {
        "filename": "synthetic.txt", "kind": "text", "pages": 0, "changes": None})) for i in ids]
    with postgres_store.db.connect() as conn:
        with conn.cursor() as cur:
            cur.executemany("INSERT INTO veil_documents (doc_id, payload, owner_id, meta) VALUES (%s, %s, %s, %s)",
                            rows)
    assert len(postgres_store.documents.list_documents(owner_id=owner)) == 200


def test_migration_003_is_additive_on_a_database_with_rows(postgres_store):
    migrations = Path(__file__).resolve().parents[1] / "migrations"
    schema = f"migration_test_{postgres_store.test_suffix}"
    with postgres_store.db.connect() as conn:
        try:
            conn.execute(f'CREATE SCHEMA "{schema}"')
            conn.execute(f'SET LOCAL search_path TO "{schema}"')
            for name in ("001_documents.sql", "002_auth.sql"):
                conn.execute((migrations / name).read_text())
            conn.execute("INSERT INTO veil_users (user_id, email, password_hash) VALUES ('u', 'u@example.test', 'x')")
            conn.execute("""INSERT INTO veil_documents (doc_id, payload, owner_id)
                VALUES ('scanned', 'x', 'u'), ('fresh', 'x', 'u'), ('ownerless', 'x', NULL)""")
            conn.execute("INSERT INTO veil_redactions (doc_id, payload) VALUES ('scanned', 'x')")
            conn.execute((migrations / "003_status_and_chat.sql").read_text())
            assert conn.execute("SELECT doc_id, status, meta, revision FROM veil_documents ORDER BY doc_id").fetchall() == [
                ("fresh", "new", None, 0), ("ownerless", "new", None, 0), ("scanned", "review", None, 0)]
            conn.execute("INSERT INTO veil_chat_turns (doc_id, owner_id, payload) VALUES ('scanned', 'u', 'x')")
            conn.execute("DELETE FROM veil_documents WHERE doc_id = 'scanned'")
            assert conn.execute("SELECT count(*) FROM veil_chat_turns").fetchone()[0] == 0
        finally:
            conn.rollback()  # drops the schema with everything in it
