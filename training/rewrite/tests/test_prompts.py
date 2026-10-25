import re

from app.llm import prompts
from dataset_common import ENTITY_TYPES


def test_prompt_constants():
    assert prompts.PROMPT_VERSION == 1
    assert prompts.MODEL_ID == "claude-haiku-4-5"


def test_prompt_starts_with_a_task_name_and_lists_every_type():
    text = prompts.T1_SYSTEM_PROMPT
    assert text.startswith("Redact personal data in one document chunk.")
    for t in ENTITY_TYPES:
        assert re.search(rf"^- {t}: ", text, re.M), t
    assert "[TYPE_N]" in text and "'s" in text


def test_custom_has_no_format_examples():
    line = next(l for l in prompts.T1_SYSTEM_PROMPT.splitlines() if l.startswith("- CUSTOM:"))
    assert not re.search(r"\d", line)
    assert "identifiers specific to an organisation" in line


def test_no_em_dashes():
    assert chr(0x2014) not in prompts.T1_SYSTEM_PROMPT  # em dash
