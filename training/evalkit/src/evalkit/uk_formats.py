"""UK identifier regexes (detection) and validators (strict checks).

Detection regexes are recall-oriented: they find candidate spans in running text.
Validators are precision-oriented: they say whether a candidate is a well-formed value.
Use both: regex -> validator -> (optional) context words -> label.
"""
import re

# ---------------------------------------------------------------- POSTCODE
# Rules from Wikipedia "Postcodes in the United Kingdom" > Validation (R-26):
# pos1 not Q,V,X; pos2 not I,J,Z; A9A third letter in ABCDEFGHJKPSTUW;
# AA9A fourth letter in ABEHMNPRVWXY; inward unit letters never C,I,K,M,O,V.
_OUTWARD = (
    r"(?:[A-PR-UWYZ][0-9]{1,2}"          # A9, A99
    r"|[A-PR-UWYZ][A-HK-Y][0-9]{1,2}"    # AA9, AA99
    r"|[A-PR-UWYZ][0-9][A-HJKPSTUW]"     # A9A
    r"|[A-PR-UWYZ][A-HK-Y][0-9][ABEHMNPRVWXY])"  # AA9A
)
_INWARD = r"[0-9][ABD-HJLNP-UW-Z]{2}"
POSTCODE_RE = re.compile(rf"\b(?:GIR ?0AA|{_OUTWARD} ?{_INWARD})\b", re.I)

def is_valid_postcode(s: str) -> bool:
    s = s.strip().upper()
    return re.fullmatch(rf"(?:GIR ?0AA|{_OUTWARD} ?{_INWARD})", s) is not None

# Official gov.uk regex, copied verbatim from the Bulk Data Transfer PDF (R-75), for comparison only.
GOVUK_POSTCODE_RE_VERBATIM = (r"^([Gg][Ii][Rr] 0[Aa]{2})|((([A-Za-z][0-9]{1,2})|(([A-Za-z][A-Ha-hJ-Yj-y][0-9]{1,2})"
                              r"|(([A Za-z][0-9][A-Za-z])|([A-Za-z][A-Ha-hJ-Yj-y][0-9]?[A-Za-z])))) [0-9][A-Za-z]{2})$")

# ---------------------------------------------------------------- NI NUMBER
# HMRC NIM39110 (R-14): D,F,I,Q,U,V never 1st or 2nd letter; O never 2nd;
# BG, GB, KN, NK, NT, TN, ZZ never used; suffix always A-D.
NINO_RE = re.compile(
    r"\b(?!BG|GB|KN|NK|NT|TN|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z]"
    r"[ -]?\d{2}[ -]?\d{2}[ -]?\d{2}[ -]?[A-D]\b", re.I)
NINO_ADMIN_PREFIXES = {"OO", "FY", "NC", "PZ", "PY", "TN"}  # HMRC: look like NINOs, not real NINOs

def is_valid_nino(s: str) -> bool:
    s = re.sub(r"[ -]", "", s.upper())
    if not re.fullmatch(r"[A-Z]{2}\d{6}[A-D]", s):
        return False
    p1, p2 = s[0], s[1]
    if p1 in "DFIQUV" or p2 in "DFIQUVO":
        return False
    if s[:2] in {"BG", "GB", "KN", "NK", "NT", "TN", "ZZ"}:
        return False
    if s == "PP999999P":
        return False
    return True

# ---------------------------------------------------------------- SORT CODE / ACCOUNT
SORT_CODE_RE = re.compile(r"\b\d{2}([- ])\d{2}\1\d{2}\b")      # same separator twice
SORT_CODE_BARE_RE = re.compile(r"(?i)(?<=sort code)[:\s]*\b(\d{6})\b")
ACCOUNT_RE = re.compile(r"\b\d{8}\b")                          # needs context words to label

def is_valid_sort_code(s: str) -> bool:
    return re.fullmatch(r"\d{2}([- ]?)\d{2}\1\d{2}", s.strip()) is not None

def normalise_account(acc: str, sort_code: str = "") -> tuple[str, str] | None:
    """Vocalink rules for nonstandard lengths (R-49, section 2.1.2). Returns (sort, 8-digit account)."""
    d = re.sub(r"[ -]", "", acc)
    sc = re.sub(r"\D", "", sort_code)
    if not d.isdigit():
        return None
    if len(d) == 8:
        return sc, d
    if len(d) == 7:
        return sc, "0" + d
    if len(d) == 6:
        return sc, "00" + d
    if len(d) == 9 and len(sc) == 6:          # Santander: last sort digit := first account digit
        return sc[:5] + d[0], d[1:]
    if len(d) == 10:                          # NatWest: last 8; Co-op/Leeds BS: first 8 (bank-specific)
        return sc, d[-8:]
    return None

