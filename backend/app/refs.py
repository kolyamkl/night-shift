"""Client, policy, claim and case references (type CUSTOM) for the regex layer.

T1 misses these most often (CUSTOM recall about 33% on the fresh split), and a missed one goes to the
AI provider in clear. Their formats differ per organisation (CL-78892, M/2023/218, CLM·1173·RS,
POL GN 147856), so this rule keys on the label in front of the value, not on the value's shape:
"Client code: CL-78892", "Our ref: M/2023/218", "policy number 239-0728815-83".

A value must hold digits, and a bare number needs at least five, so years, clause numbers and
"case 12" stay visible. Company, VAT, invoice, order and ticket numbers stay visible too, as in the
evalkit regex baseline.
"""

import re

from evalkit.spans import Span

_NO = r"(?:no\.?|nos\.?|number|num\.?|id|code|ref(?:erence)?\.?)"
LABEL = re.compile(
    r"(?i)\b(?:"
    r"(?:our|your|my|their)\s+ref(?:erence)?\.?"
    r"|ref(?:erence)?\.?(?:\s+" + _NO + r"){0,2}"
    r"|(?:client|customer|member(?:ship)?|patient|hospital|tenant|employee|staff|account|acct|a/c"
    r"|policy(?:holder)?|claims?"
    r"|case|matter|project|deposit|repair|booking|reservation|application|registration|confirmation|works"
    r"|envelope|transaction"
    r"|frequent\s+flyer"
    r")(?:\s+" + _NO + r"(?:\(s\))?){0,2}"  # "hospital reference number"
    r")"
    r"\s*(?:[:#|]|-(?=\s))?\s*"  # "|" for a label and value in two table cells
)
# One token of a reference: letters, digits and the joiners organisations use inside them.
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9/\-.·#_]*")
UPPER_TOKEN = re.compile(r"[A-Z0-9][A-Z0-9/\-.·#_]*")
DIGIT_GROUP = re.compile(r"\d{3,5}(?![\w/.-])")
KEEP_CONTEXT = re.compile(
    r"(?i)\b(?:company\s+(?:no|number|reg)|registered\s+in|vat|charity\s+(?:no|number)|invoice|order|ticket)\b"
)
DATE = re.compile(r"\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}")
MONEY = re.compile(r"\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2}")  # "DEPOSIT 102.06" is an amount
MAX_LEN = 40


def _value_ok(value: str) -> bool:
    digits = sum(c.isdigit() for c in value)
    letters = sum(c.isalpha() for c in value)
    if not digits or len(value) > MAX_LEN or DATE.fullmatch(value) or MONEY.fullmatch(value.split()[-1]):
        return False
    if not letters:
        return digits >= 5
    return digits >= 4 or len(value) >= 5


def _value_at(text: str, pos: int) -> tuple[int, int] | None:
    """The reference starting at pos: one token, up to four digit groups split by single spaces, or up
    to three upper-case tokens split by single spaces when the first ones are short and hold no digit
    ("POL GN 147856")."""
    m = TOKEN.match(text, pos)
    if not m:
        return None
    end = m.end()
    if DIGIT_GROUP.fullmatch(m.group()):  # a number written in groups: "6997 6487 7759"
        for _ in range(3):
            nxt = DIGIT_GROUP.match(text, end + 1) if text[end:end + 1] == " " else None
            if not nxt:
                break
            end = nxt.end()
    elif len(m.group()) <= 4 and not any(c.isdigit() for c in m.group()) and UPPER_TOKEN.fullmatch(m.group()):
        for _ in range(2):
            nxt = UPPER_TOKEN.match(text, end + 1) if text[end:end + 1] == " " else None
            has_digit = bool(nxt) and any(c.isdigit() for c in nxt.group())
            if not nxt or (not has_digit and len(nxt.group()) > 4):  # "FLAT DEPOSIT" is words, not a code
                break
            end = nxt.end()
            if has_digit:
                break
    while end > pos and text[end - 1] in ".-/#_":  # sentence punctuation, not part of the reference
        end -= 1
    return pos, end


def detect(text: str) -> list[Span]:
    found: list[Span] = []
    for m in LABEL.finditer(text):
        if KEEP_CONTEXT.search(text[max(0, m.start() - 25):m.start()]):
            continue
        at = _value_at(text, m.end())
        if at and _value_ok(text[at[0]:at[1]]):
            found.append(Span(at[0], at[1], "CUSTOM", text[at[0]:at[1]]))
    return found
