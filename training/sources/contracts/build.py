"""Render filled contract documents and their answer key.

Usage: python training/sources/contracts/build.py [--fills 5] [--check-only] [--selftest]

Reads data/templates/contracts/<source_id>.txt (slot syntax in README.md next to
this file), renders N fills per template with fresh fake values, and writes
data/docs/contracts.jsonl. The key (entity offsets, types, entity ids) is recorded
by this code as each value is inserted; no LLM is involved. Every run with the
same templates, Faker version and fill count produces byte-identical output.

The local check at the end enforces the documents schema and exits non-zero on
any violation. --check-only validates the existing JSONL and the templates.
"""

import argparse
import collections
import datetime as dt
import hashlib
import json
import random
import re
import sys
import unicodedata
from pathlib import Path

from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sources import BY_ID, EVAL_SOURCES, SOURCES  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TEMPLATES = REPO / "data" / "templates" / "contracts"
OUT = REPO / "data" / "docs" / "contracts.jsonl"

ENTITY_TYPES = {
    "PERSON", "ADDRESS", "POSTCODE", "EMAIL", "PHONE", "BANK_ACCOUNT", "SORT_CODE",
    "IBAN", "CARD", "NI_NUMBER", "DOB", "ID_DOC", "CUSTOM",
}
SLOT_KINDS = ENTITY_TYPES | {"SIGNATURE", "NOTICE", "COMPANY", "TITLE", "DATE", "TEXT", "CHECK", "TAG"}
SUBTYPES = {"tenancy", "employment", "nda", "lease", "engagement_letter"}

# ---------------------------------------------------------------- value pools
# Team pack 9.4 hard cases: names that are common words, transliterated and
# accented names, names written several ways.
COMMON_WORD_FIRST = [("Will", "M"), ("Rose", "F"), ("Mark", "M"), ("Grace", "F"), ("Bill", "M"),
                     ("Hope", "F"), ("May", "F"), ("Joy", "F"), ("Frank", "M"), ("Holly", "F"),
                     ("Dawn", "F"), ("Rich", "M")]
WORD_SURNAMES = ["Baker", "Mason", "Hill", "Wood", "Bell", "Brook", "Field", "Banks", "Lane", "Rice",
                 "Church", "Young", "Little", "Long", "Shepherd", "Hope", "Rose", "May", "Moss", "Marsh"]
TRANSLIT_FIRST = [("Oleksandr", "Alexander", "M"), ("Olena", "Elena", "F"), ("Mykola", "Nikolai", "M"),
                  ("Dmytro", "Dmitri", "M"), ("Yuliia", "Julia", "F"), ("Serhii", "Sergei", "M"),
                  ("Kateryna", "Ekaterina", "F"), ("Andrii", "Andrei", "M"), ("Oleksandra", "Alexandra", "F")]
TRANSLIT_LAST = ["Kovalenko", "Shevchenko", "Bondarenko", "Tkachenko", "Melnyk", "Kravchuk", "Boyko",
                 "Moroz", "Savchenko"]
ACCENT_FIRST = [("Siobhán", "Siobhan", "F"), ("Seán", "Sean", "M"), ("Róisín", "Roisin", "F"),
                ("Pádraig", "Padraig", "M"), ("Ciarán", "Ciaran", "M"), ("Éabha", "Eabha", "F"),
                ("Aoife", None, "F"), ("Niamh", None, "F")]
IRISH_LAST = [("O'Brien", None), ("Murphy", None), ("Ó Súilleabháin", "O'Sullivan"), ("MacCarthy", None),
              ("O'Connell", None), ("Byrne", None), ("Ó Murchú", "Murphy"), ("Kavanagh", None)]
OTHER_NAMES = [("Chukwuemeka", "Okafor", "M"), ("Ngozi", "Adeyemi", "F"), ("Priya", "Raghunathan", "F"),
               ("Raj", "Patel", "M"), ("Wojciech", "Nowak", "M"), ("Agnieszka", "Kowalczyk", "F"),
               ("Mei Ling", "Chen", "F"), ("Kwame", "Mensah", "M"), ("Zainab", "Hussain", "F"),
               ("Mohammed", "Al-Rashid", "M"), ("Anjali", "Sharma", "F"), ("Tomasz", "Wiśniewski", "M"),
               ("Fatima", "Begum", "F"), ("Yusuf", "Demir", "M"), ("Hiroshi", "Tanaka", "M")]

# UK towns with real postcode districts; the inward part is random.
TOWNS = [("Leeds", ["LS6", "LS7", "LS11", "LS2"]), ("Manchester", ["M14", "M20", "M4"]),
         ("Birmingham", ["B15", "B13", "B5"]), ("Bristol", ["BS8", "BS6", "BS3"]),
         ("Cardiff", ["CF10", "CF24", "CF5"]), ("Edinburgh", ["EH3", "EH6", "EH10"]),
         ("Glasgow", ["G12", "G3", "G41"]), ("Newcastle upon Tyne", ["NE1", "NE2", "NE6"]),
         ("Sheffield", ["S10", "S7", "S1"]), ("Nottingham", ["NG7", "NG1", "NG5"]),
         ("Liverpool", ["L17", "L1", "L8"]), ("Belfast", ["BT9", "BT7", "BT1"]),
         ("York", ["YO10", "YO1", "YO31"]), ("Brighton", ["BN2", "BN1", "BN3"]),
         ("Cambridge", ["CB1", "CB4", "CB2"]), ("Oxford", ["OX4", "OX2", "OX1"]),
         ("Exeter", ["EX4", "EX1", "EX2"]), ("Aberdeen", ["AB10", "AB11", "AB24"]),
         ("Swansea", ["SA1", "SA2"]), ("Norwich", ["NR2", "NR1"]),
         ("London", ["SW11", "E8", "N16", "SE15", "NW3", "W12", "EC1V", "WC2N"])]
