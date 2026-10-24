# PostgreSQL storage and accounts

[Documentation index](README.md) · [Saved-data summary](DATABASE-CONTENTS.md) · [Security](SECURITY.md)

Veil saves documents, redactions, review status and chat in PostgreSQL.
Email/password accounts protect every saved document. Registration signs the
user in immediately; there is no verification email or code.
Original text, filenames, source PDFs, extracted page layout, detected entities,
placeholder mappings, chunk results, and hide/unhide corrections are encrypted
before being written. Restarting the backend does not lose them. Opening the
same `/app?doc=<id>` URL restores the document and its last saved result without
another model call. Since migration 003 each document's review status
(`new`, `review`, `approved`, `declined`) and its chat turns (question and answer,
encrypted) are stored too, and `GET /api/documents` lists a user's documents, so
documents, review and chat survive a reload or a visit to the landing page.

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
| `veil_documents` | Opaque document ID, owner ID, encrypted document payload, revision, timestamps, review `status`, encrypted list summary `meta` |
| `veil_redactions` | Encrypted pipeline snapshot including vault and corrections; cascades on document deletion |
| `veil_chat_turns` | Turn ID, document ID, owner ID, creation time, encrypted question and answer; cascades on document (and user) deletion |
| `veil_storage_settings` | Encrypted key verification probe |
| `veil_schema_migrations` | Applied SQL filenames, checksums, and timestamps |
| `veil_users` | User ID, normalized unique email, Argon2id password hash, creation time |
| `veil_sessions` | Hashed random session token, user ID, expiry |
| `veil_auth_limits` | Short-lived login/registration rate limit counters |

SQL migrations live in `backend/migrations/`. Applied migrations are immutable;
add a new numbered SQL file for changes. Migration execution is transactional
and serialized with a PostgreSQL advisory lock. Document content and PDF bytes
are versioned JSON inside authenticated Fernet ciphertext (`bytea`), not pickle.
Document IDs, owner IDs, revision counters, review status, turn IDs, and
timestamps are plaintext; account email addresses are also plaintext. PostgreSQL cannot
search the encrypted document contents; this is intentional for this initial
storage layer. Large PDFs are stored with the document, so backups include them.

Migration 003 (`003_status_and_chat.sql`) only adds:

- `veil_documents.status text NOT NULL DEFAULT 'new'`, checked to `new`, `review`,
  `approved` or `declined`. Rows that already had a result were set to `review`
  by the migration; others stay `new`. A saved scan turns `new` into `review`;
  `PATCH /api/documents/{id}` sets the other values.
- `veil_documents.meta bytea`: Fernet-encrypted `{filename, kind, pages, changes}`,
  so `GET /api/documents` decrypts this small summary instead of every document
  with its PDF bytes. New documents get it at upload, and every saved result
  updates `changes`. Rows saved before the migration have `NULL`; the first
  listing reads their full payloads once, writes the summary and returns it. The
  write is skipped if a newer result was saved in between, so the next listing
  reads that one instead of storing a stale count. The same step turns `new`
  into `review` when the row has a result: on Railway the previous release keeps
  serving for a few seconds after the new one migrates, and a scan it saves in
  that window neither writes `meta` nor changes the status.
- `veil_chat_turns` with an index on `(doc_id, turn_id)`, and an index on
  `veil_documents (owner_id, updated_at DESC)` for the list.

Every encrypted payload is bound to its document ID and a kind (`document`,
`result`, `meta`, `turn`), so ciphertext moved to another document or column
fails to load. A chat turn stores the original and sent question, the restored
answer, the answer with placeholders, unknown placeholders and the Mubit request
ID; it does not store the redacted document sent to the model. Routine storage
operations do not log questions, answers or filenames; this is not a claim about
every third-party exception or infrastructure log.

Each successful scan/correction updates the result and increments its revision
in one transaction. A concurrently completed operation based on an older saved
revision returns HTTP 409 instead of overwriting a newer result. No transaction
is held open during model calls. Connections close after each database operation.
See [Psycopg connection transactions](https://www.psycopg.org/psycopg3/docs/basic/usage.html#connection-context).

New endpoints:

- `GET /api/documents/{id}` returns `{document, result, revision}`; `result` is
  null until a scan succeeds.
- `DELETE /api/documents/{id}` deletes the document, its result and its chat turns
  (204). Later reads/downloads return 404. A late scan cannot recreate a deleted record.
- `GET /api/documents` lists the caller's documents, last updated first, at most 200,
  with `{doc_id, filename, kind, pages, status, created_at, updated_at, has_result,
  changes, turns}` and no document text.
- `PATCH /api/documents/{id}` with `{status}` sets `review`, `approved` or `declined`.
- `GET /api/documents/{id}` also returns `status` and `turns`, oldest first.
- `POST /api/documents/{id}/ask` stores the turn before answering and adds `turn_id`
  and `created_at`; a failed ask stores nothing.

See `docs/HANDOFF.md` section 5 for the exact contract.

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
writes, cascade deletion, migration idempotency, and API behavior. They also
cover the document list (only the caller's, order, counts, the 200 limit), review
status through scans and `PATCH`, chat turns (stored in order, nothing stored on
a failed ask, deleted with the document), listing rows saved before migration 003,
migration 003 on tables that already hold rows, and that no filename, question or
answer is readable in the raw rows. They mock
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
requests. T1 still receives original chunks. Questions are now filtered using
known values and regexes, but unfamiliar values can be missed; backend approval
enforcement remains separate work. See [Security](SECURITY.md). Saving review
status is not a consent audit trail. No model training job is created by saving
a document. Documents persist until explicitly deleted;
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

## Railway-hosted database

A managed PostgreSQL service also runs on Railway (project `night-shift`, service
`Postgres`, environment `production`). It is reachable through Railway's public
TCP proxy and requires the generated password and TLS (`sslmode=require`).
The web service, private backend and PostgreSQL are all hosted. The backend
uses Railway's private database URL; local administrative access, when enabled,
uses the public TCP proxy with TLS. See [deployment](DEPLOY.md).

Its settings live in the ignored root `.env.railway`, which contains only
`DATABASE_URL` and that database's own `VEIL_STORAGE_KEY`. Pass it after `.env`
so it overrides the local database settings while keeping the other keys:

```sh
cd backend
uv run --env-file ../.env --env-file ../.env.railway --no-sync uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The Railway key is separate from the local cluster key and must stay paired with
the Railway database. Startup refuses a mismatched key. Back up the key outside
Railway. Keep `TEST_DATABASE_URL` pointed at the local `veil_test` database. Never
run the test suite against Railway. Retrieve credentials only through Railway's
protected settings. Do not paste variable dumps into docs, logs or chat.
