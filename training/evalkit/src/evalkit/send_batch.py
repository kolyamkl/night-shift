"""Send T1 redaction calls through Mubit. DRY RUN by default: nothing leaves the machine
unless you pass --live and MUBIT_API_KEY is set.

Two designs can be sent, so the team can compare them on the same chunks:
  --design list     our T1: "Find personal data in one document chunk." -> JSON list of values
                    (training/evalkit/src/evalkit/prompts.py)
  --design rewrite  the teammates' T1: "Redact personal data in one document chunk." -> the chunk
                    rewritten with [TYPE_N] placeholders (backend/app/llm/prompts.py, loaded live)
Provider comes from the model name: gpt-* via OpenAI, claude-* via Anthropic, gemini-* via Gemini's
native route (the only Gemini route on the starter credit).

Results are appended to --out (resume-safe), in the shape `evalkit.score` reads, plus the Mubit
request id, tokens and latency. Only records safe for Mubit are sent: synthetic documents ("syn-"),
or records with meta.mubit_ok == true. Local-only data (real people) is never sent.

Examples
  uv run python -m evalkit.send_batch --chunks ../../data/rounds/r1_core.jsonl --out runs/r1.jsonl
  uv run python -m evalkit.send_batch --chunks ../../data/rounds/bakeoff.jsonl --out runs/b_haiku_list.jsonl \
      --model claude-haiku-4-5 --record off --live
"""

import argparse
import importlib.util
import json
import os
import re
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import providers
from .prompts import DEFAULT_MODEL, PROMPT_VERSION, T1_SYSTEM_PROMPT
from .rewrite import spans_from_rewrite

# Published prices per 1M tokens (input, output), from work/mubit-training-guide.md section 3.6.
PRICES = {"gpt-6-luna": (0.10, 0.50), "claude-haiku-4-5": (1.0, 5.0), "gemini-3.8-flash": (0.75, 3.75)}
REPO = Path(__file__).resolve().parents[4]


