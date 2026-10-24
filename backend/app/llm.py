"""The two model calls, both through Mubit.

T1 finds personal data in a chunk, with recording left on so the calls keep training a Mubit task.
VEIL_T1_PROMPT picks one of two T1 designs (each is its own Mubit task):
- "rewrite" (default): backend/app/prompts.py with its MODEL_ID (claude-haiku-4-5) through
  https://api.mubit.ai/anthropic, sent with the anthropic SDK exactly as scripts/dataset/send_batch.py
  sends it, so the calls land in the same Mubit task ("Redact personal data"). The answer is the chunk
  rewritten with placeholders; align_rewrite turns it back into values. Chunks are at most 1400
  characters: Mubit's reviewer reads only about the first 1,530.
- "evalkit": the frozen evalkit prompt, model VEIL_T1_MODEL (default gpt-6-luna), the answer is a JSON
  list of values, chunks of at most 4000 characters (Mubit task "Find personal data").
T2 answers a question about the redacted text. It is sent with `x-middleware-record: off`, so it
creates no second task and Mubit stores no user questions.

The key (mbt_...) and the VEIL_* settings come from the environment, then backend/.env, then the
repo-root .env. Only the names asked for are read from those files, and only where the key came from
is ever reported. Without a key both calls are off and the app runs on regex only.
"""

import os
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from evalkit import providers
from evalkit.prompts import T1_SYSTEM_PROMPT
from evalkit.rewrite import PLACEHOLDER, spans_from_rewrite
from evalkit.send_batch import parse_entities
from evalkit.spans import Span

from . import prompts
from .pipeline import MAX_CHARS, T1Result

BACKEND_DIR = Path(__file__).resolve().parents[1]
# Where the key and the VEIL_* settings may live, in lookup order after the environment. Both gitignored.
KEY_FILES: tuple[tuple[str, Path], ...] = (
    ("backend/.env", BACKEND_DIR / ".env"),
    (".env", BACKEND_DIR.parent / ".env"),
)

EVALKIT, REWRITE = "evalkit", "rewrite"
T1_PROMPTS = (EVALKIT, REWRITE)
T1_CHUNK_CHARS = {EVALKIT: MAX_CHARS, REWRITE: 1400}
DEFAULT_EVALKIT_MODEL = "gpt-6-luna"
DEFAULT_T2_MODEL = "claude-haiku-4-5"

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


