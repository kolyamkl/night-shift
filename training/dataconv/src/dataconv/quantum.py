"""QuantumAiuk/uk-pii-redaction-synthetic -> canonical.

The source is masked-text pairs: user text and the same text with values replaced by [TAG]s. We recover
character spans by aligning the two: the masked text is split into literal pieces and tags, and we search
every way of placing the literals in the original text. An alignment is accepted only when it is the
single one in which every recovered value passes a format check for its tag (and, for the *_meta files,
when the recovered values equal the listed `pii` values). Anything else is skipped and counted.

train + valid -> pool A (split train). test_meta (20 unseen templates) + wild_meta + wild2_meta -> uk_eval.
"""
from __future__ import annotations

import json
import re
from collections import Counter

from .common import RAW, mk

DATASET = {
    "id": "QuantumAiuk/uk-pii-redaction-synthetic",
    "dir": "QuantumAiuk__uk-pii-redaction-synthetic",
    "short": "qauk",
    "license": "Apache-2.0",
    "pool": "A",
    "revision": "750398a543653ca8d26b0765430c563d8f52b1c0",
}

TAG_MAP = {
    "NAME": "PERSON",
    "ADDRESS": "ADDRESS",
    "POSTCODE": "POSTCODE",
    "PHONE": "PHONE",
    "EMAIL": "EMAIL",
    "NI_NUMBER": "NI_NUMBER",
    "NHS_NUMBER": "ID_DOC",  # datagen labelling contract: NHS number is ID_DOC (national, issued to the person)
    "SORT_CODE": "SORT_CODE",
    "ACCOUNT_NUMBER": "BANK_ACCOUNT",
    "DATE_OF_BIRTH": "DOB",
}
TAG_RE = re.compile(r"\[(" + "|".join(TAG_MAP) + r")\]")
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
CHECK = {
    "NAME": re.compile(r"^[^\W\d_][\w'’\-. ]{0,60}$"),
    "ADDRESS": re.compile(r"^(?=.*[^\W\d_]).{4,120}$", re.S),
    "POSTCODE": re.compile(r"^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$", re.I),
    "PHONE": re.compile(r"^\+?[\d ()\-.]{9,20}$"),
    "EMAIL": re.compile(r"^\S+@\S+\.\S+$"),
    "NI_NUMBER": re.compile(r"^[A-Z]{2}[ -]?\d{2}[ -]?\d{2}[ -]?\d{2}[ -]?[A-D]$", re.I),
    "NHS_NUMBER": re.compile(r"^\d{3}[ -]?\d{3}[ -]?\d{4}$"),
    "SORT_CODE": re.compile(r"^\d{2}[- ]?\d{2}[- ]?\d{2}$"),
    "ACCOUNT_NUMBER": re.compile(r"^\d{4} ?\d{4}$"),
    "DATE_OF_BIRTH": re.compile(r"^(?=.*\d)[\w ,./\-]{3,30}$|^(?i:\d{1,2}(st|nd|rd|th)? " + _MONTH + r")$", re.I),
}
MAX_SOLUTIONS = 50


def parse_masked(masked: str):
    lits, tags, pos = [], [], 0
    for m in TAG_RE.finditer(masked):
        lits.append(masked[pos:m.start()])
        tags.append(m.group(1))
        pos = m.end()
    lits.append(masked[pos:])
    return lits, tags


def align(text: str, masked: str):
    """Return the list of all valid alignments: each is [(start, end, tag), ...]."""
    lits, tags = parse_masked(masked)
    if not tags:
        return [[]] if text == masked else []
    if not text.startswith(lits[0]) or not text.endswith(lits[-1]):
        return []
    sols: list[list[tuple[int, int, str]]] = []

    def rec(i: int, pos: int, acc: list):
        if len(sols) > MAX_SOLUTIONS:
            return
        if i == len(tags):
            if pos == len(text):
                sols.append(list(acc))
            return
        nxt = lits[i + 1]
        last = i + 1 == len(tags)
        if last:
            cands = [len(text) - len(nxt)] if len(text) - len(nxt) > pos else []
        elif nxt == "":
            cands = range(pos + 1, len(text) + 1)
        else:
            cands, k = [], text.find(nxt, pos + 1)
            while k != -1:
                cands.append(k)
                k = text.find(nxt, k + 1)
        for k in cands:
            val = text[pos:k]
            if not val or val != val.strip() or not CHECK[tags[i]].match(val):
                continue
            acc.append((pos, k, tags[i]))
            rec(i + 1, k + len(nxt), acc)
            acc.pop()

    rec(0, len(lits[0]), [])
    return sols


def convert_pair(text: str, masked: str, pii: list | None, stats: Counter, subset: str):
    sols = align(text, masked)
    if pii is not None:
        want = Counter((p["type"], p["value"]) for p in pii)
        sols = [s for s in sols if Counter((t, text[a:b]) for a, b, t in s) == want]
    if not sols:
        stats[f"skip_{subset}_no_alignment"] += 1
        return None
    if len(sols) > 1:
        stats[f"skip_{subset}_ambiguous_alignment"] += 1
        return None
    ents = [mk(text, a, b, TAG_MAP[t]) for a, b, t in sols[0]]
    return ents, [[a, b, t] for a, b, t in sols[0]]


def _load(name: str):
    with (RAW / DATASET["dir"] / name).open(encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def convert(stats: Counter):
    for subset, fname in (("train", "train.jsonl"), ("valid", "valid.jsonl")):
        rows = _load(fname)
        stats[f"rows_read_{subset}"] = len(rows)
        for r in rows:
            msgs = {m["role"]: m["content"] for m in r["messages"]}
            out = convert_pair(msgs["user"], msgs["assistant"], None, stats, subset)
            if out is None:
                continue
            yield _rec(msgs["user"], out, subset, "A", "train")
    # test.jsonl and test_meta.jsonl hold the same 200 records; test_meta adds the pii value list
    test_users = [{m["role"]: m["content"] for m in r["messages"]}["user"] for r in _load("test.jsonl")]
    for subset, fname in (("test", "test_meta.jsonl"), ("wild", "wild_meta.jsonl"), ("wild2", "wild2_meta.jsonl")):
        rows = _load(fname)
        stats[f"rows_read_{subset}"] = len(rows)
        if subset == "test":
            stats["test_meta_matches_test_jsonl"] = int([r["text"] for r in rows] == test_users)
        for r in rows:
            out = convert_pair(r["text"], r["reference"], r["pii"], stats, subset)
            if out is None:
                continue
            yield _rec(r["text"], out, subset, "uk_eval", "eval")


def _rec(text, out, subset, pool, split):
    ents, orig = out
    return {
        "text": text,
        "entities": ents,
        "split": split,
        "doc_type": "short_message",
        "meta": {
            "mubit_ok": True,
            "pool": pool,
            "subset": subset,
            "locale": "en-GB",
            "revision": DATASET["revision"],
            "orig_labels": orig,
            "dropped_labels": {},
            "out_of_scope": [],
            "quality_flags": ["offsets_recovered_by_alignment"],
        },
    }
