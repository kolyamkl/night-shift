"""Bitext retail banking + customer support chatbot sets -> labelled UK support chats (pool A).

Each row becomes one document "Customer: <instruction>\\n\\nAgent: <response>". `{{Placeholders}}` are
filled while the text is assembled, so offsets are recorded at insertion time (never searched for):

* value slots for personal data or organisation contact details (a phone number to call, a support email,
  a customer's name) are filled with fake UK values (Faker en_GB + Ofcom drama phone ranges) and labelled;
* keep-class value slots (bank / company names, websites, working hours, order / invoice / tracking /
  transaction numbers, amounts, cities, account types) are filled with fake values and left unlabelled;
* everything else, and any slot that is a field reference ("provide your {{Account Number}}",
  "your {{Password}}"), is replaced by the slot name as plain text: no value is present, so no label.

Rows with malformed braces are skipped. Licence: CDLA-Sharing-1.0 (share-alike for anything we publish).
"""
from __future__ import annotations

import hashlib
import random
import re
from collections import Counter

import pandas as pd
from faker import Faker

from .common import RAW

DATASETS = {
    "bank": {
        "id": "bitext/Bitext-retail-banking-llm-chatbot-training-dataset",
        "dir": "bitext__Bitext-retail-banking-llm-chatbot-training-dataset",
        "file": "bitext-retail-banking-llm-chatbot-training-dataset.parquet",
        "revision": "3e3621092fc6baaf7f53ceb6f091c60ae99acb67",
        "doc_type": "support_chat_banking",
    },
    "cs": {
        "id": "bitext/Bitext-customer-support-llm-chatbot-training-dataset",
        "dir": "bitext__Bitext-customer-support-llm-chatbot-training-dataset",
        "file": "Bitext_Sample_Customer_Support_Training_Dataset_27K_responses-v11.csv",
        "revision": "430d1a89bd93bd1fa23c16f29dd53e73f0087443",
        "doc_type": "support_chat_retail",
    },
}
PH = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
FIELD_BEFORE = re.compile(r"(?i)\b(your|their|his|her|my|recipient['’]s|payee['’]s|beneficiary['’]s|customer['’]s|account holder['’]s)\s*$")
FIELD_AFTER = re.compile(
    r"(?i)^\s*(field|fields|section|box|option|tab|page|menu|details|information|associated|on file|and \{\{|or \{\{|, \{\{|,\s*and \{\{)")
SECRET = re.compile(r"(?i)password|passcode|\bpin\b|pin code|security code|cvv|access key|\bkey\b|username|user name|login|credential")

PERSON_SLOTS = {
    "Name", "Full Name", "Person Name", "Client Name", "Client Full Name", "Customer Name", "Account Holder Name",
    "Bank Account Holder Name", "Recipient Name", "Recipient's Name", "Payee Name", "Beneficiary Name",
}
FIRST_SLOTS = {"Client First Name", "First Name"}
LAST_SLOTS = {"Client Last Name", "Last Name", "Surname"}
BANK_ACCOUNT_SLOTS = {"Account Number", "Bank Account Number"}
CUSTOM_SLOTS = {
    "Loan Account Number", "Mortgage Account Number", "Loan Number", "Mortgage Number", "Customer ID",
    "Customer Number", "Membership Number", "Member ID", "Policy Number", "Client ID", "Account ID",
}
CARD_SLOTS = {"Card Number", "Credit Card Number", "Debit Card Number"}
DOB_SLOTS = {"Date of Birth", "DOB"}
ADDRESS_SLOTS = {"Address", "Home Address", "Shipping Address", "Billing Address", "Mailing Address", "Residential Address"}
POSTCODE_SLOTS = {"Postcode", "Post Code", "Zip Code", "ZIP Code", "Postal Code"}
SORT_SLOTS = {"Sort Code"}

BANKS = ["Northfield Bank", "Kestrel Bank", "Ashgrove Building Society", "Harbour & Vale Bank", "Meridian Savings",
         "Thornbury Bank", "Cobalt Bank", "Larkspur Bank", "Fenwick & Hale Bank", "Brightwater Bank"]
SHOPS = ["Hollin & Co", "Marlow Home", "Peakline Outdoors", "Bramble Market", "Oakridge Electricals",
         "Quayside Fashion", "Lumen Living", "Fairhaven Books"]
HOURS = ["9am to 5pm, Monday to Friday", "8am to 8pm, Monday to Saturday", "24 hours a day, 7 days a week",
         "9:00 to 17:30 on weekdays", "8am-6pm Mon-Fri and 9am-1pm Sat"]
# Ofcom numbers reserved for TV and radio drama (never assigned to real subscribers)
DRAMA = ["020 7946 0{3}", "0113 496 0{3}", "0114 496 0{3}", "0115 496 0{3}", "0116 496 0{3}", "0117 496 0{3}",
         "0118 496 0{3}", "0121 496 0{3}", "0131 496 0{3}", "0141 496 0{3}", "0151 496 0{3}", "0161 496 0{3}",
         "0191 498 0{3}", "028 9649 6{3}", "029 2018 0{3}", "01632 960{3}", "07700 900{3}", "0808 157 0{3}",
         "0306 999 0{3}"]


