"""One call through Mubit for each starter-credit provider route.

Starter credit routes (docs, reference/api): OpenAI /chat/completions, Anthropic /v1/messages,
Gemini /{version}/models/{model}:generateContent only. The OpenAI-compatible Gemini endpoint is
refused on the starter credit (403 starter_credit_route), so Gemini goes through its native route.

Every function returns a Reply with the text, Mubit's request id, token usage and stop reason.
"""

import os
import time
from dataclasses import dataclass

import httpx

MUBIT = os.environ.get("MUBIT_BASE", "https://api.mubit.ai")
RETRY_STATUS = {429, 503, 529}


@dataclass
class Reply:
    text: str | None
    mreq_id: str | None
    model: str | None
    input_tokens: int
    output_tokens: int
    stop_reason: str | None
    status: int


def provider_for(model: str) -> str:
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith("gemini"):
        return "gemini"
    return "openai"


def _post(url: str, headers: dict, body: dict, attempts: int = 6) -> httpx.Response:
    """POST with retry only on 429/503/529, honouring retry-after (Mubit's own retries cover sends
    that never left; anything else may already be recorded, so it is not retried)."""
    i = 0
    while True:
        r = httpx.post(url, headers=headers, json=body, timeout=180)
        i += 1
        if r.status_code not in RETRY_STATUS or i >= attempts:
            return r
        wait = float(r.headers.get("retry-after", 2 ** i))
        time.sleep(min(wait, 60))


def call_openai(key: str, model: str, system: str, user: str, session: str, extra_headers: dict,
                json_mode: bool, max_tokens: int, session_mode: str = "none",
                reasoning_effort: str | None = None) -> Reply:
    # OpenAI rejects `metadata` unless `store` is true ("The 'metadata' parameter is only allowed
    # when 'store' is enabled"). Default: send no metadata; Mubit then derives the session from the
    # instructions + first user message, which is one session per chunk (fine for round files,
    # which hold one chunk per document). session_mode="store" sends metadata.session_id with
    # store=true (the provider then keeps the completion; only acceptable for synthetic data).
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_completion_tokens": max_tokens,
    }
    if session_mode == "store":
        body["metadata"] = {"session_id": session}
        body["store"] = True
    if reasoning_effort:
        # Reasoning models count hidden reasoning inside max_completion_tokens; lower effort
        # leaves room for the answer. Not part of Mubit's task fingerprint.
        body["reasoning_effort"] = reasoning_effort
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    r = _post(f"{MUBIT}/openai/v1/chat/completions",
              {"Authorization": f"Bearer {key}", **extra_headers}, body)
    mreq = r.headers.get("x-middleware-request-id")
    if r.status_code != 200:
        return Reply(None, mreq, None, 0, 0, f"http {r.status_code}: {r.text[:300]}", r.status_code)
    d = r.json()
    ch = d["choices"][0]
    u = d.get("usage") or {}
    return Reply(ch["message"].get("content"), mreq, d.get("model"), u.get("prompt_tokens", 0),
                 u.get("completion_tokens", 0), ch.get("finish_reason"), 200)


def call_anthropic(key: str, model: str, system: str, user: str, session: str, extra_headers: dict,
                   json_mode: bool, max_tokens: int) -> Reply:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "metadata": {"user_id": session},  # Anthropic's one metadata field; Mubit takes the session from it
    }
    r = _post(f"{MUBIT}/anthropic/v1/messages",
              {"x-api-key": key, "anthropic-version": "2023-06-01", **extra_headers}, body)
    mreq = r.headers.get("x-middleware-request-id")
    if r.status_code != 200:
        return Reply(None, mreq, None, 0, 0, f"http {r.status_code}: {r.text[:300]}", r.status_code)
    d = r.json()
    text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
    u = d.get("usage") or {}
    return Reply(text, mreq, d.get("model"), u.get("input_tokens", 0), u.get("output_tokens", 0),
                 d.get("stop_reason"), 200)


def call_gemini(key: str, model: str, system: str, user: str, session: str, extra_headers: dict,
                json_mode: bool, max_tokens: int) -> Reply:
    # Gemini has no session field: Mubit derives the session from the instructions and the first
    # user message, so each chunk is its own session (fine: one chunk per document in round files).
    gen: dict[str, object] = {"maxOutputTokens": max_tokens}
    if json_mode:
        gen["responseMimeType"] = "application/json"
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": gen,
    }
    r = _post(f"{MUBIT}/gemini/v1beta/models/{model}:generateContent",
              {"x-goog-api-key": key, **extra_headers}, body)
    mreq = r.headers.get("x-middleware-request-id")
    if r.status_code != 200:
        return Reply(None, mreq, None, 0, 0, f"http {r.status_code}: {r.text[:300]}", r.status_code)
    d = r.json()
    cand = (d.get("candidates") or [{}])[0]
    parts = (cand.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    u = d.get("usageMetadata") or {}
    out = u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)
    return Reply(text, mreq, d.get("modelVersion"), u.get("promptTokenCount", 0), out,
                 cand.get("finishReason"), 200)


CALL = {"openai": call_openai, "anthropic": call_anthropic, "gemini": call_gemini}
