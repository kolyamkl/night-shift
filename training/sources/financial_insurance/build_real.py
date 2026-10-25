"""Render the slotted insurance templates (INS1, INS2) into filled documents.

Each template in data/templates/insurance/ is rendered FILLS times with Faker en_GB
values, seeded by (source_id, fill). Every inserted personal value is recorded with
its offsets, type and entity_id as it is written, so the answer key comes from code.
Fills 1-3 go to train, 4-5 to fresh. Output is merged into data/docs/insurance.jsonl
(records of other sources in that file are kept).

Template syntax is described in training/sources/financial_insurance/README.md.

Usage:
  python3 build_real.py            # render all templates, merge into insurance.jsonl
  python3 build_real.py --sweep    # list leftover structured identifiers and blanks in the templates
  python3 build_real.py --templates DIR --out FILE   # render elsewhere (tests)
"""

import argparse
import datetime as dt
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from faker import Faker

from common import (
    BLANK_RE, REPO, TYPES, assert_valid, check_entities, fake_account, fake_card, fake_driving_licence,
    fake_gb_iban, fake_ni, fake_passport, fake_sort_code, merge_write, stable_rng, sweep,
    uk_phone_valid, uncovered_hits, update_manifest,
)

TEMPLATES = REPO / "data" / "templates" / "insurance"
FILLS = 5
SEED = "night-shift-ins-v1"
SLOT_RE = re.compile(r"\{\{(\w+):(\w+)((?:\|[\w=]+)*)\}\}")
# Innermost block first, so blocks can nest.
BLOCK_RE = re.compile(r"\[\[(alt|opt|shuffle):((?:(?!\[\[).)*?)\]\]", re.S)

# Hard case 9.4: names that are common words (several are money or insurance words).
COMMON_FIRST = [("Will", 0), ("Mark", 0), ("Bill", 0), ("Frank", 0), ("Jack", 0), ("Rich", 0),
                ("Rose", 1), ("Grace", 1), ("Hope", 1), ("May", 1), ("Penny", 1), ("Faith", 1), ("Joy", 1)]
COMMON_LAST = ["Hope", "Rose", "Banks", "Cash", "Sterling", "Bond", "Price", "Fine", "Lloyd", "Marsh",
               "Payne", "Young", "Wise", "Best", "Small", "Brook", "Fields", "Mark", "Grant", "Hill"]
# Hard case 9.4: transliterated and non-English names (first, last, female).
FOREIGN = [("Oleksandr", "Kovalenko", 0), ("Olena", "Shevchenko", 1), ("Siobhán", "Ní Bhriain", 1),
           ("Aoife", "Ó Súilleabháin", 1), ("Bartłomiej", "Wiśniewski", 0), ("Wei", "Zhang", 0),
           ("Thị Lan", "Nguyễn", 1), ("Mohammed", "Al-Rashid", 0), ("Priya", "Raghunathan", 1),
           ("Chukwuemeka", "Okafor", 0), ("Dmitri", "Volkov", 0), ("Gráinne", "Mac Cárthaigh", 1),
           ("Ayşe", "Yıldız", 1), ("José María", "García", 0), ("Alexander", "Kovalenko", 0)]
INSURERS = ["Northgate Mutual Insurance plc", "Albion General Assurance Limited", "Thamesbank Insurance Company Ltd",
            "Severn & Wye Underwriting Ltd", "Pennine Indemnity plc", "Harbourline Insurance UK Limited"]
TRAP_PLACES = ["the Rose Garden car park", "the roadworks on Oak Road", "Victoria Park", "Grace Court Retail Park",
               "the Hope Street junction", "Penny Lane Business Centre"]
# Fictional companies (employers, other defendants). About a third carry a person's surname
# (hard case 9.4: a company name containing a person's name stays visible).
COMPANY_STEMS = ["Kestrel", "Brookfield", "Northgate", "Riverside", "Ashdown", "Meridian", "Harbourside", "Castlegate",
                 "Fenwick Vale", "Larchmont", "Redbridge", "Thistle"]
COMPANY_SECTORS = ["Logistics", "Packaging", "Construction", "Facilities Management", "Engineering", "Haulage",
                   "Retail", "Foods", "Scaffolding", "Property Services", "Care Homes", "Cleaning Services"]
