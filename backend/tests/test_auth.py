import uuid

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from app.auth import COOKIE, token_hash
from app.main import app


@pytest.fixture
def browser(postgres_store, monkeypatch):
    monkeypatch.setattr(app.state, "t1_factory", None)
    monkeypatch.setattr(app.state, "t2", None)
    with TestClient(app, headers={"X-Veil-Request": "1"},
                    client=(postgres_store.test_suffix, 50000)) as client:
        yield client
    with postgres_store.connect() as conn:
        conn.execute("DELETE FROM veil_auth_limits WHERE bucket = %s", (token_hash(postgres_store.test_suffix),))


def credentials(store, name="alice"):
    return {"email": f"{name}-{store.test_suffix}@example.test", "password": "a test password 123"}


def test_register_login_logout_and_password_hash(browser, postgres_store):
    body = credentials(postgres_store)
    registered = browser.post("/api/auth/register", json=body)
    assert registered.status_code == 201
    user = registered.json()
    assert set(user) == {"id", "email"}
    assert browser.get("/api/auth/me").json() == user
    cookie = registered.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Max-Age=604800" in cookie
    token = browser.cookies.get(COOKIE)
    with postgres_store.connect() as conn:
        stored = conn.execute("SELECT password_hash FROM veil_users WHERE user_id = %s", (user["id"],)).fetchone()[0]
        assert stored != body["password"] and PasswordHasher().verify(stored, body["password"])
        hashed = conn.execute("SELECT token_hash FROM veil_sessions WHERE user_id = %s", (user["id"],)).fetchone()[0]
        assert hashed == token_hash(token) and hashed != token
    assert browser.post("/api/auth/logout").status_code == 200
    assert browser.get("/api/auth/me").status_code == 401
    browser.cookies.set(COOKIE, token)
    assert browser.get("/api/auth/me").status_code == 401  # revoked token replay
    browser.cookies.clear()
    assert browser.post("/api/auth/login", json=body).json() == user
    assert browser.cookies.get(COOKIE) != token
    assert browser.get("/api/auth/me").headers["cache-control"] == "no-store"


def test_duplicate_email_normalization_and_wrong_password(browser, postgres_store):
    body = credentials(postgres_store)
    assert browser.post("/api/auth/register", json=body).status_code == 201
    duplicate = {**body, "email": " " + body["email"].upper() + " "}
    assert browser.post("/api/auth/register", json=duplicate).status_code == 409
    browser.post("/api/auth/logout")
    wrong = browser.post("/api/auth/login", json={**body, "password": "wrong password"})
    missing = browser.post("/api/auth/login", json=credentials(postgres_store, "missing"))
    assert wrong.status_code == missing.status_code == 401 and wrong.json() == missing.json()
    assert browser.post("/api/auth/login", json=duplicate).status_code == 200


def test_expiry_and_secure_cookie(browser, postgres_store, monkeypatch):
    monkeypatch.setenv("VEIL_COOKIE_SECURE", "true")
    response = browser.post("/api/auth/register", json=credentials(postgres_store))
    assert "Secure" in response.headers["set-cookie"]
    # Secure cookies are not sent over HTTP. Expiry is also enforced server side.
    assert browser.get("/api/auth/me").status_code == 401
    token = browser.cookies.get(COOKIE)
    browser.cookies.clear()
    browser.cookies.set(COOKIE, token)
    assert browser.get("/api/auth/me").status_code == 200
    with postgres_store.connect() as conn:
        conn.execute("UPDATE veil_sessions SET expires_at = now() - interval '1 second' WHERE token_hash = %s",
                     (token_hash(token),))
    assert browser.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("method,path,body", [
    ("post", "/api/documents", None),
    ("get", "/api/documents", None),
    ("get", "/api/documents/unknown", None),
    ("patch", "/api/documents/unknown", {"status": "approved"}),
    ("delete", "/api/documents/unknown", None),
    ("post", "/api/documents/unknown/redact", None),
    ("post", "/api/documents/unknown/redact/stream", None),
    ("get", "/api/documents/unknown/pages/0.png", None),
    ("get", "/api/documents/unknown/file", None),
    ("post", "/api/documents/unknown/corrections", {"action": "hide", "text": "test"}),
    ("post", "/api/documents/unknown/ask", {"question": "test"}),
    ("post", "/api/samples/test.pdf", None),
])
def test_documents_require_login(browser, method, path, body):
    assert browser.request(method, path, json=body).status_code == 401


