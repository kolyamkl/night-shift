"""T2: answer a question about the redacted text, through Mubit.

It is sent with `x-middleware-record: off`, so it creates no second Mubit task and Mubit stores no
user questions.
"""

from collections.abc import Callable

from app.llm import prompts, providers

DEFAULT_T2_MODEL = "claude-haiku-4-5"

T2 = Callable[[str, str], tuple[str, str | None]]  # (question, redacted text) -> (answer, Mubit request id)


def make_t2(key: str | None, model: str = DEFAULT_T2_MODEL, base: str = providers.MUBIT_BASE) -> T2 | None:
    if not key:
        return None
    call = providers.CALL[providers.provider_for(model)]

    def t2(question: str, redacted_text: str) -> tuple[str, str | None]:
        user = f"Document:\n{redacted_text}\n\nQuestion: {question}"
        rep = call(key, model, prompts.T2_SYSTEM_PROMPT, user, "veil-chat", {"x-middleware-record": "off"}, False,
                   2000, base=base)
        if rep.status != 200 or rep.text is None:
            raise RuntimeError(rep.stop_reason or "no answer")
        return rep.text, rep.mreq_id

    return t2
