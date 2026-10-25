# Veil: detect, hide, review, approve

**Historical v2.1 offset task.** Its teacher outputs failed validation. The current
exact-text detector is documented in [review_redaction_v2_4/README.md](../review_redaction_v2_4/README.md).
These original inputs, labels and prompts are retained for reproducibility.

A separate synthetic dataset for the user's requested workflow, covering **both
pasted chat questions and uploaded document text**. It does not replace the original
`data/docs/` dataset or change the existing T1 prompt. No API requests are made by
the generator. No trained model, web review screen or live sending integration is
included in this dataset.

## The new approach

1. A trusted redaction model identifies sensitive spans in the document **and**
   question. It returns JSON entities, not a rewritten document or an approval.
2. Local code validates each span against the original input, then inserts
   placeholders. Unrelated punctuation, amounts, dates and line breaks are preserved.
3. The application shows the original beside the combined redacted preview. The
   user can add missing redactions, correct unnecessary ones, or cancel.
4. The user explicitly confirms the exact current preview and destination.
5. Only the approved redacted document and question are eligible to leave for the
   answer provider. The original values and placeholder mapping stay local.

Suggested confirmation text: "I reviewed the document and question. Send only this
redacted preview to [provider]." The action starts unchecked. It is not a promise
that the model found every sensitive detail. Editing input, redactions or destination
requires a new confirmation; even clean text requires confirmation.

The reference implementation is in `training/review_redaction/contract.py`. It exposes
no network calls. A production application still needs an authenticated review UI,
server-owned session state, protected local storage with a retention policy, and a
transport that sends exactly the approved payload. Never take approval from model
JSON, document instructions or an untrusted request field. No raw attachment,
filename, conversation history, metadata, logging payload or vault may be silently
added to the outbound request.

## Privacy boundary before detection

User confirmation before the answer request cannot undo exposure during redaction.
Real input must reach only a local or verified trusted redactor with **no fallback
to OpenAI/Anthropic**. Mubit would remain a trusted processor if it hosts that model.
Confirm its routing guarantee before using real input; a Served by field inspected
afterwards is too late. For bootstrap teacher calls, use only these synthetic inputs.

`detector_payload()` illustrates the precondition. Its routing flags must come from
verified backend configuration, not a user or LLM claim. It does not itself discover
or enforce a remote routing configuration.

## Dataset contents

| Split | Examples | Clean examples | Purpose |
|---|---:|---:|---|
| `train.jsonl` | 288 | 24 | Initial task examples |
| `fresh.jsonl` | 144 | 12 | Development, later corrections and refresh traffic |
| `eval.jsonl` | 144 | 12 | Held-out comparison, never training or correction selection |

There are 12 scenario families, with a distinct template for each split: contacts,
payments, identity forms, email threads, account support, health notes, credentials,
custom references, question-only input, embedded hostile instructions, clean text,
and combined profiles. Train uses 24 fills per template; fresh/eval use 12 each.
This provides 36 distinct templates, not 576 independent writing styles. The count
does not guarantee Mubit will retain every example. Expand wording and real-world
format diversity before making broad performance claims.

The gold labels come from typed template slots and code, never from an LLM or copied
legacy results. No source documents were downloaded. Names and contact details are
fabricated, emails use `.test`, credentials are marked fake, IP addresses use a
documentation range, and financial identifiers are invented. Postcodes use a
deliberately fictional `ZZ` form; NI numbers use `QQ`. Some identifiers have valid
checksums for detector exercises, but these records are not real financial accounts.
This synthetic distribution does not establish production privacy or realistic UK
identifier coverage.

All 15 types occur in every split:

`PERSON`, `ADDRESS`, `POSTCODE`, `EMAIL`, `PHONE`, `BANK_ACCOUNT`, `SORT_CODE`,
`IBAN`, `CARD`, `NI_NUMBER`, `DOB`, `ID_DOC`, `CUSTOM`, `SECRET`, `HEALTH`.

Each split has at least 24 labelled occurrences of IBAN, CARD, NI_NUMBER and
SORT_CODE. Counts by type and template are in `manifest.json`.

The policy hides all email addresses, including role inboxes, employer contact
addresses, account/card suffixes, references in subjects and footers, and names
following c/o. Secrets include passwords, API tokens, PINs, CVVs and recovery codes.
Health spans cover personal conditions/treatments; generic health advice stays
visible. Common-word names are labelled only in person contexts. Company names,
amounts, ordinary dates and product names remain visible under the stated policy.
This is a defined policy, not a complete inventory of every possible sensitive fact.

## Record format

Each JSONL record contains:

