# Veil

A privacy layer for using AI with real client documents. Built for the Mubit Night Shift hackathon (London, 23 to 25 Oct 2026).

## What it does

1. Paste text, or drop a PDF, a photo or scan, an email or a code file.
2. Veil finds the personal data: a detector model called through Mubit, plus a regex layer for UK identifiers (cards, accounts, sort codes, IBAN, NI numbers, postcodes, phones, emails), client, policy, claim and case references, IP addresses and e-signature IDs. An address is then widened to its flat, building and town, and an address the model missed is read back from its postcode.
3. You review every change line by line as each part of the document comes back. Fix a miss, or show a value that is not personal.
4. Approve. Only then can you ask an AI about the document. It sees placeholders such as `[PERSON_1]`, and Veil puts the real values back into its answer.
5. Download the result: for a PDF, photo or scan, the same pages with the text and pixels under each black box removed from the file; for text, the redacted text. This is pseudonymised, not anonymised.

## Where Mubit is used

- **Detector (T1):** `backend/app/llm.py` calls `claude-haiku-4-5` with the anthropic SDK and base URL `https://api.mubit.ai/anthropic`, using the Mubit key from `MUBIT_API_KEY`. The key lives in `.env` and is never committed. Each part of a document is one call with recording on, so the calls train the Mubit task "Redact personal data". The UI lists every part with its Mubit request id (`mreq_...`).
- **Answer (T2):** the same gateway, sent with `x-middleware-record: off`, so Mubit stores no user questions.
- **Training:** ratings on those calls in the Mubit console decide which examples Mubit keeps. Adapter v1 (Qwen3 4B) passed its held-out test at 91.7%, against 66.7% for the base model. It does not serve yet: Mubit wants 20 test cases and v1 has 12.

Document text is sent through Mubit for detection. The AI you ask only sees the placeholders. Reading PDFs and the OCR of photos and scans run locally (OCR uses Apple Vision, so macOS).

## Run

```bash
cp .env.example .env    # then set MUBIT_API_KEY=mbt_...
python3 scripts/local_db.py start
cd backend && uv sync --frozen && uv run --env-file ../.env uvicorn app.main:app --reload --port 8000
npm --prefix frontend install && npm --prefix frontend run dev    # http://localhost:5173/app
```

Without a key the app runs on the regex layer only. `VEIL_T1_PROMPT=evalkit` switches the detector to the evalkit prompt on `gpt-6-luna`. All document and stream requests need a login cookie and `X-Veil-Request: 1`.

## Tests

370 tests on 24 Oct, all passing (192 backend, 48 OCR, 63 dataset, 10 evalkit, 57 frontend). The backend API tests need the local database from `scripts/local_db.py`; without `TEST_DATABASE_URL` they are skipped.

```bash
cd backend && uv run --env-file ../.env pytest -q                              # API, auth, storage, stream, pipeline, regex rules, addresses, PDF, OCR boxes
cd backend && uv run --with reportlab python -m pytest -q ../tests/ingest       # OCR with Apple Vision (macOS)
python -m pytest -q tests/dataset                                                 # dataset pipeline (pip install -r requirements.txt)
cd evalkit && uv run pytest -q                                                    # scorer, regex baseline
npm --prefix frontend test && npm --prefix frontend run build                     # stream parser, live scan state, redaction view
```

## More

[docs/HANDOFF.md](docs/HANDOFF.md) has the repo map, architecture, API, open decisions and next steps. See also [docs/DATABASE.md](docs/DATABASE.md), [docs/APP-SPEC.md](docs/APP-SPEC.md) and [backend/app/ingest/README.md](backend/app/ingest/README.md).
