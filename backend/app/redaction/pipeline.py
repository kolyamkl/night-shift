"""Find personal data in a Document and turn it into placeholders and page rectangles.

1. Regex layer over the whole text (detectors/: cards, accounts, sort codes, IBAN, NI, postcodes,
   phones, emails, client, policy, claim and case references after their label, IP addresses, UUIDs).
2. T1 (the Mubit-trained model) per chunk; every value it returns is then located across the WHOLE
   document, so a name found in chunk 2 is hidden in chunk 5 too.
3. Overlapping spans are merged into one, so a regex hit is never uncovered by a shorter model span.
   Each ADDRESS span then takes in the flat, building and town next to it (addresses.py).
4. A per-document vault gives each distinct value one placeholder; PDF words that overlap a span
   become one rectangle per line.

run_pipeline can report progress through `emit(name, data)`: "start" (the chunk plan), "regex" (the
regex hits), then one "chunk" per chunk in the order they finish. The API streams these as events.
Given an earlier result with the same plan (`reuse`), it calls T1 only for the chunks that failed.
"""

import logging
import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.logging import log_event
from app.redaction import addresses, detectors
from app.redaction.document import Document, Word
from app.redaction.spans import Entity, Span, locate, merge
from app.redaction.vault import Vault, apply

MAX_CHARS = 4000  # about 1,000 tokens per T1 call

log = logging.getLogger("veil.pipeline")
Emit = Callable[[str, dict[str, Any]], None]


@dataclass
class T1Result:
    entities: list[Entity]
    mreq_id: str | None
    error: str | None


T1 = Callable[[str], T1Result]  # one T1 call: a chunk in, the values it holds out


@dataclass
class ChunkInfo:
    index: int
    chunk_id: str
    start: int
    end: int
    status: str  # "ok", "error", "empty" (whitespace only, no call) or "off" (no model, no call)
    error: str | None = None
    mreq_id: str | None = None
    latency_ms: int | None = None
    found: int = 0  # how many values T1 returned for this chunk


@dataclass
class Box:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    type: str
    placeholder: str
    span_index: int


@dataclass
class PipelineResult:
    spans: list[Span]
    redacted_text: str
    vault: Vault
    boxes: list[Box]
    chunks: list[ChunkInfo]
    stats: dict[str, int] = field(default_factory=dict)
    model_values: dict[str, str] = field(default_factory=dict)  # what T1 returned: value -> type
    hidden: dict[str, str] = field(default_factory=dict)  # reviewer: value -> type to hide
    unhidden: set[str] = field(default_factory=set)  # reviewer: values to show
    chunk_values: list[list[Entity]] = field(default_factory=list)  # what T1 returned per chunk, by index
    plan: str = ""  # what set the chunk plan (the T1 prompt); a retry reuses chunks only under the same plan


def chunk_ranges(text: str, max_chars: int = MAX_CHARS) -> list[tuple[int, int]]:
    """Paragraph-based chunks of at most max_chars; a longer paragraph is cut at a line break or space."""
    ranges: list[tuple[int, int]] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + max_chars)
        if end < n:
            for sep in ("\n\n", "\n", " "):
                cut = text.rfind(sep, start + 1, end)
                if cut > start:
                    end = cut + len(sep)
                    break
        ranges.append((start, end))
        start = end
    return ranges or [(0, 0)]


def _boxes(doc: Document, spans: list[Span], vault: Vault) -> list[Box]:
    boxes: list[Box] = []
    for i, sp in enumerate(spans):
        ph = vault.placeholder_for(sp.text, sp.type)
        by_line: dict[tuple[int, int, int], list[Word]] = {}
        for w in doc.words:
            if w.start < sp.end and sp.start < w.end:
                by_line.setdefault(w.line, []).append(w)
        for line_words in by_line.values():
            boxes.append(Box(
                page=line_words[0].page,
                x0=min(w.bbox[0] for w in line_words), y0=min(w.bbox[1] for w in line_words),
                x1=max(w.bbox[2] for w in line_words), y1=max(w.bbox[3] for w in line_words),
                type=sp.type, placeholder=ph, span_index=i,
            ))
    return boxes


def _entity(sp: Span, source: str, offset: int = 0) -> dict[str, Any]:
    return {"start": sp.start + offset, "end": sp.end + offset, "text": sp.text, "type": sp.type, "source": source}


REUSABLE = ("ok", "empty")


def _reusable(prev: PipelineResult | None, plan: str, ranges: list[tuple[int, int]]
              ) -> dict[int, tuple[ChunkInfo, list[Entity]]]:
    """Chunks of an earlier run that need no new T1 call: same plan and ranges, status ok or empty."""
    if (prev is None or prev.plan != plan or len(prev.chunk_values) != len(prev.chunks)
            or [(c.start, c.end) for c in prev.chunks] != ranges):
        return {}
    return {c.index: (c, prev.chunk_values[c.index]) for c in prev.chunks if c.status in REUSABLE}