- `id`, `task_version`, `split`, `scenario`, `template_id`, `synthetic`.
- `input`: exactly `document` and `question`, both strings.
- `expected_detection`: `entities`, each with `source`, `start`, `end`, `text`,
  `type`, `entity_id`.
- `expected_redacted`: the document and question after local replacement.
- `requires_user_confirmation: true`: a workflow expectation, never authorization.

Offsets are zero-based **Unicode code points**, end exclusive. They are not UTF-8
byte positions or JavaScript UTF-16 positions. `input[source][start:end]` must equal
`text`. Overlapping spans, invalid offsets, invented text, unexpected fields or
conflicting identity types block preview creation. An omitted entity cannot be
discovered by span validation alone, which is why review and evaluation remain needed.

Each identity receives a stable `[VEIL_TYPE_N]` placeholder across the document and
question. Multiple lines of one address repeat the same placeholder while preserving
their original line separators. Name aliases share a placeholder. Their original
surface forms remain in the local vault. This reference does not implement answer
restoration or resolve which alias should be restored in generated prose.

## Confirmation fixtures

`review_cases.jsonl` contains 13 application scenarios, separate from the model data:
pending review, explicit approval, unchecked confirmation, rejection, question edit,
document edit, provider change, stale confirmation, reconfirmation, invalid detector
output, model-supplied approval, and manual correction before/after confirmation.

The executable `ReviewSession` contract requires explicit confirmation of a
session-specific preview ID. Updating even one field invalidates approval. Invalid
edits clear the previous approved payload. Model JSON cannot set approval. The
outbound projection contains only destination, redacted document and redacted
question. The class assumes a trusted UI handler calls `approve()`; it is not an
authentication service or a complete deployed send guard.wh

## Generate and verify

From the repository root, using Python 3.11+:

```bash
python3.11 -B training/review_redaction/build.py
python3.11 -B -m pytest training/review_redaction/tests -q
```

Generation is deterministic. Use `--out-dir /tmp/veil-review-dataset` to generate a
separate copy. The generator validates offsets, gold replacements, template split
ownership, duplicate inputs, type coverage and confirmation cases before writing.
The tests also compare the checked-in examples and request exports with the generator.

## Mubit teacher batches

A dedicated sender is now available. It selects a balanced synthetic training
batch, freezes input/request hashes, journals attempts before dispatch, saves raw
responses and Mubit request IDs, and validates JSON and exact spans locally.
It never retries attempted calls automatically, including uncertain calls after
interruption. It sends no fresh or evaluation records. Default invocation is a
dry run; sending requires `--send` and a Mubit key in the environment or `.env`.

```bash
python3.11 -B training/review_redaction/send_review_batch.py --task-version review-redaction-v2.1 --limit 40
```

Results are separate in `data/results/review-redaction-v2.1-40/`. Local validation
does not control Mubit's kept-example count or remove bad teacher answers from
its training data. API success is not evidence that an adapter has trained.

For reproducing an old batch, explicitly select `--task-version review-redaction-v2.1`.
For an additional batch, use a new `--out-dir` and pass `--exclude-run` for every
previous run directory. This excludes all attempted IDs, including uncertain
calls after interruption. For example, the second batch uses
`--exclude-run data/results/review-redaction-v2.1-40` and
`--out-dir data/results/review-redaction-v2.1-batch02-40`. Run without `--send`
first to inspect the selection. Keep the same exclusion arguments when resuming.

The candidate prompt is `system_prompt.txt`, generated from
`training/review_redaction/prompt.py`, task version `review-redaction-v2.1`. This is a
new task. Do not silently replace the original prompt or combine its scores with
the earlier plain-text rewriting pilot.

`teacher_requests/<split>.jsonl` exports input-only Anthropic request bodies, plus
separate transport headers. The candidate teacher is `claude-haiku-4-5` through
Mubit. Each request has a synthetic input and its own session ID. The generated
answer keys are deliberately excluded from requests. Mubit would record the
teacher's actual response, not automatically train on the gold answers here.

These exports are **not** directly compatible with the old chunk sender. The new
sender constructs the same request envelopes, parses the teacher's JSON, runs span
validation, saves the raw response/request ID/version and scores valid outputs
against the key. Failed validation counts as a failure. Do not relabel malformed
teacher output as correct. Reserve a mixed pilot and review its errors before bulk
sending. Exact offset generation is a hypothesis to test, not proven model behavior.

Eval exports retain `x-middleware-record: off`. Verify supported adapter evaluation
and recording behavior with Mubit before use. Never turn recording on for held-out
eval just to make it work. Verify correction ingestion separately. Dataset
generation itself never invokes the sender or API traffic.
