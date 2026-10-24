import json
import re
from dataclasses import replace

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.domain.pipeline import T1Result
from app.main import app


@pytest.fixture
def client(postgres_store):
    def t1_factory(doc_id):
        def t1(chunk):
            ents = [{"text": v, "type": "PERSON"} for v in ("Raj Patel", "Jo Smith") if v in chunk]
            return T1Result(ents, "mreq_test", None)
        return t1

    def t2(question, redacted_text):
        assert "Raj Patel" not in redacted_text and "Jo Smith" not in redacted_text
        return "The tenant is [PERSON_1].", "mreq_answer"

    app.state.models.t1_factory = t1_factory
    app.state.models.t2 = t2
    with TestClient(app, headers={"X-Veil-Request": "1"}, client=(postgres_store.test_suffix, 50000)) as test_client:
        response = test_client.post("/api/auth/register", json={"email": f"api-{postgres_store.test_suffix}@example.test", "password": "test-password"})
        assert response.status_code == 201
        yield test_client
    app.state.models.t1_factory = None
    app.state.models.t2 = None


def test_pasted_text_is_redacted(client):
    doc = client.post("/api/documents", data={"text": "Hi, I am Jo Smith, sort code 20-45-77."}).json()
    res = client.post(f"/api/documents/{doc['doc_id']}/redact").json()
    assert res["redacted_text"] == "Hi, I am [PERSON_1], sort code [SORT_CODE_1]."
    assert res["stats"] == {"PERSON": 1, "SORT_CODE": 1}
    assert res["chunks"][0]["mreq_id"] == "mreq_test"
    assert res["chunks"][0]["status"] == "ok"
    assert isinstance(res["chunks"][0]["latency_ms"], int)


def test_pdf_upload_gives_boxes_a_page_image_and_a_redacted_file(client, tenancy_pdf):
    doc = client.post("/api/documents", files={"file": ("lease.pdf", tenancy_pdf, "application/pdf")}).json()
    assert doc["kind"] == "pdf" and len(doc["pages"]) == 2
    res = client.post(f"/api/documents/{doc['doc_id']}/redact").json()
    assert {b["page"] for b in res["boxes"]} == {0, 1}
    png = client.get(f"/api/documents/{doc['doc_id']}/pages/0.png")
    assert png.headers["content-type"] == "image/png" and png.content[:4] == b"\x89PNG"
    out = client.get(f"/api/documents/{doc['doc_id']}/file")
    assert out.headers["content-type"] == "application/pdf"
    text = "".join(p.get_text() for p in pymupdf.open(stream=out.content, filetype="pdf"))
    assert "Patel" not in text


def test_text_document_downloads_as_redacted_text(client):
    doc = client.post("/api/documents", data={"text": "Jo Smith"}).json()
    client.post(f"/api/documents/{doc['doc_id']}/redact")
    out = client.get(f"/api/documents/{doc['doc_id']}/file")
    assert out.text == "[PERSON_1]"


def test_ask_sends_only_redacted_text_and_restores_the_answer(client):
    doc = client.post("/api/documents", data={"text": "Tenant: Raj Patel. Rent 950."}).json()
    client.post(f"/api/documents/{doc['doc_id']}/redact")
    ans = client.post(f"/api/documents/{doc['doc_id']}/ask", json={"question": "Who is the tenant?"}).json()
    assert ans["answer"] == "The tenant is Raj Patel."
    assert ans["answer_with_placeholders"] == "The tenant is [PERSON_1]."
    assert "[PERSON_1]" in ans["sent_text"] and "Raj Patel" not in ans["sent_text"]


def test_corrections_hide_and_unhide(client):
    doc = client.post("/api/documents", data={"text": "Jo Smith, client CL-20931."}).json()
    did = doc["doc_id"]
    client.post(f"/api/documents/{did}/redact")
    hidden = client.post(f"/api/documents/{did}/corrections",
                         json={"action": "hide", "text": "CL-20931", "type": "CUSTOM"}).json()
    assert hidden["redacted_text"] == "[PERSON_1], client [CUSTOM_1]."
    shown = client.post(f"/api/documents/{did}/corrections", json={"action": "unhide", "text": "Jo Smith"}).json()
    assert shown["redacted_text"] == "Jo Smith, client [CUSTOM_1]."


