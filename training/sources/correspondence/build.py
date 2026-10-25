#!/usr/bin/env python3
"""Render the correspondence templates into data/docs/correspondence.jsonl.

Usage (from the repo root):
    python training/sources/correspondence/build.py            # render, check, write
    python training/sources/correspondence/build.py --check    # check the existing JSONL only

Every template in data/templates/correspondence/<source_id>.txt is rendered
FILLS times with fresh fake values. The answer key (entity offsets, types and
entity ids) is recorded by this code while it renders; nothing here calls an LLM.
Output is reproducible for a given seed and pinned Faker version.

Template format
---------------
Header lines start with "# key: value" and end with a line "# ---".
Keys used: source_id, url, licence, kind, subtype, year_shifts, static_hard_cases,
sweep_allow (space-separated literal strings that look like identifiers but are not,
e.g. dates in attachment file names; the sweeps skip exactly these strings),
locales (space-separated pool the fill's locale is drawn from; default "uk uk us").

Body syntax:
  {{TYPE:key|form}}   a slot. Slots with the same TYPE and key are the same
                      real-world person or thing and share one entity_id.
  [[opt:text]]        optional text, kept with probability 0.5.
  [[opt=0.7:text]]    optional text with an explicit probability.
  [[alt:a||b||c]]     one alternative, chosen per fill.
  @group after opt/alt ([[opt@subj:...]], [[alt@sig:...]]) makes every block
  in that group take the same decision within one fill. Grouped alts rotate
  through their options by fill number; ungrouped ones are random.
  Blocks may be nested; the innermost blocks are resolved first.

Entity slots (type is the answer-key type):
  PERSON   forms: full, full_m, full_mi, first_middle_last, first, first_var,
           first_var_last, last, title_last, title_full, last_comma_first,
           last_comma_first_m, last_comma_first_mi, last_first, initials,
           initials_dot, initial_last, upper_full, upper_last,
           upper_last_slash_first, upper_last_comma_first
  EMAIL    form is an address pattern built from the person under `key`:
           <first> <last> <f> <m> <l> <lastN> <firstN> <N> (digit) <role>
           (generic mailbox word). Token case sets output case:
           <first> -> "anna", <First> -> "Anna", <FIRST> -> "ANNA".
  PHONE    forms: any, landline, mobile, intl, ext4, ext5
  ADDRESS  forms: lines, oneline, any; options: upper, indent=N, quote,
           home (no office prefix), office (no flat prefix).
           Renders ADDRESS spans (one per line) plus a POSTCODE span.
  CUSTOM   form is a format family: client_code, matter, case_triplet, pnr,
           loyalty, conf_9d_alpha, hotel_conf, student_id, tenancy_ref,
           employee_no
  CARD     forms: full, spaced, last4
  BANK_ACCOUNT forms: full, last4 (key shared with SORT_CODE and IBAN)
  SORT_CODE, IBAN (forms: compact, spaced), NI_NUMBER (compact, spaced),
  DOB (forms: uk, long, air), ID_DOC (form: passport)

Non-entity slots (rendered text is not labelled):
  {{DATE:2001-10-05T11:54:50|style}}  styles: rfc, long, notes, notes_s,
           wrote, air, airlong, dow3, year, mdy, monthday, letter (date line of
           a letter, one written style per fill), monthyear. Dates move by the
           fill's year shift (calendar-preserving) and use the fill's locale.
  {{TRAP:pool}}  over-redaction trap phrase from a pool (place, venue).
"""
import argparse
import datetime as dt
import json
import random
import re
import sys
import unicodedata
import zlib
from pathlib import Path

from faker import Faker

ROOT = Path(__file__).resolve().parents[3]
TPL_DIR = ROOT / "data" / "templates" / "correspondence"
OUT = ROOT / "data" / "docs" / "correspondence.jsonl"
GROUP = "correspondence"
SEED = 20261023
FILLS = 5
EVAL_SOURCES = {"R5", "R7", "R9"}
TYPES = {"PERSON", "ADDRESS", "POSTCODE", "EMAIL", "PHONE", "BANK_ACCOUNT", "SORT_CODE",
         "IBAN", "CARD", "NI_NUMBER", "DOB", "ID_DOC", "CUSTOM"}