INWARD_LETTERS = "ABDEFGHJLNPQRSTUWXYZ"
STREET_FIRST = ["Oak", "Mill", "Church", "Station", "Victoria", "Albert", "Park", "Queen's", "King",
                "Rose", "Willow", "Elm", "Granby", "Marlborough", "Clarence", "Hawthorn", "Beech",
                "Chapel", "Bridge", "Castle", "Grove", "Hope", "Market", "Spring", "Orchard"]
STREET_SUFFIX = ["Road", "Street", "Lane", "Avenue", "Close", "Crescent", "Terrace", "Way", "Drive",
                 "Gardens", "Place", "Row", "Walk", "Mews"]
BUILDINGS = ["Rose Court", "Willow House", "Granby Mansions", "Albion Works", "The Old Rectory",
             "Kingfisher House", "Mercury Building", "Hope Chambers"]
NEUTRAL_COMPANIES = ["Northbridge Analytics Ltd", "Harbourline Logistics plc", "Bluefen Software Limited",
                     "Kestrel Data Systems Ltd", "Ashgrove Clinical Research Ltd", "Tidewater Foods plc",
                     "Larchmont Engineering Ltd", "Brightwell Energy Ltd", "Quayside Media Group plc",
                     "Fernhill Robotics Ltd"]
JOB_TITLES = ["Director", "Managing Director", "Head of Legal", "Chief Executive Officer", "Finance Director",
              "General Counsel", "Operations Manager", "Company Secretary", "Head of Procurement",
              "Partner", "Chief Technology Officer", "Commercial Director"]
SOLE_TRADER_TITLES = ["Owner", "Proprietor", "Founder"]
# Ofcom ranges reserved for fiction, so no number belongs to anyone.
PHONE_RANGES = [("07700", "900"), ("020", "7946 0"), ("0113", "496 0"), ("0114", "496 0"),
                ("0117", "496 0"), ("0121", "496 0"), ("0131", "496 0"), ("0141", "496 0"),
                ("0161", "496 0"), ("0191", "498 0"), ("029", "2018 0"), ("028", "9018 0")]
BANK_CODES = ["NWBK", "BARC", "LOYD", "HBUK", "MIDL", "SRLG", "CPBK", "MONZ"]

# Organisation-specific identifier formats (CUSTOM). Shared by every source and
# fill so formats recur across train, fresh and eval (design 9.5).
CUSTOM_FORMATS = {
    "client": "CL-{d5}",
    "matter": "M/{year}/{d3}",
    "ref_slash": "{L3}/{yy}/{d4}",
    "nda": "NDA-{d4}-{L2}",
    "acct": "ACC#{d3}-{d3}",
    "vendor": "VND{d6}/{L1}",
    "policy": "POL {L2} {d6}",
    "dotted": "{L2}.{d4}.{d2}",
}
FOOTERS = [
    "Our ref: {{CUSTOM:our_ref}}",
    "Our ref: {{CUSTOM:our_ref}}    Your ref: {{CUSTOM:your_ref}}",
    "Client code: {{CUSTOM:client}} | Matter: {{CUSTOM:matter}}",
    "Ref. {{CUSTOM:our_ref}}",
]

DATE_FORMATS = ["{d} {B} {Y}", "{dd}/{mm}/{Y}", "{d}{sfx} {B} {Y}", "{B} {d}, {Y}", "{Y}-{mm}-{dd}",
                "{d} {b} {Y}", "{dd}.{mm}.{Y}"]
CHECKS = [("[x]", "[ ]"), ("☒", "☐"), ("[X]", "[ ]"), ("(x)", "( )")]

# ------------------------------------------------------------- template parsing
TOKEN_RE = re.compile(r"(\{\{.*?\}\})", re.S)


def load_template(path):
    header, pools, body = {}, collections.defaultdict(list), []
    for line in path.read_text(encoding="utf-8").split("\n"):
        if not body and line.startswith("#!"):
            content = line[2:].strip()
            m = re.match(r"pool (\w+): (.*)$", content)
            if m:
                pools[m.group(1)].append(m.group(2).replace("\\n", "\n"))
            elif ":" in content:
                k, v = content.split(":", 1)
                header[k.strip()] = v.strip()
            continue
        body.append(line)
    text = "\n".join(body).rstrip("\n") + "\n"
    return header, dict(pools), text


def parse(text):
    tokens = [t for t in TOKEN_RE.split(text) if t]
    nodes, i = _parse(tokens, 0, ())
    if i != len(tokens):
        raise ValueError(f"unexpected {tokens[i]!r}")
    return nodes


def _parse(tokens, i, stop):
    nodes = []
    while i < len(tokens):
        tok = tokens[i]
        if not (tok.startswith("{{") and tok.endswith("}}")):
            nodes.append(("lit", tok))
            i += 1
            continue
        tag = tok[2:-2]
        head, _, rest = tag.partition(":")
        if tag in stop:
            return nodes, i
        if head in ("ALT", "SHUFFLE"):
            sep, end = ("OR", "/ALT") if head == "ALT" else ("ITEM", "/SHUFFLE")
            parts, i = [], i + 1
            while True:
                part, i = _parse(tokens, i, (sep, end))
                if i >= len(tokens):
                    raise ValueError(f"unterminated {tok}")
                parts.append(part if head == "ALT" else _strip_nl(part))
                i += 1
                if tokens[i - 1] == "{{" + end + "}}":
                    break
            nodes.append(("alt", rest or None, parts) if head == "ALT" else ("shuffle", parts))
            continue
        if tag in ("OR", "/ALT", "ITEM", "/SHUFFLE"):
            raise ValueError(f"stray {tok}")
        if head not in SLOT_KINDS:
            raise ValueError(f"unknown slot kind in {tok}")
        arg, _, form = rest.partition("|")
        nodes.append(("slot", head, arg, form))
        i += 1
    return nodes, i


