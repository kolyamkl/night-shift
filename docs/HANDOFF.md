# Veil: handoff for the next agent

Written 2026-10-24 (hackathon day 2) for an AI coding agent picking this repo up cold. Read this first, then the files it points to. Paths are relative to the repo root. Facts marked "not verified" were not re-checked after the last merge.

## 1. What Veil is

Veil is a privacy layer for using AI chat with real client documents (Mubit "Night Shift" hackathon, London, 23 to 25 Oct 2026; repo github.com/BabyBoss45/night-shift, public).

1. The user uploads a PDF, photo, scan, email or pasted text.
2. **T1** finds personal data. T1 is a model trained through **Mubit** (teacher model `gpt-6-luna` behind Mubit's gateway while the adapter trains), plus a regex layer for UK identifiers.
3. The user reviews the redaction line by line: Approve all, Decline, "Not personal, show it" (unhide), "Fix a miss" (hide).
4. Each distinct value becomes a placeholder such as `[PERSON_1]`. The download is a truly redacted PDF (text removed under the box) or redacted text.
5. **T2** (any AI provider, default `claude-haiku-4-5` through Mubit with recording off) answers questions about the document. It sees placeholders only. Veil restores the real values locally in the answer.
6. Reviewer corrections become Mubit training signal, so the model learns a firm's own codes.

Pitch line: the edge is per-firm learning via Mubit, true PDF redaction and UK identifiers. Mask-and-restore alone is common among competitors.

## 2. Repo map

| Path | Origin | What | State |
|---|---|---|---|
| `frontend/` | Dmytro | React 19 + Vite + TS + Tailwind v4 + Motion. `/` = landing (pixel castle scroll story), `/app` = the app | Built, checked in browser desktop + mobile on 24 Oct |
| `backend/app/main.py` | Dmytro | FastAPI API (section 5) | Working; tests 26 passed before the merge |
| `backend/app/extract.py` | Dmytro | PDF via PyMuPDF: text plus every word's box and character range (needed for true redaction) | Working |
| `backend/app/pipeline.py` | Dmytro | regex + T1 per chunk, merge spans, vault placeholders, boxes per line, `rebuild()` for reviewer fixes | Working |
| `backend/app/pdfout.py` | Dmytro | True PDF redaction (`add_redact_annot` + `apply_redactions`) | Working |
| `backend/app/llm.py` | Dmytro | T1 (two prompts, `VEIL_T1_PROMPT`) and T2 calls through Mubit; key from env, `backend/.env` or root `.env` | Working with a valid key |
| `backend/app/ingest/` | Mykola (PR #9) | Local reading of PDFs and images: pdfium text layer, Apple Vision OCR (macOS), identifier repairs after OCR. See its README | Merged; wired into uploads (section 4) |
| `backend/app/prompts.py` | Mykola | **A second T1 prompt** (rewrite design, `claude-haiku-4-5`). Used by the app only with `VEIL_T1_PROMPT=rewrite`. See section 8 | Conflict, decide |
| `backend/tests/` | Dmytro | API, extract, llm, pdfout, pipeline tests | Not re-run after merge |
| `evalkit/` | Dmytro | Frozen T1 prompt the app uses (`evalkit/src/evalkit/prompts.py`), scorer, regex baseline, vault/restore, round builder, Mubit sender, `autosend.sh` | Used by backend (path dependency) |
| `datagen/` | Dmytro | Synthetic UK documents with gold spans (100k run, seed 42) and demo PDFs | Outputs in `data/synthetic/` (gitignored except `pdfs/`) |
| `dataconv/` | Dmytro | Converters for open PII datasets (TAB, Gretel, Nemotron, OpenPII, bitext, ...) into our format | Outputs in `data/external/` (gitignored, licences vary) |
| `data/synthetic/pdfs/` | Dmytro | 30 synthetic sample PDFs + `*.gold.json` labels; the app's "Try a sample" cards | Committed (fake data only) |
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
       ├─ PDF with a text layer  → extract.extract_pdf (PyMuPDF words: text + box + char range)
       ├─ PDF without text (scan) → ingest.extract (Apple Vision OCR) → text only
       ├─ image (jpg png heic tiff webp) → ingest.extract → text only
       ├─ .eml → headers + body text
       ├─ .txt .md .csv .json, code and config files (.py .ts .yaml .sql .html ...) → text
       └─ any other file that is UTF-8 with no NUL byte in its first 8 KB → text (else 415)
  └─ POST /api/documents/{id}/redact/stream   (server-sent events, what the UI should use)
     or POST /api/documents/{id}/redact        (same result in one JSON answer)
       pipeline.run_pipeline:
         chunk text (≤4000 chars for evalkit, ≤1400 for rewrite; paragraph cuts)
         → T1 per chunk in parallel (6 workers); each finished chunk is streamed as it lands
         every value T1 returns is located across the WHOLE document (evalkit.spans.locate)
         + regex layer (evalkit.regex_baseline) → merge overlaps → Vault placeholders
         → boxes: words overlapping a span, one rectangle per line (PDF only)
  └─ review in the UI → POST /corrections {hide|unhide} → pipeline.rebuild (no new T1 calls)
  └─ GET /file → true-redacted PDF (pdfout) or redacted .txt
  └─ POST /ask → T2 gets only redacted_text → evalkit.redact.restore puts values back
```

Model calls (both through Mubit, `backend/app/llm.py`):
- **T1**, recording ON (calls keep training a Mubit task), session `doc-<doc_id>`. `VEIL_T1_PROMPT` picks the prompt, and each prompt is its own Mubit task:
  - `evalkit` (default): frozen prompt `evalkit/src/evalkit/prompts.py`, model `VEIL_T1_MODEL` (default `gpt-6-luna`), chunks ≤4000 chars, answer = JSON list of `{text, type}` parsed by `evalkit.send_batch.parse_entities`. Mubit task "Find personal data".
  - `rewrite`: Mykola's `backend/app/prompts.py` with its `MODEL_ID` (`claude-haiku-4-5`; `VEIL_T1_MODEL` is ignored), chunks ≤1400 chars (Mubit's reviewer reads only about the first 1,530 chars of a call), each sent stripped of surrounding whitespace as `scripts/dataset/build_chunks.py` made the training chunks. Values with fewer than two letters or digits, and PERSON values that are only a title, are dropped, since every value is hidden everywhere in the document. Sent with the `anthropic` SDK (pinned to the version in the root `requirements.txt`) exactly as `scripts/dataset/send_batch.py` sends it, so it lands in his Mubit task "Redact personal data"; a test compares the two requests. The answer is the chunk rewritten with `[TYPE_N]` placeholders; `llm.align_rewrite` matches it line by line as a template (falling back to `evalkit.rewrite.spans_from_rewrite`) to get the values. An answer that does not line up, or `stop_reason: max_tokens`, makes the chunk an error.
- **T2**: model `VEIL_T2_MODEL` (default `claude-haiku-4-5`), header `x-middleware-record: off` (no second task, Mubit stores no user questions).
- Key and settings: the first value starting with `mbt_` in `MUBIT_API_KEY`, then `backend/.env`, then the repo-root `.env` (where `scripts/dataset/send_batch.py` reads it too). `VEIL_T1_PROMPT`, `VEIL_T1_MODEL` and `VEIL_T2_MODEL` are looked up the same way (section 5). `/api/health` reports where the key came from (`key_source`), never the key.
- No key → both off; the app still works on the regex layer only (UI shows "Numbers only for now"). The startup log says which prompt, model and key source are in use.

Storage: documents and results live in memory (`DOCS`, `RESULTS` dicts) for the server's lifetime. Nothing is written to disk; document text is never logged. Per chunk the log holds only doc id, chunk index, status, latency, `mreq_` id and the number of values found.

## 4. OCR integration (done in this merge, minimal)

`backend/app/main.py::_ocr()` calls `app.ingest.extract(data)` for images and for PDFs whose PyMuPDF text is empty, then stores the result as a **text** document (`kind="text"`). Consequences:
- Photos and scans now work end to end (redact, review, ask), on macOS only (Apple Vision).
- They have **no page boxes**: the review shows text lines, and the download is redacted `.txt`, not a redacted image.
- Text-layer PDFs still go through our PyMuPDF extractor, because the pipeline needs per-word boxes with character offsets for true redaction. `ingest` returns line boxes only.
- Deps added to `backend/pyproject.toml`: `pypdfium2`, `pillow`, `pillow-heif`, `pyobjc-framework-Vision` (darwin). `uv.lock` updated. Frontend accepts the image types and shows a "Photo" chip.

Next step for OCR (not done): build `Word`s from `ingest` `Line`s (split each line into words, estimate each word's box by character position inside the line box, convert fractions to points), turn images into a one-page PDF (`pymupdf.open(stream=..., filetype="png").convert_to_pdf()`), then reuse `pdfout.redact_pdf`; `apply_redactions` blanks image pixels under the box. Watch `Page.rotation`: ingest may rotate or deskew the image before the final OCR pass, so boxes are in the turned frame and must be mapped back.

## 5. API (FastAPI, `backend/app/main.py`)

| Method | Path | Does |
|---|---|---|
| GET | `/api/health` | `{model: on/off, t1_model, t1_prompt: evalkit/rewrite, t2_model, key_source: env/backend/.env/.env/null}` |
| POST | `/api/documents` | form `text` or `file` (≤20 MB) → `{doc_id, kind, filename, text, pages}` |
| POST | `/api/documents/{id}/redact` | runs the pipeline → `{redacted_text, entities, boxes, chunks, stats, model}`; each chunk is `{index, chunk_id, start, end, status, error, mreq_id, latency_ms, found}`. Optional `?retry=failed` (below) |
| POST | `/api/documents/{id}/redact/stream` | the same run as server-sent events (contract below). Optional `?retry=failed` |
| GET | `/api/documents/{id}/pages/{n}.png` | page image (PDF only) |
| GET | `/api/documents/{id}/file` | redacted PDF or text download |
| POST | `/api/documents/{id}/ask` | `{question}` → `{answer, answer_with_placeholders, sent_text, unknown_placeholders, mreq_id}` |
| POST | `/api/documents/{id}/corrections` | `{action: hide/unhide, text, type}` → new result |
| GET | `/api/samples` | sample cards from `data/synthetic/pdfs` (title, kind, pages, value counts from gold) |
| GET | `/api/samples/{name}/thumb.png` | thumbnail (width 120, darkened) |
| POST | `/api/samples/{name}` | opens a sample as a document |

Stream contract (`/redact/stream`, fixed: the frontend builds against it):
- Unknown doc: 404 JSON `{"detail": "Document not found. Upload it again."}` before any stream. Otherwise 200 with `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`.
- Each event is `event: <name>\ndata: <one-line JSON>\n\n`; a comment `: ping\n\n` goes out every 5 s while waiting.
- Events in order: `start` once `{doc_id, model, t1_model, t1_prompt, chunks: [{index, chunk_id, start, end}]}`; `regex` once `{entities: [{start, end, text, type, source: "regex"}]}`; `chunk` once per chunk in the order chunks finish `{index, chunk_id, start, end, status: ok/error/empty/off, error, mreq_id, latency_ms, found, entities: [{..., source: "model"}]}`; `done` once, exactly the `/redact` JSON from the same builder (`RESULTS` is stored first, so `/file`, `/ask` and `/corrections` work right away). `error` `{message}` only for an unexpected failure that stops the run; a failed chunk is a `chunk` with `status: "error"`.
- `entities` of a chunk are the occurrences, inside its `[start, end)`, of the values T1 returned for it; `found` is the number of values T1 returned. `off` = no key, no call; `empty` = whitespace-only chunk, no call. All offsets are character offsets into the `text` from `POST /api/documents`.

Retry only what failed: `POST /api/documents/{id}/redact/stream?retry=failed` (and `POST /redact?retry=failed`):
- Same events, in the same order, as a normal run.
- If `RESULTS` holds an earlier run of this document with the same chunk plan (same T1 prompt and the same ranges), its chunks with status `ok` or `empty` make no new T1 call: their `chunk` events go out at once with the stored `mreq_id`, `latency_ms`, `found` and `entities`. Only chunks that were `error` (or `off`, when the model is now on) call T1. `done` is then what a full run would give; like any scan, it starts without reviewer corrections.
- With no earlier result or a different plan, every chunk runs, as without the parameter. Any other value of `retry` is a 422.
- `PipelineResult.chunk_values` keeps what T1 returned per chunk and `PipelineResult.plan` the prompt, for this.

One scan per document at a time: each scan (`/redact` or `/redact/stream`, with or without `retry`) gets a generation number. Only the newest may store `RESULTS[doc_id]` and send `done`. An older one stops making new T1 calls, goes quiet and ends with `error` `{"message": "A newer scan of this document started, so this one stopped."}`; an older `/redact` gets 409 with the same text.

Settings and key lookup: `MUBIT_API_KEY`, `VEIL_T1_PROMPT` (`evalkit` default, or `rewrite`), `VEIL_T1_MODEL` (evalkit prompt only) and `VEIL_T2_MODEL` are each read from a real environment variable first, then from `backend/.env`, then from the repo-root `.env` (so the root `.env` that holds the key can also say `VEIL_T1_PROMPT=rewrite`). Only these names are read from the files; nothing is loaded into `os.environ`. For the key, only a value starting with `mbt_` counts. The startup log names the prompt and where it came from, for example `T1 on: prompt rewrite (VEIL_T1_PROMPT from .env), model claude-haiku-4-5, 1400-character chunks, Mubit key from .env`; a bad `VEIL_T1_PROMPT` stops startup. `VEIL_CORS` and `VEIL_SAMPLES_DIR` are read from the environment only.

## 6. How to run

```bash
# backend (Python 3.12/3.13, uv); evalkit is a path dependency
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000
# key: one line MUBIT_API_KEY=mbt_... in the root .env (or backend/.env, or export it); all gitignored.
# Lookup order: environment, backend/.env, .env. The startup log and /api/health show the source.
# Second T1 prompt (Mykola's rewrite design): VEIL_T1_PROMPT=rewrite in the same .env (see .env.example),
# or VEIL_T1_PROMPT=rewrite uv run uvicorn app.main:app --port 8000

# watch a scan stream (synthetic sample only)
DOC=$(curl -s -X POST localhost:8000/api/samples/01_tenancy_agreement.pdf | python3 -c "import json,sys; print(json.load(sys.stdin)['doc_id'])")
curl -N -X POST localhost:8000/api/documents/$DOC/redact/stream

# frontend (Vite proxies /api to 127.0.0.1:8000)
npm --prefix frontend install && npm --prefix frontend run dev   # http://localhost:5173

# tests
cd backend && uv run pytest -q          # our backend tests
npm --prefix frontend test              # vitest (redaction, icons)
python -m pytest tests -q               # Mykola's tests (needs root requirements.txt installed)
cd evalkit && uv run pytest -q
```

Deep links: `/app?sample=01_tenancy_agreement.pdf` opens a sample directly.

## 7. Frontend

- `src/main.tsx`: lazy routes, `/app*` → `App`, else `Landing`. Fonts via Fontsource: Pixelify Sans (UI), Silkscreen (labels), Source Serif 4 (document text).
- `src/App.tsx`: sessions, health check, sample deep link, layout (2 columns, 3 after Approve when the Ask panel opens).
- `src/components/`: `Rail` (sessions + model status; compact row on mobile), `Intake` (drop zone, paste, sample cards with thumbnails), `DocumentPane` (line-by-line redaction animation, review bar, popovers, approved bar + download), `AskPanel` (shown only after Approve; tabs "Ask the AI" / "What it sees"), `Victory` (full-screen knight scene after Approve).
- `src/ui/kit.tsx` + `src/ui/icons.ts`: the only component set (Button, LinkButton, TextArea, Chip, Tabs, Icon, Spinner; 12x12 icons, 16x16 pictograms). Reuse it; do not add ad hoc buttons.
- `src/landing/`: `Landing.tsx` (top bar, hero, learn demo, numbers notice, final CTA, footer), `Journey.tsx` (pinned scroll story, 4 steps, reduced-motion still version), `art.ts` (generated, do not hand-edit), `landing.css`.
- `scripts/art.py` regenerates `src/landing/art.ts` (castle, gatehouse, tower, hills, pigeon...).
- CSS: `src/index.css` tokens in `@theme`; all component classes inside `@layer components` (unlayered CSS overrides Tailwind utilities; that bug happened once).
- Rules (from DESIGN.md): everything Veil says is pixel type, everything that is the user's document is serif paper; eased motion for movement, `steps()` only for sprite frames; respect `prefers-reduced-motion`; name the chat model "AI provider", never a vendor; no em dashes in copy.

## 8. Open conflicts to resolve (team decision, do not pick silently)

1. **Two T1 designs.** The app can now run either (`VEIL_T1_PROMPT`, default `evalkit`); which one is canonical is still open.
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

Not verified:
- The full flow with a live Mubit key (T1 names and addresses, Ask). Without a key only the regex layer runs.
- OCR uploads through the app (wired in this merge; `ingest` itself has Mykola's tests and evaluation).
- Tests after this merge (backend 26 and frontend 9 passed before it).
- The last design-review round: some screenshots predate the final fixes (mobile final CTA, mobile counters, reduced-motion page).

## 12. Next steps, in order

1. Decide the canonical T1 (section 8.1) before the next training round.
2. Put a key in `backend/.env`, restart the backend, run the demo flow end to end with a sample and with a phone photo.
3. Run all test suites (section 6) and fix what the merge broke.
4. OCR boxes for images and scans (section 4), so photos also get black boxes and a redacted file.
5. After 00:05 UTC on 25 Oct: confirm `r3_reserve` was sent; apply console corrections from `evalkit/runs/corrections_todo.md`.
6. Demo prep: script in `docs/APP-SPEC.md` section 6; investor numbers page (claude.ai artifact `https://claude.ai/artifact/VrYTnta4z6487XBsKq7V9q`, private until shared) built from `docs/research/2026-10-24-veil-numbers/`.
7. Unify Python setup and dataset pipelines (sections 8.2, 8.3).
