"""UK identifier generators and validators (all values are fake).

Every generator takes a ``random.Random`` so output is deterministic per document.
Validators are used by the tests and by ``validate.py``; they accept the written
forms produced here (spaces, dashes, lower case in chat messages).
"""
from __future__ import annotations

import random
import re
from datetime import date

# --------------------------------------------------------------------------- postcodes
INWARD_LETTERS = "ABDEFGHJLNPQRSTUWXYZ"  # inward unit letters never use C I K M O V

POSTCODE_RE = re.compile(
    r"^(GIR ?0AA|[A-PR-UWYZ]([0-9]{1,2}|[A-HK-Y][0-9]{1,2}|[0-9][A-HJKPSTUW]|[A-HK-Y][0-9][ABEHMNPRV-Y]) ?[0-9][ABD-HJLNP-UW-Z]{2})$"
)


def postcode(rng: random.Random, outward: str) -> str:
    return f"{outward} {rng.randrange(10)}{rng.choice(INWARD_LETTERS)}{rng.choice(INWARD_LETTERS)}"


def is_valid_postcode(s: str) -> bool:
    return bool(POSTCODE_RE.match(s.upper().strip()))


# --------------------------------------------------------------------------- NI number
NI_FIRST = "ABCEGHJKLMNOPRSTWXYZ"   # not D F I Q U V
NI_SECOND = "ABCEGHJKLMNPRSTWXYZ"   # not D F I O Q U V
NI_BAD_PREFIX = {"BG", "GB", "KN", "NK", "NT", "TN", "ZZ"}
NI_RE = re.compile(r"^([A-Z]{2}) ?(\d{2}) ?(\d{2}) ?(\d{2}) ?([A-D])$")


def ni_number(rng: random.Random) -> str:
    while True:
        p = rng.choice(NI_FIRST) + rng.choice(NI_SECOND)
        if p not in NI_BAD_PREFIX:
            break
    return p + "".join(str(rng.randrange(10)) for _ in range(6)) + rng.choice("ABCD")


def format_ni(ni: str, style: int) -> str:
    if style == 1:
        return f"{ni[:2]} {ni[2:4]} {ni[4:6]} {ni[6:8]} {ni[8]}"
    if style == 2:
        return f"{ni[:2]} {ni[2:8]} {ni[8]}"
    return ni


def is_valid_ni(s: str) -> bool:
    m = NI_RE.match(s.upper().strip())
    if not m:
        return False
    p = m.group(1)
    return p[0] in NI_FIRST and p[1] in NI_SECOND and p not in NI_BAD_PREFIX


# --------------------------------------------------------------------------- bank details
# (bank display name, 4-letter IBAN bank code, typical sort code prefixes)
BANKS = [
    ("Barclays", "BARC", ["20", "23"]),
    ("Lloyds Bank", "LOYD", ["30", "77"]),
    ("NatWest", "NWBK", ["60", "56", "50"]),
    ("HSBC UK", "HBUK", ["40"]),
    ("Santander", "ABBY", ["09", "72"]),
    ("Nationwide", "NAIA", ["07"]),
    ("Halifax", "HLFX", ["11"]),
    ("Monzo", "MONZ", ["04"]),
    ("Starling Bank", "SRLG", ["60"]),
    ("TSB", "TSBS", ["77", "87"]),
    ("Metro Bank", "MYMB", ["23"]),
    ("Co-operative Bank", "CPBK", ["08"]),
    ("Royal Bank of Scotland", "RBOS", ["83", "16"]),
    ("Bank of Scotland", "BOFS", ["80", "12"]),
]
SORT_RE = re.compile(r"^\d{2}([- ]?)\d{2}\1\d{2}$")


def sort_code(rng: random.Random, prefix: str) -> str:
    return prefix + "".join(str(rng.randrange(10)) for _ in range(4))


def format_sort(sc: str, style: int) -> str:
    if style == 1:
        return f"{sc[:2]} {sc[2:4]} {sc[4:]}"
    if style == 2:
        return sc
    return f"{sc[:2]}-{sc[2:4]}-{sc[4:]}"


def is_valid_sort(s: str) -> bool:
    return bool(SORT_RE.match(s.strip()))


def account_number(rng: random.Random) -> str:
    return "".join(str(rng.randrange(10)) for _ in range(8))


def is_valid_account(s: str) -> bool:
    return bool(re.fullmatch(r"\d{8}|\d{4} \d{4}", s.strip()))


