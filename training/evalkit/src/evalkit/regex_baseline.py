"""Baseline 1: regex + validators + context words (team pack 9.6, methods.md recommendations).

High-risk numbers (card, account, sort code, IBAN, NI) are labelled from the regex plus a context
word even when the checksum fails: a typo in a real number is still personal data.
"""

import re

from . import uk_formats as uk
from .spans import Span

EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
CONTEXT = {
    "BANK_ACCOUNT": re.compile(r"(?i)\b(account|a/c|acc(?:ount)?\s*no|acct)\b"),
    "ID_DOC": re.compile(r"(?i)\b(passport|licence|license|nhs)\b"),
}
KEEP_CONTEXT = re.compile(r"(?i)\b(company\s+(?:no|number)|registered\s+in|vat\s+reg|invoice|order|ticket)\b")


def _near(text: str, start: int, pattern: re.Pattern, window: int = 40) -> bool:
    return bool(pattern.search(text[max(0, start - window):start]))


def detect(text: str) -> list[Span]:
    found: list[Span] = []

    def add(m: re.Match, etype: str, group: int = 0) -> None:
        s, e = m.span(group)
        found.append(Span(s, e, etype, text[s:e]))

    for m in EMAIL_RE.finditer(text):
        add(m, "EMAIL")
    for m in uk.IBAN_GB_RE.finditer(text):
        add(m, "IBAN")
    for m in uk.CARD_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        if uk.luhn_ok(digits) and 13 <= len(digits) <= 19:
            add(m, "CARD")
    for m in uk.SORT_CODE_RE.finditer(text):
        add(m, "SORT_CODE")
    for m in uk.SORT_CODE_BARE_RE.finditer(text):
        add(m, "SORT_CODE", 1)
    for m in uk.NINO_RE.finditer(text):
        add(m, "NI_NUMBER")
    for m in uk.POSTCODE_RE.finditer(text):
        if uk.is_valid_postcode(m.group(0)):
            add(m, "POSTCODE")
    for m in uk.PASSPORT_RE.finditer(text):
        add(m, "ID_DOC", 1)
    for m in uk.DL_RE.finditer(text):
        add(m, "ID_DOC")
    for m in uk.NHS_RE.finditer(text):
        if uk.is_valid_nhs(m.group(0)) and _near(text, m.start(), CONTEXT["ID_DOC"]):
            add(m, "ID_DOC")
    for m in uk.ACCOUNT_RE.finditer(text):
        if _near(text, m.start(), CONTEXT["BANK_ACCOUNT"]) and not _near(text, m.start(), KEEP_CONTEXT):
            add(m, "BANK_ACCOUNT")
    for m in uk.PHONE_RE.finditer(text):
        if uk.is_valid_uk_phone(m.group(0)):
            add(m, "PHONE")

    # Resolve overlaps: longer span wins (an IBAN contains an account number).
    found.sort(key=lambda sp: (-(sp.end - sp.start), sp.start))
    taken: list[Span] = []
    for sp in found:
        if all(sp.end <= t.start or sp.start >= t.end for t in taken):
            taken.append(sp)
    return sorted(taken, key=lambda sp: sp.start)


def predict(text: str) -> list[dict]:
    """Same shape as T1 output: [{"text", "type"}], distinct values in order."""
    seen: set[str] = set()
    out: list[dict] = []
    for sp in detect(text):
        if sp.text not in seen:
            seen.add(sp.text)
            out.append({"text": sp.text, "type": sp.type})
    return out
