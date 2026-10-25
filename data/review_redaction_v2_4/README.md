# Exact-text detector: current version v2.4

This fixes the model-generated offsets and Markdown response format in the
earlier review-redaction-v2.1 task. It is a separate task, with the same synthetic
inputs and train/fresh/eval assignments, not a new independent benchmark.
Old prompts, datasets and run outputs remain preserved. Intermediate v2.2/v2.3
fixtures and failed pilot results are historical, not the current interface.

## How it works

1. The teacher returns one `report_sensitive_text` tool block using a strict
   schema. The tool is a result container; no tool action is executed.
2. Both `document` and `question` arrays are required. An entry contains `text`,
   `type`, `entity_id`, `before`, and `after`; the model supplies no offsets.
3. Local code finds literal, case-sensitive quotations in the stated source.
   A unique exact quotation fixes the position. Context is used only when the
   quotation repeats: it must then identify exactly one occurrence. An incorrect
   unused hint on a unique quotation is reported as a diagnostic warning.
4. Local identities are scoped by `(type, entity_id)`. A name and email cannot
   share a placeholder because the model reused an owner's label. Names and
   aliases in document/question can still share their PERSON placeholder.
5. The existing redactor validates spans and preserves surrounding text. Missing
   quotations, ambiguous matches, overlapping spans and unsupported fields block
   the preview. No fuzzy matching, inferred aliases or blanket replacement occurs.
6. `TextReviewSession` retains the explicit human-confirmation gate. Input,
   extraction or destination edits invalidate approval, including failed edits.
   The outbound projection excludes originals, context hints and the vault.

The model may still omit sensitive data, misclassify text or group identities
incorrectly. Exact matching cannot prove completeness. Both sources require human
review; raw real data requires a verified trusted redactor without provider
fallback before detection. This is a training/reference pipeline, not a deployed
UI, authenticated server or persistent local vault.

## Results and limitations

The final five-case development pilot covers the reported Rose contact, payment
identifiers, a question-only input, hostile instructions and clean text. All five
API calls succeeded and returned structured tool blocks. The final local resolver
produces the gold redaction for all five original tool outputs, with an unused
context warning on the question-only case. No teacher response was modified.

See `data/results/review-redaction-v2.4-pilot5/verified-results.json` for the final
re-evaluation. `responses.jsonl` and `summary.json` preserve the initial resolver's
4/5 result. The corrected resolver only uses context to disambiguate repeats,
which resolves the fifth case without changing any quotation or replacing any
additional text. This was selected development traffic used to refine the prompt;
5/5 is not held-out performance or a production privacy guarantee.

One initial v2.2 call was recorded before the review-limit update; the five v2.3
and five v2.4 diagnostic calls sent `x-middleware-record: off`. These ten calls
do not provide training examples under Mubit's documented recording behavior.
No eval records were sent. No new adapter or kept-example count is verified.
The user's reported 230-call queue belongs to the old v2.1 task; a local fix does
not rewrite or remove those server-side examples.

The subsequent authorized recorded batch is in
`data/results/review-redaction-v2.4-train40/`: 40 new inputs, excluding all 230
prior source records and the five pilot cases. All 40 calls succeeded and passed
local format/span validation; 29 exactly matched the gold redacted text. Eleven
differences are listed in `needs-review.json` for review. These are training
diagnostics, not Mubit kept counts or held-out evaluation. Recording was enabled;
review capacity and adapter status still require console verification.

## Generate and test

```bash
python3.11 -B training/review_redaction/build_text_dataset.py
python3.11 -B -m pytest training/review_redaction/tests -q
```

Generation converts all 576 old records and checks that local resolution of each
gold extraction reproduces the old redacted answer. `expected_detection` remains
the gold offset key; `expected_extraction` is the new tool-answer key. Neither is
included in API requests. Eval exports retain recording off.

The sender defaults to the current exact-text task and requires a separate output
directory. Dry run a five-record training selection:

```bash
python3.11 -B training/review_redaction/send_review_batch.py \
  --task-version review-redaction-v2.4 --limit 5 --max-new 5 \
  --out-dir data/results/review-redaction-v2.4-next-check --no-record
```

Adding `--send` makes paid synthetic diagnostic calls, with recording disabled.
Record-off drops the task fingerprint, so this mode does not test adapter routing
or create a training task. A recorded training run requires a different output
directory without `--no-record`; do not alter recording policy within a frozen run.
Use `--exclude-run` for every earlier run of this task to avoid repeats, or explicit
`--record-id` arguments for a deliberate development regression. Never add eval
examples to training to satisfy a count.
Excluding an older version's run also checks `source_record_id`, so the same input
is excluded even when its ID changed with the contract version.

To create a reference preview:

```python
from text_detection import TextReviewSession, response_extraction

extraction = response_extraction(anthropic_message.model_dump(mode='json'))
session = TextReviewSession(original_bundle, extraction, 'anthropic')
preview = session.preview()
# Only a trusted human-review handler may approve this exact preview ID:
session.approve(preview['review_id'], confirmed=True)
approved_payload = session.outbound()
```

Do not call `approve()` automatically after detection or treat model text as a
human action. The code above illustrates the API, not a complete approval UI.

References: [Anthropic tool schemas](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools),
[Mubit recording headers](https://docs.mubit.ai/reference/api#request-headers-mubit-reads).