def _strip_nl(nodes):
    nodes = list(nodes)
    if nodes and nodes[0][0] == "lit":
        nodes[0] = ("lit", nodes[0][1].lstrip("\n"))
    if nodes and nodes[-1][0] == "lit":
        nodes[-1] = ("lit", nodes[-1][1].rstrip("\n"))
    return nodes


def count_slots(text):
    return sum(1 for t in TOKEN_RE.findall(text) if t[2:-2].partition(":")[0] in SLOT_KINDS - {"CHECK", "TAG"})


# ------------------------------------------------------------------- helpers
def ascii_fold(s):
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def luhn_ok(digits):
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def iban_ok(value):
    s = value.replace(" ", "")
    if not re.fullmatch(r"GB\d{2}[A-Z]{4}\d{14}", s):
        return False
    moved = s[4:] + s[:4]
    return int("".join(str(int(c, 36)) for c in moved)) % 97 == 1


def make_iban(bank, sort6, acct8):
    bban = bank + sort6 + acct8
    num = int("".join(str(int(c, 36)) for c in bban + "GB00"))
    return f"GB{98 - num % 97:02d}{bban}"


class Person:
    def __init__(self, first, last, gender, title, cats, alt_first=None, alt_last=None):
        self.first, self.last, self.gender, self.title = first, last, gender, title
        self.cats, self.alt_first, self.alt_last = cats, alt_first, alt_last


