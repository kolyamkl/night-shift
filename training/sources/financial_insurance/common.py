"""Shared helpers for the financial and insurance document builders.

Holds the documents schema check, the regex sweep for structured identifiers,
generators for valid fake UK numbers, and JSONL / manifest IO. Everything here
is deterministic code: the answer key never comes from an LLM.
"""

import json
import random
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DOCS_DIR = REPO / "data" / "docs"
MANIFEST = REPO / "data" / "sources" / "financial_insurance" / "manifest.json"

TYPES = {
    "PERSON", "ADDRESS", "POSTCODE", "EMAIL", "PHONE", "BANK_ACCOUNT", "SORT_CODE",
    "IBAN", "CARD", "NI_NUMBER", "DOB", "ID_DOC", "CUSTOM",
}
GROUPS = {"contracts", "correspondence", "financial", "insurance"}
SPLITS = {"train", "fresh", "eval"}
KINDS = {"template", "filled_real", "synthetic"}
EVAL_SOURCES = {"C2", "C5", "C6", "C7", "C10", "R5", "R7", "R9"}
SOURCE_RE = re.compile(r"^(C(1[0-2]|[1-9])|R(1[01]|[1-9])|INS[12]|gretel-[A-Za-z0-9_.-]+)$")
SLOT_MARKERS = ("{{", "}}", "[[", "]]")
# Unfilled form blanks (dotted or underscored fill-in lines) left in a rendered template.
BLANK_RE = re.compile(r"\.{5,}|_{4,}|…{3,}")
ENTITY_KEYS = {"start", "end", "type", "value", "entity_id"}


# ---------------------------------------------------------------- schema check

def check_records(records, group=None):
    """Return a list of error strings for a list of document records."""
    errors = []
    seen = set()
    for n, rec in enumerate(records, 1):
        where = f"record {n} ({rec.get('doc_id', '?') if isinstance(rec, dict) else '?'})"
        if not isinstance(rec, dict):
            errors.append(f"{where}: not a JSON object")
            continue
        errors += [f"{where}: {e}" for e in _check_record(rec, group)]
        if rec.get("doc_id") in seen:
            errors.append(f"{where}: duplicate doc_id")
        seen.add(rec.get("doc_id"))
    return errors


def _check_record(rec, group):
    errs = []
    need = {"doc_id", "source_id", "group", "subtype", "split", "fill", "text", "entities", "provenance"}
    missing = need - rec.keys()
    if missing:
        return [f"missing keys {sorted(missing)}"]
    extra = rec.keys() - need - {"hard_cases"}
    if extra:
        errs.append(f"unexpected keys {sorted(extra)}")
    if not isinstance(rec["doc_id"], str) or not rec["doc_id"]:
        errs.append("doc_id must be a non-empty string")
    src = rec["source_id"]
    if not isinstance(src, str) or not SOURCE_RE.match(src):
        errs.append(f"bad source_id {src!r}")
        src = ""
    if rec["group"] not in GROUPS:
        errs.append(f"bad group {rec['group']!r}")
    if group and rec["group"] != group:
        errs.append(f"group {rec['group']!r} in the {group} file")
    if not isinstance(rec["subtype"], str) or not re.fullmatch(r"[a-z0-9_]+", rec["subtype"]):
        errs.append(f"bad subtype {rec['subtype']!r}")
    fill, split = rec["fill"], rec["split"]
    if split not in SPLITS:
        errs.append(f"bad split {split!r}")
    if not isinstance(fill, int) or isinstance(fill, bool):
        errs.append(f"fill must be an int, got {fill!r}")
    elif src.startswith("gretel-"):
        if fill != 0:
            errs.append("Gretel documents must have fill 0")
    elif src:
        if not 1 <= fill <= 5:
            errs.append(f"fill {fill} outside 1..5")
        elif src in EVAL_SOURCES:
            if split != "eval":
                errs.append(f"{src} is an eval source but split is {split}")
        elif split != ("train" if fill <= 3 else "fresh"):
            errs.append(f"fill {fill} must be {'train' if fill <= 3 else 'fresh'}, got {split}")
    text = rec["text"]
    if not isinstance(text, str) or not text.strip():
        errs.append("text must be a non-empty string")
        return errs
    for m in SLOT_MARKERS:
        if m in text:
            errs.append(f"slot marker {m!r} left in text at {text.index(m)}")
    if not src.startswith("gretel-"):
        b = BLANK_RE.search(text)
        if b:
            errs.append(f"unfilled blank {b.group()!r} at {b.start()}")
    errs += check_entities(text, rec["entities"])
    if isinstance(rec["entities"], list) and all(isinstance(e, dict) and {"start", "end", "type"} <= e.keys() for e in rec["entities"]):
        for s, v in email_misses(text, rec["entities"]):
            errs.append(f"email address {v!r} at {s} is not inside an EMAIL entity")
    for s, v in placeholder_tokens(text):
        errs.append(f"placeholder-like token {v!r} at {s}")
    prov = rec["provenance"]
    if not isinstance(prov, dict):
        errs.append("provenance must be an object")
    else:
        if not str(prov.get("url", "")).startswith("http"):
            errs.append("provenance.url must be an http(s) URL")
        if not isinstance(prov.get("licence"), str) or not prov["licence"]:
            errs.append("provenance.licence missing")
        if prov.get("kind") not in KINDS:
            errs.append(f"bad provenance.kind {prov.get('kind')!r}")
    hc = rec.get("hard_cases")
    if hc is not None and (not isinstance(hc, list) or not all(isinstance(t, str) for t in hc)):
        errs.append("hard_cases must be a list of strings")
    return errs


