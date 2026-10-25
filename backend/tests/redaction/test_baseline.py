"""The regex baseline (ported from evalkit/tests/test_evalkit.py)."""

from app.redaction.detectors import baseline


def test_regex_baseline_finds_uk_identifiers():
    text = (
        "IBAN GB82 WEST 1234 5698 7654 32, sort code 20-45-77, account no 31926819, "
        "NI number AB 12 34 56 C, postcode LS6 2AB, call 07700 900123, mail jo@example.com"
    )
    types = {sp.type for sp in baseline.detect(text)}
    assert {"IBAN", "SORT_CODE", "BANK_ACCOUNT", "NI_NUMBER", "POSTCODE", "PHONE", "EMAIL"} <= types


def test_a_longer_hit_wins_over_the_number_inside_it():
    """An IBAN holds an account number; the IBAN is the one span."""
    text = "account GB82 WEST 1234 5698 7654 32"
    assert [(sp.type, sp.text) for sp in baseline.detect(text)] == [("IBAN", "GB82 WEST 1234 5698 7654 32")]