# ---------------------------------------------------------------- name pools
# Team pack 9.4: first names that are also common words.
COMMON_WORD_NAMES = {
    "m": ["Will", "Mark", "Bill", "Frank", "Robin", "Rich", "Pat", "Sonny", "Guy", "Jack"],
    "f": ["Rose", "Grace", "Hope", "May", "Jo", "Faith", "Ivy", "Holly", "Dawn", "Joy",
          "Iris", "Amber", "Penny", "Sky"],
}
# Transliterated and non-English names: (first, last, gender, other spellings of first).
INTL_NAMES = [
    ("Oleksandr", "Kovalenko", "m", ["Alexander", "Sasha"]),
    ("Olena", "Shevchuk", "f", ["Elena", "Helen"]),
    ("Siobhán", "Ní Bhriain", "f", ["Siobhan"]),
    ("Aoife", "Ó Murchú", "f", ["Aoife"]),
    ("Dmitri", "Volkov", "m", ["Dmitry", "Dima"]),
    ("Iryna", "Bondarenko", "f", ["Irina"]),
    ("Yusuf", "Al-Hashimi", "m", ["Youssef"]),
    ("Mehmet", "Yılmaz", "m", ["Mehmed"]),
    ("Agnieszka", "Wiśniewska", "f", ["Aga"]),
    ("Bartosz", "Wróblewski", "m", ["Bart"]),
    ("Priya", "Raghunathan", "f", []),
    ("Oluwaseun", "Adeyemi", "m", ["Seun"]),
    ("Chidinma", "Okonkwo", "f", ["Dinma"]),
    ("Wei", "Zhang", "m", []),
    ("Lan", "Nguyễn", "f", ["Lan Thi"]),
    ("Jürgen", "Weiß", "m", ["Juergen"]),
    ("Anaïs", "Lefèvre", "f", ["Anais"]),
    ("Rhodri", "ap Gwilym", "m", []),
    ("Eilidh", "MacLeòid", "f", ["Eilish"]),
    ("Kwame", "Mensah", "m", []),
    ("Fatima", "Begum", "f", []),
    ("Arjun", "Venkataraman", "m", []),
    ("Sinéad", "O'Driscoll", "f", ["Sinead"]),
    ("Zoë", "Fairbairn-Ndlovu", "f", ["Zoe"]),
]
NICKNAMES = {
    "William": ["Will", "Bill"], "Robert": ["Rob", "Bob"], "Richard": ["Rich"],
    "Margaret": ["Maggie"], "Elizabeth": ["Liz", "Beth"], "Joanne": ["Jo"], "Joanna": ["Jo"],
    "Josephine": ["Jo"], "Thomas": ["Tom"], "James": ["Jim", "Jamie"], "Daniel": ["Dan"],
    "Michael": ["Mike"], "Christopher": ["Chris"], "Katherine": ["Kate"], "Catherine": ["Cath"],
    "Rebecca": ["Becky"], "Jennifer": ["Jen"], "Benjamin": ["Ben"], "Samuel": ["Sam"],
    "Alexander": ["Alex"], "Victoria": ["Vicky"], "Patrick": ["Pat"], "Edward": ["Ed", "Ted"],
    "Matthew": ["Matt"], "Nicholas": ["Nick"], "Andrew": ["Andy"], "Deborah": ["Deb"],
}
TOWNS = [  # (town, postcode area); towns are not personal data
    ("Leeds", "LS"), ("Manchester", "M"), ("Bristol", "BS"), ("Kendal", "LA"), ("Norwich", "NR"),
    ("Cardiff", "CF"), ("Glasgow", "G"), ("Edinburgh", "EH"), ("Belfast", "BT"), ("York", "YO"),
    ("Cambridge", "CB"), ("Oxford", "OX"), ("Brighton", "BN"), ("Exeter", "EX"), ("Sheffield", "S"),
    ("Nottingham", "NG"), ("Leicester", "LE"), ("Reading", "RG"), ("Newcastle upon Tyne", "NE"),
    ("Liverpool", "L"), ("Birmingham", "B"), ("Bath", "BA"), ("Swansea", "SA"), ("Aberdeen", "AB"),
    ("Derby", "DE"), ("Coventry", "CV"), ("Carlisle", "CA"), ("Durham", "DH"), ("Truro", "TR"),
    ("Lincoln", "LN"), ("Ipswich", "IP"), ("Chester", "CH"), ("Wakefield", "WF"), ("Harrogate", "HG"),
    ("London", "LONDON"),
]
LONDON_DISTRICTS = ["EC1V", "EC2A", "EC3M", "EC4Y", "WC1H", "WC2B", "W1T", "SW1P", "SE1", "SE15",
                    "N7", "E14", "NW1", "SW11", "E2", "N16"]
STREETS = ["Mill Lane", "Church Street", "Station Road", "Oak Road", "Rose Avenue", "Victoria Street",
           "High Street", "Park Terrace", "Queen's Road", "Albion Place", "Hope Street", "Granby Row"]
STREET_BASES = ["Oak", "Elm", "Ash", "Mill", "Church", "Station", "Park", "Victoria", "Albert", "Queen's",
                "King's", "Manor", "Chapel", "Meadow", "Orchard", "Rose", "Grange", "Beech", "Willow", "Abbey"]
STREET_SUFFIXES = ["Road", "Street", "Lane", "Avenue", "Close", "Drive", "Way", "Crescent", "Grove",
                   "Terrace", "Gardens", "Place", "Row", "Walk", "Mews", "Court"]
OFFICE_PREFIX = ["Floor 3", "2nd Floor", "Suite 410", "Unit 7", "Level 12", "Room 3.14"]
ROLE_MAILBOXES = ["messaging.administration", "it.servicedesk", "records.management", "postmaster",
                  "compliance.office", "mail.admin"]
