# How MuGuard works

[Documentation index](README.md) · [Mubit](MUBIT.md) · [Data protection](SECURITY.md)

MuGuard has a React browser interface, a FastAPI backend and PostgreSQL storage.
The backend extracts document text, finds sensitive values, builds a redacted
copy and keeps the mapping needed to restore values in answers. Mubit is the
gateway for both detection (**T1**) and document questions (**T2**).

## System and trust boundaries

```mermaid
%%{init: {"theme": "base", "themeVariables": {"fontFamily": "ui-monospace, SFMono-Regular, Menlo, monospace", "primaryColor": "#f8f7f3", "primaryTextColor": "#0d0d0d", "primaryBorderColor": "#0d0d0d", "lineColor": "#8b8a85", "clusterBkg": "#ecebe5", "clusterBorder": "#0d0d0d", "edgeLabelBackground": "#ecebe5"}}}%%
flowchart LR
    U["User's browser"] -->|"HTTPS: upload, review, question"| W["Web: React and Caddy"]
    subgraph V["MuGuard deployment on Railway"]
        W -->|"Private network: API requests"| B["FastAPI backend"]
        B <-->|"Encrypted content; account metadata"| D[("PostgreSQL")]
        K["Server encryption key"] --> B
    end
    B -->|"T1: original text chunks"| M["Mubit gateway"]
    B -->|"T2: redacted document and question"| M
    M <-->|"Inference and configured routing"| P["Provider model or task adapter"]
    M -->|"Reply and request ID"| B
    B -->|"Review result, restored answer, download"| W
    W --> U
    classDef mubit fill:#e2231a,stroke:#0d0d0d,color:#ffffff
    classDef ink fill:#0d0d0d,stroke:#0d0d0d,color:#ecebe5
    class M mubit
    class P ink
```

The browser connects to the public web service. Caddy forwards API requests to
the private backend, which owns the database credentials and Mubit key. Original
content exists in the browser and backend memory. At rest, document content is
encrypted before PostgreSQL receives it. **T1 still receives original text**;
this is not browser-only or end-to-end encrypted processing.

## A document from upload to download

```mermaid
%%{init: {"theme": "base", "themeVariables": {"fontFamily": "ui-monospace, SFMono-Regular, Menlo, monospace", "primaryColor": "#f8f7f3", "primaryTextColor": "#0d0d0d", "primaryBorderColor": "#0d0d0d", "lineColor": "#8b8a85", "clusterBkg": "#ecebe5", "clusterBorder": "#0d0d0d", "edgeLabelBackground": "#ecebe5"}}}%%
flowchart TD
    A["Upload, paste or open a synthetic sample"] --> B["Authenticate owner and extract text"]
    B --> C["Save encrypted source, text and layout"]
    C --> R["Regex: structured identifiers and references"]
    C --> T["T1 through Mubit: detect values in original chunks"]
    R --> H["Locate values throughout the document; merge spans; expand addresses"]
    T --> H
    H --> V["Build placeholder vault, redacted text and PDF boxes"]
    V --> S["Save encrypted result and stream completion"]
    S --> E["Human reviews, hides misses or unhides false positives"]
    E -->|"Save corrections without a model call"| V
    E -->|"Download"| F["Remove covered PDF content or export redacted text"]
    E -->|"Approve in UI"| Q["Open document Q&A"]
    classDef mubit fill:#e2231a,stroke:#0d0d0d,color:#ffffff
    class T mubit
```

1. **Extract.** Text-layer PDFs use PyMuPDF text and word coordinates. Text,
   email and supported source/config files become plain text. Images and scanned
   PDFs use Apple Vision OCR when running on macOS. Railway runs Linux, where
   this OCR path is unavailable, including for mixed PDFs needing OCR.
2. **Detect.** The default rewrite task processes chunks of at most 1,400
   characters, with up to six concurrent workers. T1's placeholder rewrite is
   aligned back to the original text; the app does not trust it to replace the
   contract's wording. Regexes independently find structured values. This regex
   pass does not sanitize the chunks sent to T1.
3. **Build.** Values found in one chunk are located across the whole document.
   Overlaps are merged; address rules widen incomplete address spans. A vault
   assigns stable placeholders to matching values within this result. This is
   value matching, not a general identity-resolution system.
4. **Review.** A hide/unhide correction rebuilds the result without calling T1.
   Full rescans and failed-part retries preserve those choices. Removing a
   redaction deliberately makes that value available to subsequent Q&A.
5. **Export.** PDF word boxes become actual redaction annotations, applied to
   remove covered text and image pixels. Selected metadata is stripped too.
   Undetected values outside those boxes remain in the output.

