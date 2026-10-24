import json

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.pipeline import T1Result


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

    app.state.t1_factory = t1_factory
    app.state.t2 = t2
    with TestClient(app, headers={"X-Veil-Request": "1"}, client=(postgres_store.test_suffix, 50000)) as test_client:
        response = test_client.post("/api/auth/register", json={"email": f"api-{postgres_store.test_suffix}@example.test", "password": "test-password"})
        assert response.status_code == 201
        yield test_client
    app.state.t1_factory = None
    app.state.t2 = None


def test_pasted_text_is_redacted(client):
    doc = client.post("/api/documents", data={"text": "Hi, I am Jo Smith, sort code 20-45-77."}).json()
    res = client.post(f"/api/documents/{doc['doc_id']}/redact").json()
    assert res["redacted_text"] == "Hi, I am [PERSON_1], sort code [SORT_CODE_1]."
    assert res["stats"] == {"PERSON": 1, "SORT_CODE": 1}
    assert res["chunks"][0]["mreq_id"] == "mreq_test"


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


def test_health_reports_whether_the_model_is_on(client):
    app.state.t1_factory = None
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
        assert saved["revision"] == 2
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

    monkeypatch.setattr(postgres_store, "healthy", fail)
    response = client.get("/api/health")
    assert response.status_code == 503
    assert "secret" not in response.text


def test_samples_are_listed_and_open_as_documents(client, tenancy_pdf, tmp_path, monkeypatch):
    (tmp_path / "01_tenancy_agreement.pdf").write_bytes(tenancy_pdf)
    monkeypatch.setenv("VEIL_SAMPLES_DIR", str(tmp_path))
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
    monkeypatch.setenv("VEIL_SAMPLES_DIR", str(tmp_path))
    card = client.get("/api/samples").json()[0]
    assert card["title"] == "Periodic Tenancy Agreement"
    assert card["values"] == 3 and card["types"] == {"PERSON": 2, "SORT_CODE": 1}


def test_sample_thumbnail_is_a_small_png_of_page_one(client, tenancy_pdf, tmp_path, monkeypatch):
    (tmp_path / "01_tenancy_agreement.pdf").write_bytes(tenancy_pdf)
    monkeypatch.setenv("VEIL_SAMPLES_DIR", str(tmp_path))
    png = client.get("/api/samples/01_tenancy_agreement.pdf/thumb.png")
    assert png.headers["content-type"] == "image/png"
    assert pymupdf.Pixmap(png.content).width == 120
    assert client.get("/api/samples/..%2F..%2Fsecret.pdf/thumb.png").status_code == 404


def test_sample_labels_keep_acronyms_upper_case():
    from app.main import _label

    assert _label("05_nda.pdf") == "NDA"
    assert _label("27_cv.pdf") == "CV"
    assert _label("29_hr_form.pdf") == "HR form"
    assert _label("23_gov_letter.pdf") == "Government letter"