TRAPS = {
    "place": ["the Oak Road works", "the Rose Garden", "the Mill Lane depot", "the Hope Street bridge",
              "the Victoria Road junction", "Grace Hall", "the May Street car park"],
    "venue": ["the Rose Garden restaurant", "Will's Kitchen on Station Road", "the Grace Hotel",
              "the Hope and Anchor", "the Ivy"],
}
BANK_CODES = ["NWBK", "BARC", "LOYD", "HBUK", "MIDL", "SRLG", "NAIA", "CPBK", "MONZ", "ABBY"]
LANDLINES = [("020", 8), ("0121", 7), ("0113", 7), ("0114", 7), ("0115", 7), ("0116", 7),
             ("0117", 7), ("0118", 7), ("0131", 7), ("0141", 7), ("0151", 7), ("0161", 7),
             ("0191", 7), ("029", 8), ("028", 8), ("01223", 6), ("01865", 6), ("01904", 6),
             ("01392", 6), ("01273", 6), ("01539", 6)]
PC_LETTERS = "ABDEFGHJLNPQRSTUWXYZ"
NI_FIRST = "ABCEGHJKLMNOPRSTWXYZ"
NI_SECOND = "ABCEGHJKLMNPRSTWXYZ"
NI_BAD_PREFIX = {"BG", "GB", "NK", "KN", "TN", "NT", "ZZ"}

# The body may not contain "[[", so a match is always an innermost block.
BLOCK_RE = re.compile(r"\[\[(opt|alt)(?:@(\w+))?(?:=([0-9.]+))?:((?:(?!\[\[).)*?)\]\]", re.S)
SLOT_RE = re.compile(r"\{\{([A-Z_]+):([^|}]*)(?:\|([^}]*))?\}\}")
EMAIL_TOKEN_RE = re.compile(r"<([A-Za-z]+?)(\d?)>")


def ascii_fold(s):
    s = unicodedata.normalize("NFKD", s.replace("ı", "i").replace("ß", "ss"))
    return "".join(c for c in s if not unicodedata.combining(c))


def mailbox_word(s):
    return re.sub(r"[^a-z]", "", ascii_fold(s).lower())


def luhn_complete(digits):
    total = 0
    for i, d in enumerate(reversed(digits + "0")):
        n = int(d)
        if i % 2 == 1:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return digits + str((10 - total % 10) % 10)


def luhn_ok(digits):
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d)
        if i % 2 == 1:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def iban_check(country, bban):
    s = bban + country + "00"
    num = "".join(str(int(c, 36)) for c in s)
    return f"{98 - int(num) % 97:02d}"


def iban_ok(iban):
    s = iban.replace(" ", "")
    s = s[4:] + s[:4]
    return int("".join(str(int(c, 36)) for c in s)) % 97 == 1


