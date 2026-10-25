"""UK identifier regexes (detection) and validators (strict checks) used by the baseline detector.

Detection regexes are recall-oriented: they find candidate spans in running text.
Validators are precision-oriented: they say whether a candidate is a well-formed value.
Copied from evalkit/uk_formats.py (only the parts baseline.py uses), unchanged.
"""

import re

# ---------------------------------------------------------------- POSTCODE
# Rules from Wikipedia "Postcodes in the United Kingdom" > Validation (R-26):
# pos1 not Q,V,X; pos2 not I,J,Z; A9A third letter in ABCDEFGHJKPSTUW;
# AA9A fourth letter in ABEHMNPRVWXY; inward unit letters never C,I,K,M,O,V.
_OUTWARD = (
    r"(?:[A-PR-UWYZ][0-9]{1,2}"  # A9, A99
    r"|[A-PR-UWYZ][A-HK-Y][0-9]{1,2}"  # AA9, AA99
    r"|[A-PR-UWYZ][0-9][A-HJKPSTUW]"  # A9A
    r"|[A-PR-UWYZ][A-HK-Y][0-9][ABEHMNPRVWXY])"  # AA9A
)
_INWARD = r"[0-9][ABD-HJLNP-UW-Z]{2}"
POSTCODE_RE = re.compile(rf"\b(?:GIR ?0AA|{_OUTWARD} ?{_INWARD})\b", re.I)


def is_valid_postcode(s: str) -> bool:
    s = s.strip().upper()
    return re.fullmatch(rf"(?:GIR ?0AA|{_OUTWARD} ?{_INWARD})", s) is not None


# ---------------------------------------------------------------- NI NUMBER
# HMRC NIM39110 (R-14): D,F,I,Q,U,V never 1st or 2nd letter; O never 2nd;
# BG, GB, KN, NK, NT, TN, ZZ never used; suffix always A-D.
NINO_RE = re.compile(
    r"\b(?!BG|GB|KN|NK|NT|TN|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z]"
    r"[ -]?\d{2}[ -]?\d{2}[ -]?\d{2}[ -]?[A-D]\b",
    re.I,
)

# ---------------------------------------------------------------- SORT CODE / ACCOUNT
SORT_CODE_RE = re.compile(r"\b\d{2}([- ])\d{2}\1\d{2}\b")  # same separator twice
SORT_CODE_BARE_RE = re.compile(r"(?i)(?<=sort code)[:\s]*\b(\d{6})\b")
ACCOUNT_RE = re.compile(r"\b\d{8}\b")  # needs context words to label

# ---------------------------------------------------------------- IBAN (GB)
IBAN_GB_RE = re.compile(r"\bGB\d{2} ?[A-Z]{4} ?\d{4} ?\d{4} ?\d{4} ?\d{2}\b", re.I)

# ---------------------------------------------------------------- CARD
CARD_RE = re.compile(r"\b(?:\d[ -]?){11,18}\d\b")


def luhn_ok(d: str) -> bool:
    total, alt = 0, False
    for ch in reversed(d):
        n = int(ch)
        if alt:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        alt = not alt
    return total % 10 == 0


# ---------------------------------------------------------------- PHONE (UK)
PHONE_RE = re.compile(r"(?<![\w+])(?:(?:\+|00)44[\s-]?(?:\(0\)[\s-]?)?|\(?0)(?:\d[\s\-)]{0,2}){8,10}\d\b")


def phone_nsn(s: str) -> str | None:
    """National significant number: digits after +44 / 0044 / leading 0 (R-32)."""
    t = s.strip()
    t = re.sub(r"\(0\)", "", t)
    d = re.sub(r"[^\d+]", "", t)
    if d.startswith("+44"):
        d = d[3:]
    elif d.startswith("0044"):
        d = d[4:]
    elif d.startswith("0"):
        d = d[1:]
    else:
        return None
    return d if d.isdigit() else None


def is_valid_uk_phone(s: str) -> bool:  # noqa: PLR0911 - one rule per number range reads best
    nsn = phone_nsn(s)
    if not nsn or nsn[0] == "0":
        return False
    first, n = nsn[0], len(nsn)
    if first == "1":
        return n in (9, 10)  # 01: 10, rarely 9 (e.g. 016977 xxxx)
    if first in "23":
        return n == 10  # 02 geographic, 03 UK-wide
    if first == "7":
        return n == 10  # 07 mobile / personal / pager
    if first == "8":
        return n in (7, 9, 10)  # 0800 can be 10, 9 or 7; 0845 10 or 7
    if first == "9":
        return n == 10
    return False  # 04, 06 unused; 05 only legacy


# ---------------------------------------------------------------- NHS NUMBER
NHS_RE = re.compile(r"\b\d{3}[ -]?\d{3}[ -]?\d{4}\b")


def is_valid_nhs(s: str) -> bool:
    """NHS Data Dictionary modulus 11 (R-27)."""
    d = re.sub(r"[ -]", "", s)
    if not re.fullmatch(r"\d{10}", d):
        return False
    total = sum(int(d[i]) * (10 - i) for i in range(9))
    check = 11 - total % 11
    if check == 11:
        check = 0
    if check == 10:
        return False
    return check == int(d[9])


# ---------------------------------------------------------------- PASSPORT (UK)
# HM Passport Office: every series uses 9 numerical digits (R-24). No public check digit on the number.
PASSPORT_RE = re.compile(r"(?i)\bpassport(?:\s+(?:no\.?|number|#))?[:\s]*\b(\d{9})\b")

# ---------------------------------------------------------------- DRIVING LICENCE (GB)
# Structure from Wikipedia 'Driving licence in the United Kingdom' (R-30); month/day classes as in Presidio (R-19).
DL_RE = re.compile(
    r"\b[A-Z9]{5}\d(?:0[1-9]|1[0-2]|5[1-9]|6[0-2])(?:0[1-9]|[12]\d|3[01])\d"
    r"[A-Z][A-Z9]\d[A-Z0-9]{2}(?:\s?\d{2})?\b"
)
