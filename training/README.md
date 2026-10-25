# Training tooling

Everything that builds, sends and scores data for MuGuard's redaction model (Mubit
task T1). None of it runs inside the app. The datasets themselves live in
[`data/`](../data/README.md); the app lives in `backend/` and `frontend/`.

Three approaches were tried during the hackathon. Each keeps its code, tests and
README together, so it can be run or read on its own.

| Approach | Owner | Code | Data | Result |
| --- | --- | --- | --- | --- |
| **Rewrite**: the model returns the chunk with `[TYPE_N]` placeholders | Mykola | [`sources/`](sources/) builds the documents; [`rewrite/`](rewrite/) validates, chunks, sends and scores | `data/docs`, `data/templates`, `data/sources`, `data/fixtures`, `data/results/train.jsonl` | Adapter v1 on Qwen3-4B-Instruct-2507: **91.7%** on the held-out test, against 66.7% for the base model (24 Oct). The app's default T1 prompt |
| **List output**: the model returns a JSON list of entities | Dmytro | [`datagen/`](datagen/README.md) generates UK documents with gold spans; [`dataconv/`](dataconv/README.md) converts open PII datasets; [`evalkit/`](evalkit/README.md) holds the prompt, scorer and sender | the app's samples in `backend/samples` (committed); the 100k run and `data/external` stay local | Optional T1 prompt (`VEIL_T1_PROMPT=evalkit`); teacher bake-off in the [dataset research](../docs/research/2026-10-24-pii-dataset/BAKEOFF.md) |
| **Review redaction**: exact-text detection with a human approval step, as a separate task | Glib | [`review_redaction/`](review_redaction/) builds datasets v2.1 to v2.4 and sends frozen batches | `data/review_redaction_v2*`, `data/results/review-redaction-*` | v2.4 current; 29 of 40 training replies matched the gold redaction exactly (diagnostics, not a held-out score) |

The backend imports nothing from here. One test, `backend/tests/llm/test_t1.py`, loads
`rewrite/send_batch.py` by path to check that the app sends the same request. The sample PDFs
that `datagen.pdf` and `scripts/samples/make_tenancy.py` write live in `backend/samples/`,
because the backend serves them.

## Run

From the repository root. `make test-training` runs the pytest suites below; the
source checks run by hand.

```sh
# Rewrite approach: source checks (each builder pins its own requirements.txt),
# then the dataset pipeline (see data/README.md)
pip install -r training/sources/contracts/requirements.txt \
            -r training/sources/correspondence/requirements.txt \
            -r training/sources/financial_insurance/requirements.txt
python training/sources/contracts/build.py --check-only
python training/sources/correspondence/build.py --check
bash training/sources/financial_insurance/tests/run.sh
pip install -r requirements.txt
python training/rewrite/validate_docs.py
python -m pytest -q training/rewrite/tests

# List-output approach: uv projects, run inside their folders
(cd training/datagen && uv run pytest -q)
(cd training/dataconv && uv run pytest -q)
(cd training/evalkit && uv run pytest -q)

# Review redaction
python training/review_redaction/build_text_dataset.py
python -m pytest -q training/review_redaction/tests
```

Commands that call Mubit (`send_batch.py --send`, `send_review_batch.py`) need
`MUBIT_API_KEY` in `.env` and spend credit; each one is a dry run unless told
otherwise. Read the [Mubit guide](../docs/MUBIT.md) before sending.