# ------------------------------------------------------------------ rendering
class Fill:
    def __init__(self, source_id, fill, pools):
        seed = int(hashlib.sha256(f"contracts|{source_id}|{fill}".encode()).hexdigest()[:16], 16)
        self.source_id, self.fill = source_id, fill
        self.pool_used = set()
        self.rng = random.Random(seed)
        self.fake = Faker("en_GB")
        self.fake.seed_instance(seed)
        self.pools = pools
        self.parts, self.pos, self.entities, self.tags = [], 0, [], set()
        self.roles, self.memo, self.alts = {}, {}, {}
        r = self.rng
        self.style = {
            "date": r.choice(DATE_FORMATS),
            "check": r.choice(CHECKS),
            "initials_dotted": r.random() < 0.5,
            "wrap": None if r.random() < 0.65 else r.choice([72, 80, 96]),
            "address": r.choice(["oneline", "multiline"]),
            "footer": None if r.random() < 0.55 else r.choice(["start", "end", "end"]),
        }

    # ---- output
    def emit(self, text, etype=None, eid=None):
        if not text:
            return
        if etype:
            self.entities.append({"start": self.pos, "end": self.pos + len(text), "type": etype,
                                  "value": text, "entity_id": eid})
        self.parts.append(text)
        self.pos += len(text)

    def render(self, nodes):
        for node in nodes:
            kind = node[0]
            if kind == "lit":
                self.emit(node[1])
            elif kind == "alt":
                name, branches = node[1], node[2]
                if name and name in self.alts:
                    idx = self.alts[name]
                else:
                    idx = self.rng.randrange(len(branches))
                    if name:
                        self.alts[name] = idx
                self.render(branches[idx])
            elif kind == "shuffle":
                items = list(node[1])
                self.rng.shuffle(items)
                for j, item in enumerate(items):
                    if j:
                        self.emit("\n\n")
                    self.render(item)
            else:
                for text, etype, eid in self.slot(node[1], node[2], node[3]):
                    self.emit(text, etype, eid)

    # ---- people and roles
    def role(self, name):
        if name not in self.roles:
            self.roles[name] = {"name": name, "person": self.new_person()}
        return self.roles[name]

    def taken_surnames(self):
        names = {ro["person"].last for ro in self.roles.values()}
        names |= {w for ro in self.roles.values() for w in re.findall(r"[A-Z][\w'-]+", ro.get("company") or "")}
        return names

    def new_person(self):
        r, f = self.rng, self.fake
        for _ in range(20):
            c = r.random()
            alt_first = alt_last = None
            if c < 0.35:
                gender = r.choice("MF")
                first = f.first_name_male() if gender == "M" else f.first_name_female()
                last, cats = f.last_name(), set()
            elif c < 0.55:
                first, gender = r.choice(COMMON_WORD_FIRST)
                last = r.choice(WORD_SURNAMES) if r.random() < 0.5 else f.last_name()
                cats = {"common_word_name"}
            elif c < 0.70:
                a, b, gender = r.choice(TRANSLIT_FIRST)
                first, alt_first = (a, b) if r.random() < 0.6 else (b, a)
                last, cats = r.choice(TRANSLIT_LAST), {"transliterated_name"}
            elif c < 0.82:
                a, b, gender = r.choice(ACCENT_FIRST)
                first, alt_first = (a, b) if (b is None or r.random() < 0.5) else (b, a)
                last, alt_last = r.choice(IRISH_LAST)
                cats = {"accented_name"} if b or alt_last else {"non_english_name"}
            else:
                first, last, gender = r.choice(OTHER_NAMES)
                cats = {"non_english_name"}
            if last not in self.taken_surnames():
                break
        if r.random() < 0.05:
            title = "Mx"
        elif gender == "M":
            title = r.choice(["Mr", "Mr", "Mr", "Dr"])
        else:
            title = r.choice(["Ms", "Ms", "Mrs", "Miss", "Dr"])
        return Person(first, last, gender, title, cats, alt_first, alt_last)

    def name(self, role, form):
        p = role["person"]
        if form == "print":
            form = self.memo.setdefault(("print", role["name"]),
                                        self.rng.choice(["full", "full", "upper_full", "surname_first", "title_full"]))
        first, last = p.first, p.last
        if form == "alt_full":
            if p.alt_first or p.alt_last:
                self.tags.add("transliterated_name" if "transliterated_name" in p.cats else "accented_name")
            first, last = p.alt_first or first, p.alt_last or last
            form = "full"
        inits = [w[0] for w in first.replace("-", " ").split()]
        if form in ("initials", "initials_surname"):
            self.tags.add("initials")
        self.tags |= p.cats
        if form == "full":
            return f"{first} {last}"
        if form == "title_full":
            return f"{p.title} {first} {last}"
        if form == "title_surname":
            return f"{p.title} {last}"
        if form == "initials_surname":
            return " ".join(i + "." for i in inits) + " " + last
        if form == "initials":
            letters = inits + [last[0]]
            return ".".join(letters) + "." if self.style["initials_dotted"] else "".join(letters)
        if form == "first":
            return first
        if form == "surname":
            return last
        if form == "upper_full":
            return f"{first} {last}".upper()
        if form == "surname_first":
            return f"{last.upper()}, {first}"
        raise ValueError(f"unknown PERSON form {form!r}")

    def company(self, role, registered=False):
        if "company" not in role:
            r, f = self.rng, self.fake
            c = r.random()
            # A registered company (one with a company number) is never a sole trader.
            role["sole_trader"] = c < 0.18 and not registered
            if role["sole_trader"]:
                role["company"] = None
            else:
                for _ in range(20):
                    taken = {ro["person"].last for ro in self.roles.values()}
                    if c < 0.5:
                        name = f.company()
                    elif c < 0.75:
                        s1, s2 = f.last_name(), f.last_name()
                        name = r.choice([f"{s1} & Co Ltd", f"{s1} & Sons Limited", f"{s1} {s2} LLP",
                                         f"{f.first_name()} {s1} Associates Ltd", f"{s1} and {s2} Ltd"])
                    else:
                        name = r.choice(NEUTRAL_COMPANIES)
                    if not any(t in name for t in taken):
                        break
                role["company"] = name
                role["company_has_name"] = c < 0.75
        if registered and role["company"] is None:
            raise ValueError(f"role {role['name']!r} is a sole trader; put {{{{COMPANY:{role['name']}|registered}}}} "
                             "before any other COMPANY or TITLE slot of that role")
        return role["company"]

    def address(self, role):
        if "address" not in role:
            r = self.rng
            town, districts = r.choice(TOWNS)
            postcode = f"{r.choice(districts)} {r.randint(1, 9)}{r.choice(INWARD_LETTERS)}{r.choice(INWARD_LETTERS)}"
            num = str(r.randint(1, 220)) + (r.choice("ab") if r.random() < 0.1 else "")
            street = f"{num} {r.choice(STREET_FIRST)} {r.choice(STREET_SUFFIX)}"
            lines = []
            if r.random() < 0.35:
                lines.append(r.choice(["Flat", "Flat", "Apartment", "Unit"]) + f" {r.randint(1, 40)}"
                             + (r.choice("ABC") if r.random() < 0.2 else ""))
            if r.random() < 0.2:
                lines.append(r.choice(BUILDINGS))
            lines += [street, town]
            role["address"] = {"lines": lines, "postcode": postcode, "flat": len(lines) > 2,
                               "co": r.random() < 0.15}
        return role["address"]

    def address_pieces(self, role, form):
        a = self.address(role)
        rn = role["name"]
        if form == "any":
            form = self.memo.setdefault(("addr_form", rn), self.style["address"]
                                        if self.rng.random() < 0.7 else self.rng.choice(["oneline", "multiline"]))
        out = []
        if a["co"]:
            co = self.role(rn + "_co")
            out += [("c/o ", None, None), (self.name(co, "full"), "PERSON", co["name"]),
                    (", " if form == "oneline" else "\n", None, None)]
            self.tags.add("address_care_of")
        if a["flat"]:
            self.tags.add("address_flat")
        # The separator before the postcode is kept per role and form: a one-line address
        # never takes the line break of the same role's multi-line address.
        if form == "oneline":
            out += [(", ".join(a["lines"]), "ADDRESS", f"{rn}.address"),
                    (self.memo.setdefault(("pc_sep", rn, form), self.rng.choice([" ", ", "])), None, None)]
        elif form == "multiline":
            self.tags.add("address_split_lines")
            out += [("\n".join(a["lines"]), "ADDRESS", f"{rn}.address"),
                    (self.memo.setdefault(("pc_sep", rn, form), self.rng.choice(["\n", " "])), None, None)]
        else:
            raise ValueError(f"unknown ADDRESS form {form!r}")
        out.append((a["postcode"], "POSTCODE", f"{rn}.postcode"))
        return out

    def email(self, role, alt=False):
        key = "email2" if alt else "email"
        if key not in role:
            r, p = self.rng, role["person"]
            first = re.sub(r"[^a-z]", "", ascii_fold(p.first).lower())
            last = re.sub(r"[^a-z]", "", ascii_fold(p.last).lower())
            local = r.choice([f"{first}.{last}", f"{first}{last}", f"{first[0]}.{last}", f"{first}_{last}",
                              f"{first[0]}{last}", f"{first}{r.randint(1, 99)}", f"{last}.{first[0]}"])
            company = self.company(role)
            if company and r.random() < 0.6:
                words = [w for w in re.findall(r"[a-z]+", ascii_fold(company).lower())
                         if w not in ("ltd", "limited", "plc", "llp", "and", "co", "sons", "group")]
                domain = "".join(words[:2]) + r.choice([".co.uk", ".com", ".uk"])
            else:
                domain = self.fake.free_email_domain()
            role[key] = f"{local}@{domain}"
            if alt and role.get("email") == role[key]:
                role[key] = f"{local}.office@{domain}"
        return role[key]

    def phone(self, role):
        if "phone" not in role:
            r = self.rng
            area, rest = r.choice(PHONE_RANGES)
            tail = f"{r.randint(0, 999):03d}"
            local = f"{area} {rest}{tail}"
            intl = "+44 " + area[1:] + " " + rest + tail
            role["phone"] = r.choice([local, local, local.replace(" ", ""), intl,
                                      "+44 (0)" + area[1:] + " " + rest + tail, f"({area}) {rest}{tail}"])
        return role["phone"]

    def bank(self, role):
        if "account" not in role:
            r = self.rng
            role["account"] = f"{r.randint(10000000, 99999999)}"
            role["sort6"] = "".join(f"{r.randint(0, 99):02d}" for _ in range(3))
            role["iban"] = make_iban(r.choice(BANK_CODES), role["sort6"], role["account"])
        return role

    def card(self, role):
        if "card" not in role:
            r = self.rng
            digits = r.choice(["4", "51", "52", "53", "54", "55"])
            while len(digits) < 15:
                digits += str(r.randint(0, 9))
            digits += next(str(c) for c in range(10) if luhn_ok(digits + str(c)))
            role["card"] = digits
        return role["card"]

    def custom(self, name):
        key = ("custom", name)
        if key not in self.memo:
            r = self.rng
            fmt = CUSTOM_FORMATS.get(name) or CUSTOM_FORMATS[r.choice(sorted(CUSTOM_FORMATS))]
            letters = "ABCDEFGHJKLMNPRSTUVWXYZ"
            year = r.randint(2023, 2027)
            value = fmt.format(
                d2=f"{r.randint(0, 99):02d}", d3=f"{r.randint(1, 999):03d}", d4=f"{r.randint(0, 9999):04d}",
                d5=f"{r.randint(10000, 99999)}", d6=f"{r.randint(0, 999999):06d}", year=year,
                yy=f"{year % 100:02d}", L1=r.choice(letters), L2="".join(r.choices(letters, k=2)),
                L3="".join(r.choices(letters, k=3)))
            self.memo[key] = value
            self.tags.add("custom_identifier")
        return self.memo[key]

    def date(self, name, kind="ordinary", offset=""):
        """A date near the fill's base date; with an offset ("+364", "-30") exactly that many days from it."""
        key = ("date", name)
        if key not in self.memo:
            r = self.rng
            if kind == "dob":
                d = dt.date(1950, 1, 1) + dt.timedelta(days=r.randint(0, 19000))
            elif "base_date" not in self.memo:
                d = dt.date(2024, 1, 1) + dt.timedelta(days=r.randint(0, 1400))
                self.memo["base_date"] = d
                if offset:
                    d += dt.timedelta(days=int(offset))
            elif offset:
                d = self.memo["base_date"] + dt.timedelta(days=int(offset))
            else:
                d = self.memo["base_date"] - dt.timedelta(days=r.randint(0, 14))
            self.memo[key] = d
        return self.fmt_date(self.memo[key])

    def fmt_date(self, d):
        sfx = "th" if 11 <= d.day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(d.day % 10, "th")
        return self.style["date"].format(d=d.day, dd=f"{d.day:02d}", mm=f"{d.month:02d}", Y=d.year,
                                         B=d.strftime("%B"), b=d.strftime("%b"), sfx=sfx)

    # ---- slot dispatch: returns [(text, entity_type or None, entity_id or None)]
    def slot(self, kind, arg, form):
        r = self.rng
        if kind == "TAG":
            self.tags.add(arg)
            return []
        if kind == "CHECK":
            return [(self.style["check"][0 if arg == "x" else 1], None, None)]
        if kind == "TEXT":
            pool = self.pools.get(arg)
            if not pool:
                raise ValueError(f"empty TEXT pool {arg!r}")
            if arg in self.pool_used:
                entry = r.choice(pool)
            else:
                # First use in a fill walks a per-source permutation, so the 5 fills
                # of a source get different entries before any entry repeats.
                self.pool_used.add(arg)
                perm = list(range(len(pool)))
                random.Random(f"{self.source_id}|{arg}").shuffle(perm)
                entry = pool[perm[(self.fill - 1) % len(pool)]]
            self.render(parse(entry))
            return []
        if kind == "DATE":
            if form and not re.fullmatch(r"[+-]\d+", form):
                raise ValueError(f"DATE offset must look like +364 or -30, got {form!r}")
            return [(self.date(arg, offset=form), None, None)]
        if kind == "CUSTOM":
            return [(self.custom(arg), "CUSTOM", f"custom.{arg}")]
        role = self.role(arg)
        rn = arg
        if kind == "PERSON":
            return [(self.name(role, form or "full"), "PERSON", rn)]
        if kind == "SIGNATURE":
            self.tags.add("signature_name")
            style = self.memo.setdefault(("sig", rn), r.choice(["/s/ full", "full", "initials_surname",
                                                                 "first", "initials", "surname"]))
            prefix = "/s/ " if style.startswith("/s/") else ""
            return [(prefix, None, None), (self.name(role, style.replace("/s/ ", "")), "PERSON", rn)]
        if kind == "ADDRESS":
            return self.address_pieces(role, form or "any")
        if kind == "POSTCODE":
            return [(self.address(role)["postcode"], "POSTCODE", f"{rn}.postcode")]
        if kind == "NOTICE":
            how = self.memo.setdefault(("notice", rn), r.choice(["email", "postal"]))
            if how == "email":
                return [(self.email(role), "EMAIL", f"{rn}.email")]
            return self.address_pieces(role, form or "any")
        if kind == "EMAIL":
            alt = form == "alt"
            return [(self.email(role, alt), "EMAIL", f"{rn}.email2" if alt else f"{rn}.email")]
        if kind == "PHONE":
            return [(self.phone(role), "PHONE", f"{rn}.phone")]
        if kind == "COMPANY":
            company = self.company(role, registered=form == "registered")
            if company is None:
                self.tags.add("sole_trader")
                suffix = self.memo.setdefault(("sole", rn), r.choice([" (sole trader)", ", sole trader"]))
                return [(self.name(role, "full"), "PERSON", rn), (suffix, None, None)]
            if role.get("company_has_name"):
                self.tags.add("company_with_person_name")
            return [(company, None, None)]
        if kind == "TITLE":
            self.company(role)
            pool = SOLE_TRADER_TITLES if role["sole_trader"] else JOB_TITLES
            return [(self.memo.setdefault(("title", rn), r.choice(pool)), None, None)]
        if kind in ("BANK_ACCOUNT", "SORT_CODE", "IBAN"):
            b = self.bank(role)
            if kind == "BANK_ACCOUNT":
                if form == "last4":
                    self.tags.add("partial_number")
                    return [(b["account"][-4:], "BANK_ACCOUNT", f"{rn}.account")]
                return [(b["account"], "BANK_ACCOUNT", f"{rn}.account")]
            if kind == "SORT_CODE":
                s = b["sort6"]
                return [(f"{s[:2]}-{s[2:4]}-{s[4:]}", "SORT_CODE", f"{rn}.sort_code")]
            iban = b["iban"]
            if self.memo.setdefault(("iban_spaced", rn), r.random() < 0.5):
                iban = " ".join(iban[i:i + 4] for i in range(0, len(iban), 4))
            return [(iban, "IBAN", f"{rn}.iban")]
        if kind == "CARD":
            digits = self.card(role)
            if form == "last4":
                self.tags.add("partial_number")
                return [(digits[-4:], "CARD", f"{rn}.card")]
            return [(" ".join(digits[i:i + 4] for i in range(0, 16, 4)), "CARD", f"{rn}.card")]
        if kind == "NI_NUMBER":
            if "ni" not in role:
                while True:
                    pre = r.choice("ABCEGHJKLMNOPRSTWXYZ") + r.choice("ABCEGHJKLMNPRSTWXYZ")
                    if pre not in ("BG", "GB", "KN", "NK", "NT", "TN", "ZZ"):
                        break
                d = f"{r.randint(0, 999999):06d}"
                sfx = r.choice("ABCD")
                role["ni"] = r.choice([f"{pre}{d}{sfx}", f"{pre} {d[:2]} {d[2:4]} {d[4:]} {sfx}"])
            return [(role["ni"], "NI_NUMBER", f"{rn}.ni")]
        if kind == "DOB":
            return [(self.date(f"dob.{rn}", "dob"), "DOB", f"{rn}.dob")]
        if kind == "ID_DOC":
            key = "licence" if form == "licence" else "passport"
            if key not in role:
                if key == "passport":
                    role[key] = f"{r.randint(100000000, 999999999)}"
                else:
                    p = role["person"]
                    sur = re.sub(r"[^A-Z]", "", ascii_fold(p.last).upper())[:5].ljust(5, "9")
                    ini = re.sub(r"[^A-Z]", "", ascii_fold(p.first).upper())[:2].ljust(2, "9")
                    role[key] = (f"{sur}{r.randint(5, 9)}{r.randint(1, 12) + (50 if p.gender == 'F' else 0):02d}"
                                 f"{r.randint(1, 28):02d}{r.randint(0, 9)}{ini}9"
                                 f"{''.join(r.choices('ABCDEFGHJKLMNPRSTUVWXYZ0123456789', k=2))}")
            return [(role[key], "ID_DOC", f"{rn}.{key}")]
        raise ValueError(f"unhandled slot {kind}")


