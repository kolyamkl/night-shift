"""Mubit names a task by its model, system prompt and output format: one changed character in a T1
prompt starts a new task and resets its example count. These hashes pin both prompts."""

import hashlib

from app.llm import prompts


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def test_the_rewrite_prompt_is_frozen():
    assert (prompts.PROMPT_VERSION, prompts.MODEL_ID) == (1, "claude-haiku-4-5")
    assert sha256(prompts.T1_SYSTEM_PROMPT) == "645493209adac6ea0d5073a8f94912d7584293fdc8be20fafdd39bd29a6db7fd"


def test_the_evalkit_list_prompt_is_frozen():
    """The same text as evalkit/prompts.py T1_SYSTEM_PROMPT (PROMPT_VERSION 1), which it was copied from."""
    assert prompts.LIST_PROMPT_VERSION == 1
    assert sha256(prompts.LIST_T1_SYSTEM_PROMPT) == "dcb9dc0a55312889ac03abd2f75df5734da2f729cd2a387e35b2dd9cc4e9f695"
