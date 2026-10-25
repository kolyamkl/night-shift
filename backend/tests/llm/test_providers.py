"""Provider routing and list-prompt answers (ported from evalkit/tests/test_evalkit.py)."""

from app.llm import providers
from app.llm.t1 import parse_entities


def test_provider_routing():
    assert providers.provider_for("claude-haiku-4-5") == "anthropic"
    assert providers.provider_for("gemini-3.8-flash") == "gemini"
    assert providers.provider_for("gpt-6-luna") == "openai"


def test_list_answers_are_parsed_and_unreadable_ones_flagged():
    assert parse_entities('{"entities": [{"text": "Jo", "type": "PERSON"}]}') == (
        [{"text": "Jo", "type": "PERSON"}], False)
    assert parse_entities("not json")[1] is True


def test_a_fenced_answer_and_empty_values_are_handled():
    answer = '```json\n{"entities": [{"text": "Jo", "type": "PERSON"}, {"text": "", "type": "PERSON"}]}\n```'
    assert parse_entities(answer) == ([{"text": "Jo", "type": "PERSON"}], False)
    assert parse_entities(None) == ([], True)
