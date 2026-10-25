"""Shared helpers: canonical record, span validation, overlap resolution, merging, chunking, dedupe.

Canonical document record (see docs/research/2026-10-24-pii-dataset/work/CONTEXT.md):
    {"doc_id", "source", "doc_type", "language", "license", "text", "entities", "split", "meta"}
Every entity is {"start", "end", "text", "type"} with text[start:end] == entity text.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[4]  # repository root
EXT = ROOT / "data" / "external"
RAW = EXT / "raw"

ENTITY_TYPES = (
    "PERSON", "ADDRESS", "POSTCODE", "EMAIL", "PHONE", "BANK_ACCOUNT", "SORT_CODE",
    "IBAN", "CARD", "NI_NUMBER", "DOB", "ID_DOC", "CUSTOM",
)
ENTITY_SET = frozenset(ENTITY_TYPES)
UNTYPED = "UNTYPED"  # RedactionBench only (pool B)

MAX_CHUNK_CHARS = 6000

_WS = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# hashing / slugs
# ---------------------------------------------------------------------------
def norm_hash(text: str) -> str:
    """Exact-duplicate key: case and whitespace insensitive (same rule as datagen.build.norm_hash)."""
    return hashlib.sha1(_WS.sub(" ", text.lower()).strip().encode()).hexdigest()[:16]


def slug(s: str | None, default: str = "document", maxlen: int = 60) -> str:
    if not s:
        return default
    out = re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")
    return (out or default)[:maxlen]


# ---------------------------------------------------------------------------
# format checks used for mapping decisions (not for rejecting values)
# ---------------------------------------------------------------------------
UK_POSTCODE = re.compile(
    r"^(GIR ?0AA|[A-PR-UWYZ](?:[0-9][0-9A-HJKPSTUW]?|[A-HK-Y][0-9][0-9ABEHMNPRV-Y]?) ?[0-9][ABD-HJLNP-UW-Z]{2})$",
    re.I,
)
UK_OUTWARD = re.compile(r"^[A-PR-UWYZ](?:[0-9][0-9A-HJKPSTUW]?|[A-HK-Y][0-9][0-9ABEHMNPRV-Y]?)$", re.I)
NI_SHAPE = re.compile(r"^[A-CEGHJ-PR-TW-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]$", re.I)
UK_PHONE = re.compile(r"^(?:\+44\s?(?:\(0\)\s?)?|0)(?:\d[\s-]?){9,10}$")
BANK_CTX = re.compile(
    r"\b(bank|banking|checking|savings|current account|sort code|iban|bban|routing|deposit|"
    r"direct debit|standing order|wire|transfer|beneficiary|payee|account holder|acct\.? no)\b",
    re.I,
)
DRIVER_CTX = re.compile(r"\b(driv(?:er|ing|ers)['’]?s?\s*licen[cs]e|DL\b|DVLA)", re.I)
DOB_KEY = re.compile(r"(birth|born|\bd\.?o\.?b\b\.?|birthday|bday|b-day|birthdate|DOBs?\b)", re.I)
DOB_AFTER = re.compile(r"^[^.\n]{0,12}\b(birth|birthdate|birthday|born|dob)\b", re.I)
PHONE_EXT = re.compile(r"[,;]?\s*(?:ext\.?|extension|x)\s*\d{1,6}$", re.I)


def is_uk_postcode(s: str) -> bool:
    return bool(UK_POSTCODE.match(s.strip()))


def is_ni_shape(s: str) -> bool:
    return bool(NI_SHAPE.match(s.strip()))


def is_dob_context(text: str, start: int, end: int) -> bool:
    """A date is a DOB when a birth keyword precedes it within 50 chars with no digit or newline in
    between (so another date cannot sit between keyword and value), or a birth keyword follows closely."""
    before = text[max(0, start - 60):start]
    last = None
    for m in DOB_KEY.finditer(before):
        last = m
    if last is not None:
        gap = before[last.end():]
        if len(gap) <= 50 and not re.search(r"[\d\n]", gap):
            return True
    return bool(DOB_AFTER.search(text[end:end + 25]))


def has_bank_context(text: str, start: int, end: int, window: int = 60) -> bool:
    return bool(BANK_CTX.search(text[max(0, start - window):start] + " " + text[end:end + 25]))


def has_driver_context(text: str, start: int, window: int = 50) -> bool:
    return bool(DRIVER_CTX.search(text[max(0, start - window):start]))


def ssn_like_type(value: str) -> str:
    """Social security / national id numbers: NI_NUMBER when the value has the UK NI shape, else ID_DOC."""
    return "NI_NUMBER" if is_ni_shape(value) else "ID_DOC"


# ---------------------------------------------------------------------------
# spans
# ---------------------------------------------------------------------------
def trim(text: str, s: int, e: int) -> tuple[int, int]:
    while s < e and text[s].isspace():
        s += 1
    while e > s and text[e - 1].isspace():
        e -= 1
    return s, e


def mk(text: str, s: int, e: int, typ: str) -> dict:
    return {"start": s, "end": e, "text": text[s:e], "type": typ}


TITLE = re.compile(
    r"^(?:Mr|Mrs|Ms|Miss|Mx|Dr|Prof|Professor|Sir|Dame|Lord|Lady|Rev|Revd|Master|Mister|Madam|Mme|Mlle|"
    r"Herr|Frau|Sr|Sra|MR|MRS|MS|DR)\.?[ \t]+")
POSSESSIVE = re.compile(r"['’]s$")


def person_bounds(text: str, s: int, e: int) -> tuple[int, int]:
    """Our PERSON convention: titles and possessive 's stay outside the span."""
    m = TITLE.match(text, s, e)
    if m and m.end() < e:
        s = m.end()
    m = POSSESSIVE.search(text, s, e)
    if m and m.start() > s:
        e = m.start()
    return trim(text, s, e)