def hard_wrap(text, width, entities):
    """Break long lines at spaces (same length, so offsets stay valid), never inside an entity."""
    protected = set()
    for e in entities:
        protected.update(range(e["start"], e["end"]))
    chars = list(text)
    line_start, last_space = 0, -1
    for i, ch in enumerate(chars):
        if ch == "\n":
            line_start, last_space = i + 1, -1
            continue
        if ch == " " and i not in protected:
            last_space = i
        if i - line_start >= width and last_space > line_start:
            chars[last_space] = "\n"
            line_start, last_space = last_space + 1, -1
    return "".join(chars)


def render_doc(src, fill, header, pools, body_nodes):
    f = Fill(src["source_id"], fill, pools)
    footer = parse(f.rng.choice(FOOTERS)) if f.style["footer"] else None
    if footer and f.style["footer"] == "start":
        f.render(footer)
        f.emit("\n\n")
    f.render(body_nodes)
    if footer and f.style["footer"] == "end":
        # Entity values never end in a newline, so trimming cannot move an entity.
        f.parts = ["".join(f.parts).rstrip("\n")]
        f.pos = len(f.parts[0])
        f.emit("\n\n")
        f.render(footer)
    if footer:
        f.tags.add("footer_reference")
    text = "".join(f.parts).rstrip("\n") + "\n"
    ents = f.entities
    if f.style["wrap"]:
        text = hard_wrap(text, f.style["wrap"], ents)
        f.tags.add("hard_wrapped_lines")
    for e in ents:
        if e["type"] == "PERSON" and text[e["end"]:e["end"] + 2] in ("'s", "’s"):
            f.tags.add("possessive")
    forms = collections.defaultdict(set)
    for e in ents:
        if e["type"] == "PERSON":
            forms[e["entity_id"]].add(e["value"])
    if any(len(v) >= 3 for v in forms.values()):
        f.tags.add("one_person_three_ways")
    sid = src["source_id"]
    split = "eval" if sid in EVAL_SOURCES else ("train" if fill <= 3 else "fresh")
    return {
        "doc_id": f"contracts-{sid}-f{fill}",
        "source_id": sid,
        "group": "contracts",
        "subtype": src["subtype"],
        "split": split,
        "fill": fill,
        "text": text,
        "entities": sorted(ents, key=lambda e: e["start"]),
        "hard_cases": sorted(f.tags),
        "provenance": {"url": src.get("provenance_url", src["url"]), "licence": src["licence"],
                       "kind": src["kind"]},
    }


