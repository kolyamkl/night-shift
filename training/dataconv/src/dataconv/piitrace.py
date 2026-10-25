"""perplexity-ai/PII-TRACE -> canonical (pool B, local eval only; task rule, although the card says synthetic).

One document per conversation. Gold spans exist only in user messages, so the document text is the user
turns joined by a blank line; meta.turns gives each turn's offsets. Offsets in the source are Unicode
code-point offsets per message, which equal Python string indices.
"""
from __future__ import annotations

from collections import Counter

import pyarrow.parquet as pq

from . import mapping as M
from .common import RAW, resolve_overlaps

DATASET = {
    "id": "perplexity-ai/PII-TRACE",
    "dir": "perplexity-ai__PII-TRACE",
    "short": "trace",
    "license": "MIT",
    "pool": "B",
    "revision": "1c3eb67bbd43e8571b4433a9d3d76271f9970eb9",
}

MAP = M.Mapping(
    simple={
        "private_person": "PERSON",
        "private_email": "EMAIL",
        "private_phone": "PHONE",
        "private_address": "ADDRESS",
        "other_pii": "CUSTOM",
    },
    fn={"account_number": M.account_type, "private_date": M.dob_or_drop},
    keep=set(),
    out_of_scope={"private_url", "secret"},
)
SEP = "\n\n"


def convert(stats: Counter):
    t = pq.read_table(RAW / DATASET["dir"] / "data" / "train.parquet")
    stats["rows_read"] = t.num_rows
    for r in t.to_pylist():
        turns = sorted(r["turns"], key=lambda x: x["turn"])
        parts, offs, pos = [], {}, 0
        for tn in turns:
            if parts:
                parts.append(SEP)
                pos += len(SEP)
            offs[tn["turn"]] = pos
            parts.append(tn["user"])
            pos += len(tn["user"])
        text = "".join(parts)
        raw, bad = [], False
        for s in r["spans"]:
            if s["source"] != "user":
                stats["span_not_in_user_message"] += 1
                bad = True
                break
            a = offs[s["turn"]] + s["start"]
            b = offs[s["turn"]] + s["end"]
            if text[a:b] != s["text"]:
                bad = True
                break
            raw.append({"start": a, "end": b, "label": s["label"]})
        if bad:
            stats["skip_row_span_mismatch"] += 1
            continue
        res = M.apply(text, raw, MAP, stats)
        if res is None:
            stats["skip_row_mapping_failed"] += 1
            continue
        ents, dropped, oos = res
        # private_date that is not a DOB: an ordinary date for us, but private for PII-TRACE -> ignore zone
        oos += [[x["start"], x["end"], "private_date"] for x in raw
                if x["label"] == "private_date" and not any(e["start"] == x["start"] for e in ents)]
        ents = resolve_overlaps(ents, stats)
        yield {
            "text": text,
            "entities": ents,
            "split": "eval",
            "doc_type": "chat_conversation",
            "meta": {
                "mubit_ok": False,
                "real_personal_data": False,
                "locale": "en",
                "source_id": r["id"],
                "turns": [{"turn": tn["turn"], "start": offs[tn["turn"]], "end": offs[tn["turn"]] + len(tn["user"])} for tn in turns],
                "empty_control": not r["spans"],
                "revision": DATASET["revision"],
                "orig_labels": [[x["start"], x["end"], x["label"]] for x in raw],
                "dropped_labels": dict(dropped),
                "out_of_scope": oos,
                "quality_flags": [],
            },
        }