def iban_check(country: str, bban: str) -> str:
    rearranged = bban + country + "00"
    num = "".join(str(int(c, 36)) for c in rearranged)
    return f"{98 - int(num) % 97:02d}"


def gb_iban(bank_code: str, sc: str, acct: str) -> str:
    bban = bank_code + sc + acct
    return "GB" + iban_check("GB", bban) + bban


def format_iban(iban: str, spaced: bool) -> str:
    return " ".join(iban[i:i + 4] for i in range(0, len(iban), 4)) if spaced else iban


def is_valid_iban(s: str) -> bool:
    s = s.replace(" ", "").upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", s):
        return False
    if s.startswith("GB") and not re.fullmatch(r"GB\d{2}[A-Z]{4}\d{14}", s):
        return False
    num = "".join(str(int(c, 36)) for c in s[4:] + s[:4])
    return int(num) % 97 == 1


# --------------------------------------------------------------------------- cards
def luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _luhn_complete(body: str) -> str:
    for c in "0123456789":
        if luhn_ok(body + c):
            return body + c
    raise AssertionError


def card_number(rng: random.Random, scheme: str) -> str:
    if scheme == "visa":
        body = "4" + "".join(str(rng.randrange(10)) for _ in range(14))
    elif scheme == "mastercard":
        if rng.random() < 0.7:
            pre = str(rng.randint(51, 55))
        else:
            pre = str(rng.randint(2221, 2720))
        body = pre + "".join(str(rng.randrange(10)) for _ in range(15 - len(pre)))
    elif scheme == "amex":
        pre = rng.choice(["34", "37"])
        body = pre + "".join(str(rng.randrange(10)) for _ in range(12))
    else:
        raise ValueError(scheme)
    return _luhn_complete(body)


def format_card(num: str, style: int) -> str:
    if len(num) == 15:  # Amex 4-6-5
        if style == 0:
            return num
        sep = " " if style == 1 else "-"
        return sep.join([num[:4], num[4:10], num[10:]])
    if style == 0:
        return num
    sep = " " if style == 1 else "-"
    return sep.join(num[i:i + 4] for i in range(0, len(num), 4))


def is_valid_card(s: str) -> bool:
    d = re.sub(r"[ -]", "", s)
    return d.isdigit() and 13 <= len(d) <= 19 and luhn_ok(d)


# --------------------------------------------------------------------------- phones
# (area code display, drama-range prefix for local part or None, local length)
# 4-digit area codes with their Ofcom drama-range local prefix
LANDLINES_4 = [("0113", "496"), ("0114", "496"), ("0115", "496"), ("0116", "496"), ("0117", "496"),
               ("0118", "496"), ("0121", "496"), ("0131", "496"), ("0141", "496"), ("0151", "496"),
               ("0161", "496"), ("0191", "498")]
AREAS_5 = ["01223", "01865", "01904", "01225", "01392", "01603", "01273", "01792", "01224", "01382",
           "01522", "01733", "01604", "01452", "01242", "01905", "01244", "01925", "01942", "01274",
           "01482", "01752", "01908", "01582", "01923", "01202", "01632"]
AREAS_3 = ["020", "029", "023", "028", "024"]


def _digits(rng: random.Random, n: int) -> str:
    return "".join(str(rng.randrange(10)) for _ in range(n))


def mobile_number(rng: random.Random) -> str:
    """Return the national significant number '7xxxxxxxxx' (10 digits)."""
    if rng.random() < 0.35:
        return "7700900" + _digits(rng, 3)  # Ofcom drama range
    return "7" + rng.choice("1234589") + _digits(rng, 8)


def format_mobile(nsn: str, style: int) -> str:
    if style == 0:
        return f"0{nsn[:4]} {nsn[4:]}"             # 07700 900123
    if style == 1:
        return f"0{nsn}"                           # 07700900123
    if style == 2:
        return f"+44 {nsn[:4]} {nsn[4:]}"          # +44 7700 900123
    if style == 3:
        return f"+44 (0){nsn[:4]} {nsn[4:]}"       # +44 (0)7700 900123
    if style == 4:
        return f"0{nsn[:4]} {nsn[4:7]} {nsn[7:]}"  # 07700 900 123
    if style == 5:
        return f"+44{nsn}"                         # +447700900123
    return f"(0{nsn[:4]}) {nsn[4:]}"               # (07700) 900123


