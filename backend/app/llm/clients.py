"""The two model calls, both through Mubit.

T1 finds personal data in a chunk, with recording left on so the calls keep training a Mubit task.
VEIL_T1_PROMPT picks one of two T1 designs (each is its own Mubit task):
- "rewrite" (default): backend/app/llm/prompts.py with its MODEL_ID (claude-haiku-4-5) through
  https://api.mubit.ai/anthropic, sent with the anthropic SDK exactly as scripts/dataset/send_batch.py
  sends it, so the calls land in the same Mubit task ("Redact personal data"). The answer is the chunk
  rewritten with placeholders; align_rewrite turns it back into values. Chunks are at most 1400
  characters: Mubit's reviewer reads only about the first 1,530.
- "evalkit": the frozen evalkit prompt, model VEIL_T1_MODEL (default gpt-6-luna), the answer is a JSON
  list of values, chunks of at most 4000 characters (Mubit task "Find personal data").
T2 answers a question about the redacted text. It is sent with `x-middleware-record: off`, so it
creates no second task and Mubit stores no user questions.

The key and the VEIL_* settings are resolved in settings.py. Without a key both calls are off and the
app runs on regex only.
"""

import time
from collections.abc import Callable

from evalkit import providers
from evalkit.prompts import T1_SYSTEM_PROMPT
from evalkit.send_batch import parse_entities

from ..domain.pipeline import T1Result
from . import prompts
from .align import rewrite_values
from .settings import DEFAULT_EVALKIT_MODEL, DEFAULT_T2_MODEL, REWRITE

# The rewrite request, field for field as scripts/dataset/send_batch.py sends it.
MUBIT_ANTHROPIC = "https://api.mubit.ai/anthropic"
REWRITE_MAX_TOKENS = 2048
RETRY_STATUSES = (429, 503, 529)
REWRITE_ATTEMPTS = 4

T2_SYSTEM_PROMPT = (
    "Answer the user's question about a redacted document. Values in square brackets such as "
    "[PERSON_1] or [ACCOUNT_2] stand for hidden real values. Keep every placeholder exactly as "
    "written. Never guess hidden values. Answer briefly and plainly, in plain text without Markdown: "
    "no asterisks, no headings and no bullet symbols."
)


def _retry_after(headers, attempt: int) -> float:
    try:
        return min(60.0, max(0.0, float(headers.get("retry-after"))))
    except (TypeError, ValueError):
        return min(60.0, 2.0 ** attempt)


def _evalkit_t1(key: str, model: str) -> Callable[[str], Callable[[str], T1Result]]:
    call = providers.CALL[providers.provider_for(model)]

    def factory(doc_id: str) -> Callable[[str], T1Result]:
        def t1(chunk: str) -> T1Result:
            rep = call(key, model, T1_SYSTEM_PROMPT, chunk, f"doc-{doc_id}", {}, True, 8000)
            if rep.status != 200 or rep.text is None:
                return T1Result([], rep.mreq_id, rep.stop_reason)
            if rep.stop_reason in ("length", "max_tokens", "MAX_TOKENS"):
                return T1Result([], rep.mreq_id, "answer cut off")
            ents, bad = parse_entities(rep.text)
            return T1Result(ents, rep.mreq_id, "unreadable answer" if bad else None)
        return t1

    return factory


def _rewrite_t1(key: str, http_client=None) -> Callable[[str], Callable[[str], T1Result]]:
    import anthropic

    # As in send_batch.py: max_retries=0, because we retry only on 429/503/529 (a call that failed any
    # other way may already be recorded). The explicit api_key keeps ANTHROPIC_* settings from the
    # environment out of the request, so only the Mubit key is sent.
    client = anthropic.Anthropic(api_key=key, base_url=MUBIT_ANTHROPIC, max_retries=0, timeout=120.0,
                                 http_client=http_client)

    def factory(doc_id: str) -> Callable[[str], T1Result]:
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
                    return T1Result([], exc.response.headers.get("x-middleware-request-id"),
                                    f"http {exc.status_code}: {exc.message[:200]}")
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


def make_t1_factory(key: str | None, prompt: str = REWRITE, model: str = DEFAULT_EVALKIT_MODEL,
                    http_client=None) -> Callable[[str], Callable[[str], T1Result]] | None:
    """A per-document T1 maker, or None without a key. `model` applies to the evalkit prompt only:
    the rewrite prompt always uses prompts.MODEL_ID, since another model would be another Mubit task."""
    if not key:
        return None
    if prompt == REWRITE:
        return _rewrite_t1(key, http_client)
    return _evalkit_t1(key, model)


def make_t2(key: str | None, model: str = DEFAULT_T2_MODEL) -> Callable[[str, str], tuple[str, str | None]] | None:
    if not key:
        return None
    call = providers.CALL[providers.provider_for(model)]

    def t2(question: str, redacted_text: str) -> tuple[str, str | None]:
        user = f"Document:\n{redacted_text}\n\nQuestion: {question}"
        rep = call(key, model, T2_SYSTEM_PROMPT, user, "veil-chat", {"x-middleware-record": "off"}, False, 2000)
        if rep.status != 200 or rep.text is None:
            raise RuntimeError(rep.stop_reason or "no answer")
        return rep.text, rep.mreq_id

    return t2
