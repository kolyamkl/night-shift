"""Build the Mubit round files from the synthetic set and the external Mubit-OK pool.

Only the INPUTS of training traffic matter to Mubit: it trains on the teacher's answers, not on our
gold labels. So external data is here for input variety (formats, document kinds, non-UK forms),
and its gold labels are used only for scoring.

Writes to data/rounds/ (gitignored):
  r0_pilot.jsonl       50 eval chunks, every type covered: pick the teacher (send with --record off)
  r1_core.jsonl        500 chunks: 400 synthetic train (20 per doc type) + 100 external train
  r1_extra.jsonl       up to 1,500 more synthetic train chunks, only if Mubit wants more examples
  r2_fresh.jsonl       500 chunks: 400 synthetic fresh + 100 external (new documents)
  r3_reserve.jsonl     500 chunks for the Sunday 01:00 reset
  corrections.jsonl    200 chunks rich in hard cases and CUSTOM ids (correction demo)
  eval_synthetic.jsonl synthetic eval chunks (+ a supplement so full card numbers are covered)
  eval_uk_external.jsonl QuantumAiuk UK test and wild sets (synthetic, Apache-2.0)
Every training file holds one chunk per document, and no document appears in two files.
"""

import argparse
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

EXTERNAL_MIX = [  # (directory under data/external, share of the 100 external chunks per round)
    ("nvidia__Nemotron-PII", 25),
    ("gretelai__synthetic_pii_finance_multilingual", 25),
    ("gretelai__gretel-pii-masking-en-v1", 20),
    ("QuantumAiuk__uk-pii-redaction-synthetic", 15),
    ("ai4privacy__pii-masking-openpii-1m", 15),
]
PROVENANCE_FLAGS = ("offsets_recovered", "placeholders_filled")