# Public Lloyd's market clause codes: look like references, stay visible.
WORDINGS = ["NMA 2915", "LSW 238", "LMA 5021", "NMA 1191", "LMA 3100", "NMA 464"]
STREET_STEMS = ["Church", "Mill", "Station", "Victoria", "King's", "Queen's", "Park", "Manor", "Oak", "Elm",
                "Ash", "Beech", "Willow", "Chestnut", "Albert", "Windsor", "Grange", "Orchard", "Meadow", "Kingsway"]
STREET_SUFFIXES = ["Road", "Street", "Lane", "Avenue", "Close", "Drive", "Crescent", "Way", "Gardens", "Terrace",
                   "Grove", "Place", "Mews", "Court", "Rise", "Walk"]
# Real towns: a town alone does not identify anyone; the street and number are fake.
TOWNS = [("Altrincham", "Cheshire"), ("Bury St Edmunds", "Suffolk"), ("Harrogate", "North Yorkshire"),
         ("Stockport", "Greater Manchester"), ("Swindon", "Wiltshire"), ("Maidstone", "Kent"),
         ("Wolverhampton", "West Midlands"), ("Llandudno", "Conwy"), ("Paisley", "Renfrewshire"),
         ("Lisburn", "County Antrim"), ("Bath", "Somerset"), ("Croydon", "Surrey"), ("Leeds", "West Yorkshire"),
         ("Exeter", "Devon"), ("Norwich", "Norfolk"), ("Cardiff", "South Glamorgan"), ("Dundee", "Angus"),
         ("Luton", "Bedfordshire"), ("Sunderland", "Tyne and Wear"), ("Cheltenham", "Gloucestershire")]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]

# Organisation-specific CUSTOM formats (design 9.5). Keyed by slot key so a format recurs
# across fills and across sources. {Dn} digits, {Ln} capitals, {ln} lower case.
CUSTOM_FORMATS = {
    "claim_ref": "CLM·{D4}·{L2}",
    "insurer_ref": "{L3}/{D2}/{D6}-{l1}",
    "our_ref": "{L2}.{D4}.{D3}",
    "matter_ref": "M/{D4}/{D3}{l1}",
    "policy_no": "{L2}{D2}-{D5}/{L1}",
    "umr": "B{D4}{L2}{D6}{L1}",
    "bond_no": "FIB {D2} {D4} {L2}",
    "broker_ref": "BRK{D2}x{D4}",
    "client_id": "{D4} {D4} {D2}",
    "insured_ref": "~{L1}{D3}~{D2}",
    "works_no": "{D2}/{D4}{L1}",
    "hospital_ref": "RX{D2}-{D5}",
}
DEFAULT_CUSTOM = "{L2}{D6}"
PERSON_FORMS = {"full", "formal", "title_surname", "initial_surname", "first", "surname", "initials",
                "surname_first", "any", "signature"}