# ---------------------------------------------------------------------- check
SWEEP = {
    "EMAIL": re.compile(r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "POSTCODE": re.compile(r"\b(?:GIR ?0AA|[A-PR-UWYZ][A-HK-Y]?\d[A-Z\d]? ?\d[ABD-HJLNP-UW-Z]{2})\b"),
    "SORT_CODE": re.compile(r"\b\d{2}-\d{2}-\d{2}\b"),
    "BANK_ACCOUNT": re.compile(r"\b\d{8}\b"),
    "IBAN": re.compile(r"\bGB\d{2} ?[A-Z]{4}(?: ?\d){14}\b"),
    "NI_NUMBER": re.compile(r"\b[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z] ?\d{2} ?\d{2} ?\d{2} ?[A-D]\b"),
    "CARD": re.compile(r"\b(?:\d[ -]?){12,18}\d\b"),
    "PHONE": re.compile(r"(?:\+44\s?(?:\(0\)\s?)?\d{2,4}|\(?0\d{2,4}\)?)[\s-]?\d{3,4}[\s-]?\d{3,4}\b"),
}
VALUE_RE = {
    "POSTCODE": re.compile(r"[A-Z]{1,2}\d[A-Z\d]? \d[A-Z]{2}"),
    "EMAIL": re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}"),
    "SORT_CODE": re.compile(r"\d{2}-\d{2}-\d{2}"),
    "BANK_ACCOUNT": re.compile(r"\d{8}|\d{4}"),
    "NI_NUMBER": re.compile(r"[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z] ?\d{2} ?\d{2} ?\d{2} ?[A-D]"),
}


