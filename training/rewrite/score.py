#!/usr/bin/env python3
"""Score teacher (or adapter) outputs against the answer key.

For every chunk with a usable result, the output is aligned with the original
chunk text to recover which spans were replaced by placeholders. Placeholders
may be slightly malformed ([PERSON 1], [Person_1], [PERSON]); they still count.
Placeholder numbers are not scored strictly (numbering consistency is reported
for information only).

Typographic quotes count as their plain ASCII forms (’ and ', “ and "): Haiku
straightens them, which changes nothing a reader needs. The mapping is one
character to one character, so key offsets stay valid.

Alignment: the output is cut into literal text and placeholders. If every
literal matches the original in order, each placeholder covers the text
between its neighbours; when several cuts fit (two placeholders separated by a
single space, say), the one whose edges fall on key entity edges wins. If the
literals do not all match, the output changed text outside placeholders: the
chunk is reported, and spans are recovered approximately with difflib.

Metrics, per type and overall:
- recall: key entities overlapped by a predicted span of the same type;
- precision: predicted spans of a type that overlap a key entity of that type;
- leak rate: key entities whose value appears verbatim in the output;
- over-redaction: predicted spans that overlap no key entity, with a list of
  the ones that look like personal data, for manual review (a real value the
  fill step missed would show up here);
- documents with zero leaks; outputs that changed text outside placeholders.

Usage:
    python training/rewrite/score.py --split train [--chunks-dir data/chunks] [--results-dir data/results]
Writes <out-dir>/score-<split>.json and score-<split>.md (default out-dir: the results dir).
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from dataset_common import (
    CANONICAL_PLACEHOLDER_RE,
    CHUNKS_DIR,
    ENTITY_TYPES,
    PLACEHOLDER_RE,
    RESULTS_DIR,
    SPLITS,
    normalise_placeholder,
    read_jsonl,
)

MIN_ANCHOR = 8  # difflib matches shorter than this are not trusted as anchors in the fallback
SENTINEL_BASE = 0xF0000  # private-use code points stand in for placeholders when diffing

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
POSTCODE_RE = re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}\b")
AMOUNT_RE = re.compile(r"[£$€]|\b(?:GBP|USD|EUR)\b|^\d{1,3}(?:,\d{3})+(?:\.\d+)?$|^\d+\.\d{2}$")
DATE_RE = re.compile(
    r"^(?:\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{2}-\d{2})$"
)
# One character to one character, so offsets into the original chunk stay valid.
QUOTE_TABLE = str.maketrans({"‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
                             "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"'})


def plain_quotes(text: str) -> str:
    return text.translate(QUOTE_TABLE)


NAME_LIKE_RE = re.compile(r"^(?:(?:Mr|Mrs|Ms|Miss|Dr)\.?\s+)?[A-Z][A-Za-z'’-]+\.?(?:\s+[A-Z][A-Za-z'’-]*\.?){0,3}$")


# ---------------------------------------------------------------- parsing

def parse_output(output: str) -> tuple[list[str], list[dict]]:
    """Split an output into literals and placeholders: lits[0] ph[0] lits[1] ... ph[k-1] lits[k]."""
    lits, phs, pos = [], [], 0
    for m in PLACEHOLDER_RE.finditer(output):
        ptype = normalise_placeholder(m.group(1), m.group(2))
        if ptype is None:
            continue
        lits.append(output[pos:m.start()])
        phs.append(
            {
                "type": ptype,
                "number": int(m.group(2)) if m.group(2) else None,
                "raw": m.group(),
                "canonical": bool(CANONICAL_PLACEHOLDER_RE.fullmatch(m.group())),
            }
        )
        pos = m.end()
    lits.append(output[pos:])
    return lits, phs


# ---------------------------------------------------------------- alignment

def align_exact(orig: str, lo: int, hi: int, lits: list[str], starts: set[int], ends: set[int]) -> list[tuple[int, int]] | None:
    """Spans of orig[lo:hi] covered by each placeholder, if every literal matches exactly; else None.

    Dynamic programming over the occurrences of each literal. A cut scores 1 for
    each placeholder edge on a key entity edge and 0.25 for each edge that is not
    whitespace; ties go to the earliest cut.
    """
    k = len(lits) - 1
    if k == 0:
        return [] if orig[lo:hi] == lits[0] else None
    first, last = lits[0], lits[-1]
    e0, s_last = lo + len(first), hi - len(last)
    if e0 > s_last or orig[lo:e0] != first or orig[s_last:hi] != last:
        return None

    def start_score(x: int) -> float:
        return (x in starts) + 0.25 * (x < hi and not orig[x].isspace())

    def end_score(y: int) -> float:
        return (y in ends) + 0.25 * (y > lo and not orig[y - 1].isspace())

    # Each level holds candidates (s, e, score, back index) for one literal, sorted by s.
    levels: list[list[tuple[int, int, float, int]]] = [[(lo, e0, start_score(e0), -1)]]
    for j in range(1, k + 1):
        lit = lits[j]
        if j == k:
            positions = [s_last]
        elif lit:
            positions, p = [], orig.find(lit, e0 + 1, s_last)
            while p != -1 and p + len(lit) <= s_last:
                positions.append(p)
                p = orig.find(lit, p + 1, s_last)
        else:
            positions = list(range(e0 + 1, s_last))
        prev = levels[-1]
        cur: list[tuple[int, int, float, int]] = []
        best_score, best_idx, ptr = float("-inf"), -1, 0
        for s in positions:
            while ptr < len(prev) and prev[ptr][1] < s:
                if prev[ptr][2] > best_score:
                    best_score, best_idx = prev[ptr][2], ptr
                ptr += 1
            if best_idx < 0:
                continue
            e = s + len(lit)
            score = best_score + end_score(s) + (start_score(e) if j < k else 0.0)
            cur.append((s, e, score, best_idx))
        if not cur:
            return None
        levels.append(cur)

    # Walk back from the single candidate at the last level.
    idx, cuts = 0, []
    for j in range(k, -1, -1):
        s, e, _, back = levels[j][idx]
        cuts.append((s, e))
        idx = back
    cuts.reverse()
    return [(cuts[j][1], cuts[j + 1][0]) for j in range(k)]


def diff_changed_chars(a: str, b: str) -> int:
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return sum((i2 - i1) + (j2 - j1) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal")


def align(orig: str, output: str, starts: set[int], ends: set[int]) -> dict:
    """Recover placeholder spans. Returns spans (one per placeholder or None), changed chars and a sample."""
    lits, phs = parse_output(output)
    spans = align_exact(orig, 0, len(orig), lits, starts, ends)
    if spans is not None:
        return {"phs": phs, "spans": spans, "changed_chars": 0, "changed_sample": None}

    # Fallback: anchor on long difflib matches, align each gap exactly if possible, else approximately.
    sent = "".join(lit + (chr(SENTINEL_BASE + i) if i < len(phs) else "") for i, lit in enumerate(lits))
    sm = difflib.SequenceMatcher(None, orig, sent, autojunk=False)
    anchors = [(0, 0, 0)] + [b for b in sm.get_matching_blocks() if b.size >= MIN_ANCHOR] + [(len(orig), len(sent), 0)]
    out_spans: list[tuple[int, int] | None] = [None] * len(phs)
    changed, sample = 0, None
    for (a1, b1, n1), (a2, b2, _) in zip(anchors, anchors[1:]):
        ra, rb, oa, ob = a1 + n1, a2, b1 + n1, b2
        if ra >= rb and oa >= ob:
            continue
        region = sent[oa:ob]
        ids = [ord(ch) - SENTINEL_BASE for ch in region if ord(ch) >= SENTINEL_BASE]
        if ids:
            sub_lits = re.split(r"[\U000F0000-\U000FFFFD]", region)
            sub = align_exact(orig, ra, rb, sub_lits, starts, ends)
            if sub is not None:
                for i, sp in zip(ids, sub):
                    out_spans[i] = sp
                continue
        local = difflib.SequenceMatcher(None, orig[ra:rb], region, autojunk=False)
        for tag, i1, i2, j1, j2 in local.get_opcodes():
            if tag == "equal":
                continue
            piece = region[j1:j2]
            here = [ord(ch) - SENTINEL_BASE for ch in piece if ord(ch) >= SENTINEL_BASE]
            literal = "".join(ch for ch in piece if ord(ch) < SENTINEL_BASE)
            if here:
                if i2 > i1:
                    out_spans[here[0]] = (ra + i1, ra + i2)
                changed += len(literal)
            else:
                changed += (i2 - i1) + (j2 - j1)
            if sample is None:
                sample = {"original": orig[ra + i1:ra + i2][:120], "output": re.sub(r"[\U000F0000-\U000FFFFD]", "[...]", piece)[:120]}
    if changed == 0:
        # Every gap was absorbed by placeholders; still count the whole-output mismatch.
        changed = 1
        sample = sample or {"original": "", "output": ""}
    return {"phs": phs, "spans": out_spans, "changed_chars": changed, "changed_sample": sample}


# ---------------------------------------------------------------- scoring

def looks_personal(text: str) -> bool:
    t = text.strip()
    if not t or AMOUNT_RE.search(t) or DATE_RE.match(t):
        return False
    if EMAIL_RE.search(t) or POSTCODE_RE.search(t):
        return True
    if len(re.findall(r"\d", t)) >= 4:
        return True
    return bool(NAME_LIKE_RE.match(t))


def verbatim_in(value: str, output: str) -> bool:
    return re.search(r"(?<![A-Za-z0-9])" + re.escape(value) + r"(?![A-Za-z0-9])", output) is not None


def score_chunk(chunk: dict, output: str) -> dict:
    orig = plain_quotes(chunk["text"])
    gold = chunk["entities"]
    output = plain_quotes(output.strip())
    al = align(orig, output, {g["start"] for g in gold}, {g["end"] for g in gold})
    preds = [
        {"start": sp[0], "end": sp[1], "type": ph["type"], "raw": ph["raw"], "number": ph["number"], "canonical": ph["canonical"]}
        for ph, sp in zip(al["phs"], al["spans"])
        if sp is not None
    ]
    unaligned = sum(1 for sp in al["spans"] if sp is None)

    gold_rows = []
    for g in gold:
        over = [p for p in preds if p["start"] < g["end"] and g["start"] < p["end"]]
        covered = set()
        for p in over:
            covered.update(range(max(p["start"], g["start"]), min(p["end"], g["end"])))
        gold_rows.append(
            {
                "type": g["type"],
                "value": g["value"],
                "entity_id": g["entity_id"],
                "detected": bool(over),
                "type_match": any(p["type"] == g["type"] for p in over),
                "covered_chars": len(covered),
                "chars": g["end"] - g["start"],
                "leaked": verbatim_in(plain_quotes(g["value"]), output),
                "numbers": sorted({p["number"] for p in over if p["type"] == g["type"] and p["number"] is not None}),
            }
        )
    pred_rows = []
    for p in preds:
        over = [g for g in gold if p["start"] < g["end"] and g["start"] < p["end"]]
        text = orig[p["start"]:p["end"]]
        pred_rows.append(
            {
                "type": p["type"],
                "text": text,
                "raw": p["raw"],
                "canonical": p["canonical"],
                "overlaps_gold": bool(over),
                "type_match": any(g["type"] == p["type"] for g in over),
                "looks_personal": not over and looks_personal(text),
            }
        )

    # Numbering (information only): one number per entity_id, different ids of a type get different numbers.
    numbers_by_id: dict[tuple[str, str], set[int]] = defaultdict(set)
    for g in gold_rows:
        numbers_by_id[(g["type"], g["entity_id"])].update(g["numbers"])
    consistent = all(len(v) <= 1 for v in numbers_by_id.values())
    seen: dict[tuple[str, int], str] = {}
    for (t, eid), nums in numbers_by_id.items():
        for n in nums:
            if seen.setdefault((t, n), eid) != eid:
                consistent = False

    return {
        "chunk_id": chunk["chunk_id"],
        "doc_id": chunk["doc_id"],
        "gold": gold_rows,
        "preds": pred_rows,
        "unaligned_placeholders": unaligned,
        "changed_chars": al["changed_chars"],
        "changed_sample": al["changed_sample"],
        "numbering_consistent": consistent,
    }


def ratio(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def latest_results(results_path: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    """Latest successful row per chunk_id, and the latest failed row for chunks that never succeeded."""
    ok: dict[str, dict] = {}
    failed: dict[str, dict] = {}
    for _, row in read_jsonl(results_path):
        cid = row["chunk_id"]
        if row.get("error") or row.get("output") is None:
            failed[cid] = row
        else:
            ok[cid] = row
    return ok, {cid: row for cid, row in failed.items() if cid not in ok}


def score_split(chunks: list[dict], results_path: Path) -> dict:
    ok, failed = latest_results(results_path)
    by_id = {c["chunk_id"]: c for c in chunks}
    unknown = sorted(set(ok) - set(by_id))
    scored = [score_chunk(by_id[cid], ok[cid]["output"]) for cid in by_id if cid in ok]

    per_type = {}
    for t in ENTITY_TYPES:
        gs = [g for s in scored for g in s["gold"] if g["type"] == t]
        ps = [p for s in scored for p in s["preds"] if p["type"] == t]
        per_type[t] = {
            "gold": len(gs),
            "recalled": sum(g["type_match"] for g in gs),
            "recall": ratio(sum(g["type_match"] for g in gs), len(gs)),
            "pred": len(ps),
            "correct_pred": sum(p["type_match"] for p in ps),
            "precision": ratio(sum(p["type_match"] for p in ps), len(ps)),
            "leaked": sum(g["leaked"] for g in gs),
            "leak_rate": ratio(sum(g["leaked"] for g in gs), len(gs)),
        }
    all_g = [g for s in scored for g in s["gold"]]
    all_p = [p for s in scored for p in s["preds"]]
    over = [
        {"chunk_id": s["chunk_id"], "type": p["type"], "text": p["text"], "looks_personal": p["looks_personal"]}
        for s in scored
        for p in s["preds"]
        if not p["overlaps_gold"]
    ]
    changed = [
        {"chunk_id": s["chunk_id"], "changed_chars": s["changed_chars"], "sample": s["changed_sample"]}
        for s in scored
        if s["changed_chars"]
    ]
    malformed = Counter(p["raw"] for p in all_p if not p["canonical"])

    docs_all = defaultdict(set)
    for c in chunks:
        docs_all[c["doc_id"]].add(c["chunk_id"])
    leaks_by_doc = defaultdict(int)
    scored_by_doc = defaultdict(set)
    for s in scored:
        scored_by_doc[s["doc_id"]].add(s["chunk_id"])
        leaks_by_doc[s["doc_id"]] += sum(g["leaked"] for g in s["gold"])
    full_docs = [d for d, ids in docs_all.items() if scored_by_doc.get(d) == ids]

    overall = {
        "gold": len(all_g),
        "detected": sum(g["detected"] for g in all_g),
        "detection_recall": ratio(sum(g["detected"] for g in all_g), len(all_g)),
        "recall": ratio(sum(g["type_match"] for g in all_g), len(all_g)),
        "char_coverage": ratio(sum(g["covered_chars"] for g in all_g), sum(g["chars"] for g in all_g)),
        "pred": len(all_p),
        "precision": ratio(sum(p["type_match"] for p in all_p), len(all_p)),
        "over_redacted": len(over),
        "over_redaction_rate": ratio(len(over), len(all_p)),
        "leaked": sum(g["leaked"] for g in all_g),
        "leak_rate": ratio(sum(g["leaked"] for g in all_g), len(all_g)),
    }
    return {
        "chunks_in_split": len(chunks),
        "chunks_scored": len(scored),
        "chunks_failed": sorted(failed),
        "chunks_missing": len(chunks) - len(scored) - len([c for c in failed if c in by_id]),
        "unknown_chunk_ids": unknown,
        "overall": overall,
        "per_type": per_type,
        "documents": {
            "scored": len(scored_by_doc),
            "fully_scored": len(full_docs),
            "zero_leaks": sum(1 for d in full_docs if leaks_by_doc[d] == 0),
            "with_leaks": sorted(d for d in scored_by_doc if leaks_by_doc[d]),
        },
        "over_redactions": over,
        "over_redactions_looking_personal": [o for o in over if o["looks_personal"]],
        "changed_outside_placeholders": changed,
        "malformed_placeholders": dict(malformed),
        "unknown_placeholder_types": dict(Counter(p["type"] for p in all_p if p["type"].startswith("OTHER:"))),
        "numbering_consistent_chunks": sum(s["numbering_consistent"] for s in scored),
        "leaks": [
            {"chunk_id": s["chunk_id"], "type": g["type"], "value": g["value"]}
            for s in scored
            for g in s["gold"]
            if g["leaked"]
        ],
    }


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def markdown_report(split: str, r: dict, limit: int = 40) -> str:
    o, d = r["overall"], r["documents"]
    lines = [
        f"# T1 score: {split}",
        "",
        f"- Chunks scored: {r['chunks_scored']} of {r['chunks_in_split']} "
        f"(failed: {len(r['chunks_failed'])}, no result yet: {r['chunks_missing']})",
        f"- Key entities: {o['gold']}; recall {pct(o['recall'])} (type must match), "
        f"detection {pct(o['detection_recall'])} (any type), character coverage {pct(o['char_coverage'])}",
        f"- Predicted spans: {o['pred']}; precision {pct(o['precision'])}; over-redaction {o['over_redacted']} ({pct(o['over_redaction_rate'])})",
        f"- Leak rate: {pct(o['leak_rate'])} ({o['leaked']} key values appear verbatim in the output)",
        f"- Documents with zero leaks: {d['zero_leaks']} of {d['fully_scored']} fully scored ({d['scored']} with any result)",
        f"- Outputs that changed text outside placeholders: {len(r['changed_outside_placeholders'])}",
        f"- Placeholder numbering consistent (information only): {r['numbering_consistent_chunks']} of {r['chunks_scored']} chunks",
        "",
        "| Type | Key | Recall | Predicted | Precision | Leaked |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for t, v in r["per_type"].items():
        if v["gold"] or v["pred"]:
            lines.append(f"| {t} | {v['gold']} | {pct(v['recall'])} | {v['pred']} | {pct(v['precision'])} | {v['leaked']} |")
    lines.append(f"| all | {o['gold']} | {pct(o['recall'])} | {o['pred']} | {pct(o['precision'])} | {o['leaked']} |")

    def section(title: str, items: list[str]) -> None:
        lines.extend(["", f"## {title}", ""])
        lines.extend(items[:limit] or ["None."])
        if len(items) > limit:
            lines.append(f"- ... {len(items) - limit} more in the JSON file")

    section("Leaks", [f"- `{x['chunk_id']}` {x['type']}: {x['value']!r}" for x in r["leaks"]])
    section(
        "Over-redactions that look like personal data (review: possibly a real value the key missed)",
        [f"- `{x['chunk_id']}` as {x['type']}: {x['text']!r}" for x in r["over_redactions_looking_personal"]],
    )
    other = Counter((x["type"], x["text"]) for x in r["over_redactions"] if not x["looks_personal"])
    section("Other over-redactions", [f"- {n} x as {t}: {s!r}" for (t, s), n in other.most_common()])
    section(
        "Outputs that changed text outside placeholders",
        [
            f"- `{x['chunk_id']}`: {x['changed_chars']} chars, e.g. {x['sample']['original']!r} became {x['sample']['output']!r}"
            for x in r["changed_outside_placeholders"]
        ],
    )
    section("Malformed placeholders (tolerated)", [f"- {n} x `{raw}`" for raw, n in r["malformed_placeholders"].items()])
    section("Failed chunks", [f"- `{c}`" for c in r["chunks_failed"]])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", choices=SPLITS, action="append", help="split(s) to score; default: every split with a results file")
    ap.add_argument("--chunks-dir", type=Path, default=CHUNKS_DIR)
    ap.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    ap.add_argument("--out-dir", type=Path, default=None, help="where to write score-<split>.json/.md (default: results dir)")
    args = ap.parse_args(argv)

    out_dir = args.out_dir or args.results_dir
    splits = args.split or [s for s in SPLITS if (args.results_dir / f"{s}.jsonl").exists()]
    if not splits:
        print(f"No results files in {args.results_dir}")
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    for split in splits:
        chunks = [obj for _, obj in read_jsonl(args.chunks_dir / f"{split}.jsonl")]
        report = score_split(chunks, args.results_dir / f"{split}.jsonl")
        (out_dir / f"score-{split}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        md = markdown_report(split, report)
        (out_dir / f"score-{split}.md").write_text(md, encoding="utf-8")
        print(md)
        print(f"Wrote {out_dir / f'score-{split}.json'} and {out_dir / f'score-{split}.md'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