def test_unknown_document_is_404(client):
    assert client.post("/api/documents/nope/redact").status_code == 404


@pytest.mark.parametrize("route", ["/redact", "/redact/stream"])
@pytest.mark.parametrize("retry", ["", "?retry=failed"])
@pytest.mark.parametrize("kind", ["text", "pdf"])
def test_manual_corrections_survive_rescan_and_download(client, route, retry, kind):
    text = "Tenant: Jo Smith. Private phrase: silver meadow."
    if kind == "pdf":
        with pymupdf.open() as pdf:
            pdf.new_page().insert_text((72, 72), text)
            doc = client.post("/api/documents", files={
                "file": ("synthetic-contract.pdf", pdf.tobytes(), "application/pdf")}).json()
    else:
        doc = client.post("/api/documents", data={"text": text}).json()
    path = f"/api/documents/{doc['doc_id']}"
    assert client.post(path + "/redact").status_code == 200
    assert client.post(path + "/corrections", json={
        "action": "hide", "text": "silver meadow", "type": "CUSTOM"}).status_code == 200
    corrected = client.post(path + "/corrections", json={
        "action": "unhide", "text": "Jo Smith"}).json()
    assert "silver meadow" not in corrected["redacted_text"]
    assert "Jo Smith" in corrected["redacted_text"]

    response = client.post(path + route + retry)
    assert response.status_code == 200
    saved = client.get(path).json()["result"]
    assert saved["redacted_text"] == corrected["redacted_text"]
    assert saved["boxes"] == corrected["boxes"]
    downloaded = client.get(path + "/file")
    assert downloaded.status_code == 200
    if kind == "pdf":
        with pymupdf.open(stream=downloaded.content, filetype="pdf") as pdf:
            downloaded_text = "".join(page.get_text() for page in pdf)
    else:
        downloaded_text = downloaded.text
    assert "silver meadow" not in downloaded_text
    assert "Jo Smith" in downloaded_text


def test_health_reports_whether_the_model_is_on(client):
    app.state.models.t1_factory = None
    assert client.get("/api/health").json()["model"] == "off"


def test_document_and_corrections_survive_app_restart(client):
    doc = client.post("/api/documents", data={"text": "Jo Smith, client CL-20931."}).json()
    path = f"/api/documents/{doc['doc_id']}"
    assert client.get(path).json()["result"] is None
    client.post(path + "/redact")
    client.post(path + "/corrections", json={"action": "hide", "text": "CL-20931"})
    # Run a fresh application lifespan (no process-local document/result dictionaries).
    with TestClient(app, headers={"X-Veil-Request": "1"}, cookies=client.cookies) as restarted:
        saved = restarted.get(path).json()
        assert saved["document"] == doc
        assert saved["revision"] == 3
        assert saved["result"]["redacted_text"] == "[PERSON_1], client [CUSTOM_1]."
        assert restarted.post(path + "/ask", json={"question": "Who?"}).json()["answer"] == "The tenant is Jo Smith."
        assert restarted.delete(path).status_code == 204
        assert restarted.get(path).status_code == 404
        assert restarted.get(path + "/file").status_code == 404


def test_read_and_delete_unknown_document(client):
    assert client.get("/api/documents/missing").status_code == 404
    assert client.delete("/api/documents/missing").status_code == 404


def test_database_errors_are_sanitized(client, postgres_store, monkeypatch):
    import psycopg

    def fail():
        raise psycopg.OperationalError("secret connection string")

    monkeypatch.setattr(postgres_store.db, "healthy", fail)
    response = client.get("/api/health")
    assert response.status_code == 503
    assert "secret" not in response.text