def is_valid_account_number(s: str) -> bool:
    return re.fullmatch(r"\d{8}", re.sub(r"[ -]", "", s.strip())) is not None

# ---------------------------------------------------------------- IBAN (GB)
IBAN_GB_RE = re.compile(r"\bGB\d{2} ?[A-Z]{4} ?\d{4} ?\d{4} ?\d{4} ?\d{2}\b", re.I)

def iban_mod97(iban: str) -> int:
    s = re.sub(r"\s", "", iban).upper()
    s = s[4:] + s[:4]
    return int("".join(str(int(c, 36)) for c in s)) % 97

def is_valid_iban_gb(s: str) -> bool:
    s = re.sub(r"\s", "", s).upper()
    return re.fullmatch(r"GB\d{2}[A-Z]{4}\d{14}", s) is not None and iban_mod97(s) == 1

def make_iban_gb(bank4: str, sort6: str, acc8: str) -> str:
    bban = bank4 + sort6 + acc8
    check = 98 - iban_mod97("GB00" + bban)
    return f"GB{check:02d}{bban}"

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

def card_scheme(d: str) -> str | None:
    """IIN ranges and lengths from Wikipedia 'Payment card number' (R-29)."""
    n = len(d)
    p = lambda k: int(d[:k])
    if d[0] == "4" and n in (13, 16, 19):
        return "visa"
    if (51 <= p(2) <= 55 or 2221 <= p(4) <= 2720) and n == 16:
        return "mastercard"
    if p(2) in (34, 37) and n == 15:
        return "amex"
    if (p(4) in (6759,) or p(6) in (676770, 676774)) and 12 <= n <= 19:
        return "maestro_uk"
    if p(4) in (5018, 5020, 5038, 5893, 6304, 6759, 6761, 6762, 6763) and 12 <= n <= 19:
        return "maestro"
    if (p(4) == 6011 or 644 <= p(3) <= 649 or p(2) == 65) and 16 <= n <= 19:
        return "discover"
    if 3528 <= p(4) <= 3589 and 16 <= n <= 19:
        return "jcb"
    if p(2) in (30, 36, 38, 39) and 14 <= n <= 19:
        return "diners"
    if p(2) == 62 and 16 <= n <= 19:
        return "unionpay"
    return None

def is_valid_card(s: str) -> bool:
    d = re.sub(r"[ -]", "", s)
    return d.isdigit() and 12 <= len(d) <= 19 and luhn_ok(d) and card_scheme(d) is not None

# ---------------------------------------------------------------- PHONE (UK)
PHONE_RE = re.compile(
    r"(?<![\w+])(?:(?:\+|00)44[\s-]?(?:\(0\)[\s-]?)?|\(?0)"
    r"(?:\d[\s\-)]{0,2}){8,10}\d\b")

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

def is_valid_uk_phone(s: str) -> bool:
    nsn = phone_nsn(s)
    if not nsn or nsn[0] == "0":
        return False
    first, n = nsn[0], len(nsn)
    if first == "1":
        return n in (9, 10)            # 01: 10, rarely 9 (e.g. 016977 xxxx)
    if first in "23":
        return n == 10                 # 02 geographic, 03 UK-wide
    if first == "7":
        return n == 10                 # 07 mobile / personal / pager
    if first == "8":
        return n in (7, 9, 10)         # 0800 can be 10, 9 or 7; 0845 10 or 7
    if first == "9":
        return n == 10
    return False                       # 04, 06 unused; 05 only legacy

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

def make_nhs(first9: str) -> str | None:
    total = sum(int(first9[i]) * (10 - i) for i in range(9))
    check = 11 - total % 11
    check = 0 if check == 11 else check
    return None if check == 10 else first9 + str(check)

# ---------------------------------------------------------------- PASSPORT (UK)
# HM Passport Office: every series uses 9 numerical digits (R-24). No public check digit on the number.
PASSPORT_RE = re.compile(r"(?i)\bpassport(?:\s+(?:no\.?|number|#))?[:\s]*\b(\d{9})\b")

