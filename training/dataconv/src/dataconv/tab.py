"""Text Anonymization Benchmark (TAB, ECHR judgments) -> canonical (pool B, local eval only, real names).

Source: GitHub NorskRegnesentral/text-anonymization-benchmark echr_{train,dev,test}.json at a pinned commit.
One annotator per document (a quality-checked annotator when listed, else the first by id).
DIRECT/QUASI mentions: PERSON -> PERSON, CODE -> CUSTOM, DATETIME -> DOB when a birth keyword is next to it.
All other DIRECT/QUASI mentions (LOC, ORG, DEM, MISC, QUANTITY, other DATETIME) and PERSON NO_MASK mentions
(judges, agents, public officials) go to meta.out_of_scope so an evaluation can ignore predictions there.
"""
from __future__ import annotations

import json
from collections import Counter

from .common import RAW, is_dob_context, mk, person_bounds, resolve_overlaps, trim

DATASET = {
    "id": "NorskRegnesentral/text-anonymization-benchmark",
    "dir": "NorskRegnesentral__text-anonymization-benchmark",
    "short": "tab",
    "license": "MIT",
    "pool": "B",
    "revision": "558e09e26d6b36f5f78440074e6a233946d98bd9",
}


def pick_annotator(doc: dict) -> str:
    qc = [a for a in (doc.get("quality_checked") or []) if a in doc["annotations"]]
    return sorted(qc)[0] if qc else sorted(doc["annotations"])[0]


def convert(stats: Counter):
    for sp in ("train", "dev", "test"):
        docs = json.loads((RAW / DATASET["dir"] / f"echr_{sp}.json").read_text(encoding="utf-8"))
        stats[f"docs_read_{sp}"] = len(docs)
        for d in docs:
            out = convert_doc(d, sp, stats)
            if out is not None:
                yield out


def convert_doc(d: dict, sp: str, stats: Counter):
    text = d["text"]
    ann = pick_annotator(d)
    ents, oos, flags = [], [], []
    for m in d["annotations"][ann]["entity_mentions"]:
        s, e = m["start_offset"], m["end_offset"]
        if not (0 <= s < e <= len(text)) or text[s:e] != m["span_text"]:
            stats["mention_text_mismatch_dropped"] += 1
            continue
        s, e = trim(text, s, e)
        et, it = m["entity_type"], m["identifier_type"]
        tag = {"identifier_type": it, "entity_id": m["entity_id"], "entity_type": et}
        if it in ("DIRECT", "QUASI") and et == "PERSON":
            a, b = person_bounds(text, s, e)
            ents.append({**mk(text, a, b, "PERSON"), "_tag": tag})
        elif it in ("DIRECT", "QUASI") and et == "CODE":
            ents.append({**mk(text, s, e, "CUSTOM"), "_tag": tag})
        elif it in ("DIRECT", "QUASI") and et == "DATETIME" and is_dob_context(text, s, e):
            ents.append({**mk(text, s, e, "DOB"), "_tag": tag})
        elif it in ("DIRECT", "QUASI") or et == "PERSON":
            oos.append([s, e, f"{et}:{it}"])
        stats[f"mention_{et}_{it}"] += 1
    kept = resolve_overlaps(ents, stats)
    tags = [x.pop("_tag") for x in kept]
    for x in ents:
        x.pop("_tag", None)
    return {
        "text": text,
        "entities": kept,
        "split": "eval",
        "doc_type": "court_judgment",
        "meta": {
            "mubit_ok": False,
            "real_personal_data": True,
            "locale": "en (ECHR)",
            "source_doc_id": d["doc_id"],
            "source_split": sp,
            "annotator": ann,
            "n_annotators": len(d["annotations"]),
            "quality_checked": d.get("quality_checked"),
            "task": d.get("task"),
            "case_meta": d.get("meta"),
            "revision": DATASET["revision"],
            "entity_tags": tags,  # aligned with entities: identifier_type DIRECT/QUASI, TAB entity_id, entity_type
            "orig_labels": "see source file (mentions of the chosen annotator)",
            "dropped_labels": {},
            "out_of_scope": oos,
            "quality_flags": flags,
        },
    }
