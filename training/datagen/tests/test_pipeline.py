import json
from collections import defaultdict

import pytest

from datagen.generate import generate, write_selection
from datagen.stats import write_stats
from datagen.splits import split_for


def _run(tmp, seed, workers, n=600):
    res = generate(n, seed, tmp, workers, log=lambda *a: None)
    index = res.pop("index")
    res["mubit_files"] = write_selection(tmp, index, seed, {"mubit_round1": 120, "mubit_round2": 40,
                                                            "mubit_corrections": 10, "mubit_eval": 30})
    (tmp / "manifest.json").write_text(json.dumps(res))
    return res


@pytest.fixture(scope="module")
def run_a(tmp_path_factory):
    d = tmp_path_factory.mktemp("a")
    _run(d, 42, 1)
    return d


def _lines(p):
    return [json.loads(x) for x in open(p, encoding="utf-8")]


def test_determinism_same_seed_any_workers(run_a, tmp_path):
    _run(tmp_path, 42, 3)
    for f in ("docs.jsonl", "chunks.jsonl", "mubit_round1.jsonl", "mubit_eval.jsonl"):
        assert (run_a / f).read_bytes() == (tmp_path / f).read_bytes(), f


def test_different_seed_differs(run_a, tmp_path):
    _run(tmp_path, 43, 2, n=50)
    a = [d["text"] for d in _lines(run_a / "docs.jsonl")[:50]]
    b = [d["text"] for d in _lines(tmp_path / "docs.jsonl")]
    assert a != b


def test_records_and_chunks_consistent(run_a):
    docs = {d["doc_id"]: d for d in _lines(run_a / "docs.jsonl")}
    assert len(docs) == 600
    keys = {"doc_id", "source", "doc_type", "language", "license", "text", "entities", "split", "meta"}
    hashes = set()
    for d in docs.values():
        assert keys <= set(d)
        for e in d["entities"]:
            assert d["text"][e["start"]:e["end"]] == e["text"]
        assert d["meta"]["norm_hash"] not in hashes  # no exact duplicates
        hashes.add(d["meta"]["norm_hash"])
    per_doc = defaultdict(list)
    for c in _lines(run_a / "chunks.jsonl"):
        d = docs[c["doc_id"]]
        a, b = c["meta"]["char_start"], c["meta"]["char_end"]
        assert d["text"][a:b] == c["text"] and len(c["text"]) <= 6000
        assert c["split"] == d["split"] and c["doc_type"] == d["doc_type"]
        for e in c["entities"]:
            assert c["text"][e["start"]:e["end"]] == e["text"]
        per_doc[c["doc_id"]].append(c)
    for doc_id, cs in per_doc.items():
        assert sum(len(c["entities"]) for c in cs) == len(docs[doc_id]["entities"])
    assert set(per_doc) == set(docs)


def test_splits_disjoint_by_document(run_a):
    split_of = {}
    for c in _lines(run_a / "chunks.jsonl"):
        assert split_of.setdefault(c["doc_id"], c["split"]) == c["split"]
    assert set(split_of.values()) <= {"train", "fresh", "corrections", "eval"}
    for doc_id, sp in split_of.items():
        assert split_for(doc_id, 42) == sp
    # split shares over many ids are close to 83/10/2/5
    from collections import Counter
    cnt = Counter(split_for(f"syn-{i:06d}", 42) for i in range(100000))
    assert abs(cnt["train"] / 1e5 - 0.83) < 0.01 and abs(cnt["eval"] / 1e5 - 0.05) < 0.005


def test_mubit_files(run_a):
    split_of = {c["doc_id"]: c["split"] for c in _lines(run_a / "chunks.jsonl")}
    want = {"mubit_round1": "train", "mubit_round2": "fresh", "mubit_corrections": "corrections", "mubit_eval": "eval"}
    all_ids = defaultdict(set)
    for name, sp in want.items():
        rows = _lines(run_a / f"{name}.jsonl")
        assert rows, name
        ids = [r["chunk_id"] for r in rows]
        assert len(ids) == len(set(ids))
        assert all(split_of[r["doc_id"]] == sp for r in rows)
        all_ids[name] = {r["doc_id"] for r in rows}
        if name != "mubit_eval":
            assert len({r["doc_id"] for r in rows}) == len(rows)  # one chunk per document
        if name == "mubit_corrections":
            assert all(r["entities"] for r in rows)
    # eval keeps whole documents
    chunks_per_doc = defaultdict(int)
    for c in _lines(run_a / "chunks.jsonl"):
        chunks_per_doc[c["doc_id"]] += 1
    ev = defaultdict(int)
    for r in _lines(run_a / "mubit_eval.jsonl"):
        ev[r["doc_id"]] += 1
    assert all(ev[d] == chunks_per_doc[d] for d in ev)
    assert all_ids["mubit_round1"].isdisjoint(all_ids["mubit_eval"])


def test_stats_written(run_a):
    p = write_stats(run_a, copy_to=None)
    text = p.read_text()
    for h in ("## Totals", "## Entity types", "## Hard cases", "## Keep traps", "## Length distribution",
              "## Mubit round files", "near-duplicate"):
        assert h in text