class Filler:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.fk = Faker("en_GB")
        self.fk.seed_instance(seed)
        self.cache: dict[str, str] = {}
        self.org = self.rng.choice(BANKS)
        self.shop = self.rng.choice(SHOPS)

    def digits(self, n: int) -> str:
        return "".join(self.rng.choice("0123456789") for _ in range(n))

    def phone(self) -> str:
        pat = self.rng.choice(DRAMA)
        num = pat.replace("{3}", self.digits(3))
        if self.rng.random() < 0.2:
            num = "+44 " + num[1:]
        return num

    def domain(self, shop: bool) -> str:
        base = re.sub(r"[^a-z]", "", (self.shop if shop else self.org).lower().replace("&", "and"))
        return base + ".co.uk"

    def card(self) -> str:
        raw = self.fk.credit_card_number(card_type=self.rng.choice(["visa16", "mastercard"]))
        return " ".join(raw[i:i + 4] for i in range(0, len(raw), 4))

    def dob(self) -> str:
        d = self.fk.date_of_birth(minimum_age=18, maximum_age=85)
        return d.strftime(self.rng.choice(["%d/%m/%Y", "%d %B %Y", "%-d %b %Y"]))

    def value(self, name: str, kind: str, shop: bool) -> str:
        key = f"{kind}:{name}"
        if key in self.cache:
            return self.cache[key]
        r, fk = self.rng, self.fk
        v = {
            "PERSON": lambda: f"{fk.first_name()} {fk.last_name()}",
            "FIRST": fk.first_name,
            "LAST": fk.last_name,
            "PHONE": self.phone,
            "EMAIL_ORG": lambda: r.choice(["support", "help", "customercare", "hello", "contact"]) + "@" + self.domain(shop),
            "EMAIL": fk.free_email,
            "BANK_ACCOUNT": lambda: self.digits(8),
            "SORT_CODE": lambda: f"{self.digits(2)}-{self.digits(2)}-{self.digits(2)}",
            "CUSTOM": lambda: r.choice(["MTG", "LN", "CUS", "CID-", "AC"]) + self.digits(r.choice([7, 8, 9])),
            "CARD": self.card,
            "DOB": self.dob,
            "ADDRESS": lambda: f"{fk.building_number()} {fk.street_name()}, {fk.city()}",
            "POSTCODE": fk.postcode,
            "ORGNAME": lambda: self.shop if shop else self.org,
            "URL": lambda: "www." + self.domain(shop) + ("" if "URL" not in name or r.random() < 0.6 else "/" + r.choice(["help", "contact", "login", "support"])),
            "HOURS": lambda: r.choice(HOURS),
            "REF": lambda: r.choice({"Order": ["ORD-", "#", "ORD"], "Invoice": ["INV-", "INV"], "Tracking": ["TRK", "1Z"],
                                     "Transaction": ["TXN", "TX-"]}[next(k for k in ("Order", "Invoice", "Tracking", "Transaction") if k.lower() in name.lower())]) + self.digits(r.choice([6, 7, 8])),
            "CITY": fk.city,
            "COUNTRY": lambda: "United Kingdom",
            "ACCTYPE": lambda: r.choice(["Premium", "Standard", "Business", "Gold", "Platinum", "Basic", "Pro", "Family"]),
            "ACCCAT": lambda: r.choice(["Personal", "Business", "Family", "Student", "Joint"]),
            "AMOUNT": lambda: f"{r.randint(5, 900)}.{r.randint(0, 99):02d}",
            "MONEY": lambda: f"£{r.randint(5, 900)}.{r.randint(0, 99):02d}",
            "CURRENCY": lambda: "£",
            "DATERANGE": lambda: r.choice(["3-5", "5-7", "2-4", "7-10"]),
            "SALUTATION": lambda: r.choice(["Mr", "Mrs", "Ms", "Dr", "Miss"]),
        }[kind]()
        self.cache[key] = v
        return v


