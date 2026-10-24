# Veil: handoff for the next agent

Written 2026-10-24 (hackathon day 2) for an AI coding agent picking this repo up cold. Read this first, then the files it points to. Paths are relative to the repo root. Facts marked "not verified" were not re-checked after the last merge.

## 1. What Veil is

Veil is a privacy layer for using AI chat with real client documents (Mubit "Night Shift" hackathon, London, 23 to 25 Oct 2026; repo github.com/BabyBoss45/night-shift, public).

1. The user uploads a PDF, photo, scan, email or pasted text.
2. **T1** finds personal data. T1 is a model trained through **Mubit** (teacher model `claude-haiku-4-5` behind Mubit's gateway while the adapter trains; `gpt-6-luna` with `VEIL_T1_PROMPT=evalkit`), plus a regex layer for UK identifiers and labelled client references.
3. The user reviews the redaction line by line: Approve all, Decline, "Not personal, show it" (unhide), "Fix a miss" (hide).
4. Each distinct value becomes a placeholder such as `[PERSON_1]`. The download is a truly redacted PDF (text removed under the box) or redacted text.
5. **T2** (any AI provider, default `claude-haiku-4-5` through Mubit with recording off) answers questions about the document. It sees placeholders only. Veil restores the real values locally in the answer.
6. Reviewer corrections become Mubit training signal, so the model learns a firm's own codes.

Pitch line: the edge is per-firm learning via Mubit, true PDF redaction and UK identifiers. Mask-and-restore alone is common among competitors.

## 2. Repo map

| Path | Origin | What | State |
|---|---|---|---|
| `frontend/` | Dmytro | React 19 + Vite + TS + Tailwind v4 + Motion. `/` = landing (pixel castle scroll story), `/app` = the app | Built, checked in browser desktop + mobile on 24 Oct |
| `backend/app/main.py` | Dmytro | FastAPI API (section 5) | Working; checked live on 24 Oct (section 11) |
| `backend/app/extract.py` | Dmytro | PDF via PyMuPDF: text plus every word's box and character range (needed for true redaction) | Working |
| `backend/app/pipeline.py` | Dmytro | regex + T1 per chunk, merge spans, vault placeholders, boxes per line, `rebuild()` for reviewer fixes | Working |
| `backend/app/refs.py` | Mykola | Regex rule for client, policy, claim and case references after their label, and meter serials and supply point numbers (MPAN, MPRN) (type `CUSTOM`), part of the regex layer | Working; 85% of `data/docs` CUSTOM values, 96% of the 30 original samples |
| `backend/app/identifiers.py` | Mykola | Regex rule for IP addresses (`IP_ADDRESS`; an IPv4 address needs "IP" before it or two parts of 2+ digits, so clause numbers stay visible) and UUIDs such as e-signature references (`CUSTOM`) | Working |
| `backend/app/addresses.py` | Mykola | After merging, widens each ADDRESS span to the flat, building and town next to it, and reads back an address T1 missed from its postcode (towns, then a street with a number, then flats and buildings; company names stop it) | On Haiku's fresh answers: addresses fully hidden 54% → 76%, all values 76% → 86% (with the regex rules), 10 more characters hidden outside the answer key |
| `backend/app/pdfout.py` | Dmytro | True PDF redaction (`add_redact_annot` + `apply_redactions`) | Working |
| `backend/app/llm.py` | Dmytro | T1 (two prompts, `VEIL_T1_PROMPT`) and T2 calls through Mubit; key from env, `backend/.env` or root `.env` | Working with a valid key |
| `backend/app/ingest/` | Mykola (PR #9) | Local reading of PDFs and images: pdfium text layer, Apple Vision OCR (macOS), identifier repairs after OCR. See its README | Merged; wired into uploads (section 4) |
| `backend/app/prompts.py` | Mykola | The app's default T1 prompt (rewrite design, `claude-haiku-4-5`). See section 8 | Default since 24 Oct |
| `backend/tests/` | Dmytro | API, extract, llm, ocrdoc, pdfout, pipeline, refs, stream tests | Pass (24 Oct) |
| `evalkit/` | Dmytro | Frozen T1 prompt the app uses (`evalkit/src/evalkit/prompts.py`), scorer, regex baseline, vault/restore, round builder, Mubit sender, `autosend.sh` | Used by backend (path dependency) |
| `datagen/` | Dmytro | Synthetic UK documents with gold spans (100k run, seed 42) and demo PDFs | Outputs in `data/synthetic/` (gitignored except `pdfs/`) |
| `dataconv/` | Dmytro | Converters for open PII datasets (TAB, Gretel, Nemotron, OpenPII, bitext, ...) into our format | Outputs in `data/external/` (gitignored, licences vary) |
| `data/synthetic/pdfs/` | Dmytro | 31 synthetic sample PDFs + `*.gold.json` labels; the app's "Try a sample" cards. `31_assured_periodic_tenancy` (Mykola) is a 20-page e-signed tenancy in the layout of a real agency contract, with an InkProof signature log (IP addresses, UUID signature references), overseas addresses, a guarantor, bank details, meter serials and initials on every page; 59 invented values, built by `scripts/samples/make_tenancy.py` | Committed (fake data only) |
| `data/docs`, `data/templates`, `data/sources`, `data/fixtures` | Mykola | His T1 dataset: real public templates filled with fake values, answer keys | Committed |
| `scripts/dataset/` | Mykola | His pipeline: validate, chunk, send (`send_batch.py`), score | Committed |
| `scripts/ocr/`, `tests/ingest/` | Mykola | OCR evaluation (render docs in 4 fonts x 6 qualities) and ingest tests | Committed |
| `scripts/sources/`, `tests/dataset/` | Mykola | Source fetchers and dataset tests | Committed |
| `requirements.txt`, `.env.example` (root) | Mykola | Deps for `scripts/` and `tests/`; key template for `scripts/dataset/send_batch.py` | Committed |
| `docs/APP-SPEC.md` | Dmytro | What the web app must do (Mubit needs, flow, API, build order) | Mostly built |
| `docs/design/2026-10-24-redesign-notes.md` | Dmytro | Redesign audit, library research, decisions | Done |
| `docs/research/2026-10-24-pii-dataset/` | Dmytro | Dataset research, `TRAINING-PLAN.md`, `BAKEOFF.md` (teacher model choice), UK formats | Reference |
| `docs/research/2026-10-24-veil-numbers/` | Dmytro | About 170 verified market numbers with sources (AI data leakage, rules and fines, market and deals) | Reference; investor page built from it |
| `docs/research/2026-10-23-mubit-audit/` | Team | Mubit company and product audit | Reference |
| `docs/project-brief.md`, `docs/NIGHT-SHIFT-TEAM-PACK.md` | Team | Event rules, judging, Mubit mechanics | Reference |
| `DESIGN.md`, `.impeccable/design.json` | Dmytro | Design system v2 (tokens, type, components, motion) | Current |
| `PRODUCT.md`, `.impeccable/surfaces/*.md` | Dmytro | Product context and per-surface briefs (app = Operate, landing = Persuade) | Current |
| `.impeccable/mocks/`, `.impeccable/questions/` | Dmytro | Early UI variant mocks and decision pages | Historical |
| `.claude/launch.json` | Dmytro | Dev servers: `veil-backend` (port 8000), `veil-frontend` (port 5173) | Current |

## 3. Architecture and data flow

```
upload / paste / sample
  └─ POST /api/documents
       ├─ PDF with a text layer, no scanned page → extract.extract_pdf (PyMuPDF words: text + box + char range)
       ├─ PDF with a scanned page (ingest.scanned_pages) → ocrdoc.document_from_ocr (ingest OCR) → PDF + word boxes
       ├─ image (jpg png heic tiff webp) → ocrdoc.document_from_ocr → image turned into a PDF + word boxes
       ├─ .eml → headers + body text
       ├─ .txt .md .csv .json, code and config files (.py .ts .yaml .sql .html ...) → text
       └─ any other file that is UTF-8 with no NUL byte in its first 8 KB → text (else 415)
  └─ POST /api/documents/{id}/redact/stream   (server-sent events, what the UI should use)
     or POST /api/documents/{id}/redact        (same result in one JSON answer)
       pipeline.run_pipeline:
         chunk text (≤4000 chars for evalkit, ≤1400 for rewrite; paragraph cuts)
         → T1 per chunk in parallel (6 workers); each finished chunk is streamed as it lands
         every value T1 returns is located across the WHOLE document (evalkit.spans.locate)
         + regex layer (evalkit.regex_baseline + app/refs.py + app/identifiers.py) → merge overlaps
         → widen addresses (app/addresses.py) → Vault placeholders
         → boxes: words overlapping a span, one rectangle per line (PDF only)
  └─ review in the UI → POST /corrections {hide|unhide} → pipeline.rebuild (no new T1 calls)
  └─ GET /file → true-redacted PDF (pdfout) or redacted .txt
  └─ POST /ask → T2 gets only redacted_text → evalkit.redact.restore puts values back
```

Model calls (both through Mubit, `backend/app/llm.py`):
- **T1**, recording ON (calls keep training a Mubit task), session `doc-<doc_id>`. `VEIL_T1_PROMPT` picks the prompt, and each prompt is its own Mubit task:
  - `evalkit`: frozen prompt `evalkit/src/evalkit/prompts.py`, model `VEIL_T1_MODEL` (default `gpt-6-luna`), chunks ≤4000 chars, answer = JSON list of `{text, type}` parsed by `evalkit.send_batch.parse_entities`. Mubit task "Find personal data".
  - `rewrite` (default): Mykola's `backend/app/prompts.py` with its `MODEL_ID` (`claude-haiku-4-5`; `VEIL_T1_MODEL` is ignored), chunks ≤1400 chars (Mubit's reviewer reads only about the first 1,530 chars of a call), each sent stripped of surrounding whitespace as `scripts/dataset/build_chunks.py` made the training chunks. Values with fewer than two letters or digits, and PERSON values that are only a title, are dropped, since every value is hidden everywhere in the document. Sent with the `anthropic` SDK (pinned to the version in the root `requirements.txt`) exactly as `scripts/dataset/send_batch.py` sends it, so it lands in his Mubit task "Redact personal data"; a test compares the two requests. The answer is the chunk rewritten with `[TYPE_N]` placeholders; `llm.align_rewrite` matches it line by line as a template (falling back to `evalkit.rewrite.spans_from_rewrite`) to get the values. An answer that does not line up, or `stop_reason: max_tokens`, makes the chunk an error.
- **T2**: model `VEIL_T2_MODEL` (default `claude-haiku-4-5`), header `x-middleware-record: off` (no second task, Mubit stores no user questions).
- Key and settings: the first value starting with `mbt_` in `MUBIT_API_KEY`, then `backend/.env`, then the repo-root `.env` (where `scripts/dataset/send_batch.py` reads it too). `VEIL_T1_PROMPT`, `VEIL_T1_MODEL` and `VEIL_T2_MODEL` are looked up the same way (section 5). `/api/health` reports where the key came from (`key_source`), never the key.
- No key → both off; the app still works on the regex layer only (UI shows "Numbers only for now"). The startup log says which prompt, model and key source are in use.

Storage (updated 24 Oct): documents, source PDFs, layout, pipeline results, vaults,
and review corrections persist encrypted in PostgreSQL. `backend/app/storage.py`
replaces the old `DOCS`/`RESULTS` dictionaries. See [DATABASE.md](DATABASE.md) for
setup, migrations, deletion, tests, and email/password accounts. Document text
is never logged. `/app?doc=<id>` reopens saved work. Since migration 003 the backend
also stores each document's review status and chat turns (questions and answers
encrypted) and lists a user's documents (`GET /api/documents`, section 5).
Registration/login need no email verification. Every document route is scoped
to its signed-in owner. Legacy ownerless records remain private and require
explicit administrative assignment; registration does not claim them.
Per-chunk logs contain only IDs, status, timing, and counts.

