"""T1: find personal data in one chunk, through Mubit, with recording left on so the calls keep
training a Mubit task. VEIL_T1_PROMPT picks one of two designs (each is its own Mubit task):

- "rewrite" (default): prompts.T1_SYSTEM_PROMPT on prompts.MODEL_ID (claude-haiku-4-5) through
  https://api.mubit.ai/anthropic, sent with the anthropic SDK exactly as training/rewrite/send_batch.py
  sends it, so the calls land in the same Mubit task ("Redact personal data"). The answer is the chunk
  rewritten with placeholders; rewrite.rewrite_values turns it back into values. Chunks are at most
  1400 characters: Mubit's reviewer reads only about the first 1,530.
- "evalkit": the frozen list prompt (prompts.LIST_T1_SYSTEM_PROMPT) on VEIL_T1_MODEL (default
  gpt-6-luna); the answer is a JSON list of values, chunks of at most 4000 characters (Mubit task
  "Find personal data").
"""

import json
import re
import time
from collections.abc import Callable, Mapping
from typing import Any

from app.core.config import T1_PROMPTS
from app.llm import prompts, providers
from app.llm.rewrite import rewrite_values
from app.redaction.pipeline import MAX_CHARS, T1, T1Result
from app.redaction.spans import Entity

EVALKIT, REWRITE = T1_PROMPTS
T1_CHUNK_CHARS = {EVALKIT: MAX_CHARS, REWRITE: 1400}
DEFAULT_EVALKIT_MODEL = "gpt-6-luna"

# The rewrite request, field for field as training/rewrite/send_batch.py sends it.
MUBIT_ANTHROPIC = "https://api.mubit.ai/anthropic"
REWRITE_MAX_TOKENS = 2048
RETRY_STATUSES = (429, 503, 529)
REWRITE_ATTEMPTS = 4

T1Factory = Callable[[str], T1]  # document id -> T1 for that document's chunks
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


def parse_entities(content: str | None) -> tuple[list[Entity], bool]:
    """Values from a list-prompt answer, and whether the answer was unreadable (training/evalkit/send_batch.py)."""
    try:
        data = json.loads(_FENCE.sub("", (content or "").strip()))
        ents = data.get("entities", [])
        clean = [{"text": str(e["text"]), "type": str(e["type"])} for e in ents if e.get("text")]
    except (ValueError, AttributeError, TypeError, KeyError):
        return [], True
    return clean, False


def _retry_after(headers: Mapping[str, str], attempt: int) -> float:
    try:
        return min(60.0, max(0.0, float(headers.get("retry-after"))))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return min(60.0, 2.0**attempt)


def _evalkit_t1(key: str, model: str, base: str) -> T1Factory:
    call = providers.CALL[providers.provider_for(model)]

    def factory(doc_id: str) -> T1:
        def t1(chunk: str) -> T1Result:
            rep = call(key, model, prompts.LIST_T1_SYSTEM_PROMPT, chunk, f"doc-{doc_id}", {}, True, 8000, base=base)
            if rep.status != 200 or rep.text is None:
                return T1Result([], rep.mreq_id, rep.stop_reason)
            if rep.stop_reason in ("length", "max_tokens", "MAX_TOKENS"):
                return T1Result([], rep.mreq_id, "answer cut off")
            ents, bad = parse_entities(rep.text)
            return T1Result(ents, rep.mreq_id, "unreadable answer" if bad else None)

        return t1

    return factory


def _rewrite_t1(key: str, http_client: Any = None) -> T1Factory:
    import anthropic  # noqa: PLC0415 - only the rewrite design needs the SDK

    # As in send_batch.py: max_retries=0, because we retry only on 429/503/529 (a call that failed any
    # other way may already be recorded). The explicit api_key keeps ANTHROPIC_* settings from the
    # environment out of the request, so only the Mubit key is sent.
    client = anthropic.Anthropic(
        api_key=key, base_url=MUBIT_ANTHROPIC, max_retries=0, timeout=120.0, http_client=http_client
    )

    def factory(doc_id: str) -> T1:
        def t1(chunk: str) -> T1Result:
            attempt = 0
            while True:
                attempt += 1
                try:
                    raw = client.messages.with_raw_response.create(
                        model=prompts.MODEL_ID,
                        max_tokens=REWRITE_MAX_TOKENS,
                        system=prompts.T1_SYSTEM_PROMPT,
                        messages=[{"role": "user", "content": chunk.strip()}],  # as build_chunks.py sent them
                        metadata={"user_id": f"doc-{doc_id}"},
                    )
                    break
                except anthropic.APIStatusError as exc:
                    if exc.status_code in RETRY_STATUSES and attempt < REWRITE_ATTEMPTS:
                        time.sleep(_retry_after(exc.response.headers, attempt))
                        continue
                    return T1Result(
                        [],
                        exc.response.headers.get("x-middleware-request-id"),
                        f"http {exc.status_code}: {exc.message[:200]}",
                    )
            mreq = raw.headers.get("x-middleware-request-id")
            msg = raw.parse()
            if msg.stop_reason == "max_tokens":
                return T1Result([], mreq, "answer cut off")
            values = rewrite_values(chunk, "".join(b.text for b in msg.content if b.type == "text"))
            if values is None:
                return T1Result([], mreq, "unreadable answer")
            return T1Result(values, mreq, None)

        return t1

    return factory


def make_t1_factory(
    key: str | None,
    prompt: str = REWRITE,
    model: str = DEFAULT_EVALKIT_MODEL,
    http_client: Any = None,
    base: str = providers.MUBIT_BASE,
) -> T1Factory | None:
    """A per-document T1 maker, or None without a key. `model` and `base` apply to the evalkit prompt
    only: the rewrite prompt always uses prompts.MODEL_ID at MUBIT_ANTHROPIC, since another model would
    be another Mubit task."""
    if not key:
        return None
    if prompt == REWRITE:
        return _rewrite_t1(key, http_client)
    return _evalkit_t1(key, model, base)