def read(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def stratified(rows: list[dict], per_type: int, rng: random.Random, used: set[str]) -> list[dict]:
    by_type = defaultdict(list)
    for r in rows:
        if r["doc_id"] not in used:
            by_type[r.get("doc_type", "?")].append(r)
    out = []
    for t in sorted(by_type):
        pool = by_type[t]
        rng.shuffle(pool)
        out.extend(pool[:per_type])
    # Top up from what is left if some types were short.
    target = per_type * len(by_type)
    rest = [r for r in rows if r["doc_id"] not in used and r not in out]
    rng.shuffle(rest)
    out.extend(rest[: max(0, target - len(out))])
    for r in out:
        used.add(r["doc_id"])
    return out


def strict_clean(meta: dict) -> bool:
    if meta.get("out_of_scope"):
        return False
    flags = [f for f in meta.get("quality_flags", []) if not f.startswith(PROVENANCE_FLAGS)]
    return not flags and meta.get("mubit_ok") is True


def external_candidates(root: Path, rng: random.Random) -> dict[str, list[dict]]:
    """First chunk of strict-clean train documents, per source, shuffled."""
    docs_meta = {}
    with open(root / "pool_mubit_ok.jsonl", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("split", "train") == "train" and strict_clean(d["meta"]):
                docs_meta[d["doc_id"]] = d["meta"]
    out = {}
    for name, _ in EXTERNAL_MIX:
        rows = []
        with open(root / name / "chunks.jsonl", encoding="utf-8") as f:
            for line in f:
                c = json.loads(line)
                if c["chunk_id"].endswith("-c00") and c["doc_id"] in docs_meta:
                    c.setdefault("meta", {})["mubit_ok"] = True
                    rows.append(c)
        rng.shuffle(rows)
        # Prefer GB-locale rows where the source has locales.
        rows.sort(key=lambda c: 0 if docs_meta[c["doc_id"]].get("locale", "en-GB") == "en-GB" else 1)
        out[name] = rows
    return out


def take_external(cands: dict[str, list[dict]], used: set[str]) -> list[dict]:
    out = []
    for name, n in EXTERNAL_MIX:
        picked = [c for c in cands[name] if c["doc_id"] not in used][:n]
        for c in picked:
            used.add(c["doc_id"])
        out.extend(picked)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="../../data")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    data = Path(a.data)
    syn, ext, out = data / "synthetic", data / "external", data / "rounds"
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(a.seed)
    used: set[str] = set()

    r1_pool = read(syn / "mubit_round1.jsonl")
    r2_pool = read(syn / "mubit_round2.jsonl")
    ext_cands = external_candidates(ext, rng)

    r1_core = stratified(r1_pool, 20, rng, used) + take_external(ext_cands, used)
    r1_extra = [r for r in r1_pool if r["doc_id"] not in used][:1500]
    used.update(r["doc_id"] for r in r1_extra)
    r2 = stratified(r2_pool, 20, rng, used) + take_external(ext_cands, used)
    r3 = stratified(r2_pool, 20, rng, used) + take_external(ext_cands, used)

    eval_syn = read(syn / "mubit_eval.jsonl")
    have = {c["chunk_id"] for c in eval_syn}
    # Supplement: eval-split chunks with full card numbers (the curated eval holds only card endings).
    supplement = []
    with open(syn / "chunks.jsonl", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            if c["split"] != "eval" or c["chunk_id"] in have:
                continue
            if any(e["type"] == "CARD" and len(re.sub(r"\D", "", e["text"])) >= 13 for e in c["entities"]):
                supplement.append(c)
    rng.shuffle(supplement)
    eval_all = eval_syn + supplement[:60]

    # Pilot: 50 eval chunks covering every entity type and many doc types.
    pilot, covered = [], Counter()
    cand = eval_all[:]
    rng.shuffle(cand)
    for c in sorted(cand, key=lambda c: -len({e["type"] for e in c["entities"]})):
        types = {e["type"] for e in c["entities"]}
        if len(pilot) < 50 and (not types or any(covered[t] < 6 for t in types)):
            pilot.append(c)
            covered.update(types)
    while len(pilot) < 50:
        pilot.append(cand.pop())

    files = {
        "r0_pilot.jsonl": pilot,
        "r1_core.jsonl": r1_core,
        "r1_extra.jsonl": r1_extra,
        "r2_fresh.jsonl": r2,
        "r3_reserve.jsonl": r3,
        "corrections.jsonl": read(syn / "mubit_corrections.jsonl"),
        "eval_synthetic.jsonl": eval_all,
        "eval_uk_external.jsonl": read(ext / "uk_eval.jsonl"),
    }
    for name, rows in files.items():
        write(out / name, rows)

    # Sanity: one chunk per document in training files, and no document in two training files.
    train_files = ["r1_core.jsonl", "r1_extra.jsonl", "r2_fresh.jsonl", "r3_reserve.jsonl", "corrections.jsonl"]
    seen: dict[str, str] = {}
    for name in train_files:
        ids = [r["doc_id"] for r in files[name]]
        assert len(ids) == len(set(ids)), f"{name}: repeated document"
        for d in ids:
            assert d not in seen, f"{d} in {seen.get(d)} and {name}"
            seen[d] = name
    eval_docs = {r["doc_id"] for r in eval_all}
    assert not eval_docs & set(seen), "eval document leaked into a training file"

    lines = ["| File | Chunks | Documents | Synthetic | External | Doc types | Entities |", "|---|---:|---:|---:|---:|---:|---:|"]
    for name, rows in files.items():
        n_syn = sum(1 for r in rows if r["doc_id"].startswith("syn-"))
        lines.append(f"| {name} | {len(rows)} | {len({r['doc_id'] for r in rows})} | {n_syn} | {len(rows) - n_syn} | "
                     f"{len({r.get('doc_type') for r in rows})} | {sum(len(r['entities']) for r in rows)} |")
    table = "\n".join(lines)
    (out / "SUMMARY.md").write_text("# Mubit round files\n\n" + table + "\n", encoding="utf-8")
    print(table)


if __name__ == "__main__":
    main()
