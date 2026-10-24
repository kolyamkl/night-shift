# Product

<!-- impeccable:product-schema 1 -->

## Platform

Web. The React/Vite/TypeScript/Tailwind interface talks to a FastAPI backend,
with PostgreSQL storage and model requests through Mubit. The app is deployed
on Railway; macOS development additionally supports Apple Vision OCR.

## Users

People reviewing contracts, letters, bills and other documents who want control
over which personal values appear in the version they share with an answering
AI. This includes individuals and staff at firms handling client documents.

## Product purpose

MuGuard is a document redaction and review desk: detect sensitive values, inspect
and correct them, export a redacted file, and ask questions using placeholders.
The backend restores values in answers. Accounts keep saved documents, review
status and chat available after a reload.

The current implementation sends original chunks through Mubit for detection.
The answering model receives the redacted document and a filtered question.
Do not describe the app as preventing all original data from reaching providers,
end-to-end encrypted, fully anonymous, or compliant by default. See
[Data protection](docs/SECURITY.md) for the implemented boundary and open gaps.

## Positioning

The product combines UK identifier rules, model-assisted detection, human review,
PDF content removal and useful answers with values restored. Mubit provides
recorded task traffic, review, training and routing tools. Automatic learning
from in-app corrections is a future integration: current hide/unhide changes
update the saved document, not Mubit feedback or model weights.

## Terminology

- T1: detector; T2: answering model. Both requests go through Mubit.
- Placeholder: a token such as `[PERSON_1]`; the vault maps it to the hidden value.
- Pseudonymised: values are replaced but can be restored by the backend.
- Review status: saved UI workflow state, not a versioned consent audit trail.
- Model “on”: a key is configured; not proof that a trained adapter serves calls.

## Experience and constraints

Use invented people and identifiers in demos. Show the review step and the actual
redacted content, and label incomplete scans clearly. Keep the walkthrough under
three minutes. Follow [DESIGN.md](DESIGN.md) for the pixel castle visual system,
readable document typography and reduced-motion behavior. Public UI copy avoids
em dashes. The current product name remains MuGuard.

[Documentation index](docs/README.md) · [Architecture](docs/ARCHITECTURE.md)