def test_samples_are_listed_and_open_as_documents(client, tenancy_pdf, tmp_path, monkeypatch):
    (tmp_path / "01_tenancy_agreement.pdf").write_bytes(tenancy_pdf)
    monkeypatch.setattr(app.state, "config", replace(app.state.config, samples_dir=tmp_path))
    names = client.get("/api/samples").json()
    assert names == [{"name": "01_tenancy_agreement.pdf", "label": "Tenancy agreement", "title": "Tenancy agreement",
                      "kind": "tenancy_agreement", "pages": 2, "values": None, "types": {}}]
    doc = client.post("/api/samples/01_tenancy_agreement.pdf").json()
    assert doc["kind"] == "pdf" and doc["filename"] == "01_tenancy_agreement.pdf"
    assert client.post("/api/samples/../../etc/passwd").status_code == 404


def test_sample_cards_use_the_gold_file_for_title_and_value_counts(client, tenancy_pdf, tmp_path, monkeypatch):
    (tmp_path / "02_tenancy_agreement.pdf").write_bytes(tenancy_pdf)
    gold = {"doc_type": "tenancy_agreement", "text": "Periodic Tenancy Agreement\nTenant: Raj Patel",
            "entities": [{"type": "PERSON"}, {"type": "PERSON"}, {"type": "SORT_CODE"}]}
    (tmp_path / "02_tenancy_agreement.gold.json").write_text(json.dumps(gold))
    monkeypatch.setattr(app.state, "config", replace(app.state.config, samples_dir=tmp_path))
    card = client.get("/api/samples").json()[0]
    assert card["title"] == "Periodic Tenancy Agreement"
    assert card["values"] == 3 and card["types"] == {"PERSON": 2, "SORT_CODE": 1}


def test_sample_thumbnail_is_a_small_png_of_page_one(client, tenancy_pdf, tmp_path, monkeypatch):
    (tmp_path / "01_tenancy_agreement.pdf").write_bytes(tenancy_pdf)
    monkeypatch.setattr(app.state, "config", replace(app.state.config, samples_dir=tmp_path))
    png = client.get("/api/samples/01_tenancy_agreement.pdf/thumb.png")
    assert png.headers["content-type"] == "image/png"
    assert pymupdf.Pixmap(png.content).width == 120
    assert client.get("/api/samples/..%2F..%2Fsecret.pdf/thumb.png").status_code == 404


def test_sample_labels_keep_acronyms_upper_case():
    from app.services.samples import label as _label

    assert _label("05_nda.pdf") == "NDA"
    assert _label("27_cv.pdf") == "CV"
    assert _label("29_hr_form.pdf") == "HR form"
    assert _label("23_gov_letter.pdf") == "Government letter"


def test_health_names_the_prompt_and_where_the_key_came_from(client, monkeypatch):
    monkeypatch.setattr(app.state.models, "key_source", ".env")
    monkeypatch.setattr(app.state.models, "t1_prompt", "rewrite")
    monkeypatch.setattr(app.state.models, "t1_model", "claude-haiku-4-5")
    monkeypatch.setattr(app.state.models, "t2_model", "claude-haiku-4-5")
    health = client.get("/api/health").json()
    assert health == {"model": "on", "t1_model": "claude-haiku-4-5", "t1_prompt": "rewrite",
                      "t2_model": "claude-haiku-4-5", "key_source": ".env", "database": "postgresql"}
    assert "mbt_" not in json.dumps(health)


@pytest.mark.parametrize("name", ["settings.py", "app.tsx", "deploy.yaml", "query.sql", "Dockerfile", "notes.weird"])
def test_code_config_and_other_text_files_are_read_as_text(client, name):
    doc = client.post("/api/documents", files={"file": (name, b"owner = 'Jo Smith'\n", "text/plain")}).json()
    assert doc["kind"] == "text" and doc["filename"] == name and doc["text"] == "owner = 'Jo Smith'\n"