## 4. OCR integration (photos and scans get boxes)

`backend/app/main.py::_ocr()` handles images, and every PDF in which ingest finds a scanned page (`app.ingest.scanned_pages`: no text, or little text over an image covering 40% of the page, such as a scan with a page-number stamp). Other PDFs keep `extract.extract_pdf`. `_ocr()` calls `backend/app/ocrdoc.py::document_from_ocr(data, filename)`, which runs `app.ingest.extract(data)` (Apple Vision OCR, macOS only) and returns a **PDF** document (`kind="pdf"`) with word boxes. Photos and scans then get black boxes in the "Pages" view and a truly redacted PDF download, like text-layer PDFs. Checked by Nick on his Mac with real Vision: three synthetic samples photographed upright, turned 90 degrees and skewed 3 degrees gave exact offsets and full coverage, and re-OCR of the redacted PDFs read no hidden value.

- **Images** (jpg, png, heic, tiff, webp) become a PDF with PyMuPDF: one page per image or TIFF frame that ingest read. An iPhone MPO JPEG is one page: its later frames are a depth map or a preview (`ingest.extract.page_frames`). EXIF orientation is applied and transparency goes on white, as ingest does before OCR, so pixels and boxes agree.
  - Every image is encoded again (JPEG q92 for photos, PNG otherwise) with no metadata, so EXIF (GPS, device, owner), XMP and PNG text never reach the PDF.
  - The stored image is at most 3000 px on its long side (OCR already read the full-size one).
  - Page size: a scan keeps its paper size (pixels at its dpi). A photo (no dpi, or a page longer than 1200 pt at its dpi; phones say 72 dpi) gets a page whose long side is 842 pt (A4). A 3024 x 4032 phone photo: page 632 x 842 pt, page PNG at `scale=2` 0.6 s and 1.2 MB, redacted PDF 1.6 s and 3.9 MB (it was 7.6 s and 16 MB, 2.7 s and 6.4 MB at 72 dpi).