def classify(name: str) -> tuple[str, str | None]:
    """Return (fill kind, our type or None). kind 'LITERAL' means: write the slot name as plain text."""
    n = name.strip()
    low = n.lower()
    if SECRET.search(n):
        return "LITERAL", None
    if n in PERSON_SLOTS:
        return "PERSON", "PERSON"
    if n in FIRST_SLOTS:
        return "FIRST", "PERSON"
    if n in LAST_SLOTS:
        return "LAST", "PERSON"
    if ("phone" in low and "number" in low) or "toll-free number" in low or low in ("telephone", "hotline", "phone"):
        return "PHONE", "PHONE"
    if "email" in low:
        return ("EMAIL", "EMAIL") if n == "Email Address" else ("EMAIL_ORG", "EMAIL")
    if n in BANK_ACCOUNT_SLOTS:
        return "BANK_ACCOUNT", "BANK_ACCOUNT"
    if n in CUSTOM_SLOTS:
        return "CUSTOM", "CUSTOM"
    if n in CARD_SLOTS:
        return "CARD", "CARD"
    if n in DOB_SLOTS:
        return "DOB", "DOB"
    if n in ADDRESS_SLOTS:
        return "ADDRESS", "ADDRESS"
    if n in POSTCODE_SLOTS:
        return "POSTCODE", "POSTCODE"
    if n in SORT_SLOTS:
        return "SORT_CODE", "SORT_CODE"
    # keep-class value slots (filled, unlabelled)
    if "url" in low.split() or low.endswith(" url") or low in ("company website", "website", "bank website", "banking website"):
        return "URL", None
    if low in ("bank name", "company name", "company", "bank", "mortgage provider", "store name", "brand name"):
        return "ORGNAME", None
    if "hours" in low:
        return "HOURS", None
    if re.search(r"(?i)\b(order|invoice|tracking|transaction)\b.*\b(number|id)\b", n):
        return "REF", None
    if low == "delivery city":
        return "CITY", None
    if low == "delivery country":
        return "COUNTRY", None
    if low == "account type":
        return "ACCTYPE", None
    if low == "account category":
        return "ACCCAT", None
    if low in ("refund amount",):
        return "AMOUNT", None
    if low in ("money amount", "amount"):
        return "MONEY", None
    if low == "currency symbol":
        return "CURRENCY", None
    if low == "date range":
        return "DATERANGE", None
    if low == "salutation":
        return "SALUTATION", None
    return "LITERAL", None


_LIST_TAIL = re.compile(r"\{\{[^{}]+\}\}\s*(?:,\s*and|,\s*or|,|and|or|/)?\s*$")


def _list_head(before: str) -> str:
    """Strip preceding placeholders of a list ("your {{A}}, {{B}} and {{C}}") so the list's head is checked."""
    prev = None
    while prev != before:
        prev = before
        before = _LIST_TAIL.sub("", before)
    return before


ORG_TYPES = {"PHONE", "EMAIL_ORG"}


def render(template: str, filler: Filler, shop: bool, parts: list, ents: list, base: int, stats: Counter,
           personal_ok: bool = True) -> int:
    """Append the filled template to parts; record entity offsets relative to the whole document."""
    pos = base
    last = 0
    for m in PH.finditer(template):
        lit = template[last:m.start()]
        parts.append(lit)
        pos += len(lit)
        name = m.group(1)
        kind, typ = classify(name)
        before = _list_head(template[max(0, m.start() - 200):m.start()])
        after = template[m.end():m.end() + 25]
        possessive = bool(FIELD_BEFORE.search(before))
        is_field = possessive or bool(FIELD_AFTER.match(after))
        if typ is not None and kind not in ORG_TYPES and not personal_ok:
            is_field = True  # the banking agent asks for the customer's details; it never knows them
        if kind == "LITERAL" or is_field:
            val = name.lower() if possessive else name
            stats["slot_literal"] += 1
            typ = None
        else:
            val = filler.value(name, kind, shop)
            stats["slot_filled_" + (typ or "keep")] += 1
        if typ is not None:
            ents.append({"start": pos, "end": pos + len(val), "text": val, "type": typ})
        parts.append(val)
        pos += len(val)
        last = m.end()
    tail = template[last:]
    parts.append(tail)
    return pos + len(tail)


def convert_key(key: str, stats: Counter):
    for ds in (DATASETS[key],):
        path = RAW / ds["dir"] / ds["file"]
        df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
        stats[f"rows_read_{key}"] = len(df)
        shop = key == "cs"
        for i, r in enumerate(df.to_dict("records")):
            ins, resp = str(r["instruction"]), str(r["response"])
            if any(PH.sub("", t).count(ch) for t in (ins, resp) for ch in "{}"):
                stats[f"skip_{key}_malformed_braces"] += 1
                continue
            seed = int(hashlib.sha1(f"{key}-{i}".encode()).hexdigest()[:8], 16)
            filler = Filler(seed)
            parts, ents = [], []
            pos = 0
            parts.append("Customer: ")
            pos += len("Customer: ")
            pos = render(ins.strip(), filler, shop, parts, ents, pos, stats)
            sep = "\n\nAgent: "
            parts.append(sep)
            pos += len(sep)
            render(resp.strip(), filler, shop, parts, ents, pos, stats, personal_ok=shop)
            text = "".join(parts)
            assert all(text[e["start"]:e["end"]] == e["text"] for e in ents)
            yield {
                "text": text,
                "entities": ents,
                "split": "train",
                "doc_type": ds["doc_type"],
                "source": ds["id"],
                "meta": {
                    "mubit_ok": True,
                    "locale": "en (source US-leaning; fills en-GB)",
                    "source_row": i,
                    "intent": r.get("intent"),
                    "category": r.get("category"),
                    "revision": ds["revision"],
                    "orig_labels": sorted({m.group(1) for t in (ins, resp) for m in PH.finditer(t)}),
                    "dropped_labels": {},
                    "out_of_scope": [],
                    "quality_flags": ["placeholders_filled_with_fake_uk_values"],
                    "share_alike": "CDLA-Sharing-1.0",
                },
            }