class Fill:
    """Fake values for one rendering of one template."""

    def __init__(self, source_id, fill, meta, seed):
        self.rng = random.Random(f"{seed}:{source_id}:{fill}")
        self.fake = Faker("en_GB")
        self.fake.seed_instance(self.rng.getrandbits(32))
        self.locale = self.rng.choice(meta.get("locales", "uk uk us").split())
        shifts = [int(x) for x in meta.get("year_shifts", "0").split()]
        self.year_shift = self.rng.choice(shifts)
        self.people, self.values, self.used_last, self.used_first = {}, {}, set(), set()
        self.tags = set(meta.get("static_hard_cases", "").split())
        # Person categories: guarantee one common-word and one non-English name per document.
        self.categories = ["common", "intl"] + [
            self.rng.choice(["faker", "faker", "faker", "common", "intl"]) for _ in range(40)]
        head = self.categories[:4]
        self.rng.shuffle(head)
        self.categories[:4] = head

    # ------------------------------------------------------------ people
    def person(self, key):
        if key in self.people:
            return self.people[key]
        rng, fake = self.rng, self.fake
        cat = self.categories[len(self.people)] if len(self.people) < len(self.categories) else "faker"
        for _ in range(50):
            gender = rng.choice("mf")
            variants = []
            if cat == "intl":
                first, last, gender, variants = rng.choice(INTL_NAMES)
                variants = list(variants)
            else:
                last = fake.last_name()
                if cat == "common":
                    first = rng.choice(COMMON_WORD_NAMES[gender])
                else:
                    first = fake.first_name_male() if gender == "m" else fake.first_name_female()
                variants = list(NICKNAMES.get(first, []))
            if last not in self.used_last and first not in self.used_first:
                break
        self.used_last.add(last)
        self.used_first.add(first)
        middle = fake.first_name_male() if gender == "m" else fake.first_name_female()
        if gender == "m":
            title = "Mr"
        else:
            title = rng.choice(["Ms", "Ms", "Mrs", "Miss"])
        if rng.random() < 0.1:
            title = "Dr"
        p = {"first": first, "last": last, "middle": middle, "mi": middle[0], "gender": gender,
             "title": title, "variants": variants, "cat": cat, "digit": str(rng.randint(1, 9))}
        if cat == "common" or any(v in sum(COMMON_WORD_NAMES.values(), []) for v in variants):
            p["common"] = True
        self.people[key] = p
        return p

    def render_person(self, key, form):
        p = self.person(key)
        first, last, mi = p["first"], p["last"], p["mi"]
        if p["cat"] == "intl":
            self.tags.add("non_english_name")
        if p.get("common") and form not in ("last", "upper_last"):
            self.tags.add("common_word_name")
        title = p["title"] + ("." if self.locale == "us" else "")
        if form in ("first_var", "first_var_last"):
            options = [first] + p["variants"]
            chosen = self.rng.choice(options)
            if chosen != first:
                self.tags.add("transliterated_name" if p["cat"] == "intl" else "same_person_multiple_forms")
                if chosen in COMMON_WORD_NAMES["m"] + COMMON_WORD_NAMES["f"]:
                    self.tags.add("common_word_name")
            first_v = chosen
        if form in ("first", "first_var", "title_last", "initials", "initials_dot"):
            self.tags.add("signature_or_greeting_name")
        if form in ("initials", "initials_dot", "initial_last"):
            self.tags.add("initials")
        forms = {
            "full": f"{first} {last}",
            "full_m": f"{first} {mi} {last}",
            "full_mi": f"{first} {mi}. {last}",
            "first_middle_last": f"{first} {p['middle']} {last}",
            "first": first,
            "first_var": first_v if form == "first_var" else None,
            "first_var_last": f"{first_v} {last}" if form == "first_var_last" else None,
            "last": last,
            "title_last": f"{title} {last}",
            "title_full": f"{title} {first} {last}",
            "last_comma_first": f"{last}, {first}",
            "last_comma_first_m": f"{last}, {first} {mi}",
            "last_comma_first_mi": f"{last}, {first} {mi}.",
            "last_first": f"{last} {first}",
            "initials": (first[0] + last[0]).upper(),
            "initials_dot": f"{first[0]}.{last[0]}.".upper(),
            "initial_last": f"{first[0]}. {last}",
            "upper_full": f"{first} {last}".upper(),
            "upper_last": ascii_fold(last).upper(),
            "upper_last_slash_first": ascii_fold(f"{last}/{first}").upper(),
            "upper_last_comma_first": f"{last.upper()}, {first}",
        }
        if forms.get(form) is None:
            raise ValueError(f"unknown PERSON form {form!r}")
        return forms[form]

    def render_email(self, key, pattern):
        def token(m):
            name, n = m.group(1), m.group(2)
            low = name.lower()
            if low == "role":
                v = self.values.setdefault(("role", key), self.rng.choice(ROLE_MAILBOXES))
            elif low == "n" and not n:
                v = self.person(key)["digit"]
            else:
                p = self.person(key)
                base = {"first": p["first"], "last": p["last"], "f": p["first"][0], "m": p["mi"],
                        "l": p["last"][0]}[low]
                v = mailbox_word(base)
                if n:
                    v = v[: int(n)]
                self.tags.add("email_from_name")
            if name.isupper():
                return v.upper()
            if name[0].isupper():
                return v.capitalize()
            return v
        return EMAIL_TOKEN_RE.sub(token, pattern)

    # ------------------------------------------------------------ numbers
    def phone(self, key, style):
        k = ("PHONE", key)
        if k in self.values:
            return self.values[k]
        rng = self.rng
        digits = lambda n: "".join(str(rng.randint(0, 9)) for _ in range(n))
        if style == "ext4":
            v = str(rng.randint(2, 8)) + digits(3)
        elif style == "ext5":
            v = str(rng.randint(2, 8)) + digits(4)
        else:
            if style == "any":
                style = rng.choice(["landline", "landline", "mobile", "intl"])
            mobile = style == "mobile" or (style == "intl" and rng.random() < 0.4)
            if mobile:
                body = "7" + str(rng.choice([4, 5, 7, 8, 9])) + digits(8)
                nat = f"0{body[:4]} {body[4:]}"
                intl = rng.choice([f"+44 {body[:4]} {body[4:]}", f"+44 (0){body[:4]} {body[4:]}"])
            else:
                code, n = rng.choice(LANDLINES)
                first = rng.choice("378") if code == "020" else str(rng.randint(2, 8))
                sub = first + digits(n - 1)
                if n == 8:
                    sub_f = f"{sub[:4]} {sub[4:]}"
                elif n == 7:
                    sub_f = f"{sub[:3]} {sub[3:]}"
                else:
                    sub_f = sub
                nat = rng.choice([f"{code} {sub_f}", f"({code}) {sub_f}"])
                intl = rng.choice([f"+44 {code[1:]} {sub_f}", f"+44 (0){code[1:]} {sub_f}"])
            v = intl if style == "intl" else nat
        self.values[k] = v
        return v

    def postcode(self, area):
        rng = self.rng
        if area == "LONDON":
            district = rng.choice(LONDON_DISTRICTS)
        elif len(area) == 1:
            district = area + str(rng.randint(1, 30))
        else:
            district = area + str(rng.randint(1, 20))
        return f"{district} {rng.randint(1, 9)}{rng.choice(PC_LETTERS)}{rng.choice(PC_LETTERS)}"

    def address(self, key, kind=None):
        """kind "home" never gets an office prefix, kind "office" never a flat number."""
        k = ("ADDRESS", key)
        if k not in self.values:
            rng = self.rng
            town, area = rng.choice(TOWNS)
            r = rng.random()
            if r < 0.3:
                street = rng.choice(STREETS)
            else:
                base = self.fake.last_name() if r < 0.65 else rng.choice(STREET_BASES)
                street = f"{base} {rng.choice(STREET_SUFFIXES)}"
            lines = []
            r = rng.random()
            if r < 0.2 and kind != "office":
                lines.append(f"Flat {rng.randint(1, 24)}")
                self.tags.add("flat_number")
            elif r < 0.45 and kind != "home":
                lines.append(rng.choice(OFFICE_PREFIX))
            lines.append(f"{rng.randint(1, 240)} {street}")
            lines.append(town)
            self.values[k] = (lines, self.postcode(area))
        return self.values[k]

    def render_address(self, key, form):
        opts = form.split(",")
        layout = opts[0] or "any"
        upper = "upper" in opts
        indent = next((" " * int(o[7:]) for o in opts if o.startswith("indent=")), "")
        if "quote" in opts:
            indent = "> "
        lines, pc = self.address(key, next((o for o in opts if o in ("home", "office")), None))
        if layout == "any":
            layout = self.rng.choice(["lines", "oneline"])
        if upper:
            lines, pc = [ln.upper() for ln in lines], pc.upper()
        eid, pid = f"address:{key}", f"postcode:{key}"
        segs = []
        if layout == "oneline":
            # A flat or office prefix joins the street with a comma, as usually written.
            segs.append((", ".join(lines), "ADDRESS", eid))
            segs.append((self.rng.choice([" ", ", "]), None, None))
            segs.append((pc, "POSTCODE", pid))
            return segs
        self.tags.add("multiline_address")
        if len(lines) == 3 and self.rng.random() < 0.5:
            lines = [f"{lines[0]}, {lines[1]}", lines[2]]
        for i, ln in enumerate(lines):
            if i:
                segs.append(("\n" + indent, None, None))
            segs.append((ln, "ADDRESS", eid))
        segs.append((self.rng.choice(["\n" + indent, " ", "  "]), None, None))
        segs.append((pc, "POSTCODE", pid))
        return segs

    def bank(self, key):
        k = ("BANK", key)
        if k not in self.values:
            rng = self.rng
            sort = "".join(str(rng.randint(0, 9)) for _ in range(6))
            acct = str(rng.randint(1, 9)) + "".join(str(rng.randint(0, 9)) for _ in range(7))
            code = rng.choice(BANK_CODES)
            bban = code + sort + acct
            iban = "GB" + iban_check("GB", bban) + bban
            self.values[k] = {"sort": f"{sort[:2]}-{sort[2:4]}-{sort[4:]}", "acct": acct, "iban": iban}
        return self.values[k]

    def card(self, key):
        k = ("CARD", key)
        if k not in self.values:
            rng = self.rng
            prefix = rng.choice(["4", "4", "51", "52", "53", "54", "55"])
            body = prefix + "".join(str(rng.randint(0, 9)) for _ in range(15 - len(prefix)))
            self.values[k] = luhn_complete(body)
        return self.values[k]

    def custom(self, key, family):
        k = ("CUSTOM", key)
        if k in self.values:
            return self.values[k]
        rng = self.rng
        d = lambda n: "".join(str(rng.randint(0, 9)) for _ in range(n))
        letters = lambda n, pool="ABCDEFGHJKLMNPQRSTUVWXYZ": "".join(rng.choice(pool) for _ in range(n))
        if family == "client_code":
            v = f"CL-{d(5)}"
        elif family == "matter":
            v = f"M/{rng.randint(2015, 2026)}/{d(3)}"
        elif family == "case_triplet":
            v = f"{letters(3)}-{d(4)}-{letters(1)}{d(1)}"
        elif family == "pnr":
            while True:
                v = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
                if sum(c.isdigit() for c in v) in (1, 2, 3):
                    break
        elif family == "loyalty":
            v = f"{letters(4)}{d(6)}"
        elif family == "conf_9d_alpha":
            v = f"{d(9)}{letters(5)}"
        elif family == "hotel_conf":
            v = str(rng.randint(1, 9)) + d(7)
        elif family == "student_id":
            v = f"S{d(8)}"
        elif family == "tenancy_ref":
            v = f"{d(7)}/{d(2)}"
        elif family == "employee_no":
            v = f"E{d(6)}"
        else:
            raise ValueError(f"unknown CUSTOM family {family!r}")
        self.tags.add("custom_identifier")
        self.values[k] = v
        return v

    def ni(self, key, form):
        k = ("NI", key)
        if k not in self.values:
            while True:
                pre = self.rng.choice(NI_FIRST) + self.rng.choice(NI_SECOND)
                if pre not in NI_BAD_PREFIX:
                    break
            self.values[k] = (pre, "".join(str(self.rng.randint(0, 9)) for _ in range(6)),
                              self.rng.choice("ABCD"))
        pre, num, suf = self.values[k]
        return f"{pre} {num[:2]} {num[2:4]} {num[4:]} {suf}" if form == "spaced" else pre + num + suf

    def dob(self, key, form):
        k = ("DOB", key)
        if k not in self.values:
            start = dt.date(1950, 1, 1)
            self.values[k] = start + dt.timedelta(days=self.rng.randint(0, 50 * 365))
        d = self.values[k]
        self.tags.add("dob_vs_other_dates")
        if form == "air":
            return d.strftime("%d%b%y").upper()
        if form == "long":
            return f"{d.day} {d.strftime('%B %Y')}"
        return d.strftime("%d/%m/%Y")

    # ------------------------------------------------------------ non-entities
    def date(self, iso, style):
        d = dt.datetime.fromisoformat(iso)
        d = d.replace(year=d.year + self.year_shift)
        us = self.locale == "us"
        h12 = d.strftime("%I").lstrip("0") or "12"
        ampm = d.strftime("%p")
        if style == "rfc":
            tz = "-0800 (PST)" if us else "+0000 (GMT)"
            return f"{d.strftime('%a')}, {d.day} {d.strftime('%b %Y %H:%M:%S')} {tz}"
        if style == "long":
            if us:
                return f"{d.strftime('%A, %B %d, %Y')} {h12}:{d.strftime('%M')} {ampm}"
            return f"{d.strftime('%A')} {d.day} {d.strftime('%B %Y %H:%M')}"
        if style in ("notes", "notes_s"):
            secs = ":%S" if style == "notes_s" else ""
            if us:
                return d.strftime(f"%m/%d/%Y %I:%M{secs} %p")
            return d.strftime(f"%d/%m/%Y %H:%M{secs}")
        if style == "wrote":
            if us:
                return f"{h12}:{d.strftime('%M')} {ampm} {d.month}/{d.day}/{d.strftime('%y')}"
            return d.strftime("%H:%M %d/%m/%y")
        if style == "air":
            return d.strftime("%d%b").upper()
        if style == "airlong":
            return d.strftime("%b %d %Y").upper()
        if style == "dow3":
            return d.strftime("%a").upper()
        if style == "year":
            return str(d.year)
        if style == "mdy":
            return f"{d.month}/{d.day}/{d.year}" if us else d.strftime("%d/%m/%Y")
        if style == "letter":
            if us:
                return f"{d.strftime('%B')} {d.day}, {d.year}"
            if "letter_style" not in self.values:
                self.values["letter_style"] = self.rng.choice(["plain", "plain", "ordinal"])
            sfx = ""
            if self.values["letter_style"] == "ordinal":
                sfx = "th" if 11 <= d.day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(d.day % 10, "th")
            return f"{d.day}{sfx} {d.strftime('%B %Y')}"
        if style == "monthyear":
            return d.strftime("%B %Y")
        if style == "monthday":
            sfx = "th" if 11 <= d.day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(d.day % 10, "th")
            return f"{d.strftime('%B')} {d.day}{sfx}" if us else f"{d.day} {d.strftime('%B')}"
        raise ValueError(f"unknown DATE style {style!r}")

    # ------------------------------------------------------------ dispatch
    def render(self, typ, key, form):
        """Return a list of (text, entity type or None, entity_id or None)."""
        if typ == "PERSON":
            return [(self.render_person(key, form or "full"), "PERSON", f"person:{key}")]
        if typ == "EMAIL":
            return [(self.render_email(key, form), "EMAIL", f"email:{key}:{form.lower()}")]
        if typ == "PHONE":
            return [(self.phone(key, form or "any"), "PHONE", f"phone:{key}")]
        if typ == "ADDRESS":
            return self.render_address(key, form)
        if typ == "CUSTOM":
            return [(self.custom(key, form), "CUSTOM", f"custom:{key}")]
        if typ == "CARD":
            c = self.card(key)
            if form == "last4":
                self.tags.add("partial_number")
                v = c[-4:]
            elif form == "spaced":
                v = " ".join(c[i:i + 4] for i in range(0, 16, 4))
            else:
                v = c
            return [(v, "CARD", f"card:{key}")]
        if typ == "BANK_ACCOUNT":
            a = self.bank(key)["acct"]
            if form == "last4":
                self.tags.add("partial_number")
                a = a[-4:]
            return [(a, "BANK_ACCOUNT", f"bank_account:{key}")]
        if typ == "SORT_CODE":
            return [(self.bank(key)["sort"], "SORT_CODE", f"sort_code:{key}")]
        if typ == "IBAN":
            i = self.bank(key)["iban"]
            if form == "spaced":
                i = " ".join(i[n:n + 4] for n in range(0, len(i), 4))
            return [(i, "IBAN", f"iban:{key}")]
        if typ == "NI_NUMBER":
            return [(self.ni(key, form), "NI_NUMBER", f"ni_number:{key}")]
        if typ == "DOB":
            return [(self.dob(key, form), "DOB", f"dob:{key}")]
        if typ == "ID_DOC":
            k = ("ID_DOC", key)
            v = self.values.setdefault(k, str(self.rng.randint(1, 9)) + "".join(
                str(self.rng.randint(0, 9)) for _ in range(8)))
            return [(v, "ID_DOC", f"id_doc:{key}")]
        if typ == "DATE":
            return [(self.date(key, form), None, None)]
        if typ == "TRAP":
            self.tags.add("over_redaction_trap")
            return [(self.rng.choice(TRAPS[key]), None, None)]
        raise ValueError(f"unknown slot type {typ!r}")