def landline_number(rng: random.Random, style: int) -> str:
    """UK landline in one of 4 written styles (national, +44, (area), +44 (0))."""
    r = rng.random()
    if r < 0.4:
        area, pre = rng.choice(LANDLINES_4)
        groups = [area, pre, (str(rng.randrange(1)) if rng.random() < 0.6 else str(rng.randrange(10))) + _digits(rng, 3)]
    elif r < 0.7:
        area = rng.choice(AREAS_5)
        groups = [area, ("960" + _digits(rng, 3)) if area == "01632" else (str(rng.randint(2, 7)) + _digits(rng, 5))]
    else:
        area = rng.choice(AREAS_3)
        if area == "020" and rng.random() < 0.4:
            first = "7946"
            rest = "0" + _digits(rng, 3)
        else:
            first = str(rng.choice([3, 7, 8] if area == "020" else [2, 3, 7, 8, 9])) + _digits(rng, 3)
            rest = _digits(rng, 4)
        groups = [area, first, rest]
    nat = groups[0][1:]
    tail = " ".join(groups[1:])
    if style == 0:
        return f"{groups[0]} {tail}"
    if style == 1:
        return f"+44 {nat} {tail}"
    if style == 2:
        return f"({groups[0]}) {tail}"
    return f"+44 (0){nat} {tail}"


PHONE_RE = re.compile(r"^(\+44 ?(\(0\))?|0|\(0)[\d ()]{8,16}$")


def is_valid_phone(s: str) -> bool:
    d = re.sub(r"[^\d+]", "", s)
    if d.startswith("+44"):
        d = "0" + d[3:]
        if d.startswith("00"):
            d = d[1:]
    return bool(PHONE_RE.match(s.strip())) and d.startswith("0") and len(d) in (10, 11)


# --------------------------------------------------------------------------- ID documents
def passport_number(rng: random.Random) -> str:
    return str(rng.randint(1, 9)) + _digits(rng, 8)


def is_valid_passport(s: str) -> bool:
    return bool(re.fullmatch(r"\d{9}", s.replace(" ", "")))


def driving_licence(rng: random.Random, last: str, first: str, middle: str, dob: date, female: bool) -> str:
    """16-character DVLA-style licence number (structure only; check letters random)."""
    import unicodedata

    def ascii_letters(s: str) -> str:
        s = unicodedata.normalize("NFKD", s)
        return "".join(c for c in s if c.isascii() and c.isalpha()).upper()

    sur = ascii_letters(last)
    if sur.startswith("MAC"):
        sur = "MC" + sur[3:]
    sur = (sur + "99999")[:5]
    month = dob.month + (50 if female else 0)
    y = f"{dob.year % 100:02d}"
    inits = (ascii_letters(first)[:1] + ascii_letters(middle)[:1] + "99")[:2]
    check = rng.choice("ABCDEFGHJKLMNPRSTUWXYZ") + rng.choice("ABCDEFGHJKLMNPRSTUWXYZ")
    return f"{sur}{y[0]}{month:02d}{dob.day:02d}{y[1]}{inits}9{check}"


LICENCE_RE = re.compile(r"^[A-Z9]{5}(\d)(\d{2})(\d{2})(\d)[A-Z9]{2}\d[A-Z]{2}$")


def is_valid_licence(s: str) -> bool:
    m = LICENCE_RE.match(s.replace(" ", "").upper())
    if not m:
        return False
    month, day = int(m.group(2)), int(m.group(3))
    return (1 <= month <= 12 or 51 <= month <= 62) and 1 <= day <= 31


def format_licence(lic: str, spaced: bool) -> str:
    return f"{lic[:5]} {lic[5:11]} {lic[11:]}" if spaced else lic


def nhs_number(rng: random.Random) -> str:
    while True:
        # 60% in the 999 range NHS England reserves for test data (never issued), 40% elsewhere so the
        # model does not learn the prefix as a cue
        body = ("999" + _digits(rng, 6)) if rng.random() < 0.6 else (str(rng.choice([4, 6, 7])) + _digits(rng, 8))
        s = sum(int(d) * w for d, w in zip(body, range(10, 1, -1)))
        check = 11 - s % 11
        if check == 11:
            check = 0
        if check == 10:
            continue
        return body + str(check)


def format_nhs(n: str, spaced: bool) -> str:
    return f"{n[:3]} {n[3:6]} {n[6:]}" if spaced else n


