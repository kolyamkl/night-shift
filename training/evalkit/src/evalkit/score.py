"""Score predicted redactions against gold spans (team pack section 10, methods.md 3.4).

Inputs
  --gold  canonical chunk or document JSONL (text + entities with start/end/type)
  --pred  JSONL lines {"id": <chunk_id or doc_id>, "entities": [{"text", "type"}]}
          (the output of `evalkit.send_batch` and `evalkit.baseline` has this shape)

Headline metrics
  leaks_per_100_docs  gold values not fully hidden, per 100 documents
  zero_leak_docs      share of documents with no leaked value
Per type
  recall_strict / recall_partial (type-agnostic: any placeholder hides the value)
  type_accuracy (strict matches that also got the right type)
Precision side
  precision (predicted spans that overlap a gold span), over_redaction (spans on nothing),
  keep_trap_hits (spans that overlap a planted keep trap)
"""

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Mapping

from .spans import Span, locate


def pred_spans(text: str, pred: dict | list | None) -> list[Span]:
    """A prediction is either {"entities": [{"text","type"}]} (values: every occurrence is hidden)
    or {"spans": [{"start","end","type"}]} (exact spans, e.g. recovered from a rewrite answer)."""
    if isinstance(pred, list):
        return locate(text, pred)
    pred = pred or {}
    if pred.get("spans") is not None:
        return sorted((Span(s["start"], s["end"], s.get("type", "UNKNOWN"), text[s["start"]:s["end"]])
                       for s in pred["spans"]), key=lambda s: s.start)
    return locate(text, pred.get("entities") or [])


def _coverage(start: int, end: int, pred: list) -> float:
    covered = 0
    for p in pred:
        lo, hi = max(start, p.start), min(end, p.end)
        if hi > lo:
            covered += hi - lo
    return covered / max(1, end - start)


def score_records(gold_records: list[dict], preds: Mapping[str, dict | list]) -> dict:
    per_type = defaultdict(Counter)
    totals = Counter()
    doc_leaks: dict[str, int] = defaultdict(int)
    missing_pred = 0

    for rec in gold_records:
        rid = rec.get("chunk_id") or rec["doc_id"]
        doc_id = rec["doc_id"]
        doc_leaks.setdefault(doc_id, 0)
        if rid not in preds:
            missing_pred += 1
        pred = pred_spans(rec["text"], preds.get(rid))
        totals["pred_spans"] += len(pred)

        for g in rec["entities"]:
            t = g["type"]
            per_type[t]["gold"] += 1
            totals["gold"] += 1
            cov = _coverage(g["start"], g["end"], pred)
            if cov >= 1.0:
                per_type[t]["hidden"] += 1
            else:
                per_type[t]["leaked"] += 1
                totals["leaked"] += 1
                doc_leaks[doc_id] += 1
                if cov == 0:
                    per_type[t]["leaked_fully"] += 1
            if cov > 0:
                per_type[t]["partial"] += 1
            exact = [p for p in pred if p.start == g["start"] and p.end == g["end"]]
            if exact:
                per_type[t]["strict"] += 1
                if exact[0].type == t:
                    per_type[t]["typed"] += 1

        golds = rec["entities"]
        traps = (rec.get("meta") or {}).get("keep_traps") or []
        for p in pred:
            if any(p.start < g["end"] and g["start"] < p.end for g in golds):
                totals["pred_on_gold"] += 1
            else:
                totals["over_redaction"] += 1
            if any(p.start < k["end"] and k["start"] < p.end for k in traps if "start" in k):
                totals["keep_trap_hits"] += 1
        totals["keep_traps"] += sum(1 for k in traps if "start" in k)

    n_docs = len(doc_leaks)
    result = {
        "records": len(gold_records),
        "docs": n_docs,
        "records_without_prediction": missing_pred,
        "gold_values": totals["gold"],
        "leaked_values": totals["leaked"],
        "leaks_per_100_docs": round(100 * totals["leaked"] / max(1, n_docs), 2),
        "zero_leak_docs": round(sum(1 for v in doc_leaks.values() if v == 0) / max(1, n_docs), 4),
        "recall_hidden": round(1 - totals["leaked"] / max(1, totals["gold"]), 4),
        "precision": round(totals["pred_on_gold"] / max(1, totals["pred_spans"]), 4),
        "over_redaction_spans": totals["over_redaction"],
        "keep_trap_hit_rate": round(totals["keep_trap_hits"] / max(1, totals["keep_traps"]), 4),
        "per_type": {},
    }
    for t, c in sorted(per_type.items(), key=lambda kv: -kv[1]["gold"]):
        g = max(1, c["gold"])
        result["per_type"][t] = {
            "gold": c["gold"],
            "recall_hidden": round(c["hidden"] / g, 4),
            "recall_strict": round(c["strict"] / g, 4),
            "recall_partial": round(c["partial"] / g, 4),
            "type_accuracy": round(c["typed"] / max(1, c["strict"]), 4),
            "leaked": c["leaked"],
            "leaked_fully": c["leaked_fully"],
        }
    return result


def to_markdown(name: str, r: dict) -> str:
    lines = [
        f"## {name}",
        "",
        f"- Documents: {r['docs']} ({r['records']} records, {r['records_without_prediction']} without a prediction)",
        f"- Leaks per 100 documents: **{r['leaks_per_100_docs']}** ({r['leaked_values']} of {r['gold_values']} values)",
        f"- Zero-leak documents: **{r['zero_leak_docs']:.1%}**",
        f"- Values hidden (recall): {r['recall_hidden']:.1%}; precision: {r['precision']:.1%}; "
        f"over-redacted spans: {r['over_redaction_spans']}; keep-trap hit rate: {r['keep_trap_hit_rate']:.1%}",
        "",
        "| Type | Gold | Hidden | Strict | Partial | Right type | Leaked (fully) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for t, c in r["per_type"].items():
        lines.append(
            f"| {t} | {c['gold']} | {c['recall_hidden']:.1%} | {c['recall_strict']:.1%} | "
            f"{c['recall_partial']:.1%} | {c['type_accuracy']:.1%} | {c['leaked']} ({c['leaked_fully']}) |"
        )
    return "\n".join(lines) + "\n"


def load_jsonl(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--pred", required=True)
    ap.add_argument("--name", default="run")
    ap.add_argument("--json-out")
    ap.add_argument("--md-out")
    a = ap.parse_args()
    gold = load_jsonl(a.gold)
    preds = {p["id"]: p for p in load_jsonl(a.pred) if not p.get("error")}
    res = score_records(gold, preds)
    md = to_markdown(a.name, res)
    print(md)
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
    if a.md_out:
        with open(a.md_out, "a", encoding="utf-8") as f:
            f.write(md + "\n")


if __name__ == "__main__":
    main()