def load_template(path):
    lines = path.read_text(encoding="utf-8").split("\n")
    meta, i = {}, 0
    while i < len(lines) and lines[i].startswith("#"):
        if lines[i].strip() == "# ---":
            i += 1
            break
        k, v = lines[i][1:].split(":", 1)
        meta[k.strip()] = v.strip()
        i += 1
    else:
        raise SystemExit(f"{path}: header must end with '# ---'")
    return meta, "\n".join(lines[i:]).strip("\n") + "\n"


def resolve_blocks(body, rng, fill_no=1, source_id=""):
    """Grouped alts rotate with the fill number so every layout shows up across fills."""
    groups = {}

    def sub(m):
        kind, grp, p, content = m.groups()
        gkey = (kind, grp) if grp else None
        if kind == "opt":
            if gkey in groups:
                on = groups[gkey]
            else:
                on = rng.random() < float(p or 0.5)
            if gkey:
                groups[gkey] = on
            return content if on else ""
        options = content.split("||")
        if gkey in groups:
            idx = groups[gkey]
        elif grp:
            idx = (fill_no + zlib.crc32(f"{source_id}:{grp}".encode())) % len(options)
        else:
            idx = rng.randrange(len(options))
        if gkey:
            groups[gkey] = idx
        return options[idx % len(options)]

    while BLOCK_RE.search(body):  # innermost blocks first, then the blocks around them
        body = BLOCK_RE.sub(sub, body)
    return body