@pytest.mark.parametrize("data", [b"PK\x03\x04\x00\x00binary", b"\xff\xfe\xfa not utf-8"])
def test_real_binaries_are_still_refused(client, data):
    res = client.post("/api/documents", files={"file": ("archive.bin", data, "application/octet-stream")})
    assert res.status_code == 415
    assert res.json()["detail"] == "This file type is not supported yet. Use PDF, an image, TXT or EML, or paste the text."


def test_an_empty_text_file_is_refused(client):
    res = client.post("/api/documents", files={"file": ("empty.txt", b"  \n", "text/plain")})
    assert res.status_code == 400


ISO_UTC = r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$"


def test_document_list_holds_only_the_callers_documents_newest_first(client, postgres_store, tenancy_pdf):
    note = client.post("/api/documents", files={"file": ("synthetic-note.txt", b"Tenant: Jo Smith.", "text/plain")}).json()
    pdf = client.post("/api/documents", files={"file": ("synthetic-lease.pdf", tenancy_pdf, "application/pdf")}).json()
    pasted = client.post("/api/documents", data={"text": "Tenant: Raj Patel, sort code 20-45-77."}).json()
    scanned = client.post(f"/api/documents/{pasted['doc_id']}/redact").json()
    client.post(f"/api/documents/{pasted['doc_id']}/ask", json={"question": "Who is the tenant?"})
    client.post(f"/api/documents/{pasted['doc_id']}/ask", json={"question": "What is the sort code?"})

    response = client.get("/api/documents")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    listed = response.json()
    assert [d["doc_id"] for d in listed] == [pasted["doc_id"], pdf["doc_id"], note["doc_id"]]
    first = listed[0]
    assert set(first) == {"doc_id", "filename", "kind", "pages", "status", "created_at", "updated_at",
                          "has_result", "changes", "turns"}
    assert (first["filename"], first["kind"], first["pages"], first["status"]) == ("pasted.txt", "text", 0, "review")
    assert (first["has_result"], first["changes"], first["turns"]) == (True, len(scanned["entities"]), 2)
    assert first["changes"] == 2
    assert {k: listed[1][k] for k in ("filename", "kind", "pages", "status", "has_result", "changes", "turns")} == {
        "filename": "synthetic-lease.pdf", "kind": "pdf", "pages": 2, "status": "new",
        "has_result": False, "changes": None, "turns": 0}
    assert listed[2]["filename"] == "synthetic-note.txt"
    for doc in listed:
        assert re.match(ISO_UTC, doc["created_at"]) and re.match(ISO_UTC, doc["updated_at"])
        assert doc["updated_at"] >= doc["created_at"]
    assert "Raj Patel" not in response.text and "Jo Smith" not in response.text  # no document text

    client.post("/api/auth/logout")
    other = {"email": f"api-other-{postgres_store.test_suffix}@example.test", "password": "test-password"}
    assert client.post("/api/auth/register", json=other).status_code == 201
    assert client.get("/api/documents").json() == []
    mine = client.post("/api/documents", data={"text": "Jo Smith"}).json()
    assert [d["doc_id"] for d in client.get("/api/documents").json()] == [mine["doc_id"]]
    client.post("/api/auth/logout")
    assert client.get("/api/documents").status_code == 401


