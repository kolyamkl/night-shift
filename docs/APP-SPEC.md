# Veil web app: what to build

> Historical build specification. Some requirements below were proposals and some privacy statements predate the implementation. Use [Architecture](ARCHITECTURE.md), [Mubit](MUBIT.md) and [Security](SECURITY.md) for current behavior.

One page, Quillbot-style: drop or paste anything (text, PDF, image, email), see what personal data was found, get the same file back with black boxes, and ask Claude or GPT about it without the provider ever seeing the personal data.

## 1. What Mubit needs from the app (checked against docs.mubit.ai and Context7, 24 Oct)
- **There is no Mubit SDK to integrate for this.** The app calls OpenAI / Anthropic / Gemini exactly as usual, with the base URL set to Mubit and the Mubit key. Context7 only indexes the older memory SDK (`mubit.learn`), which injects lessons into the system prompt. **Do not use it for T1**: a changing system prompt splits the task.
- **No correction API, and no per-call "served by" signal.** Corrections are made in the console on the request (organisers' PagerPal). Serving shows in the console as "Routed requests" / "Task rules", and the task pipeline is Collecting, First training, Tests, Silent test, Live.
- So the backend's Mubit duties are small:
  1. **T1 (redaction):** call it with the frozen prompt (`evalkit/src/evalkit/prompts.py`), one chunk per call, `x-middleware-record` left at full so the calls keep training the adapter.
  2. **Keep the request id** (`x-middleware-request-id`) for every T1 chunk, so a reviewer can find that call in the console and correct it.
  3. **T2 (answer):** send only redacted text with `x-middleware-record: off`. It still goes through Mubit (the rule), but creates no second task and stores no user questions.
- **Privacy guard:** until the T1 task is Live in the console, T1 calls go to the teacher model. Use synthetic documents in the demo. A "real data" switch stays off until the adapter serves (team pack FR-9).

## 2. User flow (one page)
1. **Input:** a big box like Quillbot. Paste text, or drop PDF / PNG / JPG / DOCX / EML / TXT. Plus sample buttons: "Tenancy agreement", "Bank statement", "Screenshot of a chat".
2. **Scan, in a few seconds:** a progress bar per chunk.
3. **Result view, two panels:**
   - **Left, "Your document":** the PDF page or image with black boxes over each found value; or, for text, the text with highlighted values. Hover a box to see its type (PERSON, CARD ...).
   - **Right, "What the AI sees":** the redacted text with `[PERSON_1]`-style placeholders.
   - **Strip above:** counts by type ("3 names, 1 address, 1 card, 2 client codes").
4. **Actions:**
   - **Download redacted file:** the same PDF or image, with the text under the boxes truly removed.
   - **Ask about this document:** a chat box. The question plus the redacted text goes to Claude/GPT. The answer comes back with real values restored, and a "show what was sent" toggle.
   - **Fix:**
     - click a box to un-hide it (false positive);
     - select missed text, pick a type, then "Hide" (missed value);
     - each fix is stored with the chunk's request id, and the "Fix in Mubit" link opens the console Requests page filtered by session.
5. **Footer metrics:** values hidden, latency, "served by: teacher / adapter" (manual, from the console), regex-only comparison for the same document.

## 3. Backend (FastAPI, Python)
Reuse `evalkit` modules: `prompts.py`, `spans.py`, `redact.py`, `regex_baseline.py`, `uk_formats.py`, `providers.py`.

| Endpoint | Input | Output |
|---|---|---|
| `POST /api/documents` | multipart file or `{text}` | `{doc_id, kind, pages, text}`: text plus word layout (below) |
| `POST /api/documents/{id}/redact` | | `{entities, redacted_text, boxes, stats, chunks: [{chunk_id, mreq_id}]}` |
| `GET /api/documents/{id}/file` | | the redacted PDF or PNG |
| `POST /api/documents/{id}/ask` | `{question}` | `{answer, answer_with_placeholders, sent_text}` |
| `POST /api/documents/{id}/corrections` | `{action: hide/unhide, start, end, type}` | updated `{entities, redacted_text, boxes}` |
| `GET /api/samples` | | demo documents (synthetic) |

### 3.1 Extraction: text plus where each word is
| Input | Library | Output |
|---|---|---|
| PDF with a text layer | PyMuPDF `page.get_text("words")` | words with `(x0, y0, x1, y1)` per page |
| Scanned PDF | PyMuPDF render the page (200 dpi), then OCR | words with pixel boxes, scaled back to PDF points |
| PNG / JPG / screenshot | OCR **locally**: Apple Vision via `ocrmac` (macOS, best), fallback Tesseract (`pytesseract`, needs `brew install tesseract`) | words with pixel boxes |
| DOCX | `python-docx` (paragraphs, tables, headers, footers) | text (no boxes; the redacted copy is rebuilt from paragraphs) |
| EML | Python `email` | headers (From / To / Cc names and addresses) + body as text |
| TXT / pasted | as is | text |

- Build one document string by joining words (space within a line, `\n` between lines, `\n\n` between blocks). Record each word's character range, so `char -> word -> box`.
- **Never send an image or PDF to a model provider.** OCR runs locally; only text goes to T1.

### 3.2 Redaction
1. Split the text into chunks of at most about 1,000 tokens on paragraph boundaries (same rule as `datagen/chunker.py`).
2. **Regex layer** (`regex_baseline.detect`): cards, accounts, sort codes, IBAN, NI, postcodes, phones, emails. These spans are final: the model may add spans but never remove one.
3. **T1 through Mubit,** chunks in parallel (up to 6 at a time):
   - `gpt-6-luna` (or the bake-off winner), `response_format: json_object`, `max_completion_tokens` 8000;
   - parse `{"entities": [...]}`, then `spans.locate` finds every occurrence in the chunk.
4. **Merge** regex and model spans (longer wins). Then propagate every found value to the whole document: if "Patel" is found in chunk 2, hide it in chunk 5 too.
5. **Vault** (`redact.Vault`): one placeholder per distinct value per document, so `redacted_text` is consistent.
6. **Boxes:** for each span, the words whose character range overlaps it. Group them by line, so a value split over two lines gets two rectangles.

### 3.3 Redacted file
- **PDF:** `page.add_redact_annot(rect, fill=(0, 0, 0))` for each box, then `page.apply_redactions()`. This removes the text under the box; a drawn rectangle would not. Save as a new file.
- **Image:** Pillow `ImageDraw.rectangle(box, fill="black")`, save as PNG.
- **DOCX / EML / TXT:** return the redacted text as `.txt` (MVP). Rebuilding a `.docx` with replaced runs is a stretch goal.

### 3.4 Ask (T2)
- Prompt: "Answer the user's question about a redacted document. Values in square brackets such as [PERSON_1] stand for hidden values. Keep every placeholder exactly as written. Never guess hidden values."
- Send through Mubit with `x-middleware-record: off`, using Claude (`/anthropic`, `claude-haiku-4-5`) or GPT.
- `redact.restore()` puts the real values back. Unknown placeholders are flagged, never guessed.

### 3.5 Storage and safety
- In memory or SQLite under a temp folder; delete documents when the session ends. Never log document text.
- Mubit key only in the backend environment; the browser talks only to our backend (Mubit has no CORS anyway).
- CORS: allow the frontend dev origin only.

## 4. Frontend (one page)
- **Stack:** React + Vite + TypeScript + Tailwind; `pdf.js` to show PDF pages, or show server-rendered page PNGs (simpler: the backend returns page images and box coordinates). Overlay boxes with absolute-positioned divs.
- **States:** empty (drop zone + samples), scanning (per-chunk progress), result (two panels + chat + fixes), error (a clear message, plus "try a sample").
- Copy: plain, no em dashes. Claims: "personal details replaced before anything is sent", never "anonymised".

## 5. Build order (MVP first)
1. Backend: `/documents` (text + PDF text layer) → `/redact` (regex + T1) → `/file` (PDF redaction). Test with `data/synthetic/pdfs/*.pdf` and their `.gold.json`.
2. Frontend: drop zone → result view (left PDF page with boxes, right redacted text) → download.
3. `/ask` with restore.
4. Images via OCR (`ocrmac`), with boxes on the image.
5. Corrections UI with request ids and the console link.
6. Stretch: DOCX, EML, scanned PDFs, face and signature blur, the drop-in OpenAI-compatible proxy.

## 6. Demo script hook
Drop a tenancy agreement PDF:
1. 14 values are hidden in 4 seconds.
2. Download it: the names are gone from the file itself.
3. Ask "When can the landlord raise the rent?": the answer names the real landlord, but "show what was sent" proves Claude only saw `[PERSON_1]`.
4. Fix a missed client code. It joins the corrections queue, and the next version of the model catches it.
