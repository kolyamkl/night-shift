#!/usr/bin/env python3
"""Send chunks to the T1 teacher through Mubit and store the answers.

DRY RUN BY DEFAULT: without --send it only prints what would be sent and a
cost estimate. Real calls need --send and MUBIT_API_KEY (a Mubit key, mbt_...;
never a provider key), taken from the environment or, when unset there, from
the repo's .env file (--env-file).

Each call (official anthropic SDK, base_url https://api.mubit.ai/anthropic):
- model prompts.MODEL_ID, system prompts.T1_SYSTEM_PROMPT, max_tokens 2048,
  no temperature, top_p, top_k or thinking (they stay at the defaults);
- one user message containing exactly the chunk text;
- metadata.user_id = "doc-<doc_id>": Mubit takes the session from it, one
  session per document, so a document never spans Mubit's train and test sets;
- eval split only: header x-middleware-record: off (see --eval-record-off).

Answers are appended to data/results/<split>.jsonl with Mubit's request id
(x-middleware-request-id). The script is resumable: chunk_ids already in the
results file are skipped. Rows that ended in an error are skipped too, unless
--retry-errors is given; the scorer uses the latest successful row per chunk.

429 and 503 (and Anthropic's 529 overloaded) are retried after the retry-after
header, up to --max-attempts. Other errors are recorded and not retried, since
Mubit may already have recorded the call.

Usage:
    python training/rewrite/send_batch.py --split train --limit 10            # dry run
    python training/rewrite/send_batch.py --split train --limit 10 --send     # real calls
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from dataset_common import CHUNKS_DIR, REPO_ROOT, RESULTS_DIR, SPLITS, estimate_tokens, read_jsonl

sys.path.insert(0, str(REPO_ROOT / "backend"))
from app.llm import prompts  # noqa: E402

MUBIT_BASE_URL = "https://api.mubit.ai/anthropic"
MAX_TOKENS = 2048
# Haiku 4.5 list price, USD per million tokens (design section 3).
PRICE_IN_PER_M = 1.0
PRICE_OUT_PER_M = 5.0
# Rough per-call overhead for the message wrapper, in tokens.
MESSAGE_OVERHEAD_TOKENS = 10
RETRY_STATUSES = (429, 503, 529)


def load_env_file(path: Path) -> None:
    """Set KEY=VALUE lines from path in os.environ, never overriding a variable that is already set."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        key, value = key.strip(), value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_chunks(chunks_dir: Path, split: str) -> list[dict]:
    path = chunks_dir / f"{split}.jsonl"
    if not path.exists():
        raise SystemExit(f"{path} not found; run build_chunks.py first")
    return [obj for _, obj in read_jsonl(path)]


def done_chunk_ids(results_path: Path, retry_errors: bool) -> set[str]:
    """chunk_ids to skip: every chunk with a row, or only those with a successful row."""
    done: set[str] = set()
    if not results_path.exists():
        return done
    for _, row in read_jsonl(results_path):
        if not retry_errors or not row.get("error"):
            done.add(row["chunk_id"])
    return done


def request_headers(split: str, eval_record_off: bool) -> dict[str, str]:
    headers: dict[str, str] = {}
    if split == "eval" and eval_record_off:
        # PENDING Mubit's answer (design section 8): is eval traffic with recording
        # off acceptable, and can the adapter still serve it? Use
        # --no-eval-record-off to send eval calls as normal recorded calls.
        headers["x-middleware-record"] = "off"
    return headers


def estimate_cost(chunks: list[dict]) -> tuple[int, int, float]:
    system_tokens = estimate_tokens(prompts.T1_SYSTEM_PROMPT)
    tokens_in = sum(system_tokens + MESSAGE_OVERHEAD_TOKENS + c["est_tokens"] for c in chunks)
    tokens_out = sum(estimate_tokens(c["expected_redacted"]) for c in chunks)
    usd = tokens_in / 1e6 * PRICE_IN_PER_M + tokens_out / 1e6 * PRICE_OUT_PER_M
    return tokens_in, tokens_out, usd


def retry_after_seconds(headers, attempt: int) -> float:
    value = headers.get("retry-after") if headers is not None else None
    try:
        if value is not None:
            return max(0.0, float(value))
    except ValueError:
        pass
    return min(60.0, 2.0 ** attempt)


def make_client(api_key: str, base_url: str, http_client=None):
    import anthropic

    # max_retries=0: this script owns retries so it can honour retry-after and
    # never re-send after an error Mubit may already have recorded. Passing
    # api_key explicitly stops the SDK reading ANTHROPIC_* credentials from the
    # environment, so only the Mubit key is sent.
    return anthropic.Anthropic(
        api_key=api_key, base_url=base_url, max_retries=0, timeout=600.0, http_client=http_client
    )


