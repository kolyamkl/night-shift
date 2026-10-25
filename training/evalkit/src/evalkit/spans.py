"""Locate predicted values in text.

T1 returns values, not offsets (LLM offsets are unreliable). We find every occurrence in code.
Matching is whitespace-flexible because multi-line addresses and PDF text often differ only in
line breaks or double spaces.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    type: str
    text: str


def _flex_pattern(value: str) -> re.Pattern | None:
    # Split on whitespace and commas: a model may write "Flat 3, 12 Oak Road, Leeds" for an
    # address that sits on three lines with no commas.
    parts = [p for p in re.split(r"[\s,]+", value) if p]
    if not parts:
        return None
    body = r"[\s,]+".join(re.escape(p) for p in parts)
    # Do not match inside a longer word or number: "Will" must not hit "willing", "1234" not "12345".
    return re.compile(rf"(?<![\w]){body}(?![\w])")


def find_all(text: str, value: str) -> list[tuple[int, int]]:
    pat = _flex_pattern(value)
    if pat is None:
        return []
    return [(m.start(), m.end()) for m in pat.finditer(text)]


def locate(text: str, entities: list[dict]) -> list[Span]:
    """Turn [{"text", "type"}] into non-overlapping spans covering every occurrence.

    Longer values win over shorter overlapping ones, so "Oleksandra Kovalenko" is one span even if
    "Kovalenko" was also returned.
    """
    candidates: list[Span] = []
    for ent in entities:
        value = (ent.get("text") or "").strip()
        etype = ent.get("type") or "UNKNOWN"
        for s, e in find_all(text, value):
            candidates.append(Span(s, e, etype, text[s:e]))
    candidates.sort(key=lambda sp: (-(sp.end - sp.start), sp.start))
    taken: list[Span] = []
    for sp in candidates:
        if all(sp.end <= t.start or sp.start >= t.end for t in taken):
            taken.append(sp)
    return sorted(taken, key=lambda sp: sp.start)