def check_entities(text, entities):
    errs = []
    if not isinstance(entities, list):
        return ["entities must be a list"]
    prev_end = -1
    id_type = {}
    for i, e in enumerate(entities):
        if not isinstance(e, dict) or set(e) != ENTITY_KEYS:
            errs.append(f"entity {i}: keys must be {sorted(ENTITY_KEYS)}")
            continue
        s, t = e["start"], e["end"]
        if not (isinstance(s, int) and isinstance(t, int) and 0 <= s < t <= len(text)):
            errs.append(f"entity {i}: bad offsets {s}..{t}")
            continue
        if text[s:t] != e["value"]:
            errs.append(f"entity {i}: text[{s}:{t}]={text[s:t]!r} != value {e['value']!r}")
        if e["value"] != e["value"].strip():
            errs.append(f"entity {i}: value has surrounding whitespace {e['value']!r}")
        if e["type"] not in TYPES:
            errs.append(f"entity {i}: bad type {e['type']!r}")
        if e["type"] == "PERSON" and POSSESSIVE_END_RE.search(e["value"]) and len(e["value"]) > 2:
            errs.append(f"entity {i}: PERSON value {e['value']!r} ends with a possessive")
        if not isinstance(e["entity_id"], str) or not e["entity_id"]:
            errs.append(f"entity {i}: entity_id must be a non-empty string")
        elif id_type.setdefault(e["entity_id"], e["type"]) != e["type"]:
            errs.append(f"entity {i}: entity_id {e['entity_id']!r} used with two types")
        if s < prev_end:
            errs.append(f"entity {i}: overlaps or is out of order (start {s} < previous end {prev_end})")
        prev_end = max(prev_end, t)
    return errs


# Two rules of scripts/dataset/validate_docs.py, mirrored here so check.py and the builders
# reject what that validator rejects: every email address lies inside an EMAIL entity, and
# the text has no token the scorer would read as a placeholder ([PERSON], [Address 2]).
VALIDATOR_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
PLACEHOLDER_RE = re.compile(r"\[\s*([A-Za-z]+(?:[ _-]+[A-Za-z]+)*)(?:[ _-]*#?(\d+))?\s*\]")
POSSESSIVE_END_RE = re.compile(r"['’]s?$")


def email_misses(text, entities):
    """(start, value) of email addresses not inside an EMAIL entity."""
    spans = [(e["start"], e["end"]) for e in entities if e.get("type") == "EMAIL"]
    return [(m.start(), m.group()) for m in VALIDATOR_EMAIL_RE.finditer(text)
            if not any(s <= m.start() and m.end() <= t for s, t in spans)]


