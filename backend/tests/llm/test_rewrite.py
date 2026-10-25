"""The rewrite diff (ported from evalkit/tests/test_evalkit.py; the scoring check stays in evalkit)."""

from app.llm.rewrite import spans_from_rewrite


def test_rewrite_answers_become_exact_spans():
    original = "Dear Mr Patel,\nyour account 31926819 is open. Patel's card ends 4821."
    answer = "Dear [PERSON_1],\nyour account [BANK_ACCOUNT_1] is open. [PERSON_1]'s card ends [CARD_1]."
    spans, changed = spans_from_rewrite(original, answer)
    texts = [(s.text, s.type) for s in spans]
    assert ("31926819", "BANK_ACCOUNT") in texts and ("4821", "CARD") in texts
    assert any(t.endswith("Patel") for t, _ in texts)
    assert changed == 0
    assert all(original[s.start : s.end] == s.text for s in spans)


def test_rewrite_counts_text_changed_outside_placeholders():
    spans, changed = spans_from_rewrite("Pay Jo Smith now.", "Please pay [PERSON_1] now.")
    assert [s.text for s in spans] == ["Jo Smith"]
    assert changed > 0
