"""Bring the teammates' documents (data/docs/*.jsonl, ~180 realistic templated documents) into our
chunk format, and build the shared bake-off set.

Writes (data/rounds/, gitignored):
  team_train.jsonl  their train + fresh documents as chunks (Mubit-safe: fake values in real templates)
  team_eval.jsonl   their eval documents as chunks (eval sources C2, C5, C10, R5, R7, R9 + Gretel eval)
  bakeoff.jsonl     one fixed comparison set: 50 synthetic eval + 40 team eval + 30 open UK eval chunks
"""

import argparse
import json
import random
from pathlib import Path

MAX_CHARS = 4000  # about 1,000 tokens, the teammates' chunk size


def chunk(text: str, entities: list[dict]) -> list[tuple[int, int]]:
    """Cut on blank lines, then line breaks, never inside an entity."""
    def safe(pos: int) -> bool:
        return all(not (e["start"] < pos < e["end"]) for e in entities)

    cuts, start = [], 0
    while len(text) - start > MAX_CHARS:
        window = text[start:start + MAX_CHARS]
        pos = None
        for sep in ("\n\n", "\n", ". ", " "):
            i = window.rfind(sep)
            while i > MAX_CHARS * 0.3:
                cand = start + i + len(sep)
                if safe(cand):
                    pos = cand
                    break
                i = window.rfind(sep, 0, i)
            if pos:
                break
        pos = pos or start + MAX_CHARS
        while not safe(pos):
            pos -= 1
        cuts.append((start, pos))
        start = pos
    cuts.append((start, len(text)))
    return cuts


def to_chunks(doc: dict) -> list[dict]:
    ents = [{"start": e["start"], "end": e["end"], "text": e["value"], "type": e["type"]} for e in doc["entities"]]
    out = []
    for n, (s, e) in enumerate(chunk(doc["text"], ents)):
        raw = doc["text"][s:e]
        lead = len(raw) - len(raw.lstrip())
        text = raw.strip()
        if not text:
            continue
        base = s + lead
        rel = [{**x, "start": x["start"] - base, "end": x["end"] - base} for x in ents
               if x["start"] >= base and x["end"] <= base + len(text)]
        assert all(text[x["start"]:x["end"]] == x["text"] for x in rel), doc["doc_id"]
        out.append({
            "doc_id": f"team-{doc['doc_id']}", "chunk_id": f"team-{doc['doc_id']}-c{n:02d}",
            "text": text, "entities": rel, "split": doc["split"], "doc_type": doc.get("subtype", doc["group"]),
            "meta": {"mubit_ok": True, "source": f"team/{doc['source_id']}", "group": doc["group"],
                     "provenance": doc.get("provenance", {}).get("kind")},
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default="../..")
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    repo = Path(a.repo)
    rounds = repo / "data" / "rounds"
    train, evals = [], []
    for f in sorted((repo / "data" / "docs").glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                doc = json.loads(line)
                (evals if doc["split"] == "eval" else train).extend(to_chunks(doc))

    def write(name: str, rows: list[dict]) -> None:
        with open(rounds / name, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    write("team_train.jsonl", train)
    write("team_eval.jsonl", evals)

    rng = random.Random(a.seed)

    def sample(rows: list[dict], n: int) -> list[dict]:
        rows = rows[:]
        rng.shuffle(rows)
        return rows[:n]

    syn = [json.loads(x) for x in (rounds / "eval_synthetic.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    uk = [json.loads(x) for x in (rounds / "eval_uk_external.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    for r in uk:
        r.setdefault("chunk_id", r["doc_id"])
        r.setdefault("meta", {})["mubit_ok"] = True  # QuantumAiuk: synthetic, Apache-2.0
    bake = sample(syn, 50) + sample(evals, 40) + sample(uk, 30)
    write("bakeoff.jsonl", bake)
    print(f"team_train: {len(train)} chunks, team_eval: {len(evals)} chunks, bakeoff: {len(bake)} chunks "
          f"({sum(len(r['entities']) for r in bake)} gold values)")


if __name__ == "__main__":
    main()
