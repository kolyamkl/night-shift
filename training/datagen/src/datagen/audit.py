"""Label audit: look for personal data that is in the text but NOT inside any gold span.

Regex detectors (email, postcode, UK phone, sort code, NI number, IBAN, long digit runs) and a
name detector (first names and surnames from the generator's own pools, capitalised, outside
spans and outside keep traps) are run over the unlabelled parts of every document. Every hit is
either a generator bug (missed label) or a legitimate keep trap, so the report is reviewed by hand.

    uv run python -m datagen.audit --docs ../../data/synthetic/docs.jsonl --limit 20000
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from . import names

DETECTORS = {
    "EMAIL": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "POSTCODE": re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]? ?\d[ABD-HJLNP-UW-Z]{2}\b", re.I),
    "PHONE": re.compile(r"(?<![\w/])(?:\+44\s?(?:\(0\)\s?)?|\(?0)\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}\b"),
    "SORT_CODE": re.compile(r"\b\d{2}-\d{2}-\d{2}\b"),
    "NI_NUMBER": re.compile(r"\b[A-CEGHJ-PR-TW-Z]{2} ?\d{2} ?\d{2} ?\d{2} ?[A-D]\b"),
    "IBAN": re.compile(r"\bGB\d{2} ?[A-Z]{4}(?: ?\d){14}\b"),
    "DIGITS8+": re.compile(r"(?<![\d.,£])\d{8,19}(?![\d.])"),
    "STREET": re.compile(r"\b\d{1,3}[A-Z]? [A-Z][a-z']+(?: [A-Z][a-z']+)? (?:Road|Street|Lane|Avenue|Close|Crescent|"
                         r"Drive|Grove|Way|Terrace|Gardens|Place|Mews|Rise|Walk|Court|Square|Row|Parade|View)\b"),
    "DOB_CUE": re.compile(r"(?:\bborn(?: on)?|\bDOB|[Dd]ate of [Bb]irth|D\.O\.B\.?)[:\s]+\d{1,2}[/. -]\d{1,2}[/. -]\d{2,4}"),
}
_STOP = {"Will", "Rose", "Mark", "Grace", "Hope", "May", "Bill", "Joy", "Faith", "Frank", "Holly", "Ivy", "Dawn",
         "Penny", "Summer", "Amber", "Iris", "Heather", "Ruby", "June", "April", "Sue", "Pearl", "Daisy", "Miles",
         "Guy", "Ray", "Rich", "Drew", "Jack", "Robin", "Pat", "Sonny", "Victor", "Art", "Baker", "Green", "White",
         "Wood", "Hill", "Bell", "King", "Young", "Moss", "Rice", "Hall", "Stone", "Cook", "Bishop", "Church",
         "Marsh", "Fox", "Banks", "Brook", "Mills", "Lane", "Field", "Bird", "Sharp", "Park", "Victoria", "Chester",
         "Lincoln", "Grove", "Ash", "Lee", "Long", "Little", "Price", "Major", "Black", "Hunt", "Page", "Rose",
         "Read", "Booth", "Wells", "Nash", "Gill", "Chan", "Li", "Ng", "Ali", "Shah", "Singh", "Kaur", "Wing",
         "Ward", "North", "West", "South", "Brown", "Spencer", "Lloyd", "Lloyds", "Barclay", "Barclays", "Sage",
         "Morgan", "Lewis", "John", "Ross", "Next", "Boots", "Morrison", "Morrisons", "Sainsbury", "Jordan",
         "Austin", "Florence", "Charlotte", "Sydney", "Chelsea", "Kent", "Devon", "Clifton", "Stanley", "Albert",
         "Nelson", "Wellington", "Cromwell", "Gladstone", "Thornton", "Lancaster", "Clarence", "Cavendish",
         "Grosvenor", "Osborne", "Windsor", "York", "Marlborough", "Highfield", "Fairfield", "Belmont", "Holbeck",
         "Kingsway", "Granby", "Mercury", "Bristol", "Leeds", "Watson", "Oak", "Elm", "Cedar", "Beech",
         "Willow", "Lime", "Rowan", "Heron", "Kestrel", "Hawthorn", "Primrose", "Laburnum", "Bramble", "Foxglove",
         "Sandringham", "Balmoral", "Devonshire", "Coronation", "Jubilee", "Alexandra", "Duncan", "Russell",
         # surnames that are also everyday words in headings and labels
         "Day", "Case", "Lord", "Love", "Best", "Bond", "Gold", "Golden", "Silver", "Frost", "Snow", "Winter",
         "Summers", "Spring", "Glass", "Dean", "Knight", "Power", "Law", "Hale", "Short", "Strong", "Swift",
         "Wise", "Noble", "Moon", "Star", "Pope", "Nurse", "Doctor", "Gardener", "Head", "Read"}


def name_vocab() -> set[str]:
    v = set()
    for o in names.ORIGINS.values():
        for k in ("m", "f", "l"):
            for n in o[k]:
                for part in n.replace("-", " ").split():
                    if len(part) > 2 and part[0].isupper():
                        v.add(part)
    v |= set(names.COMMON_WORD_F) | set(names.COMMON_WORD_M)
    from . import world
    org_words = set()
    for nm in [o.name for o in world.SYNTH_ORGS] + world.ALL_PUBLIC + world.PRODUCTS + world.HOSPITAL_TRUSTS \
            + world.COUNCILS + world.TOWN_NAMES + world._CO_WORDS + world._CO_TRADES + world._BUILDINGS \
            + world._STREET_STEMS:
        org_words |= set(nm.replace("-", " ").split())
    return v - _STOP - org_words


_WORD = re.compile(r"[A-ZÁÉÍÓÚŁŚŻ][\w'’áéíóúłśżąęćń-]+")


def unlabelled_regions(rec: dict) -> list[tuple[int, int]]:
    """Text regions outside entity spans and outside keep traps."""
    cover = [(e["start"], e["end"]) for e in rec["entities"]]
    cover += [(k["start"], k["end"]) for k in rec["meta"].get("keep_traps", [])]
    cover.sort()
    out, pos = [], 0
    for s, e in cover:
        if s > pos:
            out.append((pos, s))
        pos = max(pos, e)
    if pos < len(rec["text"]):
        out.append((pos, len(rec["text"])))
    return out


def audit_record(rec: dict, vocab: set[str]) -> list[tuple[str, str]]:
    hits = []
    text = rec["text"]
    for a, b in unlabelled_regions(rec):
        seg = text[a:b]
        for name, rx in DETECTORS.items():
            for m in rx.finditer(seg):
                hits.append((name, m.group()))
        for m in _WORD.finditer(seg):
            w = m.group().rstrip("'’s").rstrip("'’")
            if w in vocab:
                hits.append(("NAME?", w))
    return hits


def run(docs: Path, limit: int | None = None, examples: int = 6) -> dict:
    vocab = name_vocab()
    by_kind = Counter()
    by_dt = defaultdict(Counter)
    ex = defaultdict(list)
    n = 0
    for line in open(docs, encoding="utf-8"):
        rec = json.loads(line)
        n += 1
        for kind, val in audit_record(rec, vocab):
            by_kind[kind] += 1
            by_dt[rec["doc_type"]][kind] += 1
            if len(ex[(rec["doc_type"], kind)]) < examples:
                i = rec["text"].find(val)
                ctx = rec["text"][max(0, i - 50): i + len(val) + 30].replace("\n", "\\n")
                ex[(rec["doc_type"], kind)].append(f"{rec['doc_id']}: {val!r} ... {ctx}")
        if limit and n >= limit:
            break
    return {"docs": n, "by_kind": by_kind, "by_doc_type": by_dt, "examples": ex}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--docs", type=Path, default=Path("../../data/synthetic/docs.jsonl"))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--examples", type=int, default=4)
    a = ap.parse_args(argv)
    r = run(a.docs, a.limit, a.examples)
    print(f"audited {r['docs']} docs; unlabelled hits by detector: {dict(r['by_kind'])}")
    for dt, c in sorted(r["by_doc_type"].items()):
        print(f"  {dt}: {dict(c)}")
    for (dt, kind), xs in sorted(r["examples"].items()):
        print(f"--- {dt} / {kind}")
        for x in xs:
            print("   ", x[:220])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
