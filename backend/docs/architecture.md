# Backend architecture

The MuGuard backend is a FastAPI app that stores documents encrypted in PostgreSQL, hides personal
data in them (regex layer plus the T1 model through Mubit), streams the scan to the browser, answers
questions about the redacted text (T2) and returns a truly redacted file. This page records the
audit of the first version, the layout it was rebuilt into, and why.

The rebuild changed structure only. Every path, method, status code, body, the `veil_session`
cookie, the `X-Veil-Request` header and the SSE events are the same (see [Contract](#the-api-contract)).

## 1. Audit of the first version

Line numbers refer to commit `decae56` (before the rebuild).

**One file did everything.** `app/main.py` (500 lines) held:

| Lines | What | Problem |
|---|---|---|
| 41-46 | log handler set up at import | logging config inside the route module, no request id |
| 59-67 | app, CORS (`VEIL_CORS` read inline) | app construction at import, no factory to build a test app |
| 70-79 | CSRF and no-store middleware | security policy hidden among routes |
| 82-88 | settings, Mubit key and model clients built at import, put on `app.state` one attribute at a time | global state with no type; tests had to poke `app.state.t1_factory` |
| 90-102 | upload file-type tables | upload rules mixed with HTTP |
| 105-130 | five exception handlers, mapping storage exceptions to HTTP | errors split between `HTTPException` in helpers and handlers here |
| 133-218 | helpers (`_scanned`, `_email_to_text`, `_ocr`, `_store`) | domain logic raising `HTTPException` |
| 144-159 | response bodies built as dicts | no response models: the contract lived only in the frontend and the tests |
| 221-500 | all 15 non-auth routes | routers, services and storage calls in one place |
| 288-375 | scan supersession, worker thread and SSE queue | concurrency logic inside the route module |
| 446-448 | `VEIL_SAMPLES_DIR` read from `os.environ` on every request | settings scattered |

**Other modules.**

- `app/auth.py:40-135`: SQL written inside route handlers and the `current_user` dependency;
  `VEIL_COOKIE_SECURE` read per request (line 83).
- `app/storage.py:41-270`: one class owned configuration (`from_env`, line 51), connections,
  migrations and the key probe (58-87), encryption (93-102) and every document query.
- `app/llm.py:63-133`: the settings lookup (environment, `backend/.env`, `.env`) lived in the LLM
  module, while `DATABASE_URL` and `VEIL_STORAGE_KEY` were read in `storage.py:53`, `VEIL_CORS` in
  `main.py:62`, `VEIL_COOKIE_SECURE` in `auth.py:83`, `VEIL_SAMPLES_DIR` in `main.py:448`, and
  `MUBIT_BASE` in evalkit at import time. Six places read configuration.
- `app/question.py:26` imported the private `_merge` and `_regex` from `pipeline.py`.
- **evalkit coupling.** Eight backend modules imported the evaluation kit (`addresses.py:21`,
  `identifiers.py:15`, `refs.py:17`, `pipeline.py:25-27`, `storage.py:13-14`, `question.py:23-24`,
  `llm.py:27-31`, `main.py:25`), through a path dependency (`pyproject.toml:15,25`) that the
  Dockerfile had to copy (`Dockerfile:9`). Production code depended on research tooling.
- **Tooling.** No linter, formatter or type checker configured; one flat `tests/` folder whose API
  tests patched `main` module internals (`test_stream.py:44-51,193,211`).

## 2. Research

The target layout follows Dmytro's FastAPI template (`~/Projects/templates/tpl-api-fastapi/template/`:
`app/core/`, `app/modules/items/` with router, service, repository and schemas, `app/api.py` as the
router registry, `tests/contract/`) and its skills `api-and-interface-design`,
`observability-and-instrumentation`, `security-and-hardening` and `deprecation-and-migration`.
Three public codebases agree on the same shape:

- **Netflix Dispatch**: one package per feature with `views.py`, `service.py`, `models.py`
  ([incident/](https://github.com/Netflix/dispatch/tree/main/src/dispatch/incident)); thin sync views
  that call a service ([views.py](https://github.com/Netflix/dispatch/blob/main/src/dispatch/incident/views.py#L59-L161));
  keyword-only service functions ([service.py](https://github.com/Netflix/dispatch/blob/main/src/dispatch/incident/service.py#L64-L67));
  one router registry ([api.py](https://github.com/Netflix/dispatch/blob/main/src/dispatch/api.py#L71-L269));
  typed domain errors ([exceptions.py](https://github.com/Netflix/dispatch/blob/main/src/dispatch/exceptions.py));
  background work opens its own database session, never the request's
  ([decorators.py](https://github.com/Netflix/dispatch/blob/main/src/dispatch/decorators.py#L88-L133)).
- **zhanymkanov/fastapi-best-practices**: package per domain with router, schemas, service,
  dependencies and exceptions, and explicit module imports
  ([Project Structure](https://github.com/zhanymkanov/fastapi-best-practices#project-structure));
  sync routes run in the threadpool, so blocking I/O belongs in `def`, not `async def`
  ([I/O Intensive Tasks](https://github.com/zhanymkanov/fastapi-best-practices#io-intensive-tasks));
  reusable dependencies ([Beyond Dependency Injection](https://github.com/zhanymkanov/fastapi-best-practices#beyond-dependency-injection));
  ruff for lint and format ([Use ruff](https://github.com/zhanymkanov/fastapi-best-practices#use-ruff)).
- **fastapi/full-stack-fastapi-template**: one pydantic-settings `Settings` with `env_ignore_empty`
  ([core/config.py](https://github.com/fastapi/full-stack-fastapi-template/blob/b1125d8839482cb7bbae603ddc6d0081bf87532e/backend/app/core/config.py#L15-L91));
  `Annotated` dependencies such as `SessionDep` and `CurrentUser`
  ([api/deps.py](https://github.com/fastapi/full-stack-fastapi-template/blob/b1125d8839482cb7bbae603ddc6d0081bf87532e/backend/app/api/deps.py#L21-L49));
  a router registry ([api/main.py](https://github.com/fastapi/full-stack-fastapi-template/blob/b1125d8839482cb7bbae603ddc6d0081bf87532e/backend/app/api/main.py#L6-L14));
  ruff and strict mypy in `pyproject.toml`
  ([pyproject.toml](https://github.com/fastapi/full-stack-fastapi-template/blob/b1125d8839482cb7bbae603ddc6d0081bf87532e/backend/pyproject.toml#L36-L61)).

What did not fit at our size: Dispatch's per-tenant sessions, plugins and flows; a settings class per
domain; an ORM model per module; async database drivers (the template's async advice assumes them).

## 3. Layout

```
backend/
  app/
    main.py              create_app(): settings, model calls, error handlers, middleware, routers
    api.py               router registry + /api/health
    dependencies.py      SettingsDep, DatabaseDep, ModelsDep (what routes take from app.state)
    core/                plumbing, no feature logic
      config.py          Settings: the one pydantic-settings class
      logging.py         key=value event logs with a request id; RequestIdMiddleware
      errors.py          AppError hierarchy + registered exception handlers
      security.py        X-Veil-Request check, no-store, session token helpers
      crypto.py          PayloadCipher: Fernet, bound to row and kind
      db.py              Database: connections, immutable SQL migrations, storage-key check
    modules/             HTTP features: router (HTTP only) -> service (rules) -> repository (SQL)
      auth/              register, login, me, logout; CurrentUser dependency
      documents/         upload or paste (uploads.py), list, open, status, delete; the documents repository
      scan/              redact and the SSE stream (stream.py), supersession, ?retry=failed
      corrections/       hide or unhide a value
      ask/               a question about the redacted text
      samples/           sample documents and thumbnails
      files/             page images and the redacted download
    redaction/           domain: no FastAPI, no database
      document.py        Document, Word; PDF text layer and pasted text
      ocr.py             scans and photos as PDF documents with word boxes (uses ingest)
      detectors/         the regex layer: baseline (UK formats), refs, identifiers
      spans.py vault.py  values -> spans -> placeholders, and back
      addresses.py       widen an ADDRESS span to the whole address
      pipeline.py        regex + T1 per chunk -> merged spans, vault, boxes
      question.py        pseudonymise a question, plain-text answers
      pdf.py             true PDF redaction and metadata stripping
    llm/                 domain: the model calls through Mubit
      t1.py t2.py        the two T1 designs (rewrite, evalkit list) and T2
      prompts.py         frozen T1 prompts (pinned by hash in tests) and the T2 prompt
      rewrite.py         read values out of a rewrite answer
      providers.py       one HTTP call per provider route
      models.py          Models: the calls and names the services use, built from Settings
    ingest/              domain: Apple Vision OCR and PDF text layers (unchanged)
    prompts.py extract.py addresses.py pipeline.py    deprecated adapters, see section 5
  migrations/            immutable SQL, applied in order at startup
  tests/                 mirrors app/: api/, core/, llm/, redaction/, modules/, plus test_contract.py
```

Before, for comparison: `app/` held `main.py`, `auth.py`, `storage.py`, `llm.py`, `prompts.py`,
`pipeline.py`, `extract.py`, `ocrdoc.py`, `pdfout.py`, `question.py`, `addresses.py`, `refs.py`,
`identifiers.py` and `ingest/`, all side by side; `tests/` was flat.

**Dependency direction.** `core` imports nothing from the app. `redaction`, `llm` and `ingest` import
only `core` (logging, settings names) and each other. `modules` import the domain packages and
`core`. `api.py` and `main.py` import modules. Nothing imports `main`.

**Inside a module.**

- *router*: parses the request, calls a service, returns a typed schema. No SQL, no rules.
  Function names are kept from the first version, so OpenAPI operationIds did not change.
- *service*: the rules and the error decisions. Raises `AppError` subclasses, never `HTTPException`.
- *repository*: parameterized SQL only. Every document query is scoped by owner, so another user's
  document is simply not found (404). The documents repository stores the whole document aggregate
  (document, result, status, chat turns); scan, corrections, ask and files use it rather than
  keeping their own tables.
- *schemas*: request and response bodies. The response models list the fields the frontend reads
  (`frontend/src/api.ts`), in the same order as the old dicts.

## 4. Decisions

- **Settings** (`core/config.py`). One `BaseSettings` class with the same environment names
  (`DATABASE_URL`, `VEIL_STORAGE_KEY`, `MUBIT_API_KEY`, `MUBIT_BASE`, `VEIL_T1_PROMPT`,
  `VEIL_T1_MODEL`, `VEIL_T2_MODEL`, `VEIL_CORS`, `VEIL_COOKIE_SECURE`, `VEIL_SAMPLES_DIR`). A custom
  settings source keeps the old lookup exactly: environment, then `backend/.env`, then the root
  `.env`, one name at a time; empty values skipped; a `MUBIT_API_KEY` that is not `mbt_...` falls
  through; nothing loaded into `os.environ`; where each value came from is recorded so
  `/api/health` can say `key_source` without the key. pydantic-settings' own dotenv source cannot do
  the fall-through or the reporting. Settings are read once in `create_app()`; tests override them
  with a fixture instead of setting environment variables mid-test.
- **Errors** (`core/errors.py`). One hierarchy (`BadRequestError` ... `ServiceUnavailableError`)
  and handlers registered in one place. The body stays `{"detail": "..."}`, FastAPI's own shape,
  which the frontend reads; the template's RFC 9457 problem+json would change every error body, so
  it is not used here. Database failures map to a fixed 503 message, decryption failures to another,
  so no connection string or stored value reaches a client.
- **Logging** (`core/logging.py`). `event key=value` lines through `log_event()`, with a request id
  on every line (taken from `X-Request-ID` or generated, and sent back in that header), carried into
  the scan thread. Callers log ids, counts, statuses and exception type names only, never document
  text, values, questions or file names (a test checks the scan logs). This keeps the stdlib logger
  and adds no dependency; a JSON renderer can be added behind the same calls.
- **Database** (`core/db.py`). Raw psycopg 3 with the existing immutable SQL migrations and their
  checksums, not SQLAlchemy and Alembic: every payload column is ciphertext, the queries are few and
  specific, and changing the migration system under a live database buys nothing now. Each
  repository call opens its own short connection, so the scan thread never shares the request's
  connection (the Dispatch rule). A new test applies every migration to an empty schema.
- **Sync endpoints.** psycopg is used synchronously, so routes are `def` and run in FastAPI's
  threadpool; the SSE scan runs in its own thread so it finishes even if the browser leaves.
- **Security** (`core/security.py`, `modules/auth`). Unchanged behaviour, now in one place:
  `X-Veil-Request: 1` on every state-changing `/api` call, `Cache-Control: no-store` on auth and
  document responses, HttpOnly SameSite=Lax session cookies holding a 256-bit token whose SHA-256
  is stored, Argon2id passwords with a dummy-hash check for unknown emails, 30 attempts a minute
  per client address.
- **No `/api/v1` prefix, no OpenTelemetry or Sentry.** The template has them; adding a prefix would
  break the frontend, and tracing is out of scope for the hackathon.

## 5. Leaving evalkit

What the backend used from evalkit is now in the backend, with its tests:
`spans.py` (Span, locate) -> `redaction/spans.py`; `redact.py` (Vault, apply, restore) ->
`redaction/vault.py`; `regex_baseline.py` and the parts of `uk_formats.py` it uses ->
`redaction/detectors/`; `providers.py` -> `llm/providers.py`; `rewrite.py` -> `llm/rewrite.py`;
`send_batch.parse_entities` -> `llm/t1.py`; `prompts.T1_SYSTEM_PROMPT` ->
`llm/prompts.LIST_T1_SYSTEM_PROMPT`. Copied byte for byte where it matters: every regex was compared
with the original, and both frozen T1 prompts are pinned by SHA-256 in `tests/llm/test_prompts.py`,
because Mubit fingerprints a task by its prompt. `evalkit/` itself is untouched.

Code outside `backend/` still imports the old paths (`scripts/dataset/send_batch.py` and
`tests/dataset/` use `app.prompts`; `scripts/readme_numbers.py` uses `app.addresses`, `app.pipeline`
and `app.llm.rewrite_values`; `scripts/samples/make_tenancy.py` uses `app.extract`). Following the
deprecation skill, each old path is a small adapter that re-exports from the new place and names
the caller that keeps it alive. Delete an adapter once its caller imports the new module.

## The API contract

- `tests/contract/openapi.json` is the OpenAPI document of the first version. `tests/test_contract.py`
  fails if a path, method, operationId, parameter, request body, documented status or request schema
  changes. Success bodies may be described in more detail (they now have response models) but not
  changed; the API tests check those bodies exactly.
- The API tests (`tests/api/`) kept every assertion; only how they swap fakes in changed
  (`app.state.models`, the scan module, a `settings` fixture).
- The frontend end-to-end suite (`frontend/`, Playwright projects `app`, `app-real`, `app-retry`,
  `app-phone`) passes against the rebuilt backend as it does against the first version.

## Working on it

```bash
cd backend
uv run --env-file ../.env pytest -q     # needs TEST_DATABASE_URL (scripts/local_db.py sets it)
uv run ruff check app tests && uv run ruff format --check app tests
uv run mypy
```

A new feature is a new folder under `app/modules/` with router, service, schemas (and repository if
it stores something), and one line in `app/api.py`.

## Left for later

- Point `scripts/` and `tests/dataset/` at the new import paths, then delete the adapters
  (`app/prompts.py`, `app/extract.py`, `app/addresses.py`, `app/pipeline.py`, the re-export in
  `app/llm/__init__.py`).
- `POST /api/documents/{id}/ask` returns the provider's exception text in its 502 detail (kept to
  avoid changing the contract); replace it with a fixed message.
- mypy `--strict` reports 28 more findings, mostly in the OCR modules (`ingest/`, `redaction/ocr.py`).
- An unhandled exception still reaches uvicorn's default traceback log, which can include its
  message; a handler that logs the type only would close that.
- JSON log rendering for Railway, and RED metrics per endpoint, if the app outlives the hackathon.
