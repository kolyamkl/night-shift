"""List the teacher's or adapter's mistakes per chunk, with the Mubit request id and the corrected
answer ready to paste into the console (the organisers' PagerPal flow: correct the reply on its request).

  uv run python -m evalkit.mistakes --gold ../../data/rounds/corrections.jsonl --results runs/corrections.jsonl \
      --out runs/corrections_todo.md --top 40
"""

import argparse
import json

from .score import _coverage, load_jsonl, pred_spans


def gold_answer(rec: dict) -> dict:
    """The corrected T1 reply: distinct values in order of first appearance."""
    seen, ents = set(), []
    for e in sorted(rec["entities"], key=lambda e: e["start"]):
        if e["text"] not in seen:
            seen.add(e["text"])
            ents.append({"text": e["text"], "type": e["type"]})
    return {"entities": ents}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--results", required=True, help="send_batch output")
    ap.add_argument("--out", required=True, help="markdown to-do list for the console")
    ap.add_argument("--top", type=int, default=40)
    a = ap.parse_args()
    gold = {(r.get("chunk_id") or r["doc_id"]): r for r in load_jsonl(a.gold)}
    rows = []
    for res in load_jsonl(a.results):
        rec = gold.get(res["id"])
        if rec is None or res.get("error"):
            continue
        pred = pred_spans(rec["text"], res)
        missed = [g for g in rec["entities"] if _coverage(g["start"], g["end"], pred) < 1.0]
        extra = [p for p in pred if not any(p.start < g["end"] and g["start"] < p.end for g in rec["entities"])]
        if missed or extra or res.get("parse_error"):
            rows.append((len(missed) * 3 + len(extra), res, rec, missed, extra))
    rows.sort(key=lambda r: -r[0])
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(f"# Corrections to make in the Mubit console ({len(rows)} chunks with mistakes, top {a.top})\n\n")
        f.write("For each item: open Requests, find the request id (or filter by Session), and replace the reply "
                "with the corrected JSON.\n\n")
        for _, res, rec, missed, extra in rows[: a.top]:
            f.write(f"## {res['id']}  ·  `{res.get('mreq_id')}`  ·  session `doc-{rec['doc_id']}`\n\n")
            if missed:
                distinct = list(dict.fromkeys((g["text"], g["type"]) for g in missed))
                f.write("Missed: " + "; ".join(f"`{t}` ({ty})" for t, ty in distinct) + "\n\n")
            if extra:
                f.write("Hidden but not personal: " + "; ".join(f"`{p.text}`" for p in extra) + "\n\n")
            f.write("Corrected reply:\n\n```json\n" + json.dumps(gold_answer(rec), ensure_ascii=False) + "\n```\n\n")
    print(f"{len(rows)} chunks with mistakes; wrote the top {min(a.top, len(rows))} to {a.out}")


if __name__ == "__main__":
    main()