def test_review_status_follows_scans_and_patch(client):
    doc = client.post("/api/documents", data={"text": "Tenant: Jo Smith. Private phrase: silver meadow."}).json()
    path = f"/api/documents/{doc['doc_id']}"

    def status():
        listed = {d["doc_id"]: d["status"] for d in client.get("/api/documents").json()}
        saved = client.get(path).json()["status"]
        assert listed[doc["doc_id"]] == saved
        return saved

    assert status() == "new"
    assert client.post(path + "/redact").status_code == 200
    assert status() == "review"
    response = client.patch(path, json={"status": "approved"})
    assert response.status_code == 200 and response.json() == {"doc_id": doc["doc_id"], "status": "approved"}
    # Editing and rescanning after approval keep the approval (PR 18).
    client.post(path + "/corrections", json={"action": "hide", "text": "silver meadow"})
    client.post(path + "/redact")
    client.post(path + "/redact/stream")
    assert status() == "approved"
    assert client.patch(path, json={"status": "declined"}).json()["status"] == "declined"
    client.post(path + "/redact")
    assert status() == "declined"
    assert client.patch(path, json={"status": "review"}).json()["status"] == "review"
    assert status() == "review"
    for bad in ({"status": "new"}, {"status": "done"}, {}, {"status": None}):
        assert client.patch(path, json=bad).status_code == 422
    assert status() == "review"
    assert client.patch("/api/documents/missing", json={"status": "approved"}).status_code == 404
    assert client.patch(path, json={"status": "approved"}, headers={"X-Veil-Request": ""}).status_code == 403

    streamed = client.post("/api/documents", data={"text": "Jo Smith"}).json()
    assert client.post(f"/api/documents/{streamed['doc_id']}/redact/stream").status_code == 200
    assert client.get(f"/api/documents/{streamed['doc_id']}").json()["status"] == "review"


def test_chat_turns_are_stored_in_order_and_failed_asks_store_nothing(client):
    doc = client.post("/api/documents", data={"text": "Tenant: Raj Patel. Rent 950."}).json()
    path = f"/api/documents/{doc['doc_id']}"
    assert client.post(path + "/ask", json={"question": "Too early?"}).status_code == 409
    client.post(path + "/redact")
    answers = [client.post(path + "/ask", json={"question": q}).json() for q in ("Who is the tenant?", "And again?")]
    for answer in answers:
        assert isinstance(answer["turn_id"], int) and re.match(ISO_UTC, answer["created_at"])
        assert answer["answer"] == "The tenant is Raj Patel."
    assert answers[0]["turn_id"] < answers[1]["turn_id"]
    turns = client.get(path).json()["turns"]
    assert turns == [{"turn_id": a["turn_id"], "created_at": a["created_at"], "question": q, "sent_question": q,
                      "answer": "The tenant is Raj Patel.", "answer_with_placeholders": "The tenant is [PERSON_1].",
                      "unknown_placeholders": [], "mreq_id": "mreq_answer"}
                     for a, q in zip(answers, ("Who is the tenant?", "And again?"))]

    def broken(question, redacted_text):
        raise RuntimeError("gateway timeout")

    app.state.models.t2 = broken
    assert client.post(path + "/ask", json={"question": "Lost question?"}).status_code == 502
    app.state.models.t2 = None
    assert client.post(path + "/ask", json={"question": "Lost question?"}).status_code == 503
    assert client.get(path).json()["turns"] == turns
    assert [d["turns"] for d in client.get("/api/documents").json() if d["doc_id"] == doc["doc_id"]] == [2]


def test_status_and_turns_survive_app_restart_and_go_with_the_document(client, postgres_store):
    doc = client.post("/api/documents", data={"text": "Tenant: Raj Patel."}).json()
    path = f"/api/documents/{doc['doc_id']}"
    client.post(path + "/redact")
    client.patch(path, json={"status": "approved"})
    turn = client.post(path + "/ask", json={"question": "Who is the tenant?"}).json()
    with TestClient(app, headers={"X-Veil-Request": "1"}, cookies=client.cookies) as restarted:
        saved = restarted.get(path).json()
        assert saved["status"] == "approved"
        assert [t["turn_id"] for t in saved["turns"]] == [turn["turn_id"]]
        assert restarted.get("/api/documents").json()[0]["doc_id"] == doc["doc_id"]
        assert restarted.delete(path).status_code == 204
    with postgres_store.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM veil_chat_turns WHERE doc_id = %s",
                            (doc["doc_id"],)).fetchone()[0] == 0
    assert client.get("/api/documents").json() == []


