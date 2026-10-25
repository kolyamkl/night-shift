"""Finding values in text (ported from evalkit/tests/test_evalkit.py), and merging overlaps."""

from app.redaction.spans import Span, locate, merge


def test_locate_finds_every_occurrence_and_prefers_longer_values():
    text = "Oleksandra Kovalenko signed. Later Kovalenko paid. Kovalenko again."
    spans = locate(text, [{"text": "Kovalenko", "type": "PERSON"}, {"text": "Oleksandra Kovalenko", "type": "PERSON"}])
    assert [s.text for s in spans] == ["Oleksandra Kovalenko", "Kovalenko", "Kovalenko"]


def test_locate_is_whitespace_and_comma_flexible_and_word_bounded():
    text = "Flat 3\n12 Oak Road\nLeeds\nWill is willing."
    spans = locate(
        text, [{"text": "Flat 3, 12 Oak Road, Leeds", "type": "ADDRESS"}, {"text": "Will", "type": "PERSON"}]
    )
    assert spans[0].text == "Flat 3\n12 Oak Road\nLeeds"
    assert [s.text for s in spans if s.type == "PERSON"] == ["Will"]  # not inside "willing"


def test_merge_unions_overlaps_and_keeps_the_longest_type():
    text = "Account 12345678 at 20-45-77"
    spans = [
        Span(8, 16, "BANK_ACCOUNT", "12345678"),
        Span(0, 12, "CUSTOM", "Account 1234"),
        Span(20, 28, "SORT_CODE", "20-45-77"),
    ]
    assert merge(spans, text) == [Span(0, 16, "CUSTOM", "Account 12345678"), Span(20, 28, "SORT_CODE", "20-45-77")]
