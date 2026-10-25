# MuGuard documentation

Start with the [project overview](../README.md), then follow the path that fits
what you need. These guides describe the code checked on **24 October 2026**;
live model routing and training status must be checked in Mubit.

| Question | Guide |
| --- | --- |
| What does the app do, and how do I run it? | [Project README](../README.md) |
| How does a document move through the system? | [Architecture and diagrams](ARCHITECTURE.md) |
| Where do we use Mubit, and how does training work? | [Mubit integration](MUBIT.md) |
| Who can see sensitive data, and what protection exists? | [Data protection and limits](SECURITY.md) |
| What is stored in PostgreSQL? | [Saved data](DATABASE-CONTENTS.md) |
| How do I configure storage, accounts and migrations? | [Database operations](DATABASE.md) |
| What are the endpoints, events and implementation details? | [Developer handoff](HANDOFF.md) |
| How is the app hosted? | [Railway deployment](DEPLOY.md) |
| What are the visual rules? | [Design system](../DESIGN.md) and [product context](../PRODUCT.md) |
| Where does the training data come from? | [Dataset guide](../data/README.md) |

## Component guides

- [Ingestion and OCR](../backend/app/ingest/README.md), [OCR evaluation](../scripts/ocr/README.md).
- [Training tooling overview](../training/README.md): [synthetic document generator](../training/datagen/README.md), [external dataset converters](../training/dataconv/README.md), [review-redaction datasets](../data/review_redaction_v2_4/README.md), [evaluation toolkit](../training/evalkit/README.md).
- Source builders: [contracts](../training/sources/contracts/README.md), [financial and insurance](../training/sources/financial_insurance/README.md), [correspondence templates](../data/templates/correspondence/README.md).

## Research and earlier plans

The [original app specification](APP-SPEC.md), [project brief](project-brief.md),
[team pack](NIGHT-SHIFT-TEAM-PACK.md) and [redesign notes](design/2026-10-24-redesign-notes.md)
record earlier requirements and decisions. They are not evidence that a feature
is shipped. The current guides above take precedence for implementation claims.

Research snapshots retain their dates and sources:

- [Mubit research](research/2026-10-23-mubit-audit/report.md).
- [PII datasets and experiments](research/2026-10-24-pii-dataset/README.md).
- [Market and privacy research](research/2026-10-24-veil-numbers/README.md).

## Repository layout

[Repository structure](architecture/repo-structure.md) explains where each folder
lives and why, with the moves made on 25 October 2026. Dated research notes keep
the paths of their day; the move table there maps old paths to new ones.

## Keeping these docs accurate

Update the relevant guide when changing a boundary: outbound model payloads,
recording, auth, approval, storage, deletion or training feedback. Link the code
that implements a claim. Label historical measurements with their dataset and
date; a unit-test count or a console label is not a privacy guarantee.

Diagrams use Mermaid and render on GitHub. Their adjacent prose and tables carry
the same explanation for readers whose Markdown viewer does not render Mermaid.
