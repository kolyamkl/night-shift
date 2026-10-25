"""The regex layer: identifiers with a fixed shape, found without a model.

- baseline.py: cards, accounts, sort codes, IBAN, NI, postcodes, phones, emails, passports, licences;
- refs.py: client, policy, claim and case references after their label (type CUSTOM);
- identifiers.py: IP addresses and UUIDs.
"""

from app.redaction.detectors import baseline, identifiers, refs
from app.redaction.spans import Span


def detect(text: str) -> list[Span]:
    """Every regex hit in the text. The baseline comes first, so on a tie its type wins over CUSTOM."""
    return baseline.detect(text) + refs.detect(text) + identifiers.detect(text)