_DIGITS = re.compile(r"\d")


def span_ok(typ: str, val: str) -> bool:
    """Cheap sanity checks: a span that fails is a broken source label (the row is skipped)."""
    nd = len(_DIGITS.findall(val))
    if typ == "EMAIL":
        # plain, spaced ("a @ b.com") or spelled-out ("a at b dot com") addresses; never multi-line
        return "\n" not in val and (bool(re.fullmatch(r"\S+ ?@ ?\S+", val)) or bool(re.search(r"\bat\b.*\bdot\b", val)))
    if typ == "PHONE":
        return nd >= 7 and "@" not in val
    if typ == "CARD":
        return nd >= 4
    if typ == "IBAN":
        return bool(re.match(r"^[A-Z]{2}\d{2}", val.replace(" ", "")))
    if typ == "PERSON":
        return bool(re.search(r"[^\W\d_]", val)) and nd == 0 and "@" not in val and len(val.split()) <= 8 and "\n" not in val
    if typ == "POSTCODE":
        return nd >= 1 and "\n" not in val and len(val) <= 12
    if typ in ("SORT_CODE", "BANK_ACCOUNT", "NI_NUMBER"):
        return nd >= 2 and "\n" not in val
    if typ == "DOB":
        return (nd >= 1 or bool(re.search(r"(?i)jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec", val))) and "\n" not in val
    if typ in ("ID_DOC", "CUSTOM"):
        return nd >= 1 and "\n" not in val and len(val) <= 60
    if typ == "ADDRESS":
        return bool(re.search(r"[^\W\d_]", val)) and "@" not in val
    return True


def resolve_overlaps(spans: list[dict], log: Counter | None = None) -> list[dict]:
    """Keep non-overlapping spans; on overlap keep the longer (ties: the earlier). Logs drops."""
    order = sorted(spans, key=lambda x: (-(x["end"] - x["start"]), x["start"]))
    kept: list[dict] = []
    for sp in order:
        if any(sp["start"] < k["end"] and k["start"] < sp["end"] for k in kept):
            if log is not None:
                log["overlap_dropped_" + sp["type"]] += 1
            continue
        kept.append(sp)
    kept.sort(key=lambda x: (x["start"], x["end"]))
    return kept


def merge_runs(text: str, spans: list[dict], key: str, members: set[str], gap: re.Pattern) -> list[dict]:
    """Merge consecutive spans whose ``span[key]`` is in ``members`` and whose gap text matches ``gap``.

    Input spans are dicts with start/end and ``key``; output keeps non-members unchanged and turns each
    run of members into one dict {start, end, parts: [labels...]}.
    """
    spans = sorted(spans, key=lambda x: (x["start"], x["end"]))
    out: list[dict] = []
    for sp in spans:
        if sp[key] in members and out and out[-1].get("_run") and gap.fullmatch(text[out[-1]["end"]:sp["start"]]):
            out[-1]["end"] = sp["end"]
            out[-1]["parts"].append(sp[key])
        elif sp[key] in members:
            out.append({"start": sp["start"], "end": sp["end"], "parts": [sp[key]], "_run": True})
        else:
            out.append(dict(sp))
    return out