def rewrite_prompt() -> tuple[str, int]:
    """The teammates' prompt, read from backend/app/llm/prompts.py so edits there are picked up."""
    path = REPO / "backend" / "app" / "llm" / "prompts.py"
    spec = importlib.util.spec_from_file_location("team_prompts", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.T1_SYSTEM_PROMPT, mod.PROMPT_VERSION


def is_mubit_safe(rec: dict) -> bool:
    meta = rec.get("meta") or {}
    if meta.get("mubit_ok") is False:
        return False
    return str(rec.get("doc_id", "")).startswith("syn-") or meta.get("mubit_ok") is True


def build_request(rec: dict, model: str, temperature: float | None, reasoning_effort: str | None) -> dict:
    """The list-design request in OpenAI shape (kept for the dry run and the tests)."""
    req = {
        "model": model,
        "messages": [
            {"role": "system", "content": T1_SYSTEM_PROMPT},
            {"role": "user", "content": rec["text"]},
        ],
        "response_format": {"type": "json_object"},
        "metadata": {"session_id": f"doc-{rec['doc_id']}"},
    }
    if temperature is not None:
        req["temperature"] = temperature
    if reasoning_effort:
        req["reasoning_effort"] = reasoning_effort
    return req


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


def parse_entities(content: str | None) -> tuple[list[dict], bool]:
    try:
        data = json.loads(_FENCE.sub("", (content or "").strip()))
        ents = data.get("entities", [])
        clean = [{"text": str(e["text"]), "type": str(e["type"])} for e in ents if e.get("text")]
        return clean, False
    except (ValueError, AttributeError, TypeError, KeyError):
        return [], True


def load_done(path: str) -> set[str]:
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {json.loads(line)["id"] for line in f if line.strip() and not json.loads(line).get("error")}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chunks", required=True, help="chunk JSONL (canonical format)")
    ap.add_argument("--out", required=True, help="results JSONL (appended)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--design", choices=["list", "rewrite"], default="list")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--max-tokens", type=int, default=0, help="default 8000 (list) or 8000 (rewrite); reasoning models spend part of it thinking")
    ap.add_argument("--record", choices=["full", "metadata", "off"], default="full",
                    help="full = training traffic; off = comparison only (no task fingerprint, nothing trained)")
    ap.add_argument("--reasoning-effort", default=None, help="OpenAI reasoning models only, e.g. low")
    ap.add_argument("--openai-session", choices=["none", "store"], default="none",
                    help="OpenAI only: 'store' sends metadata.session_id with store=true (OpenAI requires store for metadata)")
    ap.add_argument("--live", action="store_true", help="actually call Mubit")
    a = ap.parse_args()

    if a.design == "list":
        system, version, json_mode = T1_SYSTEM_PROMPT, PROMPT_VERSION, True
    else:
        system, version = rewrite_prompt()
        json_mode = False
    max_tokens = a.max_tokens or 8000
    provider = providers.provider_for(a.model)

    with open(a.chunks, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    unsafe = [r for r in records if not is_mubit_safe(r)]
    records = [r for r in records if is_mubit_safe(r)]
    done = load_done(a.out)
    todo = [r for r in records if (r.get("chunk_id") or r["doc_id"]) not in done]
    if a.limit:
        todo = todo[: a.limit]

    chars = sum(len(r["text"]) for r in todo)
    est_in = chars / 4 + len(system) / 4 * len(todo)
    est_out = (150 if a.design == "list" else chars / 4 / max(1, len(todo))) * len(todo)
    print(f"design {a.design} (prompt v{version}) | model {a.model} via {provider} | record={a.record}")
    print(f"records: {len(records)} safe, {len(unsafe)} skipped as not Mubit-safe, {len(done)} already done, {len(todo)} to send")
    print(f"sessions (documents): {len({r['doc_id'] for r in todo})}")
    print("doc types:", dict(Counter(r.get("doc_type", "?") for r in todo).most_common(12)))
    if a.model in PRICES:
        pi, po = PRICES[a.model]
        print(f"estimated token cost: ${(est_in * pi + est_out * po) / 1e6:.2f}")
    if not todo:
        return
    if not a.live:
        print("\nDRY RUN. System prompt starts:", system.splitlines()[0])
        print("First user message:", todo[0]["text"][:300].replace("\n", " | "))
        print("\nAdd --live to send.")
        return

    key = os.environ.get("MUBIT_API_KEY")
    if not key or not key.startswith("mbt_"):
        sys.exit("MUBIT_API_KEY is missing or is not a Mubit key (mbt_...).")
    headers = {} if a.record == "full" else {"x-middleware-record": a.record}
    call = providers.CALL[provider]
    if provider == "openai":
        base_call = call

        def call(*args):  # noqa: F811 - wraps the OpenAI call with the session mode
            return base_call(*args, session_mode=a.openai_session, reasoning_effort=a.reasoning_effort)
    lock = threading.Lock()
    stats = Counter()

    def one(rec: dict) -> dict:
        rid = rec.get("chunk_id") or rec["doc_id"]
        out = {"id": rid, "doc_id": rec["doc_id"], "design": a.design, "prompt_version": version,
               "model_asked": a.model, "record": a.record}
        t0 = time.perf_counter()
        try:
            rep = call(key, a.model, system, rec["text"], f"doc-{rec['doc_id']}", headers, json_mode, max_tokens)
        except Exception as e:  # noqa: BLE001 - log every failure and keep going
            out.update({"error": f"{type(e).__name__}: {e}"})
            out["latency_ms"] = round((time.perf_counter() - t0) * 1000)
            return out
        out.update({"mreq_id": rep.mreq_id, "model": rep.model, "input_tokens": rep.input_tokens,
                    "output_tokens": rep.output_tokens, "stop_reason": rep.stop_reason,
                    "latency_ms": round((time.perf_counter() - t0) * 1000)})
        if rep.status != 200 or rep.text is None:
            out["error"] = rep.stop_reason
        elif rep.stop_reason in ("max_tokens", "length", "MAX_TOKENS"):
            out["error"] = f"truncated ({rep.stop_reason})"
        elif a.design == "list":
            ents, bad = parse_entities(rep.text)
            out.update({"entities": ents, "parse_error": bad, "raw": rep.text if bad else None})
        else:
            spans, changed = spans_from_rewrite(rec["text"], rep.text)
            out.update({"output": rep.text, "changed_chars": changed,
                        "spans": [{"start": s.start, "end": s.end, "type": s.type} for s in spans]})
        return out

    with open(a.out, "a", encoding="utf-8") as fout, ThreadPoolExecutor(max_workers=a.concurrency) as pool:
        futures = [pool.submit(one, r) for r in todo]
        for i, fut in enumerate(as_completed(futures), 1):
            res = fut.result()
            with lock:
                fout.write(json.dumps(res, ensure_ascii=False) + "\n")
                fout.flush()
                stats["error" if res.get("error") else ("parse_error" if res.get("parse_error") else "ok")] += 1
            if i % 25 == 0 or i == len(futures):
                print(f"{i}/{len(futures)} {dict(stats)}", flush=True)


if __name__ == "__main__":
    main()
