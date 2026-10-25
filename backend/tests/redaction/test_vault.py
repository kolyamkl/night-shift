"""Placeholders and restoring an answer (ported from evalkit/tests/test_evalkit.py)."""

from app.redaction.spans import locate
from app.redaction.vault import Vault, apply, restore


def test_redact_is_consistent_and_restores_exact_and_tolerant_forms():
    text = "Pay Jo Smith from account 12345678. Jo Smith agreed."
    vault = Vault()
    spans = locate(text, [{"text": "Jo Smith", "type": "PERSON"}, {"text": "12345678", "type": "BANK_ACCOUNT"}])
    red = apply(text, spans, vault)
    assert red == "Pay [PERSON_1] from account [ACCOUNT_1]. [PERSON_1] agreed."
    restored, unknown = restore("Yes, PERSON 1 owns [ACCOUNT_1]. [PERSON_7] is unknown.", vault)
    assert restored.startswith("Yes, Jo Smith owns 12345678.")
    assert "[PERSON_7]" in unknown