def ascii_fold(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


class Fill:
    def __init__(self, source_id, fill):
        self.rng = stable_rng(SEED, source_id, fill)
        self.fake = Faker("en_GB")
        self.fake.seed_instance(self.rng.randrange(2 ** 31))
        r = self.rng
        self.style = {
            "address": r.choice(["lines", "oneline"]),
            "date": r.choice(["%d %B %Y", "%d/%m/%Y", "{dth} {B} {Y}", "%d.%m.%Y"]),
            "dob": r.choice(["%d/%m/%Y", "%d %B %Y", "%d.%m.%Y", "%d-%b-%Y"]),
            "initial_dot": r.random() < 0.6,
            "spaced": r.random() < 0.5,
        }
        self.persons, self.addresses, self.values, self.keeps = {}, {}, {}, {}
        self.keep_values = set()
        self.used_names = set()
        self.tags = set()
        self.person_forms = defaultdict(list)

    # ------------------------------------------------ generated values
    def person(self, key):
        if key not in self.persons:
            r, f = self.rng, self.fake
            while True:
                roll = r.random()
                if roll < 0.25:
                    first, female = r.choice(COMMON_FIRST)
                    last = r.choice(COMMON_LAST) if r.random() < 0.6 else f.last_name()
                    kind = "common_word_name"
                elif roll < 0.4:
                    first, last, female = r.choice(FOREIGN)
                    kind = "transliterated_name"
                else:
                    female = r.random() < 0.5
                    first = f.first_name_female() if female else f.first_name_male()
                    last = f.last_name()
                    if r.random() < 0.3:
                        last = r.choice(COMMON_LAST)
                    kind = "common_word_name" if last in COMMON_LAST else None
                if (first, last) not in self.used_names:
                    break
            self.used_names.add((first, last))
            title = r.choice(["Ms", "Mrs", "Miss", "Dr", "Mx"] if female else ["Mr", "Mr", "Mr", "Dr", "Mx"])
            dob = dt.date(r.randint(1946, 2003), r.randint(1, 12), r.randint(1, 28))
            self.persons[key] = dict(first=first, last=last, female=bool(female), title=title, dob=dob, kind=kind)
        return self.persons[key]

    def address(self, key):
        if key not in self.addresses:
            r, f = self.rng, self.fake
            stem = r.choice(STREET_STEMS + [f.last_name()])
            street = f"{r.randint(1, 240)}{r.choice(['', '', '', 'A', 'B'])} {stem} {r.choice(STREET_SUFFIXES)}"
            if r.random() < 0.15:
                street = f"{r.choice(['Rose', 'Ivy', 'Holly', 'Orchard', 'Meadow'])} Cottage, {street.split(' ', 1)[1]}"
            lines = [street]
            if r.random() < 0.3:
                flat = f"{r.choice(['Flat', 'Apartment', 'Unit'])} {r.randint(1, 40)}"
                lines = [flat, street] if r.random() < 0.5 else [f"{flat}, {street}"]
            town, county = r.choice(TOWNS)
            if r.random() < 0.3:
                lines.append(f"{r.choice(['Upper', 'Lower', 'Little', 'Great', 'North', 'South'])} {r.choice(STREET_STEMS)}")
            lines.append(town.upper() if r.random() < 0.3 else town)
            if r.random() < 0.4:
                lines.append(county)
            care_of = r.random() < 0.15
            self.addresses[key] = dict(lines=lines, postcode=f.postcode(), care_of=care_of)
        return self.addresses[key]

    def value(self, typ, key, form):
        """Single-value types; the same (type, key, form) always gives the same value."""
        k = (typ, key, form if typ in ("ID_DOC",) else "")
        if k in self.values:
            return self.values[k]
        r, f = self.rng, self.fake
        if typ == "EMAIL":
            p = self.person(key)
            fi, la = ascii_fold(p["first"]).lower().split()[0], re.sub(r"[^a-z]", "", ascii_fold(p["last"]).lower())
            local = r.choice([f"{fi}.{la}", f"{fi[0]}{la}", f"{fi}_{la}{r.randint(1, 99)}", f"{la}.{fi[0]}"])
            v = f"{local}@{f.free_email_domain() if r.random() < 0.6 else f.domain_name()}"
        elif typ == "PHONE":
            while True:
                v = f.cellphone_number() if form == "mobile" else f.phone_number()
                if uk_phone_valid(v):
                    break
        elif typ == "SORT_CODE":
            v = fake_sort_code(r)
        elif typ == "BANK_ACCOUNT":
            v = fake_account(r)
        elif typ == "IBAN":
            v = fake_gb_iban(r, self.values.get(("SORT_CODE", key, "")), self.values.get(("BANK_ACCOUNT", key, "")))
        elif typ == "CARD":
            v = fake_card(r)
        elif typ == "NI_NUMBER":
            v = fake_ni(r)
        elif typ == "ID_DOC":
            if form == "passport":
                v = fake_passport(r)
            else:
                p = self.person(key)
                v = fake_driving_licence(r, ascii_fold(p["last"]), ascii_fold(p["first"]), p["dob"], p["female"])
        elif typ == "CUSTOM":
            v = self.custom(CUSTOM_FORMATS.get(key, DEFAULT_CUSTOM))
            if key in CUSTOM_FORMATS:
                self.tags.add("custom_unusual_format")
        else:
            raise ValueError(f"no generator for {typ}")
        self.values[k] = v
        return v

    def custom(self, fmt):
        def sub(m):
            kind, n = m.group(1), int(m.group(2))
            pool = {"D": "0123456789", "L": "ABCDEFGHJKLMNPRSTUVWXYZ", "l": "abcdefghjkmnpqrstuvwxyz"}[kind]
            return "".join(self.rng.choice(pool) for _ in range(n))
        return re.sub(r"\{([DLl])(\d+)\}", sub, fmt)

    def fmt_date(self, d, fmt):
        if "{dth}" in fmt:
            suffix = "th" if 11 <= d.day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(d.day % 10, "th")
            return fmt.format(dth=f"{d.day}{suffix}", B=MONTHS[d.month - 1], Y=d.year)
        return d.strftime(fmt)

    def keep(self, key, mods):
        """Unlabelled filler (amounts, ordinary dates, company names, traps). Different keys
        get different values where the pool allows (two insurers in one letter are not the same)."""
        if key in self.keeps:
            return self.keeps[key]
        for _ in range(20):
            v = self._keep_value(key, mods)
            if v not in self.keep_values:
                break
        self.keep_values.add(v)
        self.keeps[key] = v
        return v

    def _keep_value(self, key, mods):
        r, f = self.rng, self.fake
        kind = mods[0] if mods else key
        if kind.startswith("date"):
            v = self.fmt_date(dt.date(r.randint(2019, 2025), r.randint(1, 12), r.randint(1, 28)), self.style["date"])
        elif kind.startswith("amount"):
            lo, hi = {"small": (50, 5000), "big": (100000, 10000000)}.get(mods[1] if len(mods) > 1 else "", (1000, 50000))
            v = f"£{r.randint(lo, hi):,}" + (f".{r.randint(0, 99):02d}" if r.random() < 0.4 else "")
        elif kind.startswith("year"):
            v = str(r.randint(2019, 2025))
        elif kind.startswith("insurer"):
            v = r.choice(INSURERS)
        elif kind.startswith("firm"):
            a, b = f.last_name(), r.choice(COMMON_LAST + [f.last_name()])
            v = r.choice([f"{a} & {b} LLP", f"{a} {b} Solicitors", f"{a} & Co Solicitors Limited"])
            self.tags.add("company_person_name")
        elif kind.startswith("company"):
            sector = r.choice(COMPANY_SECTORS)
            if r.random() < 0.35:
                v = r.choice([f"{f.last_name()} & Sons Ltd", f"{r.choice(COMMON_LAST)} {sector} Limited"])
                self.tags.add("company_person_name")
            else:
                v = f"{r.choice(COMPANY_STEMS)} {sector} {r.choice(['Ltd', 'Limited', 'plc', '(UK) Limited'])}"
        elif kind.startswith("wording"):
            v = r.choice(WORDINGS)
            self.tags.add("over_redaction_trap")
        elif kind.startswith("place"):
            v = r.choice(TRAP_PLACES)
            self.tags.add("over_redaction_trap")
        else:
            raise ValueError(f"unknown keep slot {key!r} {mods}")
        return v

    # ------------------------------------------------ rendering to pieces
    def person_text(self, p, form):
        dot = "." if self.style["initial_dot"] else ""
        if form == "any":
            form = self.rng.choice(["full", "title_surname", "initial_surname", "surname"])
        elif form == "signature":
            form = self.rng.choice(["full", "first", "initial_surname"])
        first, last = p["first"], p["last"]
        out = {
            "full": f"{first} {last}",
            "formal": f"{p['title']} {first} {last}",
            "title_surname": f"{p['title']} {last}",
            "initial_surname": f"{first[0]}{dot} {last}",
            "first": first,
            "surname": last,
            "initials": first[0] + last[0],
            "surname_first": f"{last.upper()}, {first}",
        }[form]
        if form in ("initial_surname", "initials"):
            self.tags.add("initials")
        return out

    def slot(self, typ, key, mods):
        """Return a list of (text, type or None, entity_id or None) pieces."""
        form = mods[0] if mods else ""
        eid = f"{key}.{typ.lower()}"
        if typ == "keep":
            return [(self.keep(key, mods), None, None)]
        if typ not in TYPES:
            raise ValueError(f"unknown slot type {typ!r}")
        if typ == "PERSON":
            form = form or "full"
            if form not in PERSON_FORMS:
                raise ValueError(f"unknown PERSON form {form!r}")
            p = self.person(key)
            if p["kind"]:
                self.tags.add(p["kind"])
            text = self.person_text(p, form)
            self.person_forms[key].append((form, text))
            pieces = [(text, "PERSON", eid)]
            if "poss" in mods:
                pieces.append(("'" if text.endswith("s") and self.rng.random() < 0.5 else "'s", None, None))
                self.tags.add("possessive")
            return pieces
        if typ == "ADDRESS":
            a = self.address(key)
            layout = form if form in ("lines", "oneline") else self.style["address"]
            sep = "\n" if layout == "lines" else ", "
            self.tags.add("address_multiline" if layout == "lines" else "address_oneline")
            pieces = []
            if a["care_of"] and "noco" not in mods:
                p = self.person(f"{key}_co")
                pieces += [("c/o ", None, None), (self.person_text(p, "full"), "PERSON", f"{key}_co.person"), (sep, None, None)]
                self.tags.add("care_of_address")
            pieces.append((sep.join(a["lines"]), "ADDRESS", eid))
            if "nopostcode" not in mods:
                pieces += [("\n" if layout == "lines" else self.rng.choice([", ", " "]), None, None),
                           (a["postcode"], "POSTCODE", f"{key}.postcode")]
            return pieces
        if typ == "POSTCODE":
            return [(self.address(key)["postcode"], "POSTCODE", eid)]
        if typ == "DOB":
            return [(self.fmt_date(self.person(key)["dob"], self.style["dob"]), "DOB", eid)]
        v = self.value(typ, key, form)
        if form == "last4":
            self.tags.add("partial_number")
            return [(re.sub(r"\D", "", v)[-4:], typ, eid)]
        if form == "masked":
            self.tags.add("partial_number")
            d = re.sub(r"\D", "", v)
            mask = self.rng.choice(["**** **** **** ", "XXXX-XXXX-XXXX-", "xxxxxxxx"])
            return [(mask, None, None), (d[-4:], typ, eid)]
        if typ == "ID_DOC":
            eid = f"{key}.id_doc_{form or 'licence'}"
        if self.style["spaced"]:
            if typ == "NI_NUMBER":
                v = f"{v[:2]} {v[2:4]} {v[4:6]} {v[6:8]} {v[8]}"
            elif typ == "IBAN":
                v = " ".join(v[i:i + 4] for i in range(0, len(v), 4))
            elif typ == "CARD":
                v = " ".join(v[i:i + 4] for i in range(0, len(v), 4))
        return [(v, typ, eid)]

    # ------------------------------------------------ whole document
    def resolve_blocks(self, body):
        def pick(m):
            kind, items = m.group(1), [i.strip() for i in m.group(2).split("||")]
            if kind == "alt":
                return self.rng.choice(items)
            if kind == "opt":
                return items[0] if self.rng.random() < 0.5 else ""
            self.rng.shuffle(items)
            return "\n\n".join(items)
        while True:
            body, n = BLOCK_RE.subn(pick, body)
            if not n:
                return re.sub(r"\n{3,}", "\n\n", body)

    def render(self, body):
        body = self.resolve_blocks(body)
        out, entities, pos, last = [], [], 0, 0
        for m in SLOT_RE.finditer(body):
            lit = body[last:m.start()]
            out.append(lit)
            pos += len(lit)
            mods = [x for x in m.group(3).split("|") if x]
            for text, typ, eid in self.slot(m.group(1), m.group(2), mods):
                if typ:
                    entities.append(dict(start=pos, end=pos + len(text), type=typ, value=text, entity_id=eid))
                out.append(text)
                pos += len(text)
            last = m.end()
        out.append(body[last:])
        for key, forms in self.person_forms.items():
            if len({t for _, t in forms}) >= 3:
                self.tags.add("name_variants")
            if forms and all(f == "signature" for f, _ in forms):
                self.tags.add("signature_only_name")
        return "".join(out), entities


def load_template(path):
    raw = path.read_text(encoding="utf-8")
    head, sep, body = raw.partition("\n---\n")
    if not sep:
        sys.exit(f"{path}: missing '---' line between header and body")
    meta = {}
    for line in head.splitlines():
        if line.startswith("#") and ":" in line:
            k, _, v = line[1:].partition(":")
            meta[k.strip()] = v.strip()
    for k in ("source_id", "group", "subtype", "url", "licence", "kind"):
        if k not in meta:
            sys.exit(f"{path}: header is missing '# {k}:'")
    return meta, body


def render_template(path, fills=FILLS):
    meta, body = load_template(path)
    records = []
    for fill in range(1, fills + 1):
        fl = Fill(meta["source_id"], fill)
        text, entities = fl.render(body)
        doc_id = f"{meta['group']}-{meta['source_id']}-f{fill}"
        errs = check_entities(text, entities)
        leaks = [h for h in uncovered_hits(text, entities) if h[2] != "ACCOUNT8"]
        if errs or leaks:
            print(f"RENDER CHECK FAILED for {doc_id}:", file=sys.stderr)
            for e in errs + [f"unlabelled {k} {v!r} at {s}" for s, _, k, v in leaks]:
                print("  " + e, file=sys.stderr)
            sys.exit(1)
        records.append(dict(
            doc_id=doc_id, source_id=meta["source_id"], group=meta["group"], subtype=meta["subtype"],
            split="train" if fill <= 3 else "fresh", fill=fill, text=text, entities=entities,
            hard_cases=sorted(fl.tags),
            provenance=dict(url=meta["url"], licence=meta["licence"], kind=meta["kind"]),
        ))
    return meta, records


def sweep_template(path):
    """Leftover structured identifiers and unfilled blanks in a template body (slots masked)."""
    _, body = load_template(path)
    masked = SLOT_RE.sub(lambda m: "␣" * len(m.group()), body)
    hits = [(s, k, v) for s, _, k, v in sweep(masked)] + [(m.start(), "BLANK", m.group()) for m in BLANK_RE.finditer(masked)]
    for s, kind, value in sorted(hits):
        print(f"{path.name}:{masked.count(chr(10), 0, s) + 1}: {kind} {value!r}")
    return len(hits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--templates", type=Path, default=TEMPLATES)
    ap.add_argument("--out", type=Path, help="write here instead of merging into data/docs/insurance.jsonl")
    ap.add_argument("--fills", type=int, default=FILLS)
    ap.add_argument("--sweep", action="store_true")
    args = ap.parse_args()
    paths = sorted(args.templates.glob("INS*.txt"))
    if not paths:
        sys.exit(f"no templates (INS*.txt) in {args.templates}")
    if args.sweep:
        sys.exit(1 if sum(sweep_template(p) for p in paths) else 0)

    records, sources = [], {}
    for p in paths:
        meta, recs = render_template(p, args.fills)
        records += recs
        sources[meta["source_id"]] = dict(template=str(p.relative_to(REPO)) if p.is_relative_to(REPO) else str(p),
                                          url=meta["url"], licence=meta["licence"], kind=meta["kind"],
                                          subtype=meta["subtype"], documents=len(recs))
    groups = {r["group"] for r in records}
    if groups != {"insurance"}:
        sys.exit(f"templates must all be in the insurance group, got {groups}")
    if args.out:
        assert_valid(records, "insurance", str(args.out))
        args.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
        path, total = args.out, len(records)
    else:
        own = {r["source_id"] for r in records}
        path, total = merge_write("insurance", records, lambda r: r["source_id"] in own)
        update_manifest("real", dict(
            seed=SEED, fills=args.fills, faker_locale="en_GB", sources=sources,
            counts=dict(documents=len(records), by_split=dict(Counter(r["split"] for r in records)),
                        by_type=dict(Counter(e["type"] for r in records for e in r["entities"]))),
        ))
    types = Counter(e["type"] for r in records for e in r["entities"])
    print(f"rendered {len(records)} documents from {len(paths)} templates into {path} ({total} records in file)")
    print("entities by type:", dict(sorted(types.items())))
    print("hard cases:", dict(Counter(t for r in records for t in r["hard_cases"])))


if __name__ == "__main__":
    main()