- **Scanned PDFs** keep their bytes. If ingest stopped at its 100-page limit, the unread pages are dropped, since nothing on them would be hidden. Text-layer pages of a mixed PDF are read from pdfium's text by ingest, and their boxes come from inverting ingest's own formula (`_from_text_layer`), right on turned and cropped pages too.
- **Text** = exactly `ingest`'s text, so offsets agree with T1 and the regex layer. Each OCR line is found, in reading order (`ingest.layout.group_rows`), in the text ingest assembled before its identifier repairs, then carried over to the repaired text by aligning the two (`difflib`). So lines whose postcode or account number was repaired still get boxes. A line that cannot be placed is skipped and counted in a log warning (counts only, never document text).
- **Word boxes**: each line is split into words. A word's box is its share of the line box, estimated twice (from character counts and from Helvetica widths) and covering both, plus 1.5 average characters each side, clipped to the line box. On test renders in Arial, Times, Calibri, Cambria and Courier metrics this covered every word. Character counts alone missed by up to 3 characters. Lines that Vision reads on their side or upside down are split along their reading direction (`Line.angle`).
- **Frames**: ingest's OCR line boxes are fractions of the last image it read for that page: the page as shown (EXIF applied; for PDFs as pdfium renders it, with /Rotate and CropBox), turned counterclockwise by `Page.rotation` (a deskew, or 90/180/270) with the canvas grown to fit. `ocrdoc` undoes that turn about the page centre, scales to points, then removes the PDF's own /Rotate (`page.derotation_matrix`). So `Word.bbox` is in PyMuPDF's unrotated page frame, the same frame as `extract.py` words and `add_redact_annot`.
- **Download** (`pdfout.redact_pdf`, every PDF, text or scan):
  - `apply_redactions(images=PDF_REDACT_IMAGE_PIXELS)` (PyMuPDF's default, now explicit) blanks the image pixels under each box in the file, then draws the black box.
  - Then, on every page, boxed or not, it takes out what lies outside the page content and can name people: document info (author, title...), XMP, embedded files and file attachments, the outline (bookmarks), page thumbnails, XMP and app data (`/PieceInfo`) on pages and images, and EXIF, XMP, IPTC and comments inside JPEG images. The JPEG image data stays byte for byte; JFIF, ICC and Adobe colour segments are kept because decoding needs them.
- **Fallback**: if building the PDF or the boxes fails unexpectedly, the document is kept as text only (`kind="text"`, the old behaviour) with a log warning.
- **Tests**: `backend/tests/test_ocrdoc.py` and `test_pdfout.py` (`cd backend && uv run pytest -q`). On Linux a fake Vision reader stands in. It finds three colour marks on each test page to work out how ingest turned the image. Everything else is the real ingest (EXIF, deskew, 90/180/270 retries, layout, repairs). Ingest's own tests: `cd backend && uv run --with reportlab python -m pytest -q ../tests/ingest` (plain `pytest` there runs from the project venv without reportlab and fails 3 tests).

Known limits:
- Word boxes are estimates inside Vision's line box (Vision gives no per-word boxes here). They cover a character or two more than the word. On text-layer pages of a mixed PDF this also removes a neighbouring character or two of real text.
- A mixed PDF now needs Apple Vision: on a machine without it, its upload gets the OCR error (415) instead of a text PDF whose scanned pages would stay unread.
- Pages with /Rotate 90 or 270 (scans, and text-layer PDFs before this change): the boxes are right in the downloaded PDF, but the review overlay draws them over the page as shown, so they look misplaced there.
- A redacted photo still grows (1.5 MB in, 3.9 MB out) because MuPDF stores a changed image losslessly.

## 5. API (FastAPI, `backend/app/main.py`)

| Method | Path | Does |
|---|---|---|
| GET | `/api/health` | `{model: on/off, t1_model, t1_prompt: evalkit/rewrite, t2_model, key_source, database: postgresql}` |
| POST | `/api/auth/register` | `{email, password}` creates an account and session without email verification |
| POST | `/api/auth/login` | `{email, password}` signs in |
| GET | `/api/auth/me` | current `{id, email}` or 401 |
| POST | `/api/auth/logout` | revokes the current session |
| POST | `/api/documents` | form `text` or `file` (≤20 MB) → `{doc_id, kind, filename, text, pages}` |
| GET | `/api/documents` | the caller's documents for the sidebar, last updated first, at most 200, no text (contract below) |
| GET | `/api/documents/{id}` | saved `{document, result, revision, status, turns}` |
| PATCH | `/api/documents/{id}` | `{status: review/approved/declined}` → `{doc_id, status}` |
| DELETE | `/api/documents/{id}` | deletes the document, result and chat turns; returns 204 |
| POST | `/api/documents/{id}/redact` | runs the pipeline → `{redacted_text, entities, boxes, chunks, stats, model}`; each chunk is `{index, chunk_id, start, end, status, error, mreq_id, latency_ms, found}`. Optional `?retry=failed` (below) |
| POST | `/api/documents/{id}/redact/stream` | the same run as server-sent events (contract below). Optional `?retry=failed` |
| GET | `/api/documents/{id}/pages/{n}.png` | page image (PDF only) |
| GET | `/api/documents/{id}/file` | redacted PDF or text download |
| POST | `/api/documents/{id}/ask` | `{question}` → `{answer, answer_with_placeholders, sent_text, unknown_placeholders, mreq_id, turn_id, created_at}`; the turn is stored |
| POST | `/api/documents/{id}/corrections` | `{action: hide/unhide, text, type}` → new result |
| GET | `/api/samples` | sample cards from `data/synthetic/pdfs` (title, kind, pages, value counts from gold) |
| GET | `/api/samples/{name}/thumb.png` | thumbnail (width 120, darkened) |
| POST | `/api/samples/{name}` | opens a sample as a document |

Saved documents, review status and chat (fixed: the frontend builds against it; additions only):
- `GET /api/documents` → `[{doc_id, filename, kind: "pdf"/"text", pages, status, created_at, updated_at, has_result, changes, turns}]`. Only the caller's documents, `updated_at` newest first, at most 200. `pages` is 0 for text. `changes` is the number of hidden spans in the latest result (the length of `entities`), `null` without a result. `turns` is the number of stored chat turns. No document text.
- Times are ISO 8601 UTC with milliseconds, as JavaScript's `toISOString` gives: `2026-10-24T17:36:24.912Z`.
- `status` is `new`, `review`, `approved` or `declined`. Upload and sample give `new`. A saved scan (`/redact`, or `done` of `/redact/stream`) turns `new` into `review` and leaves `approved` and `declined` alone, since editing after approve is allowed. `PATCH /api/documents/{id}` `{status}` sets `review`, `approved` or `declined` (anything else is 422; an unknown or foreign document is 404).
- `GET /api/documents/{id}` adds `status` and `turns: [{turn_id, created_at, question, answer, answer_with_placeholders, unknown_placeholders, mreq_id}]`, oldest first.
- `POST /ask` stores the turn, encrypted, before it answers, and adds `turn_id` and `created_at`. A failed ask (409 not scanned, 502 model error, 503 model off) stores nothing. `sent_text` is not stored.
- `updated_at` moves on upload, scan, correction, a status change and a stored chat turn, so the sidebar order follows activity.

Env: `DATABASE_URL`, `VEIL_STORAGE_KEY` (required), `MUBIT_API_KEY` (or `backend/.env`), `VEIL_T1_MODEL`, `VEIL_T2_MODEL`, `VEIL_CORS`, `VEIL_SAMPLES_DIR`. Load root configuration with `uv run --env-file ../.env` from `backend/`.

Stream contract (`/redact/stream`, fixed: the frontend builds against it):
- Unknown doc: 404 JSON `{"detail": "Document not found."}` for a missing document or another owner; unauthenticated requests get 401 before any stream. Otherwise 200 with `Content-Type: text/event-stream`, `Cache-Control: no-store`, `X-Accel-Buffering: no`.
- Each event is `event: <name>\ndata: <one-line JSON>\n\n`; a comment `: ping\n\n` goes out every 5 s while waiting.
- Events in order: `start` once `{doc_id, model, t1_model, t1_prompt, chunks: [{index, chunk_id, start, end}]}`; `regex` once `{entities: [{start, end, text, type, source: "regex"}]}`; `chunk` once per chunk in the order chunks finish `{index, chunk_id, start, end, status: ok/error/empty/off, error, mreq_id, latency_ms, found, entities: [{..., source: "model"}]}`; `done` once, exactly the `/redact` JSON from the same builder (the encrypted result is stored in PostgreSQL first, so `/file`, `/ask` and `/corrections` work right away). `error` `{message}` only for an unexpected failure that stops the run; a failed chunk is a `chunk` with `status: "error"`.
- `entities` of a chunk are the occurrences, inside its `[start, end)`, of the values T1 returned for it; `found` is the number of values T1 returned. `off` = no key, no call; `empty` = whitespace-only chunk, no call. All offsets are character offsets into the `text` from `POST /api/documents`.

Retry only what failed: `POST /api/documents/{id}/redact/stream?retry=failed` (and `POST /redact?retry=failed`):
- Same events, in the same order, as a normal run.
- If PostgreSQL holds an earlier run of this document with the same chunk plan (same T1 prompt and the same ranges), its chunks with status `ok` or `empty` make no new T1 call: their `chunk` events go out at once with the stored `mreq_id`, `latency_ms`, `found` and `entities`. Only chunks that were `error` (or `off`, when the model is now on) call T1. `done` is then what a full run would give; like any scan, it starts without reviewer corrections.
- With no earlier result or a different plan, every chunk runs, as without the parameter. Any other value of `retry` is a 422.
- `PipelineResult.chunk_values` keeps what T1 returned per chunk and `PipelineResult.plan` the prompt, for this.

One scan per document at a time: each scan (`/redact` or `/redact/stream`, with or without `retry`) reserves a PostgreSQL revision. Only the newest may save its result and send `done`. A newer scan or reviewer correction invalidates the reserved revision across backend workers. An older one stops making new T1 calls, goes quiet and ends with `error` `{"message": "A newer scan of this document started, so this one stopped."}`; an older `/redact` gets 409 with the same text.

Settings and key lookup: `MUBIT_API_KEY`, `VEIL_T1_PROMPT` (`rewrite` default, or `evalkit`), `VEIL_T1_MODEL` (evalkit prompt only) and `VEIL_T2_MODEL` are each read from a real environment variable first, then from `backend/.env`, then from the repo-root `.env` (so the root `.env` that holds the key can also say `VEIL_T1_PROMPT=evalkit`). Only these names are read from the files; nothing is loaded into `os.environ`. For the key, only a value starting with `mbt_` counts. The startup log names the prompt and where it came from, for example `T1 on: prompt rewrite (VEIL_T1_PROMPT from .env), model claude-haiku-4-5, 1400-character chunks, Mubit key from .env`; a bad `VEIL_T1_PROMPT` stops startup. `VEIL_CORS` and `VEIL_SAMPLES_DIR` are read from the environment only.

## 6. How to run

```bash
# backend (Python 3.12/3.13, uv); evalkit is a path dependency
python3 scripts/local_db.py start
cd backend && uv sync --frozen && uv run --env-file ../.env uvicorn app.main:app --reload --port 8000
# key: one line MUBIT_API_KEY=mbt_... in the root .env (or backend/.env, or export it); all gitignored.
# Lookup order: environment, backend/.env, .env. The startup log and /api/health show the source.
# T1 prompt: rewrite (default, claude-haiku-4-5). For the evalkit prompt on gpt-6-luna put
# VEIL_T1_PROMPT=evalkit in the same .env (see .env.example), or VEIL_T1_PROMPT=evalkit uv run uvicorn ...
# All document/stream requests need a login cookie and X-Veil-Request: 1.

# watch a scan stream (synthetic sample only)
DOC=$(curl -s -X POST localhost:8000/api/samples/01_tenancy_agreement.pdf | python3 -c "import json,sys; print(json.load(sys.stdin)['doc_id'])")
curl -N -X POST localhost:8000/api/documents/$DOC/redact/stream

# frontend (Vite proxies /api to 127.0.0.1:8000)
npm --prefix frontend install && npm --prefix frontend run dev   # http://localhost:5173

# tests
cd backend && uv run --env-file ../.env pytest -q  # includes separate veil_test database
cd backend && uv run --with reportlab python -m pytest -q ../tests/ingest   # OCR (Apple Vision, macOS)
npm --prefix frontend test && npm --prefix frontend run build

python -m pytest tests -q               # Mykola's tests (needs root requirements.txt installed)
cd evalkit && uv run pytest -q
```

Deep links: `/app?sample=01_tenancy_agreement.pdf` opens a sample directly;
`/app?doc=<id>` reopens a document already saved in PostgreSQL.

## 7. Frontend

- `src/main.tsx`: lazy routes, `/app*` → `App`, else `Landing`. Fonts via Fontsource: Pixelify Sans (UI), Silkscreen (labels), Source Serif 4 (document text).
- `src/App.tsx`: sessions, health check, sample deep link, layout (2 columns, 3 after Approve when the Ask panel opens). Runs one live scan per document. A scan keeps running in the background while the person opens the intake or another document (the backend finishes and stores it anyway); only closing the app aborts it. Coming back shows the progress so far or the finished result, without replaying passes that already ended.
- Saved documents (added 24 Oct, frontend side; needs the backend's list, status and turns): going to the landing page and back, or a reload, keeps every document with its review status and chat.
  - After login `App` calls `GET /api/documents` and fills the rail with every saved document (filename, status chip). A row is opened only when clicked: `GET /api/documents/{id}` gives the result (shown at once, no replay of the scan), the status (approved opens the Ask panel) and the chat turns. While it loads the middle column shows `Opening` (in `DocumentPane.tsx`), with Try again if it fails.
  - Status to page: no result means "new" (rail chip "Not scanned", a Scan button that runs the stream with `retry=failed`, so parts the server already read are reused); otherwise "approved" and "declined" as stored, anything else "review". A scan that was still running when the person left carries on on the server: the document comes back with its result, or as "new" if it has none yet.
  - Approve, Decline and Edit redactions send `PATCH /api/documents/{id}` with `approved`, `declined`, `review`. The page changes at once; if the save fails it goes back and the bar says "Not saved." A new ask appends the turn the backend returns (it is stored already). Turns do not keep the text sent, so "What it sees" uses the current redacted text. The rail cannot remove documents yet, so nothing calls DELETE.
  - The open document is in the URL as `?doc=<id>` (`history.replaceState` on every switch), so a reload reopens it; `?sample=` still opens a sample.
  - Older backend: `GET /api/documents` answering 404 "Not Found" or 405 (the backend before this change only has POST there) means no saved list. The rail then works as before (only what was opened in this tab, "Save a document's link to reopen it") and no PATCH is sent. Chrome logs that one 405 as a console error on each load until the backend has the list.
  - Pure mapping in `src/session.ts` (`uiStatus`, `fromSummary`, `fromStored`, `mergeList`, `withOpened`) with tests in `src/session.test.ts`; the 404 and 405 fallback is tested in `src/api.test.ts`. Nothing about a document is kept in localStorage; only the open document's ID is in the URL.
- `src/components/`: `Rail` (every saved document with its status, or the sessions of this tab on an older backend, + model status; compact row on mobile), `Intake` (drop zone, paste, sample cards with thumbnails), `DocumentPane` (the live redaction pass, review bar, popovers, approved bar + download), `Routing` (each part's status, time and Mubit request id, copyable; a "N parts" toggle in the document header and in "What it sees"), `AskPanel` (shown only after Approve; tabs "Ask the AI" / "What it sees"), `Victory` (full-screen knight scene after Approve).
- Live scan: `api.redactStream` POSTs `/api/documents/{id}/redact/stream` and reads the Server-Sent Events with its own parser (`src/sse.ts`; EventSource cannot POST). If the route does not exist (405, or 404 with detail `"Not Found"`) it calls the one-shot `/redact` and rebuilds the same events from the result (`synthesise`), so the UI has one code path. `src/scan.ts` is the pure reducer from events to `Session.scan` (parts with status, live values deduplicated by start and end, done), plus the pass helpers; tests in `src/*.test.ts`.
- The pass is driven by real events: lines of a part still being read pulse calmly; when a part's `chunk` event arrives its lines are swept (values flash, then bars), so parts finish out of order on screen too. Progress = finished parts / parts; the change counter counts values in finished parts. On `done` the page switches to the final result (placeholders, page boxes) and the review bar rises after the last pass. A part with `status: "error"` gets a dashed gutter, a "Not checked by the AI" note (reason on hover) and Retry; model off shows "Numbers only for now". Reduced motion: no passes, states change in place.
- Retry: `POST .../redact/stream?retry=failed`. The backend sends parts it already read ("ok", "empty") again at once from its stored run, without calling T1, and reads only the parts that failed (or were "off" if the model is now on). In the UI those parts keep their bars and their ended pass; only the parts read again sweep (a pass belongs to one reading of a part, its `order`). An older backend ignores the parameter and reads everything again; repeated parts update their details but still get no second pass. "Try again" after a failed run also sends `retry=failed`, so the backend can skip what it already has.
- Pages view: a page image is requested at a scale capped to about 1600 px wide and 8 MP (`pageScale`), because photos and scans arrive as PDF pages of one point per pixel (a phone photo is about 4032 points wide). Each image has its width and height set before it loads (no layout jump) and is fetched only when it comes within one screen of view.
- Offsets: the backend counts Python code points, the browser UTF-16 units. `scan.ts` maps every offset (stream events, results, corrections) when the text has emoji or other astral characters.
- Mock stream for frontend work without the real stream: start the backend on 8000 (no key needed), then `npm --prefix frontend run mock` (port 8010, passes every other call to 8000) and `npm --prefix frontend run dev:mock` (Vite with `VEIL_API=http://127.0.0.1:8010`). 5 parts, 0.6 to 3 s each, part 3 fails, fake `mreq_mock...` ids; part 3 succeeds on a retry, which reuses the other parts; flags `MOCK_MODEL=off`, `MOCK_ERROR=none` or `always`, `MOCK_FAIL=1`, `MOCK_NO_STREAM=1`, `MOCK_RETRY=ignore`, `MOCK_SLOW=2` (see the top of `scripts/mock-stream.mjs`). It never calls Mubit. It also stands in for the saved list, status and chat (`GET /api/documents`, `PATCH /api/documents/{id}`, `status` and `turns` on `GET /api/documents/{id}`, `turn_id` on `/ask`), kept in memory per account for documents created or opened through it, and answers `/ask` itself when the backend has no chat model (no AI is called). A scan carries on when the browser leaves, as on the backend; `MOCK_LEAVE=stop` stops it instead, so the document comes back as "new". `MOCK_NO_LIST=1` answers like an older backend (list 404 "Not Found", PATCH 405, no status or turns). Headless check of the whole flow (open, approve, ask, landing and back, reload): screenshots in `frontend/docs/persist-chats/`. `VEIL_API` also points `npm run dev` at any other backend.
- `src/ui/kit.tsx` + `src/ui/icons.ts`: the only component set (Button, LinkButton, TextArea, Chip, Tabs, Icon, Spinner; 12x12 icons, 16x16 pictograms). Reuse it; do not add ad hoc buttons.
- `src/landing/`: `Landing.tsx` (top bar, hero, learn demo, numbers notice, final CTA, footer), `Journey.tsx` (pinned scroll story, 4 steps, reduced-motion still version), `art.ts` (generated, do not hand-edit), `landing.css`.
- `scripts/art.py` regenerates `src/landing/art.ts` (castle, gatehouse, tower, hills, pigeon...).
- CSS: `src/index.css` tokens in `@theme`; all component classes inside `@layer components` (unlayered CSS overrides Tailwind utilities; that bug happened once).
- Rules (from DESIGN.md): everything Veil says is pixel type, everything that is the user's document is serif paper; eased motion for movement, `steps()` only for sprite frames; respect `prefers-reduced-motion`; name the chat model "AI provider", never a vendor; no em dashes in copy.

## 8. Open conflicts to resolve (team decision, do not pick silently)

1. **Two T1 designs.** The app runs either (`VEIL_T1_PROMPT`). Since 24 Oct the default is `rewrite` (Nick's call): his Mubit task "Redact personal data" has a trained v1 adapter (held-out test 91.7% vs 66.7% for the base model), and the Night Shift check-in bot looks for Claude Haiku calls through `api.mubit.ai/anthropic`. `evalkit` stays available with `VEIL_T1_PROMPT=evalkit`.
   - App + all Mubit training so far: `evalkit/src/evalkit/prompts.py` (`PROMPT_VERSION = 1`), output = JSON list of entities, teacher `gpt-6-luna`. Mubit console task "Find personal data", Training v1.
   - Mykola: `backend/app/prompts.py`, output = the chunk rewritten with placeholders, model `claude-haiku-4-5`, used by `scripts/dataset/send_batch.py`. Marked "DRAFT pending Nick's review".
   - Mubit fingerprints a task by model + system prompt + tools + output format. Any change creates a new task with zero kept examples. Pick one before more training traffic. `evalkit` can already send Mykola's documents (`evalkit/src/evalkit/team_docs.py`, rounds `team_train` / `team_eval`) and recover spans from rewrite answers (`rewrite.py`).
2. **Two dataset pipelines**: `datagen` + `dataconv` + `evalkit/build_rounds` (outputs gitignored under `data/synthetic`, `data/external`, `data/rounds`) vs `data/docs` + `scripts/dataset` (committed). Pick one format as canonical, or keep the converter.
3. **Two Python setups**: `backend/pyproject.toml` (uv, used by the app) vs root `requirements.txt` + `tests/` (Mykola). Both can import `backend/app`. Fold into one before adding more.
4. **Two PDF readers**: PyMuPDF words (`extract.py`, needed for boxes) vs pdfium lines (`ingest`). Keep PyMuPDF for text-layer PDFs unless `ingest` gains word boxes with character offsets.

## 9. Mubit training state (24 Oct, 12:01 UTC)

- Console: task "Find personal data", Training v1, 103 examples kept from about 1,070 calls. About half of the examples are rejected by Mubit's reviewer; screenshot the "Show each" reasons to learn why.
- Sent with recording on, 0 errors: `team_train`, `corrections`, `r2_fresh` (11:45 to 12:01 UTC).
- Queued: `r3_reserve`, sent by `evalkit/autosend.sh` after the daily limit resets at 2026-10-25 00:05 UTC. It runs in a terminal on Dmytro's Mac (`caffeinate -is ./autosend.sh`). If the Mac sleeps or the terminal closes, run it again.
- Run logs and `corrections_todo.md` (wrong answers with `mreq_` ids for console corrections) are in `evalkit/runs/`, which is gitignored: they exist only on Dmytro's Mac.
- Rules: only synthetic or Mubit-safe records go through Mubit. `data/external/eval_local_only.jsonl` must never be sent. The daily training limit resets at 00:00 UTC.

## 10. Hard rules for any agent

- Never commit keys. `.env`, `.env.*`, `*.env` are gitignored (`.env.example` is the exception). A Mubit key was shown in screenshots: rotate it in app.mubit.ai.
- Do not commit `data/external/`, `data/rounds/`, the rest of `data/synthetic/` (size, licences) or `evalkit/runs/`.
- Honest claims only: say "pseudonymised", never "anonymised" or "compliant". T1 runs through Mubit (a remote gateway), so never claim the file never leaves the laptop. Correct copy: "the AI only sees the placeholders". OCR itself is local (Apple Vision).
- No em dashes in user-facing text or docs. Plain, short English in the UI.
- The repo is public. Commit or push only when a human asks. Work on a branch and open a PR.

## 11. Done, verified, not verified

Done and checked in the browser on 24 Oct (1440x900 and 375x812, no console errors on a fresh load): landing scroll story, app intake, redaction pass, review, victory, Ask panel layout.

Checked on Nick's Mac on 24 Oct, after PRs #11 to #13, with a live Mubit key and the `rewrite` prompt, synthetic data only:
- Tenancy sample (4 pages): 8 chunks streamed, every one `ok` with an `mreq_` id, 1.3 to 3.3 s each, 5.8 s in all; 23 of 24 answer-key values hidden (the miss was the client code `NPM-404605`, now caught by `refs.py`). The downloaded PDF has no hidden value in its text and no metadata. Ask went through Mubit with the values restored. `?retry=failed` answered in 21 ms with no new T1 call.
- Pasted text and a `.py` file: names, email, phone, address, NI number, account, sort code and client code hidden.
- Photos of two sample pages through the API: every answer-key value hidden; re-OCR of the redacted PDF reads none of them.
- The UI against that backend: parts light up as Mubit answers, the parts list shows the real request ids, no console errors.
- Tests: backend, ingest on macOS (Apple Vision), evalkit, `tests/dataset`, frontend tests and build all pass.

Not verified:
- The last design-review round: some screenshots predate the final fixes (mobile final CTA, mobile counters, reduced-motion page).

## 12. Next steps, in order

1. A real phone photo (HEIC) through the app on a Mac.
2. After 00:05 UTC on 25 Oct: confirm `r3_reserve` was sent; apply console corrections from `evalkit/runs/corrections_todo.md`.
3. Demo prep: script in `docs/APP-SPEC.md` section 6; investor numbers page (claude.ai artifact `https://claude.ai/artifact/VrYTnta4z6487XBsKq7V9q`, private until shared) built from `docs/research/2026-10-24-veil-numbers/`.
4. Unify Python setup and dataset pipelines (sections 8.2, 8.3).
