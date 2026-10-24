# Local PostgreSQL storage

Veil now saves documents and redactions in PostgreSQL instead of process memory.
Email/password accounts protect every saved document. Registration signs the
user in immediately; there is no verification email or code.
Original text, filenames, source PDFs, extracted page layout, detected entities,
placeholder mappings, chunk results, and hide/unhide corrections are encrypted
before being written. Restarting the backend does not lose them. Opening the
same `/app?doc=<id>` URL restores the document and its last saved result without
another model call. The UI asks for review again; approvals and chat history are
not persisted by this change. Other open documents in the sidebar are still UI
state; save their individual URLs to reopen them.

## Run locally

Prerequisites: PostgreSQL 16+ binaries (`initdb`, `pg_ctl`, `psql`, `createdb`) on
PATH, uv, and Node compatible with the frontend dependencies.

From the repository root:

```sh
python3 scripts/local_db.py start
```

This creates an isolated cluster in ignored `.local/postgres`, listening only on
`127.0.0.1:55432`, with `veil` and `veil_test` databases. It generates a local
database password and a Fernet encryption key, saves private setup information in
`.local/postgres-config.json`, and adds `DATABASE_URL`, `TEST_DATABASE_URL`, and
`VEIL_STORAGE_KEY` to the ignored root `.env`. It preserves the Mubit key and
refuses to overwrite conflicting database settings. Repeating `start` reuses the
same cluster and key. TCP connections require SCRAM authentication; the local
Unix socket uses trust inside the private `.local` directory. The local `veil`
role is a cluster administrator for development only.

Backend, in a separate terminal:

```sh
cd backend
uv sync --frozen
uv run --env-file ../.env --no-sync uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend, in another terminal:

```sh
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open <http://127.0.0.1:5173/app>. `GET /api/health` checks database connectivity
and reports `database: "postgresql"`. Startup applies migrations and checks the
encryption key; missing configuration, an unavailable database, or a wrong key
stops startup instead of silently falling back to temporary memory.

From the root, inspect or stop only this cluster:

```sh
python3 scripts/local_db.py status
python3 scripts/local_db.py stop
```

Stopping does not delete data. For an existing PostgreSQL service, supply its
`DATABASE_URL` and generate `VEIL_STORAGE_KEY` using `Fernet.generate_key()`;
skip the local cluster script. The app role needs migration permissions in its
own database. Keep the database and encryption key together in your recovery
plan, with the key stored separately from database backups. Never replace the
key on an existing database: automatic key rotation is not implemented.

## Schema and behavior

| Table | Purpose |
| --- | --- |
| `veil_documents` | Opaque document ID, owner ID, encrypted document payload, revision, timestamps |
| `veil_redactions` | Encrypted pipeline snapshot including vault and corrections; cascades on document deletion |
| `veil_storage_settings` | Encrypted key verification probe |
| `veil_schema_migrations` | Applied SQL filenames, checksums, and timestamps |
| `veil_users` | User ID, normalized unique email, Argon2id password hash, creation time |
| `veil_sessions` | Hashed random session token, user ID, expiry |
| `veil_auth_limits` | Short-lived login/registration rate limit counters |

SQL migrations live in `backend/migrations/`. Applied migrations are immutable;
add a new numbered SQL file for changes. Migration execution is transactional
and serialized with a PostgreSQL advisory lock. Document content and PDF bytes
are versioned JSON inside authenticated Fernet ciphertext (`bytea`), not pickle.
Document IDs, owner IDs, revision counters, and timestamps are plaintext; account
email addresses are also plaintext. PostgreSQL cannot
search the encrypted document contents; this is intentional for this initial
storage layer. Large PDFs are stored with the document, so backups include them.

