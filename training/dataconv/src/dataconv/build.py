"""Run converters, validate, dedupe, chunk, write per-dataset outputs, then combine pools.

    uv run dataconv build [short ...]   # convert datasets (default: all)
    uv run dataconv combine             # pool_mubit_ok.jsonl, eval_local_only.jsonl, uk_eval.jsonl
"""
from __future__ import annotations

import importlib
import json
import sys
from collections import Counter

from .common import ENTITY_SET, EXT, UNTYPED, chunk_doc, norm_hash, read_jsonl, record, type_counts, validate_doc, write_jsonl

MODULES = ["openpii", "nemotron", "gretel_fin", "gretel_en", "quantum", "bitext_bank", "bitext_cs", "tab", "redactionbench", "piitrace"]


def load(name: str):
    return importlib.import_module(f"dataconv.{name}")


def build_one(name: str) -> dict:
    mod = load(name)
    ds = mod.DATASET
    stats: Counter = Counter()
    out_dir = EXT / ds["dir"]
    allowed = ENTITY_SET | {UNTYPED} if ds.get("untyped") else ENTITY_SET
    docs, seen = [], set()
    for part in mod.convert(stats):
        stats["converted"] += 1
        h = norm_hash(part["text"])
        if h in seen:
            stats["skip_duplicate_text"] += 1
            continue
        seen.add(h)
        meta = dict(part["meta"])
        meta.setdefault("pool", ds["pool"])
        meta["norm_hash"] = h
        rec = record(
            doc_id=f"{ds['short']}-{len(docs) + 1:06d}",
            source=part.get("source", ds["id"]), doc_type=part["doc_type"], license_id=part.get("license", ds["license"]),
            text=part["text"], entities=part["entities"], split=part["split"], meta=meta,
        )
        errs = validate_doc(rec, allowed, strip_check=not ds.get("untyped"))
        if errs:
            stats["skip_invalid_after_mapping"] += 1
            if stats["skip_invalid_after_mapping"] <= 5:
                print("INVALID", name, errs[:3], file=sys.stderr)
            continue
        docs.append(rec)
    chunks = [c for d in docs for c in chunk_doc(d)]
    write_jsonl(out_dir / "docs.jsonl", docs)
    write_jsonl(out_dir / "chunks.jsonl", chunks)
    summary = {
        "dataset": ds["id"], "short": ds["short"], "license": ds["license"], "revision": ds.get("revision"),
        "pool": ds["pool"], "docs_kept": len(docs), "chunks": len(chunks),
        "docs_by_pool": dict(Counter(d["meta"]["pool"] for d in docs)),
        "docs_by_split": dict(Counter(d["split"] for d in docs)),
        "entities_by_type": type_counts(docs),
        "entities_by_type_by_pool": {
            p: type_counts(d for d in docs if d["meta"]["pool"] == p) for p in sorted({d["meta"]["pool"] for d in docs})
        },
        "docs_with_out_of_scope": sum(1 for d in docs if d["meta"].get("out_of_scope")),
        "docs_with_quality_flags": dict(Counter(f for d in docs for f in d["meta"].get("quality_flags", []))),
        "dropped_labels": dict(sum((Counter(d["meta"].get("dropped_labels", {})) for d in docs), Counter()).most_common()),
        "doc_chars_max": max((len(d["text"]) for d in docs), default=0),
        "stats": dict(sorted(stats.items())),
    }
    (out_dir / "stats.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps({k: summary[k] for k in ("dataset", "docs_kept", "chunks", "docs_by_pool", "entities_by_type")}, ensure_ascii=False))
    return summary


def combine() -> dict:
    """Route per-dataset docs into the three combined files; enforce pool separation by text hash."""
    pools = {"A": [], "B": [], "uk_eval": []}
    for name in MODULES:
        ds = load(name).DATASET
        p = EXT / ds["dir"] / "docs.jsonl"
        if not p.exists():
            print("missing", p, file=sys.stderr)
            continue
        for d in read_jsonl(p):
            pools[d["meta"]["pool"]].append(d)
    log = Counter()
    b_hashes = {d["meta"]["norm_hash"] for d in pools["B"]}
    uk_hashes = {d["meta"]["norm_hash"] for d in pools["uk_eval"]}
    a_out, a_seen = [], set()
    for d in pools["A"]:
        h = d["meta"]["norm_hash"]
        if h in b_hashes:
            log["A_removed_text_in_pool_B"] += 1
            continue
        if h in uk_hashes:
            log["A_removed_text_in_uk_eval"] += 1
            continue
        if h in a_seen:
            log["A_removed_cross_dataset_duplicate"] += 1
            continue
        a_seen.add(h)
        a_out.append(d)

    def dedupe(rows, tag):
        seen, out = set(), []
        for d in rows:
            if d["meta"]["norm_hash"] in seen:
                log[f"{tag}_removed_cross_dataset_duplicate"] += 1
                continue
            seen.add(d["meta"]["norm_hash"])
            out.append(d)
        return out

    b_out = dedupe(pools["B"], "B")
    uk_out = dedupe(pools["uk_eval"], "uk_eval")
    n_a = write_jsonl(EXT / "pool_mubit_ok.jsonl", a_out)
    n_b = write_jsonl(EXT / "eval_local_only.jsonl", b_out)
    n_uk = write_jsonl(EXT / "uk_eval.jsonl", uk_out)
    summary = {
        "pool_mubit_ok": {"docs": n_a, "by_source": dict(Counter(d["source"] for d in a_out)),
                          "entities_by_type": type_counts(a_out)},
        "eval_local_only": {"docs": n_b, "by_source": dict(Counter(d["source"] for d in b_out)),
                            "entities_by_type": type_counts(b_out)},
        "uk_eval": {"docs": n_uk, "by_subset": dict(Counter(d["meta"].get("subset") for d in uk_out)),
                    "entities_by_type": type_counts(uk_out)},
        "log": dict(log),
    }
    (EXT / "combined_stats.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    return summary


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ("build", "combine"):
        print(__doc__)
        return
    if argv[0] == "combine":
        combine()
        return
    names = argv[1:] or MODULES
    for n in names:
        build_one(n)