def is_valid_uk_passport(s: str) -> bool:
    return re.fullmatch(r"\d{9}", s.strip()) is not None

# ---------------------------------------------------------------- DRIVING LICENCE (GB)
# Structure from Wikipedia 'Driving licence in the United Kingdom' (R-30); month/day classes as in Presidio (R-19).
DL_RE = re.compile(
    r"\b[A-Z9]{5}\d(?:0[1-9]|1[0-2]|5[1-9]|6[0-2])(?:0[1-9]|[12]\d|3[01])\d"
    r"[A-Z][A-Z9]\d[A-Z0-9]{2}(?:\s?\d{2})?\b")

def is_valid_gb_driving_licence(s: str) -> bool:
    t = re.sub(r"\s", "", s.upper())
    if len(t) == 18:
        if not t[16:].isdigit():
            return False
        t = t[:16]
    if not re.fullmatch(r"[A-Z9]{5}\d\d{2}\d{2}\d[A-Z][A-Z9]\d[A-Z0-9]{2}", t):
        return False
    if not re.fullmatch(r"[A-Z]+9*", t[:5]):      # letters, then 9-padding only at the end
        return False
    mm, dd = int(t[6:8]), int(t[8:10])
    if mm > 50:
        mm -= 50                                    # female: month + 50
    if not 1 <= mm <= 12:
        return False
    max_day = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mm - 1]
    return 1 <= dd <= max_day

# ---------------------------------------------------------------- VAT (GB)
VAT_RE = re.compile(r"\bGB ?(?:\d{3} ?\d{4} ?\d{2}(?: ?\d{3})?|GD[0-4]\d{2}|HA[5-9]\d{2})\b", re.I)

def is_valid_gb_vat(s: str) -> bool:
    """HMRC reference-checker VatReferenceChecker (R-72): weights 8..2 on 7 digits, 97-mod or 97-mod after +55."""
    t = re.sub(r"[\s-]", "", s.upper())
    if t.startswith("GB"):
        t = t[2:]
    m = re.fullmatch(r"GD([0-4]\d{2})|HA([5-9]\d{2})", t)
    if m:
        return True
    if not re.fullmatch(r"\d{9}(\d{3})?", t):
        return False
    t9 = t[:9]
    wsum = sum(int(t9[i]) * w for i, w in enumerate([8, 7, 6, 5, 4, 3, 2]))
    expected = int(t9[7:9])
    def check(total: int) -> bool:
        while total > 97:
            total -= 97
        return 97 - total == expected
    return check(wsum) or check(wsum + 55)

# ---------------------------------------------------------------- COMPANIES HOUSE
CH_PREFIXES = ("SC NI OC SO NC LP SL NL R0 FC SF NF GE GS GN SE ES EN AC SA NA ZC SZ NZ "
               "IP SP IC SI NP NV RC SR NR NO").split()      # Companies House URI guide list
CRN_RE = re.compile(rf"\b(?:\d{{8}}|(?:{'|'.join(CH_PREFIXES)})\d{{6}})\b")

def is_valid_crn(s: str) -> bool:
    t = re.sub(r"\s", "", s.upper())
    if t == "00000000":
        return False
    return re.fullmatch(r"\d{8}", t) is not None or (t[:2] in CH_PREFIXES and re.fullmatch(r"\d{6}", t[2:]) is not None and len(t) == 8)

# ---------------------------------------------------------------- UTR
UTR_RE = re.compile(r"\bK?\d{5} ?\d{5}K?\b")

def is_valid_utr(s: str) -> bool:
    """HMRC reference-checker UtrReferenceChecker (R-72): check digit is the FIRST digit."""
    t = re.sub(r"\s", "", s.upper())
    if t.startswith("K"):
        t = t[1:]
    elif t.endswith("K"):
        t = t[:-1]
    if not re.fullmatch(r"\d{10}", t):
        return False
    wsum = sum(int(t[i + 1]) * w for i, w in enumerate([6, 7, 8, 9, 10, 5, 4, 3, 2]))
    return "21987654321"[wsum % 11] == t[0]

def make_utr(last9: str) -> str:
    wsum = sum(int(last9[i]) * w for i, w in enumerate([6, 7, 8, 9, 10, 5, 4, 3, 2]))
    return "21987654321"[wsum % 11] + last9