def validate_doc(doc: dict, allowed: frozenset = ENTITY_SET, strip_check: bool = True) -> list[str]:
    errs = []
    text = doc["text"]
    prev_end = -1
    for e in doc["entities"]:
        s, t = e["start"], e["end"]
        if not (isinstance(s, int) and isinstance(t, int) and 0 <= s < t <= len(text)):
            errs.append(f"bad offsets {e}")
            continue
        if text[s:t] != e["text"]:
            errs.append(f"text mismatch {text[s:t]!r} != {e['text']!r}")
        if e["type"] not in allowed:
            errs.append(f"bad type {e['type']}")
        if s < prev_end:
            errs.append(f"overlap at {s}")
        prev_end = max(prev_end, t)
        if strip_check and e["text"] != e["text"].strip():
            errs.append(f"padded span {e['text']!r}")
    return errs


def record(doc_id: str, source: str, doc_type: str, license_id: str, text: str, entities: list[dict],
           split: str, meta: dict, language: str = "en") -> dict:
    return {
        "doc_id": doc_id, "source": source, "doc_type": doc_type, "language": language,
        "license": license_id, "text": text, "entities": entities, "split": split, "meta": meta,
    }


# ---------------------------------------------------------------------------
# chunking: <= ~6,000 chars, paragraph boundaries first, never cut a span
# ---------------------------------------------------------------------------
_CUTS = (
    (re.compile(r"\n[ \t]*\n"), 0.4),   # paragraph break
    (re.compile(r"\n"), 0.3),           # line break
    (re.compile(r"(?<=[.!?;])\s"), 0.3),  # sentence end
    (re.compile(r"\s"), 0.2),           # any whitespace
)


def _inside_span(p: int, spans: list[tuple[int, int]]) -> bool:
    return any(s < p < e for s, e in spans)


def chunk_bounds(text: str, entities: list[dict], max_chars: int = MAX_CHUNK_CHARS) -> list[tuple[int, int]]:
    spans = [(e["start"], e["end"]) for e in entities]
    n = len(text)
    out = []
    a = 0
    while n - a > max_chars:
        hi = a + max_chars
        cut = None
        for pat, min_frac in _CUTS:
            lo = a + int(max_chars * min_frac)
            best = None
            for m in pat.finditer(text, lo, hi + 1):
                p = m.end()
                if p <= hi and not _inside_span(p, spans):
                    best = p
            if best is not None and best > a:
                cut = best
                break
        if cut is None:  # hard cut; move back to the start of any span it would split
            cut = hi
            for s, e in spans:
                if s < cut < e:
                    cut = s
            if cut <= a:  # a single span longer than max_chars: keep it whole
                cut = max(e for s, e in spans if s < hi < e)
        out.append((a, cut))
        a = cut
    out.append((a, n))
    return [(x, y) for x, y in out if text[x:y].strip()]


def chunk_doc(doc: dict, max_chars: int = MAX_CHUNK_CHARS) -> list[dict]:
    chunks = []
    for i, (a, b) in enumerate(chunk_bounds(doc["text"], doc["entities"], max_chars)):
        ents = [
            {"start": e["start"] - a, "end": e["end"] - a, "text": e["text"], "type": e["type"]}
            for e in doc["entities"] if a <= e["start"] and e["end"] <= b
        ]
        chunks.append({
            "doc_id": doc["doc_id"],
            "chunk_id": f"{doc['doc_id']}-c{i:02d}",
            "text": doc["text"][a:b],
            "entities": ents,
            "split": doc["split"],
            "doc_type": doc["doc_type"],
            "meta": {"char_start": a, "char_end": b, "source": doc["source"],
                     "mubit_ok": doc["meta"]["mubit_ok"], "license": doc["license"]},
        })
    return chunks


# ---------------------------------------------------------------------------
# io
# ---------------------------------------------------------------------------
def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def type_counts(docs: Iterable[dict]) -> dict:
    c = Counter()
    for d in docs:
        for e in d["entities"]:
            c[e["type"]] += 1
    return dict(c.most_common())
