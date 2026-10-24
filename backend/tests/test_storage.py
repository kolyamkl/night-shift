from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import os
from threading import Barrier

import pytest
from cryptography.fernet import Fernet
from evalkit.redact import restore

from app.extract import extract_pdf, extract_text
from app.pipeline import T1Result, rebuild, run_pipeline
from app.storage import MissingDocument, PostgresStore, StaleRevision


def detector(_text):
    return T1Result([{"text": "Raj Patel", "type": "PERSON"}], "mreq_test", None)


def test_reconnect_preserves_pdf_vault_layout_and_review_edits(postgres_store, tenancy_pdf):
    doc = extract_pdf(tenancy_pdf, "private-lease.pdf")
    postgres_store.create(doc)
    result = run_pipeline(doc, detector)
    result = rebuild(doc, result, hide={"950 pounds": "CUSTOM"}, unhide={"20-45-77"})
    assert postgres_store.save_result(doc.doc_id, result, 0) == 1
    # A new object opens fresh database connections and loads everything from disk.
    fresh = PostgresStore(postgres_store._url, os.environ.get("VEIL_STORAGE_KEY")
                          or "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    fresh.initialize()
    saved = fresh.get(doc.doc_id, owner_id=postgres_store.test_owner)
    assert asdict(saved.document) == asdict(doc)
    assert asdict(saved.result) == asdict(result)
    assert restore("Tenant [PERSON_1]", saved.result.vault)[0] == "Tenant Raj Patel"
    assert saved.revision == 1


def test_database_payloads_do_not_contain_original_text_or_vault(postgres_store):
    doc = extract_text("Raj Patel secret CL-20931", "Raj Patel.txt")
    postgres_store.create(doc)
    postgres_store.save_result(doc.doc_id, run_pipeline(doc, detector), 0)
    with postgres_store.connect() as conn:
        row = conn.execute("""SELECT d.payload, r.payload FROM veil_documents d
            JOIN veil_redactions r USING (doc_id) WHERE doc_id = %s""", (doc.doc_id,)).fetchone()
    for value in row:
        assert b"Raj Patel" not in bytes(value)
        assert b"CL-20931" not in bytes(value)
    assert postgres_store.get(doc.doc_id).document.text == doc.text


def test_wrong_key_fails_before_any_write(postgres_store):
    wrong = PostgresStore(postgres_store._url, Fernet.generate_key().decode())
    with pytest.raises(RuntimeError, match="does not match"):
        wrong.initialize()


def test_concurrent_results_cannot_silently_overwrite_each_other(postgres_store):
    doc = extract_text("Raj Patel")
    postgres_store.create(doc)
    barrier = Barrier(2)

    def save(value):
        saved = postgres_store.get(doc.doc_id)
        result = run_pipeline(doc, detector)
        result = rebuild(doc, result, hide={"Raj Patel": value})
        barrier.wait(timeout=5)
        try:
            postgres_store.save_result(doc.doc_id, result, saved.revision)
            return value
        except StaleRevision:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, ["PERSON", "CUSTOM"]))
    winners = [r for r in results if r is not None]
    assert len(winners) == 1
    assert postgres_store.get(doc.doc_id).result.hidden == {"Raj Patel": winners[0]}
    assert postgres_store.get(doc.doc_id).revision == 1


def test_delete_cascades_and_late_scan_cannot_resurrect_document(postgres_store):
    doc = extract_text("Raj Patel")
    postgres_store.create(doc)
    result = run_pipeline(doc, detector)
    postgres_store.save_result(doc.doc_id, result, 0)
    postgres_store.delete(doc.doc_id)
    with postgres_store.connect() as conn:
        assert conn.execute("SELECT 1 FROM veil_redactions WHERE doc_id = %s", (doc.doc_id,)).fetchone() is None
    with pytest.raises(MissingDocument):
        postgres_store.get(doc.doc_id)
    with pytest.raises(MissingDocument):
        postgres_store.save_result(doc.doc_id, result, 1)


def test_migrations_are_idempotent(postgres_store):
    postgres_store.initialize()
    postgres_store.initialize()
    with postgres_store.connect() as conn:
        assert conn.execute("SELECT count(*) FROM veil_schema_migrations").fetchone()[0] == 2


def test_configuration_fails_closed():
    with pytest.raises(RuntimeError, match="Set DATABASE_URL"):
        PostgresStore("", "")
    with pytest.raises(RuntimeError, match="Fernet key"):
        PostgresStore("postgresql://example", "bad")


def test_scan_reservations_supersede_across_store_instances(postgres_store):
    doc = extract_text("Raj Patel")
    postgres_store.create(doc)
    owner = postgres_store.test_owner
    second = PostgresStore(postgres_store._url, os.environ.get("VEIL_STORAGE_KEY")
                           or "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    old = postgres_store.begin_scan(doc.doc_id, owner_id=owner)
    new = second.begin_scan(doc.doc_id, owner_id=owner)
    assert new.revision > old.revision
    assert not postgres_store.is_current(doc.doc_id, old.revision, owner_id=owner)
    assert second.is_current(doc.doc_id, new.revision, owner_id=owner)
    result = run_pipeline(doc, detector, plan="evalkit")
    with pytest.raises(StaleRevision):
        postgres_store.save_result(doc.doc_id, result, old.revision)
    second.save_result(doc.doc_id, result, new.revision, owner_id=owner)
    assert postgres_store.get(doc.doc_id).result.plan == "evalkit"


def test_legacy_snapshot_loads_without_stream_metadata(postgres_store):
    doc = extract_text("Raj Patel")
    postgres_store.create(doc)
    original = run_pipeline(doc, detector)
    legacy = asdict(original)
    legacy["unhidden"] = []
    for key in ("plan", "chunk_values"):
        legacy.pop(key)
    for chunk in legacy["chunks"]:
        for key in ("index", "status", "latency_ms"):
            chunk.pop(key)
    with postgres_store.connect() as conn:
        conn.execute("INSERT INTO veil_redactions (doc_id, payload) VALUES (%s, %s)",
                     (doc.doc_id, postgres_store._encrypt(doc.doc_id, "result", legacy)))
    saved = postgres_store.get(doc.doc_id).result
    assert saved.redacted_text == original.redacted_text
    assert saved.chunks[0].index == 0 and saved.chunks[0].status == "ok"
    assert saved.plan == "" and saved.chunk_values == []
