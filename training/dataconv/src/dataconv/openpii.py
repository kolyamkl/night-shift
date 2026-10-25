"""ai4privacy/pii-masking-openpii-1m -> canonical (pool A, short_message).

Only English rows. The train.jsonl file is sorted by (language, region); we downloaded the whole en-GB
byte range and 12 evenly spaced 4 MB slices of the other English regions (see raw download_manifest.json).
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .common import RAW, is_dob_context, is_uk_postcode, merge_runs, mk, span_ok, ssn_like_type, trim

DATASET = {
    "id": "ai4privacy/pii-masking-openpii-1m",
    "dir": "ai4privacy__pii-masking-openpii-1m",
    "short": "openpii",
    "license": "CC-BY-4.0",
    "pool": "A",
    "revision": "ecfdc547f4a0955600cfe6ab98ba2a162207fcc0",
}
CAP = 60_000

SIMPLE = {
    "EMAIL": "EMAIL",
    "TELEPHONENUM": "PHONE",
    "CREDITCARDNUMBER": "CARD",
    "PASSPORTNUM": "ID_DOC",
    "DRIVERLICENSENUM": "ID_DOC",
    "IDCARDNUM": "ID_DOC",
    "TAXNUM": "CUSTOM",
    "ZIPCODE": "POSTCODE",
}
DROP = {"TITLE", "AGE", "GENDER", "SEX"}          # keep classes: left unlabelled
PERSON_PARTS = {"GIVENNAME", "SURNAME"}
ADDR_PARTS = {"BUILDINGNUM", "STREET", "CITY"}
NAME_GAP = re.compile(r"[ \t]{1,2}")
# separators allowed inside one address run: spaces, comma, newline, "#", "No."/"number" (house-number markers),
# and " in " (street ... in Town). Anything longer (" near ", " with building number ") breaks the run.
ADDR_GAP = re.compile(r"[ \t]*(?:,|#|No\.?|no\.?|number|Nr\.?)?[ \t]*,?[ \t]*(?:\n[ \t]*)?|[ \t]+in[ \t]+")
UK_PHONE_LOOSE = re.compile(r"^(\+44|0)[\d\s()-]{9,15}$")


def iter_rows(raw_dir: Path):
    seen = set()
    for f in sorted(raw_dir.glob("train_bytes_*.jsonl.part")):
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                if r["uid"] in seen:
                    continue
                seen.add(r["uid"])
                yield r


def convert(stats: Counter):
    raw_dir = RAW / DATASET["dir"]
    rows = [r for r in iter_rows(raw_dir) if r.get("language") == "en"]
    stats["rows_read_en"] = len(rows)
    # GB first (all of it), then the other English locales, up to CAP
    rows.sort(key=lambda r: (r["region"] != "GB", r["region"], r["uid"]))
    kept = 0
    for r in rows:
        if kept >= CAP:
            stats["skip_cap"] += 1
            continue
        out = convert_row(r, stats)
        if out is None:
            continue
        kept += 1
        yield out


def convert_row(r: dict, stats: Counter):
    text = r["source_text"]
    raw = []
    for m in r["privacy_mask"]:
        s, e = trim(text, m["start"], m["end"])
        if s >= e or text[s:e] != m["value"].strip():
            stats["skip_row_span_mismatch"] += 1
            return None
        raw.append({"start": s, "end": e, "label": m["label"]})
    orig = [[x["start"], x["end"], x["label"]] for x in raw]
    dropped = Counter()
    flags = set()

    # merge GIVENNAME/SURNAME runs, then address part runs
    runs = merge_runs(text, raw, "label", PERSON_PARTS, NAME_GAP)
    for x in runs:
        if x.get("_run"):
            x["label"] = "_PERSON"
            del x["_run"]
    runs = merge_runs(text, runs, "label", ADDR_PARTS, ADDR_GAP)

    ents = []
    for x in runs:
        lab = x["label"] if not x.get("_run") else None
        s, e = x["start"], x["end"]
        val = text[s:e]
        if lab is None:  # address-part run
            parts = set(x["parts"])
            sig = "+".join(sorted(parts))
            stats["addr_run_" + sig] += 1
            if "STREET" in parts and ("BUILDINGNUM" in parts or "CITY" in parts):
                ents.append(mk(text, s, e, "ADDRESS"))
            elif parts == {"CITY"}:
                dropped["CITY"] += 1  # a town on its own is not labelled (keep class)
            else:
                # a street or house number we cannot assemble into a full address: ambiguous label, skip row
                stats["skip_row_ambiguous_address_part_" + sig] += 1
                return None
            continue
        if lab == "_PERSON":
            ents.append(mk(text, s, e, "PERSON"))
        elif lab in DROP:
            dropped[lab] += 1
        elif lab == "DATE":
            if is_dob_context(text, s, e):
                ents.append(mk(text, s, e, "DOB"))
                stats["date_to_dob"] += 1
            else:
                dropped["DATE"] += 1
        elif lab == "SOCIALNUM":
            ents.append(mk(text, s, e, ssn_like_type(val)))
        elif lab in SIMPLE:
            typ = SIMPLE[lab]
            ents.append(mk(text, s, e, typ))
            if r["region"] == "GB":
                if typ == "POSTCODE" and not is_uk_postcode(val):
                    flags.add("postcode_not_full_uk")
                if typ == "PHONE" and not UK_PHONE_LOOSE.match(val):
                    flags.add("phone_not_uk_format")
        else:
            stats["unknown_label_" + lab] += 1
            return None
    for x in ents:
        if not span_ok(x["type"], x["text"]):
            stats["skip_row_broken_span_" + x["type"]] += 1
            return None
    for f in flags:
        stats["gb_rows_flag_" + f] += 1
    meta = {
        "mubit_ok": True,
        "locale": f"en-{r['region']}",
        "source_uid": r["uid"],
        "source_split": r["split"],
        "revision": DATASET["revision"],
        "orig_labels": orig,
        "dropped_labels": dict(dropped),
        "out_of_scope": [],
        "quality_flags": sorted(flags),
    }
    return {"text": text, "entities": ents, "split": "train", "doc_type": "short_message", "meta": meta}
