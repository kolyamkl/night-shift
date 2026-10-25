"""RedactionBench/RedactionBench -> canonical (pool B, local eval only). Untyped spans, recall-only eval.

Every span becomes type UNTYPED; its tier (`mandatory` must be redacted, `contextual` may be redacted
without penalty) is kept in meta.span_tiers, aligned with entities. Span text is kept exactly as in the
source (no trimming), so single-character "combinator" spans survive.
"""
from __future__ import annotations

from collections import Counter

import pyarrow.parquet as pq

from .common import RAW, UNTYPED, slug

DATASET = {
    "id": "RedactionBench/RedactionBench",
    "dir": "RedactionBench__RedactionBench",
    "short": "rb",
    "license": "CC-BY-4.0",
    "pool": "B",
    "untyped": True,
    "revision": "d45e9cec89bc49c69355e252fec29cc0229982f6",
}


def convert(stats: Counter):
    t = pq.read_table(RAW / DATASET["dir"] / "data" / "test-00000-of-00001.parquet")
    stats["rows_read"] = t.num_rows
    for r in t.to_pylist():
        text = r["raw_text"]
        ents, tiers = [], []
        for x in sorted(r["spans"], key=lambda x: (x["start"], x["end"])):
            s, e = x["start"], x["end"]
            if not (0 <= s < e <= len(text)):
                stats["span_bad_offsets_dropped"] += 1
                continue
            if ents and s < ents[-1]["end"]:
                stats["span_overlap_dropped"] += 1
                continue
            ents.append({"start": s, "end": e, "text": text[s:e], "type": UNTYPED})
            tiers.append(x["label"])
            stats["span_" + x["label"]] += 1
        yield {
            "text": text,
            "entities": ents,
            "split": "eval",
            "doc_type": slug(r["genre"].lstrip("_")),
            "meta": {
                "mubit_ok": False,
                "real_personal_data": False,
                "real_web_document": not r["is_synthetic"],
                "category": r["category"],
                "genre": r["genre"],
                "is_synthetic": r["is_synthetic"],
                "original_document_url": r["original_document_url"],
                "span_tiers": tiers,
                "revision": DATASET["revision"],
                "orig_labels": "untyped: see span_tiers",
                "dropped_labels": {},
                "out_of_scope": [],
                "quality_flags": [],
            },
        }
