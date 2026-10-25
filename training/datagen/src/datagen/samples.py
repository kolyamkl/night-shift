"""Write a small committed-safe sample (fake data only): 20 documents and 40 chunks.

    uv run python -m datagen.samples --data ../../data/synthetic --out samples
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def write_samples(data: Path, out: Path, seed: int = 42, n_docs: int = 20, n_chunks: int = 40) -> None:
    rng = random.Random(f"{seed}:samples")
    out.mkdir(parents=True, exist_ok=True)
    by_type: dict[str, list[dict]] = {}
    neg: list[dict] = []
    with open(data / "docs.jsonl", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 20000:
                break
            d = json.loads(line)
            if d["meta"]["negative"]:
                if len(neg) < 50:
                    neg.append(d)
            elif len(d["text"]) < 7000:
                by_type.setdefault(d["doc_type"], []).append(d)
    docs = [rng.choice(v) for _, v in sorted(by_type.items())][: n_docs - 2] + rng.sample(neg, 2)
    with open(out / "docs_sample.jsonl", "w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    # chunks: the 3 longest sampled-type documents' chunks (multi-chunk) + round-1 chunks
    chunks = []
    with open(data / "mubit_round1.jsonl", encoding="utf-8") as f:
        pool = [json.loads(x) for x in f]
    multi = [c for c in pool if c["meta"]["n_chunks"] > 1][:6]
    rest = rng.sample([c for c in pool if c["meta"]["n_chunks"] == 1], n_chunks - len(multi))
    chunks = multi + rest
    with open(out / "chunks_sample.jsonl", "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, default=Path("../../data/synthetic"))
    ap.add_argument("--out", type=Path, default=Path("samples"))
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args(argv)
    write_samples(a.data, a.out, a.seed)
    print(f"wrote {a.out}/docs_sample.jsonl and {a.out}/chunks_sample.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