def send_one(client, chunk: dict, headers: dict[str, str], max_attempts: int, max_tokens: int) -> dict:
    import anthropic

    row = {
        "chunk_id": chunk["chunk_id"],
        "doc_id": chunk["doc_id"],
        "split": chunk["split"],
        "request_id": None,
        "output": None,
        "stop_reason": None,
        "latency_ms": None,
        "usage": None,
        "model": None,
        "prompt_version": prompts.PROMPT_VERSION,
        "record_off": headers.get("x-middleware-record") == "off",
        "error": None,
        "sent_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    for attempt in range(1, max_attempts + 1):
        row["error"] = row["request_id"] = None
        t0 = time.monotonic()
        try:
            raw = client.messages.with_raw_response.create(
                model=prompts.MODEL_ID,
                max_tokens=max_tokens,
                system=prompts.T1_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": chunk["text"]}],
                metadata={"user_id": f"doc-{chunk['doc_id']}"},
                extra_headers=headers or None,
            )
            row["latency_ms"] = round((time.monotonic() - t0) * 1000)
            row["request_id"] = raw.headers.get("x-middleware-request-id")
            msg = raw.parse()
            row["output"] = "".join(b.text for b in msg.content if b.type == "text")
            row["stop_reason"] = msg.stop_reason
            row["usage"] = msg.usage.model_dump(exclude_none=True)
            row["model"] = msg.model
            if msg.stop_reason == "max_tokens":
                row["error"] = "stop_reason=max_tokens: output truncated"
            elif not row["request_id"]:
                row["error"] = "no x-middleware-request-id header: the call did not come through Mubit"
            return row
        except anthropic.APIStatusError as e:
            row["latency_ms"] = round((time.monotonic() - t0) * 1000)
            row["request_id"] = e.response.headers.get("x-middleware-request-id")
            row["error"] = f"HTTP {e.status_code} {e.type or ''}: {e.message}".strip()
            if e.status_code in RETRY_STATUSES and attempt < max_attempts:
                time.sleep(retry_after_seconds(e.response.headers, attempt))
                continue
            return row
        except anthropic.APIError as e:
            row["latency_ms"] = round((time.monotonic() - t0) * 1000)
            row["error"] = f"{type(e).__name__}: {e}"
            return row
    return row


def run(args: argparse.Namespace, http_client=None) -> int:
    chunks = load_chunks(args.chunks_dir, args.split)
    results_path = args.results_dir / f"{args.split}.jsonl"
    done = done_chunk_ids(results_path, args.retry_errors)
    todo = [c for c in chunks if c["chunk_id"] not in done]
    if args.limit is not None:
        todo = todo[: args.limit]
    headers = request_headers(args.split, args.eval_record_off)

    tokens_in, tokens_out, usd = estimate_cost(todo)
    print(f"split {args.split}: {len(chunks)} chunks, {len(done)} already in {results_path}, {len(todo)} to send")
    print(f"model {prompts.MODEL_ID}, prompt v{prompts.PROMPT_VERSION}, base_url {args.base_url}, headers {headers or '{}'}")
    print(
        f"estimated tokens: {tokens_in:,} in, {tokens_out:,} out; estimated cost ${usd:.4f} "
        f"at ${PRICE_IN_PER_M:g} / ${PRICE_OUT_PER_M:g} per million (estimator over-counts slightly)"
    )

    if not args.send:
        for c in todo[: args.show]:
            preview = c["text"][:70].replace("\n", " ")
            print(f"  would send {c['chunk_id']}  session doc-{c['doc_id']}  ~{c['est_tokens']} tokens  {preview!r}")
        if len(todo) > args.show:
            print(f"  ... and {len(todo) - args.show} more")
        print("DRY RUN: nothing sent. Add --send to make real calls.")
        return 0

    load_env_file(args.env_file)
    api_key = os.environ.get("MUBIT_API_KEY", "")
    if not api_key.startswith("mbt_"):
        print("MUBIT_API_KEY must be set to a Mubit key starting with mbt_ (never a provider key).")
        return 2
    if not todo:
        print("Nothing to send.")
        return 0

    client = make_client(api_key, args.base_url, http_client)
    results_path.parent.mkdir(parents=True, exist_ok=True)
    n_ok = n_err = 0
    with results_path.open("a", encoding="utf-8") as out, ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {
            pool.submit(send_one, client, c, headers, args.max_attempts, args.max_tokens): c for c in todo
        }
        for fut in as_completed(futures):
            row = fut.result()
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            if row["error"]:
                n_err += 1
                print(f"  ERROR {row['chunk_id']}: {row['error']}")
            else:
                n_ok += 1
            if (n_ok + n_err) % 25 == 0:
                print(f"  {n_ok + n_err}/{len(todo)} done")
    print(f"Done: {n_ok} ok, {n_err} errors, appended to {results_path}")
    return 1 if n_err else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", choices=SPLITS, default="train")
    ap.add_argument("--send", action="store_true", help="make real calls (default is a dry run)")
    ap.add_argument("--limit", type=int, default=None, help="send at most this many chunks in this run")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--max-attempts", type=int, default=5, help="attempts per chunk on 429/503/529")
    ap.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    ap.add_argument("--retry-errors", action="store_true", help="also re-send chunks whose earlier rows all failed")
    ap.add_argument(
        "--eval-record-off",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="send x-middleware-record: off on the eval split (default on; pending Mubit's answer)",
    )
    ap.add_argument("--chunks-dir", type=Path, default=CHUNKS_DIR)
    ap.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    ap.add_argument("--base-url", default=MUBIT_BASE_URL)
    ap.add_argument("--show", type=int, default=10, help="dry run: how many chunks to list")
    ap.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env",
                    help="read MUBIT_API_KEY from this file when it is not already set in the environment")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
