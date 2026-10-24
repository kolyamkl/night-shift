# dataconv

Converts open PII datasets into the Veil canonical document format (see
[format context](../docs/research/2026-10-24-pii-dataset/work/CONTEXT.md)). Report: [external datasets](../docs/research/2026-10-24-pii-dataset/work/external-datasets.md).

[Documentation index](../docs/README.md) · [Mubit workflow](../docs/MUBIT.md)

Run from this package directory. Conversion does not authorize sending real
personal data or restricted datasets to Mubit. Keep `eval_local_only.jsonl`
local and review provenance/licences before using any converted records.

**Portability prerequisite:** this older tool still has machine-specific path
constants in [common.py](src/dataconv/common.py), [dl_hf.py](scripts/dl_hf.py)
and [dl_openpii.py](scripts/dl_openpii.py). Point `ROOT`, `RAW` and `OUT` at your
checkout before running the download/build commands below. Changing directory
alone does not override those constants.

```bash
cd dataconv  # from the repository root
uv sync
uv run python scripts/dl_hf.py        # pinned HF shards -> data/external/raw/<dataset>/
uv run python scripts/dl_openpii.py   # English byte ranges of ai4privacy openpii-1m (file sorted by language/region)
# TAB: echr_{train,dev,test}.json, LICENSE.txt from github.com/NorskRegnesentral/text-anonymization-benchmark
#      at commit 558e09e26d6b36f5f78440074e6a233946d98bd9 -> data/external/raw/NorskRegnesentral__text-anonymization-benchmark/
uv run dataconv build                 # per dataset: data/external/<dataset>/{docs,chunks}.jsonl + stats.json
uv run dataconv combine               # pool_mubit_ok.jsonl, eval_local_only.jsonl, uk_eval.jsonl
uv run pytest
```

Downloads are read as data only (parquet / JSON / CSV, `ast.literal_eval` for Python-literal span strings);
no code from the downloaded repos is imported or run.