def test_every_document_operation_is_owner_scoped(browser, postgres_store, tenancy_pdf):
    alice = credentials(postgres_store)
    browser.post("/api/auth/register", json=alice)
    doc = browser.post("/api/documents", files={"file": ("lease.pdf", tenancy_pdf, "application/pdf")}).json()
    path = f"/api/documents/{doc['doc_id']}"
    assert browser.post(path + "/redact").status_code == 200
    browser.post("/api/auth/logout")
    browser.post("/api/auth/register", json=credentials(postgres_store, "bob"))
    for method, suffix, body in [
        ("get", "", None), ("patch", "", {"status": "approved"}), ("delete", "", None), ("post", "/redact", None),
        ("post", "/redact/stream", None),
        ("get", "/pages/0.png", None), ("get", "/file", None),
        ("post", "/corrections", {"action": "hide", "text": "Raj Patel"}),
        ("post", "/ask", {"question": "Who?"}),
    ]:
        assert browser.request(method, path + suffix, json=body).status_code == 404
    assert browser.get("/api/documents").json() == []
    browser.post("/api/auth/logout")
    browser.post("/api/auth/login", json=alice)
    assert browser.get(path).json()["status"] == "review"
    assert [d["doc_id"] for d in browser.get("/api/documents").json()] == [doc["doc_id"]]
    assert browser.get(path + "/pages/0.png").status_code == 200
    assert browser.get(path + "/file").status_code == 200
    assert browser.delete(path).status_code == 204


def test_csrf_validation_and_throttle(browser, postgres_store):
    body = credentials(postgres_store)
    assert browser.post("/api/auth/register", json=body, headers={"X-Veil-Request": ""}).status_code == 403
    bad = browser.post("/api/auth/register", json={**body, "password": "short"})
    assert bad.status_code == 422 and "short" not in bad.text
    assert browser.post("/api/auth/register", json={**body, "email": "not-an-email"}).status_code == 422
    assert browser.options("/api/auth/login", headers={"Origin": "https://evil.example",
        "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "X-Veil-Request"}).status_code == 400
    with postgres_store.connect() as conn:
        conn.execute("INSERT INTO veil_auth_limits (bucket, attempts, reset_at) VALUES (%s, 30, now() + interval '1 minute')",
                     (token_hash(postgres_store.test_suffix),))
    limited = browser.post("/api/auth/register", json=body)
    assert limited.status_code == 429 and limited.headers["retry-after"] == "60"
    with postgres_store.connect() as conn:
        conn.execute("UPDATE veil_auth_limits SET reset_at = now() - interval '1 second' WHERE bucket = %s",
                     (token_hash(postgres_store.test_suffix),))
    assert browser.post("/api/auth/register", json=body).status_code == 201


def test_ownerless_legacy_documents_stay_private(browser, postgres_store):
    # Simulate a document saved before accounts existed, without deleting it.
    doc_id = uuid.uuid4().hex
    with postgres_store.connect() as conn:
        conn.execute("INSERT INTO veil_documents (doc_id, payload) VALUES (%s, %s)", (doc_id, b"legacy"))
    try:
        browser.post("/api/auth/register", json=credentials(postgres_store))
        assert browser.get(f"/api/documents/{doc_id}").status_code == 404
        assert browser.delete(f"/api/documents/{doc_id}").status_code == 404
    finally:
        with postgres_store.connect() as conn:
            conn.execute("DELETE FROM veil_documents WHERE doc_id = %s", (doc_id,))
