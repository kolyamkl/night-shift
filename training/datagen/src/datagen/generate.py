"""CLI: generate synthetic documents, chunks, splits and Mubit round files.

    uv run python -m datagen.generate --n 100000 --seed 42 --out ../../data/synthetic

Document i is generated from ``random.Random(f"{seed}:{i}:{attempt}")`` only, so the output is
identical for the same seed whatever the number of workers.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from multiprocessing import Pool
from pathlib import Path

from .build import LICENSE, finish
from .chunker import MAX_CHARS, chunk_doc
from .dedup import NearDupIndex, signature
from .doctypes import load_all
from .splits import split_for
from .validate import check_chunk, check_record

NEG_RATE = 0.15
NEAR_DUP_J = 0.8
_REG = None


def _registry():
    global _REG
    if _REG is None:
        reg = load_all()
        pos = [(d, d.weight) for d in reg.values() if d.weight > 0]
        neg = [(d, d.neg_weight) for d in reg.values() if d.neg_weight > 0]
        _REG = (reg, [d for d, _ in pos], [w for _, w in pos], [d for d, _ in neg], [w for _, w in neg])
    return _REG


def make_doc(i: int, seed: int, attempt: int = 0, neg_rate: float = NEG_RATE,
             max_chars: int = MAX_CHARS) -> tuple[dict, list[dict]]:
    _, pos_t, pos_w, neg_t, neg_w = _registry()
    doc_id = f"syn-{i:06d}"
    last_err = None
    for a in range(attempt, attempt + 8):
        rng = random.Random(f"{seed}:{i}:{a}")
        neg = rng.random() < neg_rate
        dt = rng.choices(neg_t, neg_w)[0] if neg else rng.choices(pos_t, pos_w)[0]
        try:
            core = finish(dt.fn(rng, neg), neg)
        except Exception as ex:  # a generator bug must not stop a 100k run; retry with a new sub-seed
            last_err = repr(ex)
            continue
        meta = core["meta"]
        meta["seed"] = seed
        meta["attempt"] = a
        rec = {"doc_id": doc_id, "source": "synthetic", "doc_type": core["doc_type"], "language": "en",
               "license": LICENSE, "text": core["text"], "entities": core["entities"],
               "split": split_for(doc_id, seed), "meta": meta}
        errs = check_record(rec)
        if errs:
            last_err = errs[0]
            continue
        chunks = chunk_doc(rec, max_chars)
        cerrs = [e for c in chunks for e in check_chunk(c, rec)]
        if any(len(c["text"]) > max_chars for c in chunks):
            cerrs.append("chunk too long")
        if cerrs:
            last_err = cerrs[0]
            continue
        rec["meta"]["n_chunks"] = len(chunks)
        sig = signature(rec["text"], rec["entities"])
        rec["_sig"] = sig
        for c in chunks:
            c["_sig"] = sig if len(chunks) == 1 else signature(c["text"], c["entities"])
        return rec, chunks
    raise RuntimeError(f"{doc_id}: could not generate a valid document: {last_err}")


def _batch(args):
    a, b, seed, neg_rate, max_chars = args
    return [make_doc(i, seed, 0, neg_rate, max_chars) for i in range(a, b)]


def index_entry(line: int, c: dict, neardup: bool, sig: bytes) -> dict:
    return {
        "sig": sig,
        "line": line, "chunk_id": c["chunk_id"], "doc_id": c["doc_id"], "split": c["split"],
        "doc_type": c["doc_type"], "n": len(c["text"]), "types": sorted({e["type"] for e in c["entities"]}),
        "n_ents": len(c["entities"]), "hard": sorted({h["kind"] for h in c["meta"]["hard_cases"]}),
        "neg": not c["entities"], "variant": c["meta"]["variant_id"], "skel": c["meta"]["skeleton_hash"],
        "doc_neardup": neardup,
    }


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def generate(n: int, seed: int, out: Path, workers: int, neg_rate: float = NEG_RATE,
             max_chars: int = MAX_CHARS, batch: int = 500, log=print) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    seen_exact: set[str] = set()
    seen_skel: set[str] = set()
    index: list[dict] = []
    n_exact_retry = n_near = n_chunks = n_skel = n_chunk_near = 0
    doc_idx, chunk_idx = NearDupIndex(), NearDupIndex()
    doc_ids: list[str] = []
    ranges = [(a, min(a + batch, n), seed, neg_rate, max_chars) for a in range(0, n, batch)]
    with open(out / "docs.jsonl", "w", encoding="utf-8") as fd, \
            open(out / "chunks.jsonl", "w", encoding="utf-8") as fc:
        pool = Pool(workers) if workers > 1 else None
        it = pool.imap(_batch, ranges) if pool else map(_batch, ranges)
        done = 0
        for results in it:
            for rec, chunks in results:
                attempt = rec["meta"]["attempt"]
                # exact duplicates (case/whitespace-insensitive) are regenerated with the next sub-seed
                while rec["meta"]["norm_hash"] in seen_exact:
                    n_exact_retry += 1
                    attempt += 1
                    rec, chunks = make_doc(int(rec["doc_id"][4:]), seed, attempt, neg_rate, max_chars)
                    attempt = rec["meta"]["attempt"]
                seen_exact.add(rec["meta"]["norm_hash"])
                skel_dup = rec["meta"]["skeleton_hash"] in seen_skel
                seen_skel.add(rec["meta"]["skeleton_hash"])
                n_skel += skel_dup
                sig = rec.pop("_sig")
                j, j_i = doc_idx.check(sig)
                near = j >= NEAR_DUP_J
                doc_idx.add(sig)
                doc_ids.append(rec["doc_id"])
                rec["meta"]["skeleton_dup"] = skel_dup
                rec["meta"]["near_dup"] = near
                rec["meta"]["near_dup_of"] = doc_ids[j_i] if near else None
                rec["meta"]["max_jaccard_prev"] = round(j, 3)
                n_near += near
                fd.write(_dump(rec) + "\n")
                for c in chunks:
                    csig = c.pop("_sig")
                    cj, _ = chunk_idx.check(csig)
                    chunk_idx.add(csig)
                    n_chunk_near += cj >= NEAR_DUP_J
                    c["meta"]["doc_near_dup"] = near
                    fc.write(_dump(c) + "\n")
                    index.append(index_entry(n_chunks, c, near, csig))
                    n_chunks += 1
            done += len(results)
            if done % 10000 < batch or done == n:
                el = time.time() - t0
                log(f"  {done:>7}/{n} docs  {n_chunks} chunks  {done / el:,.0f} docs/s")
        if pool:
            pool.close()
            pool.join()
    gen_secs = time.time() - t0
    return {"n_docs": n, "n_chunks": n_chunks, "exact_dup_regenerated": n_exact_retry, "skeleton_dup_docs": n_skel,
            "near_dup_docs": n_near, "near_dup_chunks": n_chunk_near, "near_dup_threshold_jaccard": NEAR_DUP_J,
            "seconds": round(gen_secs, 1), "docs_per_sec": round(n / max(gen_secs, 1e-9), 1), "index": index}


def write_selection(out: Path, index: list[dict], seed: int, sizes: dict[str, int] | None = None) -> dict:
    from .select import select_all
    sel = select_all(index, seed, sizes)
    want: dict[int, list[str]] = {}
    for name, items in sel.items():
        for c in items:
            want.setdefault(c["line"], []).append(name)
    lines: dict[int, str] = {}
    with open(out / "chunks.jsonl", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i in want:
                lines[i] = line
    counts = {}
    for name, items in sel.items():
        with open(out / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for c in items:
                f.write(lines[c["line"]])
        counts[name] = len(items)
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=100000, help="number of documents (default 100000)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=Path("../../data/synthetic"))
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--neg-rate", type=float, default=NEG_RATE, help="share of documents with no personal data")
    ap.add_argument("--max-chars", type=int, default=MAX_CHARS, help="max characters per chunk")
    ap.add_argument("--round1", type=int, default=3000)
    ap.add_argument("--round2", type=int, default=2000)
    ap.add_argument("--corrections", type=int, default=200)
    ap.add_argument("--eval", type=int, default=1500)
    ap.add_argument("--pdfs", type=int, default=30, help="demo PDFs to render (0 to skip)")
    ap.add_argument("--no-stats", action="store_true")
    ap.add_argument("--no-copy", action="store_true", help="do not copy stats.md into docs/research")
    a = ap.parse_args(argv)
    out = a.out.resolve()
    print(f"generating {a.n} documents, seed {a.seed}, {a.workers} workers -> {out}")
    res = generate(a.n, a.seed, out, a.workers, a.neg_rate, a.max_chars)
    index = res.pop("index")
    print(f"done in {res['seconds']}s ({res['docs_per_sec']} docs/s); selecting Mubit round files")
    sizes = {"mubit_round1": a.round1, "mubit_round2": a.round2, "mubit_corrections": a.corrections,
             "mubit_eval": a.eval}
    res["mubit_files"] = write_selection(out, index, a.seed, sizes)
    split_docs: dict[str, int] = {}
    seen = set()
    for c in index:
        if c["doc_id"] not in seen:
            seen.add(c["doc_id"])
            split_docs[c["split"]] = split_docs.get(c["split"], 0) + 1
    res["split_docs"] = split_docs
    res.update({"seed": a.seed, "max_chars": a.max_chars, "neg_rate": a.neg_rate, "workers": a.workers})
    (out / "manifest.json").write_text(json.dumps(res, indent=2) + "\n")
    print(json.dumps(res, indent=2))
    if a.pdfs:
        from .pdf import build_pdfs
        rep = build_pdfs(out / "pdfs", a.pdfs, a.seed)
        print(f"pdfs: {rep['n_pdfs']} rendered, span mismatch rate {rep['mismatch_rate']:.2%}")
    if not a.no_stats:
        from .stats import RESEARCH_COPY, write_stats
        p = write_stats(out, None if a.no_copy else RESEARCH_COPY)
        print(f"stats -> {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