def _from_env_file(path: Path, name: str) -> str | None:
    """The value of one NAME=value line in a .env file (the last one wins), or None. Nothing else is read."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    value = None
    for line in lines:
        key, _, rest = line.strip().removeprefix("export ").partition("=")
        if key.strip() == name:
            value = rest.strip().strip("'\"")
    return value


def find_key(files: Sequence[tuple[str, Path]] = KEY_FILES) -> tuple[str | None, str | None]:
    """(key, where it came from): the first value starting with mbt_ in MUBIT_API_KEY, then each file.
    Callers must never log or return the key itself; the source ("env", "backend/.env", ".env") is safe."""
    value = os.environ.get("MUBIT_API_KEY", "").strip()
    if value.startswith("mbt_"):
        return value, "env"
    for source, path in files:
        value = (_from_env_file(path, "MUBIT_API_KEY") or "").strip()
        if value.startswith("mbt_"):
            return value, source
    return None, None


def setting(name: str, default: str, files: Sequence[tuple[str, Path]] = KEY_FILES) -> tuple[str, str]:
    """(value, source) of one setting: a non-empty environment variable wins, then each file, then the
    default ("default"). Only this name is read; nothing is loaded into os.environ."""
    value = os.environ.get(name, "").strip()
    if value:
        return value, "env"
    for source, path in files:
        value = (_from_env_file(path, name) or "").strip()
        if value:
            return value, source
    return default, "default"


@dataclass
class Settings:
    t1_prompt: str  # "evalkit" or "rewrite"
    t1_model: str  # the model the chosen prompt runs on
    evalkit_model: str  # VEIL_T1_MODEL, used by the evalkit prompt only
    t2_model: str
    sources: dict[str, str]  # setting name -> "env", "backend/.env", ".env" or "default"


def load_settings(files: Sequence[tuple[str, Path]] = KEY_FILES) -> Settings:
    prompt, prompt_source = setting("VEIL_T1_PROMPT", REWRITE, files)
    prompt = prompt.lower()
    if prompt not in T1_PROMPTS:
        raise ValueError(f"VEIL_T1_PROMPT (from {prompt_source}) must be one of {', '.join(T1_PROMPTS)}, "
                         f"not {prompt!r}")
    evalkit_model, model_source = setting("VEIL_T1_MODEL", DEFAULT_EVALKIT_MODEL, files)
    t2_model, t2_source = setting("VEIL_T2_MODEL", DEFAULT_T2_MODEL, files)
    # The rewrite prompt always runs on prompts.MODEL_ID: another model would be another Mubit task.
    return Settings(prompt, prompts.MODEL_ID if prompt == REWRITE else evalkit_model, evalkit_model, t2_model,
                    {"VEIL_T1_PROMPT": prompt_source, "VEIL_T1_MODEL": model_source, "VEIL_T2_MODEL": t2_source})


def describe(settings: Settings, key_source: str | None) -> str:
    """The startup log line: which prompt and model T1 uses and where they and the key came from."""
    src = settings.sources["VEIL_T1_PROMPT"]
    origin = "default" if src == "default" else f"VEIL_T1_PROMPT from {src}"
    prompt = f"prompt {settings.t1_prompt} ({origin})"
    if key_source is None:
        return f"T1 off: no Mubit key (mbt_...) in MUBIT_API_KEY, backend/.env or .env; regex layer only; {prompt}"
    return (f"T1 on: {prompt}, model {settings.t1_model}, {T1_CHUNK_CHARS[settings.t1_prompt]}-character chunks, "
            f"Mubit key from {key_source}")


# What a hidden value of a type may look like inside one line. A rewrite answer is matched line by
# line as a template; these settle where two neighbouring placeholders split, as in "[ADDRESS_1] [POSTCODE_1]".
_VALUE_PATTERNS = {
    "PERSON": r"[^\d@\n]+?",
    "POSTCODE": r"[A-Za-z0-9]{2,5}(?:[ -][A-Za-z0-9]{2,4})?",
    "EMAIL": r"[^\s@]+@[^\s@]+",
    "PHONE": r"\+?[\d(][\d\s().-]*\d",
    "SORT_CODE": r"\d{2}[- ]?\d{2}[- ]?\d{2}",
}
_ANY_VALUE = r"[^\n]+?"
_TITLES = r"(?:Mr|Mrs|Ms|Miss|Mx|Dr|Prof|Sir|Dame|Rev)\.?"
_TITLE = re.compile(rf"^{_TITLES}\s+(?=\S)", re.IGNORECASE)
_TITLE_ONLY = re.compile(_TITLES, re.IGNORECASE)


def _literal(text: str) -> str:
    return r"\s+".join(re.escape(part) for part in re.split(r"\s+", text))


def _lines(text: str) -> list[tuple[int, str]]:
    """(offset, line) for each line, leaving out blank lines at either end."""
    out, pos = [], 0
    for line in text.split("\n"):
        out.append((pos, line))
        pos += len(line) + 1
    while out and not out[-1][1].strip():
        out.pop()
    while out and not out[0][1].strip():
        out.pop(0)
    return out


def _match_line(line: str, answer: str) -> list[tuple[int, int, str]] | None:
    """Hidden (start, end, type) in one line if the answer line is that line with placeholders, else None."""
    literals, types, pos = [], [], 0
    for m in PLACEHOLDER.finditer(answer):
        literals.append(answer[pos:m.start()])
        types.append(m.group(1))
        pos = m.end()
    literals.append(answer[pos:])
    literals[0], literals[-1] = literals[0].lstrip(), literals[-1].rstrip()
    # Placeholders split only by spaces or punctuation are where the template search branches; many
    # of them on one line could make it very slow, so such a line goes to the diff instead.
    if sum(1 for lit in literals[1:-1] if not any(c.isalnum() for c in lit)) > 2:
        return None
    pattern = r"\s*" + _literal(literals[0])
    for etype, lit in zip(types, literals[1:]):
        pattern += f"({_VALUE_PATTERNS.get(etype, _ANY_VALUE)})" + _literal(lit)
    m = re.fullmatch(pattern + r"\s*", line)
    if not m:
        return None
    found = []
    for i, etype in enumerate(types, 1):
        value = m.group(i)
        start = m.start(i) + len(value) - len(value.lstrip())
        found.append((start, start + len(value.strip()), etype))
    return found


def align_rewrite(chunk: str, answer: str) -> tuple[list[Span], int]:
    """Hidden spans in the chunk and the characters changed outside placeholders.

    The chunk is sent stripped, as in the training data, so the answer is aligned against chunk.strip();
    the spans keep offsets into the chunk. The rewrite prompt keeps line breaks and never lets a value
    cross one, so lines are matched as templates one by one; a line that does not fit, or an answer with
    a different number of lines, falls back to evalkit's diff."""
    sent = chunk.strip()
    lead = len(chunk) - len(chunk.lstrip())
    lines, answers = _lines(sent), _lines(answer)
    if len(lines) != len(answers):
        spans, changed = spans_from_rewrite(sent, answer)
        return [Span(sp.start + lead, sp.end + lead, sp.type, sp.text) for sp in spans], changed
    spans = []
    changed = 0
    for (offset, line), (_, ans) in zip(lines, answers):
        found = _match_line(line, ans)
        if found is None:
            line_spans, line_changed = spans_from_rewrite(line, ans)
            found = [(sp.start, sp.end, sp.type) for sp in line_spans]
            changed += line_changed
        spans += [Span(lead + offset + s, lead + offset + e, t, line[s:e]) for s, e, t in found]
    return spans, changed


def rewrite_values(chunk: str, answer: str) -> list[dict] | None:
    """Distinct values from a rewrite answer, or None when the answer does not line up with the chunk
    (more than a little text changed outside the placeholders, such as a summary or a refusal).

    Every value is later hidden everywhere in the document, so tiny ones are dropped: fewer than two
    letters or digits, or a PERSON that is only a title (a misaligned diff can turn "Mr" into a value).
    A title before a name stays visible, as in the evalkit prompt, so "Mr Raj Patel" and a later
    "Raj Patel" share one placeholder."""
    spans, changed = align_rewrite(chunk, answer)
    if changed > max(30, len(chunk.strip()) // 20):
        return None
    values: dict[str, str] = {}
    for sp in spans:
        value = _TITLE.sub("", sp.text) if sp.type == "PERSON" else sp.text
        if sum(c.isalnum() for c in value) < 2 or (sp.type == "PERSON" and _TITLE_ONLY.fullmatch(value)):
            continue
        values.setdefault(value, sp.type)
    return [{"text": v, "type": t} for v, t in values.items()]


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