def render(meta, body, fill_no, seed):
    f = Fill(meta["source_id"], fill_no, meta, seed)
    text = resolve_blocks(body, f.rng, fill_no, meta["source_id"])
    out, ents, pos, cur = [], [], 0, 0
    for m in SLOT_RE.finditer(text):
        lit = text[pos:m.start()]
        out.append(lit)
        cur += len(lit)
        for s, typ, eid in f.render(m.group(1), m.group(2), m.group(3) or ""):
            if typ:
                ents.append({"start": cur, "end": cur + len(s), "type": typ, "value": s, "entity_id": eid})
            out.append(s)
            cur += len(s)
        pos = m.end()
    out.append(text[pos:])
    full = "".join(out)
    tags = set(f.tags)
    for e in ents:
        if e["type"] == "PERSON" and full[e["end"]:e["end"] + 2] in ("'s", "\u2019s"):
            tags.add("possessive")
    forms = {}
    for e in ents:
        if e["type"] == "PERSON":
            forms.setdefault(e["entity_id"], set()).add(e["value"])
    if any(len(v) >= 3 for v in forms.values()):
        tags.add("same_person_multiple_forms")
    return full, ents, sorted(tags)


def split_for(source_id, fill_no):
    if source_id in EVAL_SOURCES:
        return "eval"
    return "train" if fill_no <= 3 else "fresh"


