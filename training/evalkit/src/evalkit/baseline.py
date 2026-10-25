"""Write regex-baseline predictions for a gold file, in the shape `evalkit.score` reads."""

import argparse
import json

from .regex_baseline import predict


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gold", required=True, help="canonical chunk or document JSONL")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    n = 0
    with open(a.gold, encoding="utf-8") as fin, open(a.out, "w", encoding="utf-8") as fout:
        for line in fin:
            if not line.strip():
                continue
            rec = json.loads(line)
            rid = rec.get("chunk_id") or rec["doc_id"]
            fout.write(json.dumps({"id": rid, "entities": predict(rec["text"])}, ensure_ascii=False) + "\n")
            n += 1
    print(f"wrote {n} predictions to {a.out}")


if __name__ == "__main__":
    main()