def is_valid_nhs(s: str) -> bool:
    d = s.replace(" ", "").replace("-", "")
    if not re.fullmatch(r"\d{10}", d):
        return False
    tot = sum(int(c) * w for c, w in zip(d[:9], range(10, 1, -1)))
    check = 11 - tot % 11
    if check == 11:
        check = 0
    return check != 10 and check == int(d[9])


# --------------------------------------------------------------------------- dates
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]


def ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }".replace(" ", "")


DATE_STYLES = 11


def format_date(d: date, style: int) -> str:
    m = MONTHS[d.month - 1]
    if style == 0:
        return f"{d.day:02d}/{d.month:02d}/{d.year}"
    if style == 1:
        return f"{d.day} {m} {d.year}"
    if style == 2:
        return f"{ordinal(d.day)} {m} {d.year}"
    if style == 3:
        return f"{d.year}-{d.month:02d}-{d.day:02d}"
    if style == 4:
        return f"{d.day:02d}/{d.month:02d}/{d.year % 100:02d}"
    if style == 5:
        return f"{d.day} {m[:3]} {d.year}"
    if style == 6:
        return f"{d.day:02d}.{d.month:02d}.{d.year}"
    if style == 7:
        return f"{d.day:02d}-{d.month:02d}-{d.year}"
    if style == 8:
        return f"{m} {d.day}, {d.year}"
    if style == 9:
        return f"{d.day}-{m[:3]}-{d.year}"
    return f"{d.day}.{d.month}.{d.year % 100:02d}"


def random_date(rng: random.Random, start: date, end: date) -> date:
    return date.fromordinal(rng.randint(start.toordinal(), end.toordinal()))


def dob(rng: random.Random, min_age: int = 18, max_age: int = 85, today: date = date(2026, 10, 24)) -> date:
    start = date(today.year - max_age, 1, 1)
    end = date(today.year - min_age, today.month, min(today.day, 28))
    return random_date(rng, start, end)


# --------------------------------------------------------------------------- org ids
def from_pattern(rng: random.Random, pattern: str, year: int | None = None) -> str:
    """Pattern: '#' digit, '@' upper letter, '{yyyy}' / '{yy}' year, other chars literal."""
    y = year if year is not None else rng.randint(2017, 2026)
    pattern = pattern.replace("{yyyy}", str(y)).replace("{yy}", f"{y % 100:02d}")
    out = []
    for ch in pattern:
        if ch == "#":
            out.append(str(rng.randrange(10)))
        elif ch == "@":
            out.append(rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ"))
        else:
            out.append(ch)
    return "".join(out)


_UTR_LOOKUP = "21987654321"
_UTR_W = (6, 7, 8, 9, 10, 5, 4, 3, 2)


def utr(rng: random.Random, spaced: bool) -> str:
    """10-digit Unique Taxpayer Reference whose first digit is the HMRC check digit."""
    body = _digits(rng, 9)
    first = _UTR_LOOKUP[sum(int(c) * w for c, w in zip(body, _UTR_W)) % 11]
    d = first + body
    return f"{d[:5]} {d[5:]}" if spaced else d


def is_valid_utr(s: str) -> bool:
    d = s.replace(" ", "").strip("Kk")
    if not re.fullmatch(r"\d{10}", d):
        return False
    return d[0] == _UTR_LOOKUP[sum(int(c) * w for c, w in zip(d[1:], _UTR_W)) % 11]


def vat_number(rng: random.Random) -> str:
    """GB VAT registration number (9 digits, weighted mod-97 check, HMRC 97 rule)."""
    body = str(rng.randint(1, 9)) + _digits(rng, 6)
    total = sum(int(c) * w for c, w in zip(body, range(8, 1, -1)))
    return body + f"{(-total) % 97:02d}"


def format_vat(v: str, style: int) -> str:
    return [f"GB {v[:3]} {v[3:7]} {v[7:]}", f"GB{v}", f"{v[:3]} {v[3:7]} {v[7:]}"][style % 3]


def is_valid_vat(s: str) -> bool:
    d = s.replace(" ", "").upper()
    if d.startswith("GB"):
        d = d[2:]
    if not re.fullmatch(r"\d{9}", d):
        return False
    total = sum(int(c) * w for c, w in zip(d[:7], range(8, 1, -1))) + int(d[7:])
    return total % 97 == 0 or (total + 55) % 97 == 0
