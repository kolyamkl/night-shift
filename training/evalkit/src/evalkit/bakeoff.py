"""Bake-off: compare designs x teacher models on one fixed set, WITHOUT training anything.

Every call goes through Mubit with `x-middleware-record: off`: Mubit forwards it and keeps no task
fingerprint, so no task is created and no training slot is used. Then each arm is scored against the
same gold labels and one table is printed: leaks, recall, precision, over-redaction, cost, latency.

  uv run python -m evalkit.bakeoff --live                      # default arms on data/rounds/bakeoff.jsonl
  uv run python -m evalkit.bakeoff --arms list:gpt-6-luna,rewrite:claude-haiku-4-5 --live
"""

import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path

from .score import load_jsonl, score_records
from .send_batch import PRICES

DEFAULT_ARMS = "list:gpt-6-luna,list:claude-haiku-4-5,list:gemini-3.8-flash,rewrite:claude-haiku-4-5"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chunks", default="../../data/rounds/bakeoff.jsonl")
    ap.add_argument("--arms", default=DEFAULT_ARMS, help="comma-separated design:model pairs")
    ap.add_argument("--outdir", default="runs/bakeoff")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--md-out", default="runs/bakeoff/RESULTS.md")
    a = ap.parse_args()
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    gold = load_jsonl(a.chunks)
    rows = []
    for arm in a.arms.split(","):
        design, model = arm.split(":")
        res_path = out / f"{design}__{model}.jsonl"
        cmd = [sys.executable, "-m", "evalkit.send_batch", "--chunks", a.chunks, "--out", str(res_path),
               "--model", model, "--design", design, "--record", "off"] + (["--live"] if a.live else [])
        print(f"\n=== {design} x {model}")
        subprocess.run(cmd, check=False)
        if not res_path.exists():
            continue
        results = [r for r in load_jsonl(str(res_path))]
        ok = [r for r in results if not r.get("error")]
        preds = {r["id"]: r for r in ok}
        s = score_records(gold, preds)
        pi, po = PRICES.get(model, (0, 0))
        cost = sum(r.get("input_tokens", 0) * pi + r.get("output_tokens", 0) * po for r in ok) / 1e6
        lat = [r["latency_ms"] for r in ok if "latency_ms" in r]
        rows.append({
            "arm": f"{design} x {model}", "answered": f"{len(ok)}/{len(gold)}",
            "parse_errors": sum(1 for r in ok if r.get("parse_error")),
            "leaks_per_100_docs": s["leaks_per_100_docs"], "zero_leak_docs": s["zero_leak_docs"],
            "recall_hidden": s["recall_hidden"], "precision": s["precision"],
            "keep_trap_hits": s["keep_trap_hit_rate"],
            "changed_chars": sum(r.get("changed_chars", 0) for r in ok),
            "cost_per_1000_chunks": round(1000 * cost / max(1, len(ok)), 2),
            "p50_ms": round(statistics.median(lat)) if lat else None,
            "per_type": {t: v["recall_hidden"] for t, v in s["per_type"].items()},
        })
    if not rows:
        print("\nNothing scored yet (dry run). Add --live to send.")
        return
    lines = ["| Arm | Answered | Leaks/100 docs | Zero-leak docs | Hidden | Precision | Keep-trap hits | "
             "Text changed (chars) | $ per 1,000 chunks | p50 ms |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in sorted(rows, key=lambda r: r["leaks_per_100_docs"]):
        lines.append(f"| {r['arm']} | {r['answered']} | {r['leaks_per_100_docs']} | {r['zero_leak_docs']:.0%} | "
                     f"{r['recall_hidden']:.1%} | {r['precision']:.1%} | {r['keep_trap_hits']:.0%} | "
                     f"{r['changed_chars']} | {r['cost_per_1000_chunks']} | {r['p50_ms']} |")
    types = sorted({t for r in rows for t in r["per_type"]})
    lines += ["", "Hidden per type:", "", "| Arm | " + " | ".join(types) + " |",
              "|---|" + "---:|" * len(types)]
    for r in rows:
        lines.append(f"| {r['arm']} | " + " | ".join(f"{r['per_type'].get(t, 0):.0%}" for t in types) + " |")
    table = "\n".join(lines)
    Path(a.md_out).write_text("# Bake-off results\n\n" + table + "\n", encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("\n" + table)


if __name__ == "__main__":
    main()