# ---------------------------------------------------------------- checks
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
POSTCODE_RE = re.compile(r"\b[A-PR-UWYZ][A-HK-Y]?\d[A-Z\d]? ?\d[ABD-HJLNP-UW-Z]{2}\b")
SORT_RE = re.compile(r"\b\d{2}-\d{2}-\d{2}\b")
IBAN_RE = re.compile(r"\bGB\d{2} ?[A-Z]{4}(?: ?\d){14}\b")
NI_RE = re.compile(r"\b[A-CEGHJ-PR-TW-Z]{2} ?\d{2} ?\d{2} ?\d{2} ?[A-D]\b")
CARD_RE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
ACCT_RE = re.compile(r"(?<![\d-])\d{8}(?![\d-])")
UK_PHONE_RE = re.compile(r"(?:\+44\s?(?:\(0\))?\s?\d{2,4}|\(?\b0\d{2,4}\)?)[\s-]?\d{3,4}[\s-]?\d{3,4}\b")
US_PHONE_RE = re.compile(r"\(?\b\d{3}\)?[\s.-]{0,2}\d{3}[.-]\d{4}\b")
SWEEPS = [("email", EMAIL_RE), ("postcode", POSTCODE_RE), ("sort_code", SORT_RE), ("iban", IBAN_RE),
          ("ni_number", NI_RE), ("card", CARD_RE), ("8-digit", ACCT_RE), ("uk_phone", UK_PHONE_RE),
          ("us_phone", US_PHONE_RE)]
VALUE_FORMATS = {
    "EMAIL": re.compile(r"^" + EMAIL_RE.pattern + r"$"),
    "POSTCODE": re.compile(r"^" + POSTCODE_RE.pattern.replace(r"\b", "") + r"$"),
    "SORT_CODE": re.compile(r"^\d{2}-\d{2}-\d{2}$"),
    "NI_NUMBER": re.compile(r"^" + NI_RE.pattern.replace(r"\b", "") + r"$"),
    "BANK_ACCOUNT": re.compile(r"^(\d{8}|\d{4})$"),
    "ID_DOC": re.compile(r"^\d{9}$"),
}


def sweep(text, allow=()):
    """Structured identifiers in text, as (kind, match)."""
    hits = []
    for kind, rx in SWEEPS:
        for m in rx.finditer(text):
            if kind == "card" and not luhn_ok(re.sub(r"\D", "", m.group())):
                continue
            if m.group() in allow:
                continue
            hits.append((kind, m.group()))
    return hits


