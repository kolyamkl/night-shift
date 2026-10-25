#!/usr/bin/env python3
"""Validate data/docs/*.jsonl against the documents schema and labelling rules.

Errors (exit code 1): anything that would make the answer key wrong or break
the pipeline, such as bad offsets, overlapping entities, an eval source in
train, a leftover slot marker or an unlabelled email address.

Warnings (printed, exit code unaffected): likely labelling misses found by a
regex sweep (phone numbers, IBANs, postcodes and similar outside any entity)
and small schema oddities. Review them; they are not proof of a bug.

Usage:
    python training/rewrite/validate_docs.py [--docs-dir data/docs]
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from dataset_common import (
    DOCS_DIR,
    ENTITY_TYPES,
    EVAL_SOURCES,
    FILLED_SOURCES,
    GROUPS,
    PLACEHOLDER_RE,
    PROVENANCE_KINDS,
    SPLITS,
    expected_group,
    expected_split,
    is_gretel,
    normalise_placeholder,
    read_jsonl,
)

REQUIRED_FIELDS = ("doc_id", "source_id", "group", "subtype", "split", "fill", "text", "entities", "provenance")
OPTIONAL_FIELDS = ("hard_cases",)
ENTITY_FIELDS = ("start", "end", "type", "value", "entity_id")
SUBTYPE_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
SLOT_MARKER_RE = re.compile(r"\{\{|\}\}|\{%|%\}")
POSSESSIVE_RE = re.compile(r"['’]s?$")

# Regex sweep for personal values that no entity covers.
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
SWEEP_PATTERNS = {
    "PHONE": re.compile(r"(?<![\w-])(?:\+44\s?\(?0?\)?\s?\d{2,4}|\(?0\d{2,4}\)?)[\s-]?\d{3,4}[\s-]?\d{3,4}(?![\w-])"),
    "IBAN": re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,3})?\b"),
    # Any two letters, so the never-issued QQ prefix used for fake values is caught too.
    "NI_NUMBER": re.compile(r"\b[A-Z]{2} ?\d{2} ?\d{2} ?\d{2} ?[A-D]\b"),
    "POSTCODE": re.compile(r"\b(?:GIR ?0AA|[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2})\b"),
    "SORT_CODE": re.compile(r"(?<![\d-])\d{2}-\d{2}-\d{2}(?![\d-])"),
    "CARD": re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"),
}


def luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def is_int(x: object) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, where: str, msg: str) -> None:
        self.errors.append(f"ERROR   {where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"WARNING {where}: {msg}")


def check_entities(doc: dict, where: str, rep: Report) -> None:
    text = doc["text"]
    entities = doc["entities"]
    prev_start, prev_end = -1, 0
    types_by_id: dict[str, set[str]] = defaultdict(set)
    for i, ent in enumerate(entities):
        ew = f"{where} entity[{i}]"
        if not isinstance(ent, dict):
            rep.error(ew, "is not an object")
            continue
        missing = [k for k in ENTITY_FIELDS if k not in ent]
        if missing:
            rep.error(ew, f"missing field(s) {', '.join(missing)}")
            continue
        extra = sorted(set(ent) - set(ENTITY_FIELDS))
        if extra:
            rep.warn(ew, f"unknown field(s) {', '.join(extra)}")
        start, end, etype, value, eid = (ent[k] for k in ENTITY_FIELDS)
        if not (is_int(start) and is_int(end)):
            rep.error(ew, f"start and end must be integers, got {start!r} and {end!r}")
            continue
        if etype not in ENTITY_TYPES:
            rep.error(ew, f"unknown type {etype!r}; allowed: {', '.join(ENTITY_TYPES)}")
        if not isinstance(value, str) or not value:
            rep.error(ew, "value must be a non-empty string")
            continue
        if not isinstance(eid, str) or not eid:
            rep.error(ew, "entity_id must be a non-empty string")
            continue
        if not (0 <= start < end <= len(text)):
            rep.error(ew, f"offsets [{start}, {end}) outside text of length {len(text)}")
            continue
        if text[start:end] != value:
            rep.error(ew, f"text[{start}:{end}] is {text[start:end]!r} but value is {value!r}")
            continue
        if value != value.strip():
            rep.error(ew, f"value {value!r} has leading or trailing whitespace")
        if etype == "PERSON" and POSSESSIVE_RE.search(value) and len(value) > 2:
            rep.error(ew, f"PERSON value {value!r} ends with a possessive; keep \"'s\" outside the entity")
        if start < prev_start:
            rep.error(ew, f"entities not sorted by start ({start} after {prev_start})")
        elif start < prev_end:
            rep.error(ew, f"overlaps the previous entity (starts at {start}, previous ends at {prev_end})")
        prev_start, prev_end = start, max(prev_end, end)
        if etype in ENTITY_TYPES:
            types_by_id[eid].add(etype)
    for eid, types in types_by_id.items():
        if len(types) > 1:
            rep.error(where, f"entity_id {eid!r} is used with several types: {', '.join(sorted(types))}")


def covered(spans: list[tuple[int, int, str]], start: int, end: int, etype: str | None = None) -> bool:
    """True if [start, end) is inside one entity (of etype, when given)."""
    return any(s <= start and end <= e and (etype is None or t == etype) for s, e, t in spans)


def overlaps_any(spans: list[tuple[int, int, str]], start: int, end: int) -> bool:
    return any(s < end and start < e for s, e, _ in spans)


def sweep_unlabelled(doc: dict, where: str, rep: Report) -> None:
    text = doc["text"]
    spans = [
        (e["start"], e["end"], e["type"])
        for e in doc["entities"]
        if isinstance(e, dict) and is_int(e.get("start")) and is_int(e.get("end"))
    ]
    for m in EMAIL_RE.finditer(text):
        if not covered(spans, m.start(), m.end(), "EMAIL"):
            rep.error(where, f"email address {m.group()!r} at {m.start()} is not labelled as an EMAIL entity")
    for etype, rx in SWEEP_PATTERNS.items():
        for m in rx.finditer(text):
            if overlaps_any(spans, m.start(), m.end()):
                continue
            if etype == "CARD":
                digits = re.sub(r"\D", "", m.group())
                if not (13 <= len(digits) <= 19 and luhn_ok(digits)):
                    continue
            rep.warn(where, f"possible unlabelled {etype} {m.group()!r} at {m.start()}")


def check_doc(doc: object, where: str, rep: Report) -> bool:
    """Check one document. Returns False if it is too broken for further checks."""
    if not isinstance(doc, dict):
        rep.error(where, "line is not a JSON object")
        return False
    missing = [k for k in REQUIRED_FIELDS if k not in doc]
    if missing:
        rep.error(where, f"missing field(s) {', '.join(missing)}")
        return False
    extra = sorted(set(doc) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS))
    if extra:
        rep.warn(where, f"unknown field(s) {', '.join(extra)} (ignored by the pipeline)")

    ok = True
    for key in ("doc_id", "source_id", "subtype", "text"):
        if not isinstance(doc[key], str) or not doc[key]:
            rep.error(where, f"{key} must be a non-empty string")
            ok = False
    if not isinstance(doc["entities"], list):
        rep.error(where, "entities must be a list")
        ok = False
    if not ok:
        return False

    source_id, group, split, fill = doc["source_id"], doc["group"], doc["split"], doc["fill"]
    gretel = is_gretel(source_id)
    if not gretel and source_id not in FILLED_SOURCES:
        rep.error(where, f"unknown source_id {source_id!r}; expected C1..C12, R1..R11, INS1, INS2 or gretel-<row id>")
    if group not in GROUPS:
        rep.error(where, f"unknown group {group!r}; allowed: {', '.join(GROUPS)}")
    elif group not in expected_group(source_id):
        rep.error(where, f"source {source_id} cannot be in group {group!r}; expected {' or '.join(expected_group(source_id))}")
    if not SUBTYPE_RE.match(doc["subtype"]):
        rep.error(where, f"subtype {doc['subtype']!r} is not a lower-case slug")
    if split not in SPLITS:
        rep.error(where, f"unknown split {split!r}; allowed: {', '.join(SPLITS)}")
    if not is_int(fill):
        rep.error(where, f"fill must be an integer, got {fill!r}")
    elif gretel and fill != 0:
        rep.error(where, f"Gretel documents must have fill 0, got {fill}")
    elif not gretel and not 1 <= fill <= 5:
        rep.error(where, f"filled sources must have fill 1..5, got {fill}")
    elif split in SPLITS:
        want = expected_split(source_id, fill)
        if want is not None and split != want:
            why = "eval source" if source_id in EVAL_SOURCES else f"fill {fill}"
            rep.error(where, f"split is {split!r} but {source_id} ({why}) must be {want!r}")

    hard_cases = doc.get("hard_cases")
    if hard_cases is not None and not (isinstance(hard_cases, list) and all(isinstance(h, str) for h in hard_cases)):
        rep.error(where, "hard_cases must be a list of strings")

    prov = doc["provenance"]
    if not isinstance(prov, dict):
        rep.error(where, "provenance must be an object")
    else:
        for key in ("url", "licence", "kind"):
            if not isinstance(prov.get(key), str) or not prov.get(key):
                rep.error(where, f"provenance.{key} must be a non-empty string")
        if prov.get("kind") not in PROVENANCE_KINDS:
            rep.error(where, f"provenance.kind {prov.get('kind')!r} not one of {', '.join(PROVENANCE_KINDS)}")
        elif gretel and prov["kind"] != "synthetic":
            rep.warn(where, f"Gretel document with provenance.kind {prov['kind']!r}; expected 'synthetic'")

    text = doc["text"]
    for m in SLOT_MARKER_RE.finditer(text):
        rep.error(where, f"leftover slot marker {m.group()!r} at {m.start()}: {text[max(0, m.start() - 20):m.end() + 20]!r}")
    for m in PLACEHOLDER_RE.finditer(text):
        if normalise_placeholder(m.group(1), m.group(2)) in ENTITY_TYPES:
            rep.error(where, f"text contains placeholder-like token {m.group()!r} at {m.start()}; the scorer would misread it")
    if "\r" in text:
        rep.warn(where, "text contains \\r; use \\n line breaks")

    check_entities(doc, where, rep)
    sweep_unlabelled(doc, where, rep)
    return True


def validate(docs_dir: Path) -> tuple[Report, list[dict]]:
    rep = Report()
    paths = sorted(docs_dir.glob("*.jsonl"))
    if not paths:
        rep.error(str(docs_dir), "no *.jsonl files found")
        return rep, []
    good: list[dict] = []
    seen_ids: dict[str, str] = {}
    seen_fills: dict[tuple[str, int], str] = {}
    for path in paths:
        try:
            lines = list(read_jsonl(path))
        except ValueError as e:
            rep.error(str(path), str(e))
            continue
        for lineno, doc in lines:
            doc_id = doc.get("doc_id") if isinstance(doc, dict) else None
            where = f"{path.name}:{lineno} ({doc_id})"
            if not check_doc(doc, where, rep):
                continue
            if doc_id in seen_ids:
                rep.error(where, f"duplicate doc_id, first seen at {seen_ids[doc_id]}")
            seen_ids[doc_id] = where
            if not is_gretel(doc["source_id"]) and is_int(doc["fill"]):
                key = (doc["source_id"], doc["fill"])
                if key in seen_fills:
                    rep.error(where, f"{key[0]} fill {key[1]} already used by {seen_fills[key]}")
                seen_fills[key] = where
            if path.stem in GROUPS and doc["group"] != path.stem:
                rep.warn(where, f"group {doc['group']!r} stored in {path.name}")
            good.append(doc)
    return rep, good


def summary(docs: list[dict]) -> str:
    by_split = Counter(d["split"] for d in docs)
    by_group = Counter(d["group"] for d in docs)
    n_ent = sum(len(d["entities"]) for d in docs)
    gretel = Counter(d["split"] for d in docs if is_gretel(d["source_id"]))
    parts = [
        f"{len(docs)} documents, {n_ent} entities",
        "splits: " + ", ".join(f"{s} {by_split.get(s, 0)}" for s in SPLITS),
        "groups: " + ", ".join(f"{g} {by_group.get(g, 0)}" for g in GROUPS),
    ]
    if gretel:
        total = sum(gretel.values())
        parts.append(
            "Gretel by split: "
            + ", ".join(f"{s} {gretel.get(s, 0)} ({100 * gretel.get(s, 0) / total:.0f}%)" for s in SPLITS)
            + " (target about 50/30/20)"
        )
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--docs-dir", type=Path, default=DOCS_DIR)
    ap.add_argument("--max-warnings", type=int, default=200, help="print at most this many warnings (default 200)")
    args = ap.parse_args(argv)

    rep, docs = validate(args.docs_dir)
    for w in rep.warnings[: args.max_warnings]:
        print(w)
    if len(rep.warnings) > args.max_warnings:
        print(f"... {len(rep.warnings) - args.max_warnings} more warnings not shown")
    for e in rep.errors:
        print(e)
    if docs:
        print(summary(docs))
    print(f"{len(rep.errors)} error(s), {len(rep.warnings)} warning(s)")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