def sweep(text):
    hits = []
    for typ, rx in SWEEP.items():
        for m in rx.finditer(text):
            if typ == "CARD" and not luhn_ok(re.sub(r"\D", "", m.group())):
                continue
            hits.append((typ, m.start(), m.end(), m.group()))
    return hits


def check_doc(d, seen):
    errs = []
    did = d.get("doc_id", "?")
    keys = ["doc_id", "source_id", "group", "subtype", "split", "fill", "text", "entities", "provenance"]
    for k in keys:
        if k not in d:
            errs.append(f"{did}: missing {k}")
    if errs:
        return errs
    if did in seen:
        errs.append(f"{did}: duplicate doc_id")
    seen.add(did)
    sid = d["source_id"]
    if sid not in BY_ID:
        errs.append(f"{did}: unknown source_id {sid}")
    if d["group"] != "contracts":
        errs.append(f"{did}: group {d['group']}")
    if d["subtype"] not in SUBTYPES or (sid in BY_ID and d["subtype"] != BY_ID[sid]["subtype"]):
        errs.append(f"{did}: subtype {d['subtype']}")
    if not isinstance(d["fill"], int) or not 1 <= d["fill"] <= 5:
        errs.append(f"{did}: fill {d['fill']}")
    else:
        want = "eval" if sid in EVAL_SOURCES else ("train" if d["fill"] <= 3 else "fresh")
        if d["split"] != want:
            errs.append(f"{did}: split {d['split']}, expected {want}")
    prov = d["provenance"]
    if not (isinstance(prov, dict) and prov.get("url") and prov.get("licence")
            and prov.get("kind") in ("template", "filled_real", "synthetic")):
        errs.append(f"{did}: bad provenance {prov}")
    text = d["text"]
    if not isinstance(text, str) or not text.strip():
        return errs + [f"{did}: empty text"]
    if "{{" in text or "}}" in text or "#!" in text:
        errs.append(f"{did}: slot or header marker left in text")
    if "\r" in text:
        errs.append(f"{did}: carriage return in text")
    if "\u2014" in text:
        errs.append(f"{did}: em dash in text")
    prev_end = 0
    for e in d["entities"]:
        if set(e) != {"start", "end", "type", "value", "entity_id"}:
            errs.append(f"{did}: entity keys {sorted(e)}")
            continue
        s, t, typ, v = e["start"], e["end"], e["type"], e["value"]
        if not (isinstance(s, int) and isinstance(t, int) and 0 <= s < t <= len(text)):
            errs.append(f"{did}: bad offsets {e}")
            continue
        if text[s:t] != v:
            errs.append(f"{did}: text[{s}:{t}]={text[s:t]!r} != value {v!r}")
        if v != v.strip():
            errs.append(f"{did}: value has outer whitespace {v!r}")
        if typ not in ENTITY_TYPES:
            errs.append(f"{did}: type {typ}")
        if s < prev_end:
            errs.append(f"{did}: entity at {s} overlaps or is out of order")
        prev_end = t
        if not isinstance(e["entity_id"], str) or not e["entity_id"]:
            errs.append(f"{did}: empty entity_id at {s}")
        if typ in VALUE_RE and not VALUE_RE[typ].fullmatch(v):
            errs.append(f"{did}: {typ} value has an invalid format: {v!r}")
        if typ == "IBAN" and not iban_ok(v):
            errs.append(f"{did}: IBAN checksum or length wrong: {v!r}")
        if typ == "CARD" and len(v) != 4 and not luhn_ok(v.replace(" ", "")):
            errs.append(f"{did}: CARD fails Luhn: {v!r}")
    for typ, s, t, val in sweep(text):
        if not any(e["start"] < t and s < e["end"] for e in d["entities"]):
            errs.append(f"{did}: unlabelled {typ}-like value {val!r} at {s}")
    return errs