def check_doc(d, allow=()):
    errs = []
    need = {"doc_id", "source_id", "group", "subtype", "split", "fill", "text", "entities", "provenance"}
    missing = need - d.keys()
    if missing:
        return [f"missing fields {sorted(missing)}"]
    text = d["text"]
    if d["group"] != GROUP or d["split"] not in ("train", "fresh", "eval"):
        errs.append("bad group or split")
    if not (isinstance(d["fill"], int) and 1 <= d["fill"] <= 5):
        errs.append("fill must be an int 1..5")
    if set(d["provenance"]) != {"url", "licence", "kind"} or d["provenance"]["kind"] not in (
            "template", "filled_real", "synthetic"):
        errs.append("bad provenance")
    for marker in ("{{", "}}", "[[", "]]"):
        if marker in text:
            errs.append(f"slot marker {marker!r} left in text")
    prev_end, id_types = 0, {}
    for e in d["entities"]:
        if set(e) != {"start", "end", "type", "value", "entity_id"}:
            errs.append(f"entity keys {sorted(e)}")
            continue
        if e["type"] not in TYPES:
            errs.append(f"type {e['type']} not allowed")
        if text[e["start"]:e["end"]] != e["value"]:
            errs.append(f"offset mismatch at {e['start']}: {e['value']!r}")
        if e["start"] < prev_end:
            errs.append(f"entities unsorted or overlapping at {e['start']}")
        if not e["value"] or e["value"] != e["value"].strip() or "\n" in e["value"]:
            errs.append(f"entity value has edge whitespace or a newline: {e['value']!r}")
        if id_types.setdefault(e["entity_id"], e["type"]) != e["type"]:
            errs.append(f"entity_id {e['entity_id']} has two types")
        rx = VALUE_FORMATS.get(e["type"])
        if rx and not rx.match(e["value"]):
            errs.append(f"{e['type']} value has a bad format: {e['value']!r}")
        if e["type"] == "IBAN" and not iban_ok(e["value"]):
            errs.append(f"IBAN checksum fails: {e['value']}")
        if e["type"] == "CARD" and len(e["value"]) > 4 and not luhn_ok(e["value"].replace(" ", "")):
            errs.append(f"card fails Luhn: {e['value']}")
        prev_end = e["end"]
    # Unlabelled structured identifiers are key bugs: sweep the text with entities blanked out.
    masked = list(text)
    for e in d["entities"]:
        masked[e["start"]:e["end"]] = "\x00" * (e["end"] - e["start"])
    for kind, val in sweep("".join(masked), allow):
        errs.append(f"unlabelled {kind}: {val!r}")
    return errs


def check_all(docs, allow):
    errs, seen = [], set()
    for d in docs:
        if d.get("doc_id") in seen:
            errs.append(f"{d.get('doc_id')}: duplicate doc_id")
        seen.add(d.get("doc_id"))
        errs += [f"{d.get('doc_id')}: {m}" for m in check_doc(d, allow.get(d.get("source_id"), ()))]
    eval_src = {d["source_id"] for d in docs if d["split"] == "eval"}
    other_src = {d["source_id"] for d in docs if d["split"] != "eval"}
    if eval_src & other_src:
        errs.append(f"sources in eval and train/fresh: {sorted(eval_src & other_src)}")
    return errs


def check_template(path, body, allow):
    """Regex sweep of a template with all slots removed: leftover identifiers are misses."""
    bare = body
    while BLOCK_RE.search(bare):
        bare = BLOCK_RE.sub(lambda m: " ".join(m.group(4).split("||")), bare)
    bare = SLOT_RE.sub(" ", bare)
    return [f"{path.name}: leftover {k}: {v!r}" for k, v in sweep(bare, allow)]


def load_all():
    out = []
    for path in sorted(TPL_DIR.glob("R*.txt"), key=lambda p: int(p.stem[1:])):
        meta, body = load_template(path)
        if meta.get("source_id") != path.stem:
            raise SystemExit(f"{path}: source_id header does not match file name")
        out.append((path, meta, body, tuple(meta.get("sweep_allow", "").split())))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--check", action="store_true", help="only check the existing JSONL")
    args = ap.parse_args()

    templates = load_all()
    allow = {meta["source_id"]: a for _, meta, _, a in templates}
    if args.check:
        docs = [json.loads(ln) for ln in OUT.read_text(encoding="utf-8").splitlines() if ln.strip()]
    else:
        docs, errs = [], []
        for path, meta, body, tpl_allow in templates:
            errs += check_template(path, body, tpl_allow)
            for n in range(1, FILLS + 1):
                text, ents, tags = render(meta, body, n, args.seed)
                docs.append({
                    "doc_id": f"{GROUP}-{meta['source_id']}-f{n}",
                    "source_id": meta["source_id"],
                    "group": GROUP,
                    "subtype": meta["subtype"],
                    "split": split_for(meta["source_id"], n),
                    "fill": n,
                    "text": text,
                    "entities": ents,
                    "hard_cases": tags,
                    "provenance": {"url": meta["url"], "licence": meta["licence"], "kind": meta["kind"]},
                })
        if errs:
            print("\n".join(errs), file=sys.stderr)
            raise SystemExit(f"template sweep found {len(errs)} leftover identifiers")
    errs = check_all(docs, allow)
    if errs:
        print("\n".join(errs[:200]), file=sys.stderr)
        raise SystemExit(f"CHECK FAILED: {len(errs)} problems")
    if not args.check:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("w", encoding="utf-8") as fh:
            for d in docs:
                fh.write(json.dumps(d, ensure_ascii=False) + "\n")
    n_ent = sum(len(d["entities"]) for d in docs)
    by_split = {s: sum(d["split"] == s for d in docs) for s in ("train", "fresh", "eval")}
    print(f"OK: {len(docs)} documents, {n_ent} entities, splits {by_split}")


if __name__ == "__main__":
    main()
