"""Split documents into chunks of at most ``max_chars`` on paragraph boundaries.

Rules
* Prefer a paragraph break (blank line), then a line break, then a sentence end, then a space,
  looking only in the last 60% of the window so chunks are not tiny.
* Never cut inside an entity span or a keep-trap span: a cut that would land inside one is not a
  candidate, so the boundary moves to the previous safe break (or, as a last resort, to the start of
  the span that would be cut).
* Chunk text is ``doc.text[char_start:char_end]`` with surrounding whitespace trimmed; entity, hard-case
  and keep-trap offsets are relative to the chunk.
"""
from __future__ import annotations

import bisect
import hashlib
import re

from .build import skeleton

MAX_CHARS = 6000
_SEPS = [re.compile(r"\n[ \t]*\n\s*"), re.compile(r"\n"), re.compile(r"(?<=[.!?])\s+"), re.compile(r"[ \t]+")]


class _Guard:
    def __init__(self, spans: list[tuple[int, int]]):
        spans = sorted(spans)
        self.starts = [s for s, _ in spans]
        self.spans = spans
        # running max of ends lets us test "pos is strictly inside any span"
        self.maxend = []
        m = -1
        for _, e in spans:
            m = max(m, e)
            self.maxend.append(m)

    def inside(self, pos: int) -> bool:
        i = bisect.bisect_left(self.starts, pos) - 1  # spans starting strictly before pos
        return i >= 0 and self.maxend[i] > pos

    def span_start_containing(self, pos: int) -> int:
        best = pos
        for s, e in self.spans:
            if s < pos < e:
                best = min(best, s)
            if s >= pos:
                break
        return best


def find_cuts(text: str, spans: list[tuple[int, int]], max_chars: int = MAX_CHARS) -> list[tuple[int, int]]:
    n = len(text)
    guard = _Guard(spans)
    out = []
    start = 0
    while start < n:
        while start < n and text[start].isspace():
            start += 1
        if start >= n:
            break
        if n - start <= max_chars:
            out.append((start, n))
            break
        hi = start + max_chars
        lo = start + int(max_chars * 0.4)
        cut = None
        window = text[lo:hi]
        for sep in _SEPS:
            best = None
            for m in sep.finditer(window):
                c_end = lo + m.start()      # chunk ends before the separator
                c_next = lo + m.end()       # next chunk starts after it
                if c_end <= start or guard.inside(c_end) or guard.inside(c_next):
                    continue
                best = (c_end, c_next)
            if best:
                cut = best
                break
        if cut is None:  # no safe separator: hard cut, moved back to the start of any span it would split
            c = guard.span_start_containing(hi)
            if c <= start:
                c = hi  # a single span longer than max_chars (never happens with our generators)
            cut = (c, c)
        out.append((start, cut[0]))
        start = cut[1]
    # trim trailing whitespace of each chunk
    res = []
    for a, b in out:
        while b > a and text[b - 1].isspace():
            b -= 1
        if b > a:
            res.append((a, b))
    return res


def _rel(items: list[dict], a: int, b: int, clip: bool) -> list[dict]:
    out = []
    for it in items:
        s, e = it["start"], it["end"]
        if s >= a and e <= b:
            d = dict(it)
            d["start"], d["end"] = s - a, e - a
            out.append(d)
        elif clip and s < b and e > a:
            d = dict(it)
            d["start"], d["end"] = max(s, a) - a, min(e, b) - a
            out.append(d)
    return out


def chunk_doc(doc: dict, max_chars: int = MAX_CHARS) -> list[dict]:
    text = doc["text"]
    ents = doc["entities"]
    meta = doc.get("meta", {})
    keep = meta.get("keep_traps", [])
    hard = meta.get("hard_cases", [])
    refs = meta.get("entity_refs", [None] * len(ents))
    spans = [(e["start"], e["end"]) for e in ents] + [(k["start"], k["end"]) for k in keep]
    cuts = find_cuts(text, spans, max_chars)
    chunks = []
    for i, (a, b) in enumerate(cuts):
        idx = [j for j, e in enumerate(ents) if e["start"] >= a and e["end"] <= b]
        c_ents = [{"start": ents[j]["start"] - a, "end": ents[j]["end"] - a, "text": ents[j]["text"],
                   "type": ents[j]["type"]} for j in idx]
        c_text = text[a:b]
        chunks.append({
            "doc_id": doc["doc_id"],
            "chunk_id": f"{doc['doc_id']}-c{i:02d}",
            "text": c_text,
            "entities": c_ents,
            "split": doc.get("split"),
            "doc_type": doc["doc_type"],
            "meta": {
                "session_id": f"doc-{doc['doc_id']}",
                "chunk_index": i,
                "n_chunks": len(cuts),
                "char_start": a,
                "char_end": b,
                "template_id": meta.get("template_id"),
                "variant_id": meta.get("variant_id"),
                "negative": not c_ents,
                "doc_negative": meta.get("negative", False),
                "hard_cases": _rel(hard, a, b, clip=True),
                "keep_traps": _rel(keep, a, b, clip=False),
                "entity_refs": [refs[j] for j in idx],
                "skeleton_hash": hashlib.sha1(skeleton(c_text, c_ents).encode()).hexdigest()[:16],
            },
        })
    total = sum(len(c["entities"]) for c in chunks)
    if total != len(ents):  # every span must land in exactly one chunk
        raise AssertionError(f"{doc['doc_id']}: {len(ents) - total} spans lost by chunker")
    return chunks
