"""The numbers chart in the README, scored offline: no model calls.

Takes the fresh synthetic round (data/chunks-400/fresh.jsonl, with its answer key) and the claude-haiku-4-5
rewrite answers already sent through Mubit for it (data/results-400/fresh.jsonl), and scores three detectors on
the same chunks: the rules alone, the model alone, and MuGuard (both, as the app runs them). A value counts as
hidden only when every non-space character of it is covered.

Run from backend/:
    PYTHONPATH=. uv run python ../scripts/readme_numbers.py ../data ../docs/readme/numbers.json
then redraw the pictures with frontend/scripts/readme_art.py.
"""

import json
import sys
from collections import Counter

from app.llm.rewrite import rewrite_values
from app.redaction.addresses import expand
from app.redaction.detectors import detect
from app.redaction.spans import locate, merge

R = sys.argv[1]
chunks = {json.loads(l)["chunk_id"]: json.loads(l) for l in open(f"{R}/chunks-400/fresh.jsonl")}
outs = [json.loads(l) for l in open(f"{R}/results-400/fresh.jsonl")]


def spans(text, output, mode):
    model = locate(text, rewrite_values(text, output) or []) if mode != "rules" else []
    rules = detect(text) if mode != "model" else []
    return expand(text, merge(rules + model, text))


stat = Counter()
docs = set()
for o in outs:
    ch = chunks[o["chunk_id"]]
    text, gold = ch["text"], ch["entities"]
    docs.add(ch["doc_id"])
    gold_chars = {i for g in gold for i in range(g["start"], g["end"])}
    for mode in ("rules", "model", "both"):
        covered = {i for s in spans(text, o["output"], mode) for i in range(s.start, s.end)}
        for g in gold:
            full = all(i in covered for i in range(g["start"], g["end"]) if not text[i].isspace())
            for t in (g["type"], "ALL"):
                stat[(mode, t, "n")] += 1
                stat[(mode, t, "hit")] += full
        stat[(mode, "extra")] += sum(1 for i in covered if i not in gold_chars and text[i].isalnum())
        stat[(mode, "covered")] += sum(1 for i in covered if text[i].isalnum())

types = sorted({k[1] for k in stat if len(k) == 3 and k[1] != "ALL"}, key=lambda t: -stat[("both", t, "n")])
print(f"chunks {len(outs)}, documents {len(docs)}, values {stat[('both', 'ALL', 'n')]}")
out = {}
for t in ["ALL", *types]:
    row = {m: (stat[(m, t, "hit")], stat[(m, t, "n")]) for m in ("rules", "model", "both")}
    out[t] = {m: round(100 * h / n, 1) for m, (h, n) in row.items()} | {"n": row["both"][1]}
    print(f"{t:12} n={row['both'][1]:>4}  rules {out[t]['rules']:5}%  model {out[t]['model']:5}%  muguard {out[t]['both']:5}%")
for m in ("rules", "model", "both"):
    print(m, "chars hidden outside the key:", stat[(m, "extra")], "of", stat[(m, "covered")])
json.dump(out, open(sys.argv[2], "w"), indent=1)
