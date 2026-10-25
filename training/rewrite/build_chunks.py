#!/usr/bin/env python3
"""Split documents into chunks and write the answer key for every chunk.

Reads data/docs/*.jsonl (validated first), writes data/chunks/{train,fresh,eval}.jsonl.

Chunking:
- Paragraphs are separated by blank lines. Paragraphs are packed greedily into
  chunks of at most --max-tokens estimated tokens (characters / 3.5, see
  dataset_common.estimate_tokens).
- A paragraph over the limit is split on sentence boundaries, then on line
  breaks, then on whitespace, whichever is needed.
- A cut never falls inside an entity: pieces joined by an entity stay together.
- A run of consecutive paragraphs without personal data that is too long for one
  chunk is chunked on its own, starting at its first paragraph. Its chunks then
  come out byte-identical in every fill of the source, so the dedup rule below
  can drop the repeats.
- A chunk's text is an exact slice of the document; blank lines at the cut are dropped.

Answer key: expected_redacted replaces every entity with [TYPE_N]. N counts per
chunk and per type in order of first appearance; all entities sharing an
entity_id in the chunk get the same N. An entity value that runs over several
lines keeps its line breaks, with the placeholder on each line.

Dedup (design section 5): chunks with no entities are emitted once per
source_id, from its earliest fill only. Text variations (hard wrapping, date
formats) make later fills' empty chunks near-identical but not byte-identical,
and Mubit wastes near-duplicate calls. --keep-empty-variants restores the older
rule, which keeps an empty chunk from a later fill when its text is new.

Usage:
    python training/rewrite/build_chunks.py [--docs-dir data/docs] [--out-dir data/chunks] [--max-tokens 1000] [--keep-empty-variants]
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from dataset_common import (
    CHARS_PER_TOKEN,
    CHUNKS_DIR,
    DOCS_DIR,
    ENTITY_TYPES,
    GROUPS,
    MAX_CHUNK_TOKENS,
    SPLITS,
    estimate_tokens,
    format_table,
    load_docs,
    placeholder,
    write_jsonl,
)

Span = tuple[int, int]

PARAGRAPH_SEP_RE = re.compile(r"\n[ \t]*\n\s*")
# Separators for splitting a paragraph that is over the limit, finest last.
SPLIT_LEVELS = (
    ("sentence", re.compile(r"(?<=[.!?])[\"'”’)\]]*(\s+)")),
    ("line", re.compile(r"([ \t]*\n\s*)")),
    ("word", re.compile(r"(\s+)")),
)


def pieces(text: str, start: int, end: int, sep_re: re.Pattern) -> list[Span]:
    """Non-empty, whitespace-stripped spans of text[start:end] between separators.

    For the split levels the separator is the regex's group 1, so closing quotes
    after a full stop stay with their sentence.
    """
    spans, pos = [], start
    for m in sep_re.finditer(text, start, end):
        s, e = (m.start(1), m.end(1)) if sep_re.groups else (m.start(), m.end())
        spans.append((pos, s))
        pos = e
    spans.append((pos, end))
    out = []
    for s, e in spans:
        seg = text[s:e]
        lead = len(seg) - len(seg.lstrip())
        trail = len(seg) - len(seg.rstrip())
        if e - trail > s + lead:
            out.append((s + lead, e - trail))
    return out


def merge_across_entities(spans: list[Span], entities: list[dict]) -> list[Span]:
    """Join neighbouring spans whenever an entity crosses the gap between them."""
    if not spans:
        return []
    merged = [spans[0]]
    for s, e in spans[1:]:
        ps, pe = merged[-1]
        if any(ent["start"] < s and ent["end"] > pe for ent in entities):
            merged[-1] = (ps, e)
        else:
            merged.append((s, e))
    return merged


def split_unit(text: str, span: Span, entities: list[dict], max_chars: float, level: int = 0) -> list[Span]:
    s, e = span
    if e - s <= max_chars or level >= len(SPLIT_LEVELS):
        return [span]
    subs = merge_across_entities(pieces(text, s, e, SPLIT_LEVELS[level][1]), entities)
    if len(subs) <= 1:
        return split_unit(text, span, entities, max_chars, level + 1)
    out: list[Span] = []
    for sub in subs:
        out.extend(split_unit(text, sub, entities, max_chars, level + 1))
    return out


def pack(units: list[Span], max_chars: float) -> list[Span]:
    chunks: list[Span] = []
    cur_s, cur_e = units[0]
    for s, e in units[1:]:
        if e - cur_s <= max_chars:
            cur_e = e
        else:
            chunks.append((cur_s, cur_e))
            cur_s, cur_e = s, e
    chunks.append((cur_s, cur_e))
    return chunks


def chunk_spans(text: str, entities: list[dict], max_tokens: int = MAX_CHUNK_TOKENS) -> list[Span]:
    """Chunk boundaries for one document, as (start, end) offsets into text."""
    max_chars = max_tokens * CHARS_PER_TOKEN
    paragraphs = merge_across_entities(pieces(text, 0, len(text), PARAGRAPH_SEP_RE), entities)
    if not paragraphs:
        return []
    has_pd = [any(s <= ent["start"] < e for ent in entities) for s, e in paragraphs]

    # Segments: long runs of paragraphs without personal data stand alone; everything else packs together.
    segments: list[list[Span]] = []
    current: list[Span] = []
    i = 0
    while i < len(paragraphs):
        if has_pd[i]:
            current.append(paragraphs[i])
            i += 1
            continue
        j = i
        while j < len(paragraphs) and not has_pd[j]:
            j += 1
        run = paragraphs[i:j]
        if run[-1][1] - run[0][0] > max_chars:
            if current:
                segments.append(current)
                current = []
            segments.append(run)
        else:
            current.extend(run)
        i = j
    if current:
        segments.append(current)

    out: list[Span] = []
    for seg in segments:
        units: list[Span] = []
        for para in seg:
            units.extend(split_unit(text, para, entities, max_chars))
        out.extend(pack(units, max_chars))
    return out


def render_entity(value: str, ph: str) -> str:
    """The placeholder for one entity; a value over several lines keeps its line breaks."""
    if "\n" not in value:
        return ph
    return re.sub(r"\S(?:[^\n]*\S)?", ph, value)


def redact(text: str, entities: list[dict]) -> str:
    """Expected redacted text. Entities are sorted, non-overlapping, offsets relative to text."""
    numbers: dict[str, dict[str, int]] = defaultdict(dict)
    out, pos = [], 0
    for ent in entities:
        ids = numbers[ent["type"]]
        n = ids.setdefault(ent["entity_id"], len(ids) + 1)
        out.append(text[pos:ent["start"]])
        out.append(render_entity(ent["value"], placeholder(ent["type"], n)))
        pos = ent["end"]
    out.append(text[pos:])
    return "".join(out)


def chunk_document(doc: dict, max_tokens: int = MAX_CHUNK_TOKENS) -> list[dict]:
    text, entities = doc["text"], doc["entities"]
    spans = chunk_spans(text, entities, max_tokens)
    chunks, placed = [], 0
    for idx, (cs, ce) in enumerate(spans):
        ents = [
            {
                "start": ent["start"] - cs,
                "end": ent["end"] - cs,
                "type": ent["type"],
                "value": ent["value"],
                "entity_id": ent["entity_id"],
            }
            for ent in entities
            if cs <= ent["start"] and ent["end"] <= ce
        ]
        placed += len(ents)
        chunk_text = text[cs:ce]
        chunks.append(
            {
                "chunk_id": f"{doc['doc_id']}-c{idx:03d}",
                "doc_id": doc["doc_id"],
                "source_id": doc["source_id"],
                "group": doc["group"],
                "subtype": doc["subtype"],
                "split": doc["split"],
                "fill": doc["fill"],
                "chunk_index": idx,
                "doc_start": cs,
                "text": chunk_text,
                "entities": ents,
                "expected_redacted": redact(chunk_text, ents),
                "est_tokens": estimate_tokens(chunk_text),
            }
        )
    if placed != len(entities):
        raise AssertionError(f"{doc['doc_id']}: {len(entities) - placed} entities fell outside every chunk")
    return chunks


def build(
    docs: list[dict], max_tokens: int = MAX_CHUNK_TOKENS, keep_empty_variants: bool = False
) -> tuple[dict[str, list[dict]], dict]:
    """Chunk all documents and apply the dedup rule. Returns (chunks by split, stats)."""
    by_split: dict[str, list[dict]] = {s: [] for s in SPLITS}
    seen_clean: set[tuple[str, str]] = set()
    first_fill: dict[str, int] = {}
    for doc in docs:
        first_fill[doc["source_id"]] = min(doc["fill"], first_fill.get(doc["source_id"], doc["fill"]))
    stats = {"dropped": Counter(), "docs": Counter(), "over_limit": 0}
    for doc in sorted(docs, key=lambda d: (d["source_id"], d["fill"], d["doc_id"])):
        stats["docs"][(doc["split"], doc["group"])] += 1
        for ch in chunk_document(doc, max_tokens):
            if not ch["entities"]:
                key = (ch["source_id"], ch["text"])
                later_fill = not keep_empty_variants and doc["fill"] != first_fill[doc["source_id"]]
                if later_fill or key in seen_clean:
                    stats["dropped"][(ch["split"], ch["group"])] += 1
                    continue
                seen_clean.add(key)
            if ch["est_tokens"] > max_tokens:
                stats["over_limit"] += 1
            by_split[ch["split"]].append(ch)
    for rows in by_split.values():
        rows.sort(key=lambda c: (GROUPS.index(c["group"]), c["source_id"], c["fill"], c["doc_id"], c["chunk_index"]))
    return by_split, stats


def summary(by_split: dict[str, list[dict]], stats: dict, max_tokens: int) -> str:
    rows = []
    for split in SPLITS:
        for group in GROUPS:
            chs = [c for c in by_split[split] if c["group"] == group]
            ndocs = stats["docs"][(split, group)]
            if not ndocs and not chs:
                continue
            with_pd = sum(1 for c in chs if c["entities"])
            rows.append(
                [split, group, ndocs, len(chs), with_pd, len(chs) - with_pd,
                 stats["dropped"][(split, group)], sum(c["est_tokens"] for c in chs)]
            )
    all_chunks = [c for s in SPLITS for c in by_split[s]]
    with_pd = sum(1 for c in all_chunks if c["entities"])
    rows.append(["total", "", sum(stats["docs"].values()), len(all_chunks), with_pd, len(all_chunks) - with_pd,
                 sum(stats["dropped"].values()), sum(c["est_tokens"] for c in all_chunks)])
    t1 = format_table(
        ["split", "group", "docs", "chunks", "with PD", "without PD", "dup dropped", "est tokens"], rows
    )

    type_counts = {s: Counter(e["type"] for c in by_split[s] for e in c["entities"]) for s in SPLITS}
    rows2 = [[t] + [type_counts[s][t] for s in SPLITS] + [sum(type_counts[s][t] for s in SPLITS)] for t in ENTITY_TYPES]
    rows2.append(["total"] + [sum(type_counts[s].values()) for s in SPLITS] + [sum(sum(c.values()) for c in type_counts.values())])
    t2 = format_table(["entity type"] + list(SPLITS) + ["total"], rows2)

    lines = [t1, "", t2]
    if stats["over_limit"]:
        lines.append(f"\nWARNING: {stats['over_limit']} chunk(s) over {max_tokens} estimated tokens (unsplittable text)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--docs-dir", type=Path, default=DOCS_DIR)
    ap.add_argument("--out-dir", type=Path, default=CHUNKS_DIR)
    ap.add_argument("--max-tokens", type=int, default=MAX_CHUNK_TOKENS, help="chunk limit in estimated tokens")
    ap.add_argument("--skip-validation", action="store_true", help="do not run validate_docs first (not recommended)")
    ap.add_argument("--keep-empty-variants", action="store_true",
                    help="keep empty chunks from later fills when their text is new (older dedup rule)")
    args = ap.parse_args(argv)

    if not args.skip_validation:
        import validate_docs

        rep, _ = validate_docs.validate(args.docs_dir)
        if rep.errors:
            print("\n".join(rep.errors))
            print(f"{len(rep.errors)} validation error(s); fix them or run validate_docs.py for details. Nothing written.")
            return 1
    docs = load_docs(args.docs_dir)
    if not docs:
        print(f"No documents in {args.docs_dir}")
        return 1
    by_split, stats = build(docs, args.max_tokens, args.keep_empty_variants)
    for split in SPLITS:
        write_jsonl(args.out_dir / f"{split}.jsonl", by_split[split])
    print(summary(by_split, stats, args.max_tokens))
    print(f"\nWrote {', '.join(str(args.out_dir / f'{s}.jsonl') for s in SPLITS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
