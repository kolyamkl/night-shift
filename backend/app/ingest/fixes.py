"""Deterministic repair of identifiers that OCR misreads. No model is involved.

Vision confuses look-alike characters: "1" with "I" or "l", "0" with "O". Inside a run
that has the exact shape of a UK postcode, sort code, GB IBAN, National Insurance number
or a mostly-digit number of four or more characters (account, card and phone number
groups, years), only one reading makes sense, so the look-alikes are mapped back. A run
must already contain real digits, so ordinary words are never touched; a postcode must
match the UK format, and an IBAN repair that reaches the country code or check digits
must pass mod 97.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from .types import Fix

TO_DIGIT = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "|": "1"})
TO_LETTER = str.maketrans({"0": "O", "1": "I"})
LOOKALIKES = set("OoIl|")
D = "[0-9OoIl|]"  # a digit, or a character OCR mistakes for one
# Postcode digits may also come back as "g": Georgia's old-style 9 hangs below the line like a g.
PC_TO_DIGIT = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "|": "1", "g": "9"})
PD = "[0-9OoIl|g]"

# Cyrillic and Greek letters that look like Latin letters or digits. Vision sometimes returns one inside
# an English word ("EX1 ЗAY" for "EX1 3AY"); only tokens that also contain ASCII letters or digits are mapped.
HOMOGLYPHS = str.maketrans(
    {
        "А": "A",
        "В": "B",
        "Е": "E",
        "З": "3",
        "К": "K",
        "М": "M",
        "Н": "H",
        "О": "O",
        "Р": "P",
        "С": "C",
        "Т": "T",
        "У": "Y",
        "Х": "X",
        "І": "I",
        "Ј": "J",
        "Ѕ": "S",
        "а": "a",
        "е": "e",
        "з": "3",
        "о": "o",
        "р": "p",
        "с": "c",
        "у": "y",
        "х": "x",
        "і": "i",
        "ј": "j",
        "ѕ": "s",
        "Α": "A",
        "Β": "B",
        "Ε": "E",
        "Ζ": "Z",
        "Η": "H",
        "Ι": "I",
        "Κ": "K",
        "Μ": "M",
        "Ν": "N",
        "Ο": "O",
        "Ρ": "P",
        "Τ": "T",
        "Υ": "Y",
        "Χ": "X",
        "ο": "o",
    }
)
HOMOGLYPH_CHARS = "".join(chr(c) for c in HOMOGLYPHS)
MIXED_TOKEN = re.compile(r"\S*[A-Za-z0-9]\S*")

POSTCODE_CAND = re.compile(
    r"(?<![A-Za-z0-9])([A-Z01]{1,2})(" + PD + r")([A-Z0-9Il|]?)(\s?)(" + PD + r")([A-Z]{2})(?![A-Za-z0-9])"
)
POSTCODE_VALID = re.compile(r"^[A-PR-UWYZ][A-Z]?[0-9][A-Z0-9]? [0-9][ABD-HJLNP-UW-Z]{2}$")
SORT_CODE_CAND = re.compile(r"(?<![\w-])(" + D + "{2})([-–])(" + D + r"{2})\2(" + D + r"{2})(?![\w-])")
IBAN_CAND = re.compile(
    r"(?<![A-Za-z0-9])(G[B8])(\s?)(" + D + r"{2})(\s?)([A-Z]{4})((?:\s?" + D + r"){14})(?![A-Za-z0-9])"
)
NI_CAND = re.compile(
    r"(?<![A-Za-z0-9])([A-Z]{2})(\s?)(" + D + r"{2})(\s?)(" + D + r"{2})(\s?)(" + D + r"{2})(\s?)([A-D])(?![A-Za-z0-9])"
)
DIGIT_RUN_CAND = re.compile(r"(?<![A-Za-z0-9])(?=[0-9OoIl|]*[0-9])[0-9OoIl|]{4,}(?![A-Za-z0-9])")
STRAY_BEFORE_AT = re.compile(r"(?<=[A-Za-z0-9._%+'-])[/\\|,]@(?=[A-Za-z0-9-]+\.[A-Za-z]{2,})")
SPACE_AFTER_AT = re.compile(r"(?<=[A-Za-z0-9._%+'-]@)\s+(?=[A-Za-z0-9-]+\.[A-Za-z]{2,})")


def _real_digits(s: str) -> int:
    return sum(ch.isdigit() for ch in s)


def _lookalikes(s: str) -> int:
    return sum(ch in LOOKALIKES for ch in s)


def _iban_ok(compact: str) -> bool:
    moved = compact[4:] + compact[:4]
    return int("".join(str(int(ch, 36)) for ch in moved)) % 97 == 1


def _postcode(m: re.Match) -> str | None:
    area, district, third, _space, sector, unit = m.groups()
    third = third.translate(TO_DIGIT) if third in LOOKALIKES else third
    fixed = f"{area.translate(TO_LETTER)}{district.translate(PC_TO_DIGIT)}{third} {sector.translate(PC_TO_DIGIT)}{unit}"
    if _real_digits(m.group()) < 1 or not POSTCODE_VALID.match(fixed):
        return None
    return fixed


def _sort_code(m: re.Match) -> str | None:
    if _real_digits(m.group()) < 4:
        return None
    a, sep, b, c = m.groups()
    return f"{a.translate(TO_DIGIT)}{sep}{b.translate(TO_DIGIT)}{sep}{c.translate(TO_DIGIT)}"


def _iban(m: re.Match) -> str | None:
    _country, s1, check, s2, bank, rest = m.groups()
    fixed = f"GB{s1}{check.translate(TO_DIGIT)}{s2}{bank}{rest.translate(TO_DIGIT)}"
    return fixed if _iban_ok(re.sub(r"\s", "", fixed)) else None


def _ni(m: re.Match) -> str | None:
    if _real_digits(m.group()) < 4:
        return None
    prefix, s1, a, s2, b, s3, c, s4, suffix = m.groups()
    return f"{prefix}{s1}{a.translate(TO_DIGIT)}{s2}{b.translate(TO_DIGIT)}{s3}{c.translate(TO_DIGIT)}{s4}{suffix}"


def _digit_run(m: re.Match) -> str | None:
    run = m.group()
    if _real_digits(run) < 3 or _lookalikes(run) * 3 > len(run):
        return None
    return run.translate(TO_DIGIT)


RULES: list[tuple[str, re.Pattern, Callable[[re.Match], str | None]]] = [
    ("iban", IBAN_CAND, _iban),
    ("ni_number", NI_CAND, _ni),
    ("sort_code", SORT_CODE_CAND, _sort_code),
    ("postcode", POSTCODE_CAND, _postcode),
    ("digits", DIGIT_RUN_CAND, _digit_run),
]


def fix_identifiers(text: str, page: int = 0) -> tuple[str, list[Fix]]:
    """Return the repaired text and the list of repairs made, in order."""
    fixes: list[Fix] = []

    def sub_homoglyphs(m: re.Match) -> str:
        token = m.group()
        if not any(ch in HOMOGLYPH_CHARS for ch in token):
            return token
        fixed = token.translate(HOMOGLYPHS)
        fixes.append(Fix(page=page, kind="homoglyph", before=token, after=fixed))
        return fixed

    text = MIXED_TOKEN.sub(sub_homoglyphs, text)
    for kind, pattern, repair in RULES:

        def sub(m: re.Match, kind=kind, repair=repair) -> str:
            fixed = repair(m)
            if fixed is None or fixed == m.group():
                return m.group()
            fixes.append(Fix(page=page, kind=kind, before=m.group(), after=fixed))
            return fixed

        text = pattern.sub(sub, text)
    for pattern, replacement in ((STRAY_BEFORE_AT, "@"), (SPACE_AFTER_AT, "")):

        def sub_email(m: re.Match, replacement=replacement) -> str:
            fixes.append(Fix(page=page, kind="email", before=m.group(), after=replacement))
            return replacement

        text = pattern.sub(sub_email, text)
    return text, fixes