Each successful scan/correction updates the result and increments its revision
in one transaction. A concurrently completed operation based on an older saved
revision returns HTTP 409 instead of overwriting a newer result. No transaction
is held open during model calls. Connections close after each database operation.
See [Psycopg connection transactions](https://www.psycopg.org/psycopg3/docs/basic/usage.html#connection-context).

New endpoints:

- `GET /api/documents/{id}` returns `{document, result, revision}`; `result` is
  null until a scan succeeds.
- `DELETE /api/documents/{id}` deletes the document and associated result (204).
  Later reads/downloads return 404. A late scan cannot recreate a deleted record.

Existing upload, scan, correction, PDF rendering/download, and ask endpoints use
the database transparently and require an authenticated owner. Corrections restore the exact stored vault/layout;
they do not rerun the model. Deletion is a logical database deletion; backups and
PostgreSQL WAL may retain encrypted historical records until their retention ends.

## Verification

```sh
cd backend
uv run --env-file ../.env --no-sync pytest -q
```

Tests use `TEST_DATABASE_URL` and clean up only their own documents. Never point
it at the application database. Without it, PostgreSQL/API integration tests are
explicitly skipped. Tests cover reconnect/restart persistence, PDFs/layout/vault
restoration, reviewer edits, encrypted payloads, wrong-key rejection, concurrent
writes, cascade deletion, migration idempotency, and API behavior. They mock
model calls and do not send training/inference traffic.

## Scope

Accounts support multiple users with isolated documents. All document reads,
changes, scans, page images, downloads, deletion, and questions require the
owner's session; a different account receives 404. Anonymous access receives
401. Public synthetic sample previews and the landing page stay accessible,
but opening a sample as a saved document requires login. Documents created
before accounts existed keep a null owner and are inaccessible through the API;
they are preserved, not automatically given to the first person who registers.
An administrator can explicitly assign those documents after confirming ownership.

The local configuration still binds to loopback. The backend can
decrypt the stored contents; encryption at rest does not redact outbound model
requests. The existing T1 routing, question redaction, and backend approval
enforcement gaps remain separate work. No consent record or model training job
is created by saving a document. Documents persist until explicitly deleted;
there is no automatic expiry or browser delete control in this change.

## Authentication

- `POST /api/auth/register` with `{email, password}` creates an account and signs
  in immediately (201). Duplicate normalized email returns 409.
- `POST /api/auth/login` uses the same body; invalid credentials return 401.
- `GET /api/auth/me` returns `{id, email}` for the current session.
- `POST /api/auth/logout` revokes the current session and clears its cookie.

Passwords use [Argon2id](https://argon2-cffi.readthedocs.io/en/stable/api.html),
are 8–128 characters, and are never stored as plaintext. Email normalization
trims whitespace and lowercases the address. Only basic format validation is
performed; email ownership is not checked. No password reset, MFA, or email
service is configured.

Successful login/registration issues a new random session token in an HttpOnly,
SameSite=Lax cookie lasting seven days. Only its SHA-256 hash is stored in
PostgreSQL. Logout revokes it; expiry is checked server-side. Sessions survive
backend restart. Cookies are Secure on HTTPS, or when `VEIL_COOKIE_SECURE=true`
(set this behind an HTTPS reverse proxy). The browser stores no auth token in
localStorage. Logout/session expiry unmounts the document workspace.

Every mutating `/api/` request must include `X-Veil-Request: 1`, including login,
registration, logout, and uploads. The frontend adds it automatically. This
requires a CORS preflight for requests from another origin; keep `VEIL_CORS`
restricted to trusted frontend origins. Login/registration share a limit of
30 attempts per minute per client address, returning 429 with Retry-After when
exceeded. Behind a proxy, configure trusted proxy addresses deliberately;
clients sharing a proxy may share a limit. Auth and document responses have
`Cache-Control: no-store`.

Tests additionally cover login/logout, normalized duplicate email, hash storage,
expired/revoked sessions, secure cookies, CSRF, throttling, and account isolation
across all document endpoints. No verification emails or model calls are sent.
