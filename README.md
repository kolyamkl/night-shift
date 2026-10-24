# Veil

**Review sensitive information before sharing a document with an answering AI.**

Veil finds personal values in documents, lets you correct the redactions, and
replaces those values with placeholders for document Q&A. It restores names and
other values in the answer so the result remains useful to you. Built for the
Mubit Night Shift hackathon in London, 23–25 October 2026.

[Open the app](https://web-production-dc019.up.railway.app/app) ·
[Documentation](docs/README.md) · [Architecture](docs/ARCHITECTURE.md) ·
[Mubit integration](docs/MUBIT.md) · [Data protection](docs/SECURITY.md)

> **Current privacy boundary:** detection sends original document chunks through
> Mubit, with recording enabled by default. Q&A receives the redacted document
> and a filtered question. Veil does not yet guarantee that original personal
> data never reaches an external AI provider. Use synthetic documents for demos;
> see [implemented protections and limits](docs/SECURITY.md).

## How it works

### End-to-end pipeline

```mermaid
flowchart TD
    subgraph BR["Browser: React app"]
        U1["Sign in"] --> U2["Upload PDF or file, paste text, or pick a sample"]
        U5["Review: hide misses, unhide false positives"]
        U6["Approve"]
        U7["Ask a question"]
        U8["Read restored answer and What it sees"]
        U9["Download redacted PDF or text"]
    end

    subgraph RW["Railway"]
        C["Caddy web service: SPA and /api proxy"]
        subgraph BE["FastAPI backend, private network only"]
            X["Extract text and word boxes (PyMuPDF; Apple Vision OCR on macOS)"]
            RX["Rules: UK identifiers, references, contacts"]
            CH["Split into chunks of up to 1,400 chars, 6 in parallel"]
            AL["Align T1 rewrite back to original values"]
            MG["Locate values in whole document, merge spans, widen addresses"]
            VB["Vault: value to placeholder, redacted text, PDF boxes"]
            CO["Corrections: rebuild without a model call"]
            QP["Pseudonymise question with vault and rules"]
            RS["Restore values in answer, plain text"]
            PO["True redaction: remove text and pixels, strip metadata"]
        end
        DB[("PostgreSQL: Fernet-encrypted documents, results, vaults, chat")]
    end

    subgraph MB["Mubit gateway"]
        T1["T1 detect: recorded"]
        T2["T2 answer: record off"]
    end

    U2 -->|"HTTPS"| C --> X
    X --> DB
    X --> RX & CH
    CH -->|"original chunk"| T1
    T1 -->|"chunk with placeholders + mreq ID"| AL
    RX --> MG
    AL --> MG --> VB --> DB
    VB -->|"SSE progress per chunk"| U5
    U5 --> CO --> VB
    U5 --> U6 --> U7 -->|"question"| QP
    QP -->|"redacted document + redacted question"| T2
    T2 -->|"answer with placeholders"| RS --> DB
    RS --> U8
    U5 --> U9 <-->|"redacted file"| PO
```

1. **Ingest.** The browser sends the document to Caddy, which forwards `/api`
   to the private backend. The backend extracts text and word positions and saves
   the source encrypted.
2. **Detect, two ways at once.** Deterministic rules find structured values
   (emails, phones, postcodes, sort codes, account numbers, IBANs, cards, NI,
   passport, licence and NHS numbers, IP addresses and labelled references).
   In parallel the text is split into chunks, and each chunk goes to **T1**
   through Mubit, which returns it rewritten with placeholders. Veil aligns that
   rewrite back to the original to recover the exact values.
3. **Build.** Every value found anywhere is located throughout the document,
   overlaps are merged, and each distinct value gets a stable placeholder in the
   vault (`Raj Patel` → `[PERSON_1]`). Progress streams to the browser chunk by chunk.
4. **Review.** Hiding or unhiding a value rebuilds the result locally, with no
   model call, and the correction survives rescans.
5. **Ask.** After approval, the question is pseudonymised with the same vault,
   then **T2** receives only the redacted document and redacted question. The
   backend swaps placeholders back to real values before the answer is shown.
6. **Download.** The PDF is truly redacted: covered text and image pixels are
   removed from the file and hidden metadata is stripped. It is not a black box
   drawn on top.

Illustrative transformation:

| Stage | Text |
| --- | --- |
| Original | `Tenant: Raj Patel. Rent: £950.` |
| Redacted document | `Tenant: [PERSON_1]. Rent: £950.` |
| Question sent to T2 | `What does [PERSON_1] pay?` |
| Answer shown to the user | `Raj Patel pays £950.` |

The vault stays on the backend and is encrypted in storage. This is reversible
pseudonymisation, not a guarantee of anonymity or perfect detection.

## Mubit and data protection

### How Mubit works in Veil

Mubit sits between Veil and the model providers. Veil uses the normal Anthropic
request format but points it at `https://api.mubit.ai/anthropic` with a Mubit
key (`mbt_…`). Mubit routes each call to a provider model or to a task adapter
it has trained, records the call if recording is on, and returns a request ID
(`x-middleware-request-id`, an `mreq_…` value) that Veil stores with each chunk.

```mermaid
sequenceDiagram
    participant API as Veil backend
    participant M as Mubit gateway
    participant P as Provider model or trained adapter
    participant C as Mubit console

    Note over API,M: T1: find personal data (one call per chunk)
    API->>M: Fixed T1 instructions + original chunk, session doc-ID, recording on (default)
    M->>P: Route to the task's active model or adapter
    P-->>M: Chunk rewritten with placeholders
    M->>C: Record request and reply in task "Redact personal data"
    M-->>API: Reply + mreq_ request ID

    Note over API,M: T2: answer a question
    API->>M: Redacted document + pseudonymised question, x-middleware-record: off
    M->>P: claude-haiku-4-5
    P-->>M: Answer using placeholders
    M-->>API: Answer + request ID (record off was requested)
```

Recorded T1 calls feed Mubit's training loop. Each call with the same fixed
instructions and model lands in the same **task**, so the task collects many
real examples of the one job Veil needs done:

```mermaid
flowchart LR
    A["T1 calls from the app"] --> R["Recorded in the Mubit task"]
    D["Synthetic labelled dataset: scripts/dataset/send_batch.py --send"] --> R
    R --> V["Review in console: keep or reject"]
    V --> T["Train a task adapter on kept examples"]
    T --> E["Evaluate against held-out sessions"]
    E --> RT["Roll out: route T1 traffic to the adapter"]
    RT -->|"later T1 calls served by the adapter"| A
    H["Hide or unhide in Veil"] -.->|"saved locally only; review its mreq_ in the console manually"| V
```

**T1 detects; T2 answers.** Both use Mubit. The default T1 request asks
`claude-haiku-4-5` to rewrite a chunk with placeholders; Veil aligns that answer
back to the original text and combines it with deterministic rules. T2 receives
the redacted result and a pseudonymised question with recording off requested.
Model routing and adapter rollout are configured in Mubit, not proven by the
model name displayed in the app.

Recorded T1 calls can become reviewed training examples. **In-app corrections
are not automatically sent as Mubit training feedback.** See the
[Mubit guide](docs/MUBIT.md) for task/session grouping, dataset paths, review,
training, evaluation and routing.

Accounts isolate documents; Argon2id protects passwords; server-side sessions
use HttpOnly cookies; Fernet encrypts document content, vaults and chat at rest.
The backend can decrypt this data. Approval is saved but is currently enforced
by the UI rather than the `/ask` endpoint. Question filtering can miss unfamiliar
free-form values. Read the [security guide](docs/SECURITY.md) before making
privacy claims about a deployment.

## Run locally

Prerequisites: Python 3.12 or 3.13, uv, Node compatible with the frontend lockfile,
and PostgreSQL 16+ binaries on PATH. All setup commands below start at the
repository root. See [database setup](docs/DATABASE.md) for details.

```sh
# First setup only: preserve an existing .env rather than replacing it.
test -f .env || cp .env.example .env
# Edit .env to set MUBIT_API_KEY if model calls are wanted.
python3 scripts/local_db.py start
```

Backend, in one terminal:

```sh
cd backend
uv sync --frozen
uv run --env-file ../.env uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend, in another terminal:

```sh
npm --prefix frontend ci
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173
```

Open <http://127.0.0.1:5173/app>. Without a Mubit key, rule-based detection still
works and Q&A is unavailable. Photos, scans and mixed PDFs needing OCR require
Apple Vision on macOS; that path is unavailable on the Linux Railway deployment.

## Verify changes

Run each command from the repository root:

```sh
(cd backend && uv run --env-file ../.env pytest -q)
(cd backend && uv run --with reportlab python -m pytest -q ../tests/ingest)
(cd evalkit && uv run pytest -q)
npm --prefix frontend test
npm --prefix frontend run build
```

Backend integration tests need a separate `TEST_DATABASE_URL`, created by the
local setup script. Without it, those tests skip; do not interpret skips as a
passed database check. Model calls are mocked in backend tests. Dataset checks
and generation commands are in the [dataset guide](data/README.md).

## Explore the project

- [Architecture](docs/ARCHITECTURE.md): system, document and Q&A diagrams.
- [Mubit](docs/MUBIT.md): inference, sessions, training and verification.
- [Data protection](docs/SECURITY.md): trust boundaries, controls and gaps.
- [Saved data](docs/DATABASE-CONTENTS.md) and [database operations](docs/DATABASE.md).
- [Developer handoff](docs/HANDOFF.md), [deployment](docs/DEPLOY.md), [design system](DESIGN.md).
- [All documentation](docs/README.md), including datasets and historical research.