def check_template(path):
    header, pools, body = load_template(path)
    errs = [f"{path.name}: header lacks {k}" for k in ("source_id", "url", "licence") if k not in header]
    try:
        parse(body)
        for entries in pools.values():
            for entry in entries:
                parse(entry)
    except ValueError as e:
        errs.append(f"{path.name}: {e}")
    literal = TOKEN_RE.sub("\x00", body + "\n" + "\n".join(x for v in pools.values() for x in v))
    for typ, s, t, val in sweep(literal):
        errs.append(f"{path.name}: leftover {typ}-like value {val!r} outside slots")
    if "\u2014" in literal:
        errs.append(f"{path.name}: em dash")
    return errs


def fail_if(errs):
    if errs:
        print(f"CHECK FAILED: {len(errs)} problem(s)", file=sys.stderr)
        for e in errs:
            print("  " + e, file=sys.stderr)
        sys.exit(1)


SELFTEST = """{{PERSON:a|full}} ({{PERSON:a|title_surname}}, {{PERSON:a|initials_surname}}, {{PERSON:a|initials}}, \
{{PERSON:a|first}}, {{PERSON:a|surname}}'s, {{PERSON:a|upper_full}}, {{PERSON:a|surname_first}}, {{PERSON:a|alt_full}}, \
{{PERSON:a|print}}, {{PERSON:a|title_full}})
Signed: {{SIGNATURE:a}}
Home: {{ADDRESS:a|multiline}}
Also: {{ADDRESS:a|oneline}}; postcode {{POSTCODE:a}}
Notice: {{NOTICE:b|any}}
Email {{EMAIL:a}} or {{EMAIL:a|alt}}, tel {{PHONE:a}}
Account {{BANK_ACCOUNT:a}}, sort code {{SORT_CODE:a}}, IBAN {{IBAN:a}}, account ending {{BANK_ACCOUNT:a|last4}}
Card {{CARD:a}}, Visa ending {{CARD:a|last4}}
NI {{NI_NUMBER:a}}, born {{DOB:a}}, passport {{ID_DOC:a|passport}}, licence {{ID_DOC:a|licence}}
Company {{COMPANY:b}} ({{TITLE:b}}), dated {{DATE:x}} to {{DATE:y|+364}}; registered company {{COMPANY:r|registered}} ({{TITLE:r}})
Refs {{CUSTOM:client}} {{CUSTOM:matter}} {{CUSTOM:other}}
{{ALT:k}}alt-one{{OR}}alt-two{{/ALT}} {{ALT:k}}alt-one{{OR}}alt-two{{/ALT}} {{CHECK:x}} {{CHECK:o}} {{TEXT:t}}

{{SHUFFLE}}
A
{{ITEM}}
B
{{/SHUFFLE}}
""".replace("\\\n", "")


def selftest():
    """Render every slot kind for every source id and fill, then run the check."""
    nodes = parse(SELFTEST)
    pools = {"t": ["plain", "with {{PERSON:c|full}} and {{CUSTOM:client}}"]}
    docs = [render_doc(src, fill, {}, pools, nodes) for src in SOURCES for fill in range(1, 6)]
    seen = set()
    fail_if([e for d in docs for e in check_doc(d, seen)])
    for d in docs:
        t = d["text"]
        assert t.count("alt-one") in (0, 2) and t.count("alt-two") in (0, 2), "named ALT not consistent"
    types = collections.Counter(e["type"] for d in docs for e in d["entities"])
    missing = ENTITY_TYPES - set(types)
    fail_if([f"selftest: type {m} never rendered" for m in sorted(missing)])
    print(f"selftest OK: {len(docs)} renders, all 13 types, {sum(types.values())} entities")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fills", type=int, default=5)
    ap.add_argument("--check-only", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return

    templates = {p.stem: p for p in sorted(TEMPLATES.glob("C*.txt"))}
    errs = [e for p in templates.values() for e in check_template(p)]
    fail_if(errs)

    if args.check_only:
        docs = [json.loads(ln) for ln in OUT.read_text(encoding="utf-8").splitlines() if ln.strip()]
    else:
        docs = []
        for src in SOURCES:
            sid = src["source_id"]
            if sid not in templates:
                print(f"{sid}: no template, skipped")
                continue
            header, pools, body = load_template(templates[sid])
            nodes = parse(body)
            for fill in range(1, args.fills + 1):
                docs.append(render_doc(src, fill, header, pools, nodes))
            print(f"{sid}: {count_slots(body)} body slots, "
                  f"{sum(count_slots(x) for v in pools.values() for x in v)} pool slots, {args.fills} fills")

    seen = set()
    errs = [e for d in docs for e in check_doc(d, seen)]
    fail_if(errs)

    if not args.check_only:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("w", encoding="utf-8", newline="\n") as fh:
            for d in docs:
                fh.write(json.dumps(d, ensure_ascii=False) + "\n")

    types = collections.Counter(e["type"] for d in docs for e in d["entities"])
    splits = collections.Counter(d["split"] for d in docs)
    print(f"OK: {len(docs)} documents, {sum(types.values())} entities, splits {dict(splits)}")
    print("entity types: " + ", ".join(f"{k} {v}" for k, v in sorted(types.items())))


if __name__ == "__main__":
    main()
