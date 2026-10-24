# evalkit

Small toolkit for Veil's redaction task T1: the frozen prompt, placeholder redaction and restore, a regex baseline, scoring, the Mubit round builder and the Mubit batch sender.

[Documentation index](../docs/README.md) · [Current Mubit integration](../docs/MUBIT.md)

The app imports the vault, matching and regex helpers from this package. Its
optional `VEIL_T1_PROMPT=evalkit` mode uses the JSON-list prompt here; the default
app detector uses the rewrite prompt in `backend/app/llm/prompts.py`. These can be
different Mubit tasks. Do not assume a successful historical evalkit training
run is the adapter serving the current rewrite task.

```bash
cd evalkit  # from the repository root
uv sync
uv run pytest -q            # toolkit tests
```

| Module | What it does |
|---|---|
| `prompts.py` | **Frozen** T1 system prompt (`PROMPT_VERSION = 1`) and the 13 types. Changing the prompt creates a new Mubit task. |
| `spans.py` | Finds every occurrence of a predicted value in the text (whitespace- and comma-flexible, word-bounded). |
| `redact.py` | `Vault`, `apply()` for consistent `[PERSON_1]` placeholders, `restore()` with tolerant matching and unknown-placeholder reporting. |
| `uk_formats.py` | Tested UK regexes and validators (copied from `docs/research/2026-10-24-pii-dataset/work/uk-formats.md`). |
| `regex_baseline.py`, `baseline.py` | Baseline 1: regex + validators + context words. |
| `score.py` | Leaks per 100 documents, zero-leak documents, per-type recall (hidden / strict / partial), precision, over-redaction, keep-trap hits. |
| `build_rounds.py` | Builds `data/rounds/` from `data/synthetic/` and `data/external/`. |
| `send_batch.py` | Sends chunks through Mubit (GPT, Claude or Gemini; `--design list` or `--design rewrite`). **Dry run unless `--live`.** Records marked `mubit_ok: false` are refused; provenance still needs review. Resume-safe. |
| `providers.py`, `rewrite.py` | One call per provider route on the starter credit; spans recovered from rewrite answers. |
| `team_docs.py`, `bakeoff.py` | Teammates' documents in our format; compare designs x teachers with `--record off` (recording disabled in the request). |
| `mistakes.py` | Lists wrong replies with their `mreq_` id and the corrected JSON, ready to paste in the Mubit console. |

## Typical commands

```bash
# 1. Build round files (already built once; rerun after regenerating data)
uv run python -m evalkit.build_rounds --data ../data

# 2. Dry run: counts, doc types, cost estimate, first request
uv run python -m evalkit.send_batch --chunks ../data/rounds/r1_core.jsonl --out runs/r1_core.jsonl

# 3. Teacher pilot (real inference, recording off requested), once per candidate model
export MUBIT_API_KEY=mbt_...   # never commit it
uv run python -m evalkit.send_batch --chunks ../data/rounds/r0_pilot.jsonl --out runs/pilot_luna.jsonl \
  --model gpt-6-luna --record off --live
uv run python -m evalkit.score --gold ../data/rounds/r0_pilot.jsonl --pred runs/pilot_luna.jsonl --name "pilot gpt-6-luna"

# 4. Training traffic (recorded): round 1
uv run python -m evalkit.send_batch --chunks ../data/rounds/r1_core.jsonl --out runs/r1_core.jsonl --model <chosen> --live

# 5. Baseline numbers
uv run python -m evalkit.baseline --gold ../data/rounds/eval_synthetic.jsonl --out runs/regex_eval.jsonl
uv run python -m evalkit.score --gold ../data/rounds/eval_synthetic.jsonl --pred runs/regex_eval.jsonl --name regex
```

Notes:
- `send_batch` does not send `temperature` unless you pass `--temperature` (some models reject it).
- Each result line has the Mubit request id (`mreq_...`): use it to find the call in the console and to link corrections.
- Never send `data/external/eval_local_only.jsonl` (real people). `send_batch` refuses records marked `mubit_ok: false`.
