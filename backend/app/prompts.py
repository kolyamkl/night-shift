"""Deprecated import path: the prompts live in app.llm.prompts.

Kept so code outside backend/ that imports `from app import prompts` keeps working
(scripts/dataset/send_batch.py, tests/dataset/). Remove once those import app.llm.prompts.
"""

from app.llm.prompts import MODEL_ID, PROMPT_VERSION, T1_SYSTEM_PROMPT

__all__ = ["MODEL_ID", "PROMPT_VERSION", "T1_SYSTEM_PROMPT"]