def placeholder_tokens(text, strict=False):
    """(start, token) of bracketed tokens that name one of our types; with strict, also
    capitalised tokens with a number such as [NAME_1]."""
    out = []
    for m in PLACEHOLDER_RE.finditer(text):
        name, number = m.group(1), m.group(2)
        if re.sub(r"[ _-]+", "_", name.strip()).upper() in TYPES or (strict and number is not None and name == name.upper()):
            out.append((m.start(), m.group()))
    return out


def check_file(path):
    """Check one JSONL file; return (record count, errors)."""
    path = Path(path)
    group = path.stem if path.stem in GROUPS else None
    records, errors = [], []
    for ln, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as ex:
            errors.append(f"line {ln}: invalid JSON ({ex})")
    return len(records), errors + check_records(records, group)


def assert_valid(records, group, label):
    errors = check_records(records, group)
    if errors:
        print(f"SCHEMA CHECK FAILED for {label}: {len(errors)} errors", file=sys.stderr)
        for e in errors[:50]:
            print("  " + e, file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------- regex sweep

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?\b")
CARD_RE = re.compile(r"(?<![\d-])\d(?:[ -]?\d){12,18}(?![\d-])")
# Detection is broad on purpose (a synthetic value with a bad checksum or an invalid
# prefix is still personal-looking); the fake_* generators below emit only valid values.
NI_RE = re.compile(r"\b[A-Z]{2} ?\d{2} ?\d{2} ?\d{2} ?[A-D]\b")
PHONE_RE = re.compile(r"(?<![\w+])(?:\+44\s?(?:\(0\)\s?)?|\(?0)\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}(?!\d)")
# Format level, like validate_docs.py: placeholder postcodes such as AB1 2CD (letters a real
# postcode never has in the last part) must still be split out of addresses and swept.
POSTCODE_RE = re.compile(r"\b(?:GIR ?0AA|[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2})\b")
SORT_CODE_RE = re.compile(r"(?<![\d-])\d{2}-\d{2}-\d{2}(?![\d-])")
ACCOUNT8_RE = re.compile(r"(?<![\d-])\d{8}(?![\d-])")
NI_BAD_PREFIX = {"BG", "GB", "NK", "KN", "TN", "NT", "ZZ"}


def iban_valid(s):
    s = s.replace(" ", "")
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", s):
        return False
    if s.startswith("GB") and len(s) != 22:
        return False
    digits = "".join(str(int(c, 36)) for c in s[4:] + s[:4])
    return int(digits) % 97 == 1


def luhn_valid(digits):
    total = 0
    for i, c in enumerate(reversed(digits)):
        d = int(c)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def uk_phone_valid(s):
    d = re.sub(r"\D", "", s)
    if d.startswith("440"):
        d = "0" + d[3:]
    elif d.startswith("44"):
        d = "0" + d[2:]
    return d.startswith("0") and len(d) in (10, 11) and not d.startswith("00")


def sweep(text):
    """Find structured identifiers. Returns non-overlapping (start, end, kind, value),
    earlier kinds winning. Kinds are entity types, except ACCOUNT8 (an 8-digit
    number that is only a BANK_ACCOUNT in context)."""
    found = []

    def free(s, e):
        return all(e <= fs or s >= fe for fs, fe, _, _ in found)

    def add(regex, kind, ok=lambda v: True):
        for m in regex.finditer(text):
            if ok(m.group()) and free(m.start(), m.end()):
                found.append((m.start(), m.end(), kind, m.group()))

    add(EMAIL_RE, "EMAIL")
    add(IBAN_RE, "IBAN", lambda v: iban_valid(v) or re.fullmatch(r"GB\d{2}[A-Z]{4}\d{14}", v.replace(" ", "")))
    add(CARD_RE, "CARD", lambda v: luhn_valid(re.sub(r"\D", "", v)) or re.fullmatch(r"\d{4}([ -])\d{4}\1\d{4}\1\d{4}", v))
    add(NI_RE, "NI_NUMBER")
    add(PHONE_RE, "PHONE", uk_phone_valid)
    add(POSTCODE_RE, "POSTCODE")
    add(SORT_CODE_RE, "SORT_CODE")
    add(ACCOUNT8_RE, "ACCOUNT8")
    return sorted(found)


def uncovered_hits(text, entities):
    """Sweep hits that do not lie inside a labelled entity."""
    spans = [(e["start"], e["end"]) for e in entities]
    return [h for h in sweep(text) if not any(s <= h[0] and h[1] <= e for s, e in spans)]


# ---------------------------------------------------------------- fake UK values

IBAN_BANKS = ["NWBK", "BARC", "LOYD", "HBUK", "MIDL", "NAIA", "SRLG", "MONZ", "CPBK", "TSBS"]
NI_FIRST = "ABCEGHJKLMNOPRSTWXYZ"
NI_SECOND = "ABCEGHJKLMNPRSTWXYZ"


def digits(rng, n):
    return "".join(rng.choice("0123456789") for _ in range(n))


def fake_sort_code(rng):
    return f"{rng.randint(1, 99):02d}-{digits(rng, 2)}-{digits(rng, 2)}"


def fake_account(rng):
    return str(rng.randint(1, 9)) + digits(rng, 7)


def fake_gb_iban(rng, sort_code=None, account=None):
    bban = rng.choice(IBAN_BANKS) + (sort_code or fake_sort_code(rng)).replace("-", "") + (account or fake_account(rng))
    num = "".join(str(int(c, 36)) for c in bban + "GB00")
    return f"GB{98 - int(num) % 97:02d}{bban}"


def fake_card(rng):
    kind = rng.choice(["visa", "visa", "mc", "amex"])
    prefix, length = {"visa": ("4", 16), "mc": (str(rng.randint(51, 55)), 16), "amex": (rng.choice(["34", "37"]), 15)}[kind]
    body = prefix + digits(rng, length - len(prefix) - 1)
    for check in "0123456789":
        if luhn_valid(body + check):
            return body + check


def fake_ni(rng):
    while True:
        p = rng.choice(NI_FIRST) + rng.choice(NI_SECOND)
        if p not in NI_BAD_PREFIX:
            return p + digits(rng, 6) + rng.choice("ABCD")


def fake_driving_licence(rng, surname, first, dob, female):
    """DVLA style: surname(5) decade month(+50 if female) day year-digit initials(2) 9 check(2)."""
    sur = re.sub(r"[^A-Z]", "", surname.upper().replace("MAC", "MC"))[:5].ljust(5, "9")
    month = dob.month + (50 if female else 0)
    ini = (re.sub(r"[^A-Z]", "", first.upper())[:1] + "9")[:2]
    return f"{sur}{str(dob.year)[2]}{month:02d}{dob.day:02d}{str(dob.year)[3]}{ini}9{rng.choice('ABCDEFGHJKLMNPRSTUVWXYZ')}{rng.choice('ABCDEFGHJKLMNPRSTUVWXYZ')}"


def fake_passport(rng):
    return str(rng.randint(1, 9)) + digits(rng, 8)


# ---------------------------------------------------------------- IO

def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def merge_write(group, new_records, owns):
    """Replace the records this builder owns (owns(rec) is True) in data/docs/<group>.jsonl,
    keep the rest, check the result and write it sorted by doc_id."""
    path = DOCS_DIR / f"{group}.jsonl"
    kept = [r for r in read_jsonl(path) if not owns(r)]
    records = sorted(kept + list(new_records), key=lambda r: r["doc_id"])
    assert_valid(records, group, str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest.setdefault("counts", {})[path.name] = len(records)
        MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path, len(records)


def update_manifest(section, data):
    """Write one builder's section; a section that has been built is no longer blocked."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    manifest[section] = data
    manifest.get("not_built", {}).pop(section, None)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def stable_rng(*parts):
    return random.Random("|".join(str(p) for p in parts))