## Questions and answers

```mermaid
%%{init: {"theme": "base", "themeVariables": {"fontFamily": "ui-monospace, SFMono-Regular, Menlo, monospace", "primaryColor": "#f8f7f3", "primaryTextColor": "#0d0d0d", "primaryBorderColor": "#0d0d0d", "lineColor": "#8b8a85", "actorBkg": "#f8f7f3", "actorBorder": "#0d0d0d", "actorTextColor": "#0d0d0d", "actorLineColor": "#8b8a85", "signalColor": "#8b8a85", "signalTextColor": "#0d0d0d", "noteBkgColor": "#0d0d0d", "noteTextColor": "#ff6b61", "noteBorderColor": "#0d0d0d", "activationBkgColor": "#e2231a"}}}%%
sequenceDiagram
    actor User
    participant UI as Browser
    participant API as MuGuard backend
    participant DB as PostgreSQL
    participant M as Mubit and answering model
    User->>UI: Approve review, then ask a question
    UI->>API: Save status, submit question with session cookie
    API->>DB: Load owner's saved redaction and vault
    DB-->>API: Encrypted snapshot
    Note over API: Decrypt, copy vault, replace known values and regex matches in question
    API->>M: Redacted document + redacted question, record off
    M-->>API: Answer containing placeholders
    Note over API: Restore values with copied vault, normalize answer to plain text
    API->>DB: Save encrypted question and answer turn
    API-->>UI: Restored answer, sent question, request ID
    UI-->>User: Answer and What it sees
```

For example, an illustrative document `Tenant: Raj Patel. Rent: £950.` becomes
`Tenant: [PERSON_1]. Rent: £950.`. The question `What does Raj Patel pay?` becomes
`What does [PERSON_1] pay?`. A reply mentioning `[PERSON_1]` is restored on the
**backend**, then returned to the signed-in browser. The vault is not included
in the T2 request. New free-form names or addresses in questions can still be
missed: question protection uses known values and rules, not another T1 scan.

Approval is saved, and `/ask` answers only when the status is `approved` (409
otherwise). Approval is not bound to a result revision: a correction or rescan
after approval keeps it, and Approve all works while some parts were not checked.

## Streaming, retries and persistence

The POST stream emits `start`, `regex`, one `chunk` event per completed part,
then `done` after saving the final result. Parts can finish out of order. Chunk
errors remain visible and are not interpreted as proof that a part is safe.

`?retry=failed` reuses successful and empty chunks only when the saved prompt
plan and chunk boundaries match. A full rescan calls T1 again; both paths retain
manual corrections. A revision check prevents an older scan from overwriting a
newer scan or correction. There is no database transaction held during inference.

Documents, latest results, review status and chat turns survive refreshes and
backend restarts. The sidebar lists the owner's saved documents; a deep link
`/app?doc=<id>` reopens one. Approval status is retained across a rescan, so it
does not attest that a person reviewed every later version of the result.

## Code map

![The backend in four layers: entry, feature modules, domain packages and core](readme/backend.svg)

The backend is split into layers: routers speak HTTP, services hold the rules,
repositories hold the SQL, and the domain packages never import FastAPI. The
[backend architecture](../backend/docs/architecture.md) page explains why.

| Responsibility | Implementation |
| --- | --- |
| App setup and middleware | [main.py](../backend/app/main.py), [core/](../backend/app/core/) |
| API routes and ownership | [api.py](../backend/app/api.py), [modules/](../backend/app/modules/) |
| Scan, supersession and stream | [scan/service.py](../backend/app/modules/scan/service.py), [scan/stream.py](../backend/app/modules/scan/stream.py) |
| Chunking, merging, corrections and PDF boxes | [redaction/pipeline.py](../backend/app/redaction/pipeline.py) |
| Mubit requests and rewrite alignment | [llm/t1.py](../backend/app/llm/t1.py), [llm/t2.py](../backend/app/llm/t2.py), [llm/providers.py](../backend/app/llm/providers.py), [llm/rewrite.py](../backend/app/llm/rewrite.py), [llm/prompts.py](../backend/app/llm/prompts.py) |
| Question protection | [redaction/question.py](../backend/app/redaction/question.py) |
| PDF export | [redaction/pdf.py](../backend/app/redaction/pdf.py) |
| Encryption, revisions and saved chat | [documents/repository.py](../backend/app/modules/documents/repository.py) |
| Account and session checks | [modules/auth/](../backend/app/modules/auth/) |
| Browser state and streamed results | [App.tsx](../frontend/src/App.tsx), [scan.ts](../frontend/src/scan.ts) |

See the [developer handoff](HANDOFF.md) for full API and OCR details.