def run_pipeline(doc: Document, t1: T1 | None, max_chars: int = MAX_CHARS,
                 workers: int = 6, emit: Emit | None = None, plan: str = "",
                 reuse: PipelineResult | None = None, stop: Callable[[], bool] | None = None,
                 corrections: PipelineResult | None = None) -> PipelineResult:
    """`reuse`: an earlier result of this document; its ok and empty chunks are kept (no T1 call) when
    its plan and chunk ranges match. `stop`: once it returns True, chunks not yet started make no call.
    Reviewer decisions come from `corrections` (or `reuse`), independently of chunk reuse."""
    text = doc.text
    ranges = chunk_ranges(text, max_chars)
    ids = [f"{doc.doc_id}-c{i:02d}" for i in range(len(ranges))]
    kept = _reusable(reuse, plan, ranges)
    if emit:
        emit("start", {"chunks": [{"index": i, "chunk_id": ids[i], "start": s, "end": e}
                                  for i, (s, e) in enumerate(ranges)]})
        emit("regex", {"entities": [_entity(sp, "regex") for sp in detectors.detect(text)]})

    def run_chunk(i: int) -> tuple[ChunkInfo, list[Entity]]:
        s, e = ranges[i]
        if t1 is None:
            return ChunkInfo(i, ids[i], s, e, "off", "model off"), []
        if not text[s:e].strip():
            return ChunkInfo(i, ids[i], s, e, "empty"), []
        if stop is not None and stop():
            return ChunkInfo(i, ids[i], s, e, "error", "stopped: a newer scan of this document started"), []
        t0 = time.monotonic()
        try:
            r = t1(text[s:e])
        except Exception as exc:  # noqa: BLE001 - one bad chunk must not stop the document
            ms = round((time.monotonic() - t0) * 1000)
            return ChunkInfo(i, ids[i], s, e, "error", f"{type(exc).__name__}: {exc}", latency_ms=ms), []
        ms = round((time.monotonic() - t0) * 1000)
        if r.error:
            return ChunkInfo(i, ids[i], s, e, "error", r.error, r.mreq_id, ms), []
        return ChunkInfo(i, ids[i], s, e, "ok", None, r.mreq_id, ms, found=len(r.entities)), r.entities

    finished: dict[int, tuple[ChunkInfo, list[Entity]]] = {}

    def report(info: ChunkInfo, ents: list[Entity], reused: bool) -> None:
        finished[info.index] = (info, ents)
        # Metadata only: never the chunk text or the values.
        log_event(log, "t1_chunk", doc=doc.doc_id, index=info.index, status=info.status,
                  latency_ms=info.latency_ms, mreq=info.mreq_id, found=info.found, reused=reused)
        if emit:
            hits = locate(text[info.start:info.end], ents)
            emit("chunk", {**asdict(info), "entities": [_entity(sp, "model", info.start) for sp in hits]})

    for i in sorted(kept):
        report(*kept[i], reused=True)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        todo = [pool.submit(run_chunk, i) for i in range(len(ranges)) if i not in kept]
        for fut in as_completed(todo):
            report(*fut.result(), reused=False)
    chunks = [finished[i][0] for i in range(len(ranges))]
    chunk_values = [finished[i][1] for i in range(len(ranges))]

    values: dict[str, str] = {}
    for ents in chunk_values:
        for e in ents:
            values.setdefault(e["text"], e["type"])
    reviewed = corrections if corrections is not None else reuse
    hidden = dict(reviewed.hidden) if reviewed else {}
    unhidden = set(reviewed.unhidden) if reviewed else set()
    return _build(doc, values, chunks, hidden, unhidden, chunk_values, plan)


def rebuild(doc: Document, prev: PipelineResult, hide: dict[str, str] | None = None,
            unhide: set[str] | None = None) -> PipelineResult:
    """Apply reviewer fixes on top of an earlier run, reusing the model's answers (no new T1 calls)."""
    hidden = {**prev.hidden, **(hide or {})}
    unhidden = (prev.unhidden | set(unhide or ())) - set(hide or {})
    for v in unhide or ():
        hidden.pop(v, None)
    return _build(doc, prev.model_values, prev.chunks, hidden, unhidden, prev.chunk_values, prev.plan)


def _build(doc: Document, values: dict[str, str], chunks: list[ChunkInfo], hidden: dict[str, str],
           unhidden: set[str], chunk_values: list[list[Entity]], plan: str) -> PipelineResult:
    text = doc.text
    wanted = {**values, **hidden}
    model_spans = locate(text, [{"text": v, "type": t} for v, t in wanted.items()])
    spans = addresses.expand(text, merge(detectors.detect(text) + model_spans, text))
    if unhidden:
        spans = [s for s in spans if s.text not in unhidden]

    vault = Vault()
    redacted = apply(text, spans, vault)
    return PipelineResult(
        spans=spans, redacted_text=redacted, vault=vault, boxes=_boxes(doc, spans, vault),
        chunks=chunks, stats=dict(Counter(s.type for s in spans)),
        model_values=values, hidden=hidden, unhidden=unhidden, chunk_values=chunk_values, plan=plan,
    )
