"""Download only the data files we need from HF dataset repos at pinned revisions."""
import json
from pathlib import Path

from huggingface_hub import snapshot_download

RAW = Path(__file__).resolve().parents[3] / "data" / "external" / "raw"
JOBS = {
    "nvidia/Nemotron-PII": ("b70ffaf5ff39e079776134c5bf4381f00a9fd1ed", ["data/*.parquet", "README.md"]),
    "gretelai/synthetic_pii_finance_multilingual": ("7b844d16738527a04264f50214cb426a4cea0897",
        ["data/English_train-*.parquet", "data/English_test-*.parquet", "README.md"]),
    "gretelai/gretel-pii-masking-en-v1": ("e06eb1499ca8d54470f085021cd8e54f9efac7fd", ["data/*.parquet", "README.md"]),
    "QuantumAiuk/uk-pii-redaction-synthetic": ("750398a543653ca8d26b0765430c563d8f52b1c0", ["*.jsonl", "README.md"]),
    "bitext/Bitext-retail-banking-llm-chatbot-training-dataset": ("3e3621092fc6baaf7f53ceb6f091c60ae99acb67", ["*.parquet", "README.md"]),
    "bitext/Bitext-customer-support-llm-chatbot-training-dataset": ("430d1a89bd93bd1fa23c16f29dd53e73f0087443", ["*.csv", "README.md"]),
    "RedactionBench/RedactionBench": ("d45e9cec89bc49c69355e252fec29cc0229982f6", ["data/*.parquet", "croissant.json", "README.md"]),
    "perplexity-ai/PII-TRACE": ("1c3eb67bbd43e8571b4433a9d3d76271f9970eb9", ["data/*.parquet", "LICENSE", "README.md"]),
}
for rid, (rev, pats) in JOBS.items():
    d = RAW / rid.replace("/", "__")
    d.mkdir(parents=True, exist_ok=True)
    p = snapshot_download(rid, repo_type="dataset", revision=rev, allow_patterns=pats, local_dir=d)
    files = sorted(str(f.relative_to(d)) for f in d.rglob("*") if f.is_file() and ".cache" not in f.parts)
    (d / "download_manifest.json").write_text(json.dumps({"repo": rid, "revision": rev, "allow_patterns": pats, "files": files}, indent=1))
    print(rid, files, flush=True)