def test_raw_rows_hold_no_readable_filename_question_or_answer(client, postgres_store):
    secret_name = "synthetic-client-Raj-Patel.txt"
    doc = client.post("/api/documents", files={"file": (secret_name, b"Tenant: Raj Patel.", "text/plain")}).json()
    path = f"/api/documents/{doc['doc_id']}"
    client.post(path + "/redact")
    client.patch(path, json={"status": "approved"})
    client.post(path + "/ask", json={"question": "Where does Raj Patel bank?"})
    assert client.get("/api/documents").json()[0]["filename"] == secret_name
    with postgres_store.db.connect() as conn:
        rows = conn.execute("SELECT * FROM veil_documents WHERE doc_id = %s", (doc["doc_id"],)).fetchall()
        rows += conn.execute("SELECT * FROM veil_chat_turns WHERE doc_id = %s", (doc["doc_id"],)).fetchall()
        rows += conn.execute("SELECT * FROM veil_redactions WHERE doc_id = %s", (doc["doc_id"],)).fetchall()
    assert len(rows) == 3
    for value in (v for row in rows for v in row):
        raw = bytes(value) if isinstance(value, (bytes, memoryview)) else str(value).encode()
        for readable in (b"Raj Patel", b"Raj-Patel", b"synthetic-client", b"Where does", b"The tenant is"):
            assert readable not in raw


def test_image_sizes_are_bounded(client, tenancy_pdf, tmp_path, monkeypatch):
    # A huge thumbnail width or page scale would make the server render an enormous image.
    (tmp_path / "01_tenancy_agreement.pdf").write_bytes(tenancy_pdf)
    monkeypatch.setattr(app.state, "config", replace(app.state.config, samples_dir=tmp_path))
    assert client.get("/api/samples/01_tenancy_agreement.pdf/thumb.png?width=100000").status_code == 422
    assert client.get("/api/samples/01_tenancy_agreement.pdf/thumb.png?width=0").status_code == 422
    doc = client.post("/api/documents", files={"file": ("lease.pdf", tenancy_pdf, "application/pdf")}).json()
    assert client.get(f"/api/documents/{doc['doc_id']}/pages/0.png?scale=50").status_code == 422
    assert client.get(f"/api/documents/{doc['doc_id']}/pages/0.png?scale=0").status_code == 422
    assert client.get(f"/api/documents/{doc['doc_id']}/pages/0.png?scale=2").status_code == 200


def test_a_non_ascii_file_name_downloads(client):
    doc = client.post("/api/documents", files={"file": ("договір Zoë.txt", b"Jo Smith", "text/plain")}).json()
    client.post(f"/api/documents/{doc['doc_id']}/redact")
    out = client.get(f"/api/documents/{doc['doc_id']}/file")
    assert out.status_code == 200 and out.text == "[PERSON_1]"
    disposition = out.headers["content-disposition"]
    assert 'filename="_______ Zo_-redacted.txt"' in disposition
    assert "filename*=UTF-8''%D0%B4%D0%BE%D0%B3%D0%BE%D0%B2%D1%96%D1%80%20Zo%C3%AB-redacted.txt" in disposition


def test_an_upload_over_the_limit_is_refused(client, monkeypatch):
    monkeypatch.setattr(app.state, "config", replace(app.state.config, max_upload=1024 * 1024))
    big = client.post("/api/documents", files={"file": ("big.txt", b"a" * (1024 * 1024 + 1), "text/plain")})
    assert big.status_code == 413 and big.json() == {"detail": "The file is larger than 1 MB."}
    assert client.post("/api/documents", files={"file": ("ok.txt", b"a" * 1024, "text/plain")}).status_code == 200


def test_a_model_error_is_not_echoed_to_the_client(client):
    doc = client.post("/api/documents", data={"text": "Jo Smith"}).json()
    client.post(f"/api/documents/{doc['doc_id']}/redact")

    def broken(question, redacted_text):
        raise RuntimeError("upstream said: Document: [PERSON_1] secret-internal-detail")

    app.state.models.t2 = broken
    res = client.post(f"/api/documents/{doc['doc_id']}/ask", json={"question": "Who?"})
    assert res.status_code == 502 and res.json() == {"detail": "The model did not answer. Try again."}
