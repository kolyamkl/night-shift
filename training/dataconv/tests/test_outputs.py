"""Checks on the converted files in data/external (skipped when a file has not been built)."""
import json
from pathlib import Path

import pytest

from dataconv.build import MODULES, load
from dataconv.common import ENTITY_SET, EXT, MAX_CHUNK_CHARS, UNTYPED, norm_hash

KEYS = {"doc_id", "source", "doc_type", "language", "license", "text", "entities", "split", "meta"}
POOL_A = EXT / "pool_mubit_ok.jsonl"
POOL_B = EXT / "eval_local_only.jsonl"
UK_EVAL = EXT / "uk_eval.jsonl"


def rows(p: Path):
    with p.open(encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def check_spans(text, ents, allowed, strip=True):
    prev = -1
    for e in ents:
        assert 0 <= e["start"] < e["end"] <= len(text), e
        assert text[e["start"]:e["end"]] == e["text"], e
        assert e["type"] in allowed, e
        assert e["start"] >= prev, f"overlap {e}"
        prev = e["end"]
        if strip:
            assert e["text"] == e["text"].strip(), e


def need(p: Path):
    if not p.exists():
        pytest.skip(f"{p} not built")


@pytest.mark.parametrize("name", MODULES)
def test_dataset_docs_and_chunks(name):
    ds = load(name).DATASET
    docs_p, chunks_p = EXT / ds["dir"] / "docs.jsonl", EXT / ds["dir"] / "chunks.jsonl"
    need(docs_p)
    untyped = bool(ds.get("untyped"))
    allowed = {UNTYPED} if untyped else ENTITY_SET
    docs, ids, hashes = {}, set(), set()
    for d in rows(docs_p):
        assert set(d) == KEYS
        assert d["doc_id"] not in ids
        ids.add(d["doc_id"])
        check_spans(d["text"], d["entities"], allowed, strip=not untyped)
        h = norm_hash(d["text"])
        assert h not in hashes, "duplicate text"
        hashes.add(h)
        assert d["meta"]["mubit_ok"] is (d["meta"]["pool"] != "B")
        assert d["license"] == ds["license"]
        docs[d["doc_id"]] = d
    n_ent_docs = sum(len(d["entities"]) for d in docs.values())
    n_ent_chunks = 0
    for c in rows(chunks_p):
        d = docs[c["doc_id"]]
        a, b = c["meta"]["char_start"], c["meta"]["char_end"]
        assert d["text"][a:b] == c["text"]
        check_spans(c["text"], c["entities"], allowed, strip=not untyped)
        longest = max((e["end"] - e["start"] for e in c["entities"]), default=0)
        assert len(c["text"]) <= max(MAX_CHUNK_CHARS, longest)
        assert c["meta"]["mubit_ok"] == d["meta"]["mubit_ok"]
        n_ent_chunks += len(c["entities"])
    assert n_ent_chunks == n_ent_docs  # no span lost or cut by chunking


def test_pool_flags_and_separation():
    for p in (POOL_A, POOL_B, UK_EVAL):
        need(p)
    a_hashes = set()
    for d in rows(POOL_A):
        assert d["meta"]["mubit_ok"] is True and d["meta"]["pool"] == "A"
        check_spans(d["text"], d["entities"], ENTITY_SET)
        a_hashes.add(norm_hash(d["text"]))
    b_sources = set()
    for d in rows(POOL_B):
        assert d["meta"]["mubit_ok"] is False and d["meta"]["pool"] == "B"
        allowed = {UNTYPED} if d["source"] == "RedactionBench/RedactionBench" else ENTITY_SET
        check_spans(d["text"], d["entities"], allowed, strip=allowed is ENTITY_SET)
        assert norm_hash(d["text"]) not in a_hashes, "pool B text found in pool A"
        b_sources.add(d["source"])
    assert b_sources == {"NorskRegnesentral/text-anonymization-benchmark", "RedactionBench/RedactionBench",
                         "perplexity-ai/PII-TRACE"}
    for d in rows(UK_EVAL):
        assert d["meta"]["subset"] in {"test", "wild", "wild2"} and d["split"] == "eval"
        check_spans(d["text"], d["entities"], ENTITY_SET)
        assert norm_hash(d["text"]) not in a_hashes, "uk_eval text found in pool A"


def test_pool_a_sources_are_mubit_ok_only():
    need(POOL_A)
    allowed = {load(n).DATASET["id"] for n in MODULES if load(n).DATASET["pool"] == "A"}
    srcs = {d["source"] for d in rows(POOL_A)}
    assert srcs <= allowed and not srcs & {"NorskRegnesentral/text-anonymization-benchmark",
                                           "RedactionBench/RedactionBench", "perplexity-ai/PII-TRACE"}
