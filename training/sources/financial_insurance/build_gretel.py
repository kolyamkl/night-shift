"""Select about 100 English UK documents from gretelai/synthetic_pii_finance_multilingual,
map their PII labels to our 13 types, validate them, and merge them into
data/docs/financial.jsonl and data/docs/insurance.jsonl.

Only the English part of the dataset is read: the two parquet files in FILES, at the
pinned commit REVISION, downloaded with hf_hub_download to a directory outside the repo
(default /tmp/raw/financial_insurance/gretel). No other file of the dataset is fetched.
The label mapping is read from label_map.md (the committed table is the only copy).
Nothing is written inside the repo except the two JSONL files and the manifest section
"gretel".

Usage:
  python3 build_gretel.py [--revision SHA] [--n 100] [--raw DIR]
  python3 build_gretel.py --rows FILE.jsonl --out-dir DIR   # local rows, for tests
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from common import (
    NI_RE, POSTCODE_RE, REPO, assert_valid, check_entities, email_misses, iban_valid, merge_write,
    placeholder_tokens, stable_rng, sweep, update_manifest,
)

DATASET = "gretelai/synthetic_pii_finance_multilingual"
URL = f"https://huggingface.co/datasets/{DATASET}"
REVISION = "7b844d16738527a04264f50214cb426a4cea0897"
FILES = {"train": "data/English_train-00000-of-00001.parquet", "test": "data/English_test-00000-of-00001.parquet"}
RAW_DEFAULT = Path("/tmp/raw/financial_insurance/gretel")
LABEL_MAP_MD = Path(__file__).with_name("label_map.md")
SEED = "night-shift-gretel-v1"
SPLIT_SHARES = (("train", 0.5), ("fresh", 0.3), ("eval", 0.2))
INSURANCE_SHARE = 0.45
TEXT_COLS = ("generated_text", "text")
SPAN_COLS = ("pii_spans", "spans")
ID_COLS = ("__index_level_0__", "uid", "id", "index", "level_0")
LOCALE_COLS = ("language_description", "locale", "region", "country")

# Document types kept, by group: personal financial and insurance documents about an
# individual. Everything else in the English files (machine formats such as FIX, SWIFT,
# MT940, EDI, XBRL, CSV; corporate reports, prospectuses, policies and guidelines;
# marketing email, chat logs, safety data sheets, bills of lading) is left out.
DOC_TYPES = {
    "financial": [
        "Bank Statement", "Credit Card Statement", "Mortgage Amortization Schedule",
        "Loan Application", "Credit Application", "Credit Card Application", "Financial Aid Application",
        "Payment Confirmation", "Transaction Confirmation",
        "Loan Agreement", "Mortgage Contract", "Real Estate Loan Agreement",
        "Tax Return", "Tax Assessment Notice",
    ],
    "insurance": [
        "Insurance Policy", "Insurance Claim Form", "Health Insurance Claim Form", "Policyholder's Report",
        "Renewal Reminder",  # every expanded type in the data is about an insurance policy or claim
    ],
}
GROUP_OF = {t: g for g, ts in DOC_TYPES.items() for t in ts}
# Inside a document type, these expanded types (invoices, payslips, claim letters) are picked first.
PREFERRED_EXPANDED_RE = re.compile(r"invoice|salary|payroll|pay ?slip|claim (?:approval|rejection|denial)", re.I)

# UK rule. The English files mark each row's variety in language_description: either
# "English language as spoken in the United Kingdom" or "... in the United States, the UK,
# or Canada". A row is UK when that column names the UK and no other country, and the text
# has no non-UK signal. Without such a column (local test rows), the text must also carry
# a UK signal.
UK_LOCALE_RE = re.compile(r"\b(?:United Kingdom|UK|GB|en[-_]GB)\b", re.I)
OTHER_LOCALE_RE = re.compile(r"United States|\bUSA?\b|Canada|Australia|Ireland|\ben[-_](?:US|CA|AU|IE)\b")
UK_SIGNALS = [re.compile(p, re.I if i > 1 else 0) for i, p in enumerate([
    r"£|\bGBP\b",
    r"\bGB\d{2} ?[A-Z]{4}",
    r"\bsort code\b|\bnational insurance\b|\bHMRC\b|\bpostcode\b",
])] + [POSTCODE_RE, re.compile(r"(?:\+44\s?(?:\(0\)\s?)?|\b0)(?:1\d{2,4}|2\d|7\d{3})[\s-]?\d{3,4}[\s-]?\d{3,4}\b")]
NON_UK_SIGNALS = [re.compile(p) for p in [
    r"\$\s?\d|\bUSD\b|\bEUR\b|€|\bCHF\b|\bSEK\b",
    r"\b\d{3}-\d{2}-\d{4}\b",
    r"\brouting number\b|\bZIP\b|\bSocial Security\b",
    r"\b[A-Z]{2} \d{5}(?:-\d{4})?\b",
]] + [re.compile(r"\brouting number\b|\bsocial security\b", re.I)]
UK_RULE = ("language column is English; language_description names the United Kingdom and no other country "
           "(exactly 'English language as spoken in the United Kingdom'; the mixed 'United States, the UK, or Canada' "
           "rows are left out); and the text has no non-UK signal ($ or USD/EUR/CHF/SEK or €, US SSN pattern "
           "NNN-NN-NNNN, 'routing number', 'ZIP', 'Social Security', US state plus ZIP)")

# Field-label sweep (design 9.4, "fixed if the fix is unambiguous"): a value written
# right after an explicit field label is labelled when the dataset left it unlabelled.
DIGITS_TOKEN = r"(?=[A-Za-z0-9/._-]*\d)[A-Za-z0-9](?:[A-Za-z0-9/._-]*[A-Za-z0-9])?"
DATE_VALUE = (r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Z][a-z]+,?\s+\d{4}"
              r"|[A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}")
SEP = r"\**[ \t]*[:#.]?[ \t]*\**[ \t]*"  # label and value on one line; markdown bold allowed
FIELD_RULES = [
    ("DOB", re.compile(r"\b(?:date\s+of\s+birth|D\.?O\.?B\.?)" + SEP + r"(?P<v>" + DATE_VALUE + r")", re.I)),
    ("SORT_CODE", re.compile(r"\bsort\s*code" + SEP + r"(?P<v>\d{2}[- ]\d{2}[- ]\d{2}|\d{6})(?![\d-])", re.I)),
    ("BANK_ACCOUNT", re.compile(r"\b(?:bank\s+)?(?:account|acct\.?|a/c)\s*(?:number|no\.?|num\.?|#)" + SEP
                                + r"(?P<v>\d{2,}(?:[ -]\d{2,})+(?![\d-])|" + DIGITS_TOKEN + r")", re.I)),
    ("ID_DOC", re.compile(r"\b(?:passport|driving\s+licen[cs]e|driver'?s?\s+licen[cs]e)\s*(?:number|no\.?|#)?" + SEP
                          + r"(?P<v>" + DIGITS_TOKEN + r")", re.I)),
    ("CUSTOM", re.compile(r"\b(?:(?:policy|claim|customer|client|member(?:ship)?|case|patient|employee|applicant|"
                          r"application|loan)\s*(?:number|no\.?|id|#|ref(?:erence)?|code)"
                          r"|tax\s+reference(?:\s+(?:number|no\.?))?|unique\s+taxpayer\s+reference|UTR)"
                          + SEP + r"(?P<v>" + DIGITS_TOKEN + r")", re.I)),
]
MIN_FIELD_LEN = {"BANK_ACCOUNT": 4, "ID_DOC": 5, "CUSTOM": 5}
YEAR_RE = re.compile(r"(?:19|20)\d{2}")
DIGIT_TYPES = {"PHONE", "BANK_ACCOUNT", "SORT_CODE", "IBAN", "CARD", "NI_NUMBER", "DOB", "ID_DOC"}
TEMPLATE_CHARS = set("[]{}<>")
# A title written with a name goes inside the PERSON entity (T1 prompt); mentions with and
# without the title are the same person.
TITLE_BEFORE_RE = re.compile(r"\b(?:Mrs|Mr|Ms|Miss|Mx|Dr)\.? $")
TITLE_START_RE = re.compile(r"^(?:mrs|mr|ms|miss|mx|dr)\.? ")


def load_label_map():
    """Parse the markdown table: | gretel label | our type or 'keep visible' or 'drop document' | why |"""
    mapping = {}
    for line in LABEL_MAP_MD.read_text(encoding="utf-8").splitlines():
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not re.fullmatch(r"[a-z0-9_]+", cells[0]):
            continue
        target = cells[1]
        if target == "keep visible":
            mapping[cells[0]] = "KEEP"
        elif target == "drop document":
            mapping[cells[0]] = "DROP_DOC"
        else:
            mapping[cells[0]] = target
    if not mapping:
        sys.exit(f"no label rows found in {LABEL_MAP_MD}")
    return mapping


def pick_col(row, names, what, required=True):
    for n in names:
        if n in row:
            return n
    if required:
        sys.exit(f"dataset has no {what} column (looked for {names}); columns are {sorted(row)}")
    return None


def uk_check(text, row, locale_col):
    """Return None for a UK document, else the reason it is not one."""
    if locale_col:
        v = str(row[locale_col])
        if not UK_LOCALE_RE.search(v) or OTHER_LOCALE_RE.search(v):
            return "locale_not_uk"
    elif not any(p.search(text) for p in UK_SIGNALS):
        return "no_uk_signal"
    if any(p.search(text) for p in NON_UK_SIGNALS):
        return "non_uk_signal"
    return None


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") or "unknown"


def mid_word(text, s, e):
    return (s > 0 and text[s - 1].isalnum() and text[s].isalnum()) or (e < len(text) and text[e - 1].isalnum() and text[e].isalnum())


def split_address(text, s, e):
    """Split a street address span into ADDRESS parts and POSTCODE spans."""
    out, cur = [], s
    for m in POSTCODE_RE.finditer(text, s, e):
        out.append((cur, m.start(), "ADDRESS"))
        out.append((m.start(), m.end(), "POSTCODE"))
        cur = m.end()
    out.append((cur, e, "ADDRESS"))
    res = []
    for a, b, t in out:
        while a < b and text[a] in " ,;\n\t":
            a += 1
        while b > a and text[b - 1] in " ,;\n\t":
            b -= 1
        if a < b:
            res.append((a, b, t))
    return res


def value_problem(label, target, value):
    """Why a labelled value cannot be used as-is, or None."""
    if TEMPLATE_CHARS & set(value):
        return "template_placeholder_span"
    if target == "PERSON":
        if not re.search(r"[A-Z]", value) or re.search(r"[\d_@/\\:#]", value):
            return "person_span_not_a_name"
    elif target in DIGIT_TYPES and not re.search(r"\d", value):
        return f"span_value_not_valid:{target}"
    elif target == "CUSTOM":
        if label == "user_name":
            if re.search(r"\s", value):
                return "span_value_not_valid:CUSTOM"
        elif not re.search(r"\d", value) or ": " in value:
            return "span_value_not_valid:CUSTOM"
    elif target == "EMAIL" and "@" not in value:
        return "email_span_without_at"
    return None


def convert(text, raw_spans, label_map):
    """Return (entities, None, notes) or (None, drop_reason, notes)."""
    notes = Counter()
    if isinstance(raw_spans, str):
        raw_spans = json.loads(raw_spans)
    hidden, visible = [], []  # (start, end, type, group key) / (start, end, label)
    for n, sp in enumerate(raw_spans):
        label = str(sp.get("label", sp.get("type", ""))).lower()
        s, e = sp.get("start"), sp.get("end")
        if label not in label_map:
            return None, f"unmapped_label:{label}", notes
        if label_map[label] == "DROP_DOC":
            return None, f"drop_label:{label}", notes
        if not (isinstance(s, int) and isinstance(e, int) and 0 <= s < e <= len(text)):
            return None, "span_offsets_invalid", notes
        value = sp.get("value", sp.get("text"))
        if value is not None and text[s:e] != value:
            return None, "span_text_mismatch", notes
        while s < e and text[s] in " \n\t":
            s += 1
        while e > s and text[e - 1] in " \n\t.,;:":
            e -= 1
        target = label_map[label]
        if target == "KEEP":
            if s < e:
                visible.append((s, e, label))
            continue
        if target == "PERSON":
            m = re.search(r"['’]s?$", text[s:e])
            if m and e - s - len(m.group()) >= 2:
                e -= len(m.group())
                notes["possessive_trimmed"] += 1
            t = TITLE_BEFORE_RE.search(text[max(0, s - 6):s])
            if t:
                s -= len(t.group())
                notes["title_moved_inside"] += 1
        if s == e or mid_word(text, s, e):
            return None, "span_mid_word", notes
        value = text[s:e]
        if label == "bban" and iban_valid(value):
            target = "IBAN"
            notes["bban_is_iban"] += 1
        elif label == "ssn" and NI_RE.fullmatch(value):
            target = "NI_NUMBER"
            notes["ssn_in_ni_format"] += 1
        problem = value_problem(label, target, value)
        if problem:
            return None, problem, notes
        if target == "ADDRESS" and label == "street_address":
            hidden += [(a, b, t, f"addr{n}:{t}") for a, b, t in split_address(text, s, e)]
        else:
            hidden.append((s, e, target, None))

    # Field-label sweep: unlabelled values right after an explicit field label.
    for typ, rx in FIELD_RULES:
        for m in rx.finditer(text):
            s, e = m.span("v")
            v = m.group("v")
            if len(v) < MIN_FIELD_LEN.get(typ, 0) or (typ == "CUSTOM" and YEAR_RE.fullmatch(v)):
                continue
            if any(a <= s and e <= b for a, b, _, _ in hidden):
                continue
            if any(s < b and a < e for a, b, _, _ in hidden):
                return None, f"field_partial_overlap:{typ}", notes
            vis = [x for x in visible if s < x[1] and x[0] < e]
            if vis:
                if typ == "DOB" and all(x[2] in ("date", "date_time") for x in vis):
                    visible = [x for x in visible if x not in vis]
                    notes["date_relabelled_dob"] += 1
                else:
                    continue
            hidden.append((s, e, typ, None))
            notes[f"field_added:{typ}"] += 1

    # One person per span: merge PERSON spans separated only by spaces (first_name + last_name).
    hidden.sort(key=lambda h: (h[0], -h[1]))
    merged = []
    for h in hidden:
        p = merged[-1] if merged else None
        if p and p[2] == h[2] == "PERSON" and p[1] <= h[0] and re.fullmatch(r" +", text[p[1]:h[0]]):
            merged[-1] = (p[0], h[1], "PERSON", None)
            notes["merged_name_parts"] += 1
        else:
            merged.append(h)

    # Overlaps among hidden spans: same span or nested with the same type is a duplicate,
    # anything else is ambiguous and drops the document.
    clean = []
    for h in merged:
        p = clean[-1] if clean else None
        if p and h[0] < p[1]:
            if h[1] <= p[1] and h[2] == p[2]:
                notes["nested_duplicate_removed"] += 1
                continue
            return None, "overlapping_spans", notes
        clean.append(h)
    for s, e, t, _ in clean:
        for vs, ve, vl in visible:
            if s < ve and vs < e and vl == "company":
                return None, "person_data_inside_company_name", notes

    # Regex sweep for unlabelled structured identifiers.
    for s, e, kind, value in sweep(text):
        if any(a <= s and e <= b for a, b, _, _ in clean):
            continue
        if any(s < b and a < e for a, b, _, _ in clean):
            return None, f"sweep_partial_overlap:{kind}", notes
        if any(s < ve and vs < e for vs, ve, _ in visible):
            continue
        before = text[max(0, s - 40):s]
        if kind in ("EMAIL", "IBAN", "NI_NUMBER", "POSTCODE"):
            typ = kind
        elif kind == "PHONE" and (re.search(r"[\s()+-]", value) or re.search(r"tel|phone|mobile|call|fax|contact", before, re.I)):
            typ = "PHONE"
        elif kind == "CARD" and re.search(r"card", before, re.I):
            typ = "CARD"
        elif kind == "SORT_CODE" and re.search(r"sort", before[-25:], re.I):
            typ = "SORT_CODE"
        elif kind == "ACCOUNT8" and re.search(r"(account|acct|a/c)\b[^\n]{0,20}$", before, re.I):
            typ = "BANK_ACCOUNT"
        else:
            return None, f"sweep_ambiguous:{kind}", notes
        clean.append((s, e, typ, None))
        notes[f"sweep_added:{typ}"] += 1
    clean.sort()

    # entity_id: same type and value share an id; address parts of one span share an id;
    # a one-word PERSON mention joins the only longer PERSON name containing that word.
    norm = lambda v: re.sub(r"\s+", " ", v).strip().lower()
    pnorm = lambda v: TITLE_START_RE.sub("", norm(v))
    key_of = {}
    for s, e, t, g in clean:
        key_of[(s, e)] = g or (t, pnorm(text[s:e]) if t == "PERSON" else norm(text[s:e]))
    full_names = {pnorm(text[s:e]) for s, e, t, _ in clean if t == "PERSON" and " " in pnorm(text[s:e])}
    for s, e, t, _ in clean:
        v = pnorm(text[s:e])
        if t == "PERSON" and " " not in v:
            owners = [f for f in full_names if v in f.split(" ")]
            if len(owners) == 1:
                key_of[(s, e)] = ("PERSON", owners[0])
    ids = {}
    entities = []
    for s, e, t, _ in clean:
        eid = ids.setdefault(key_of[(s, e)], f"e{len(ids) + 1}")
        entities.append(dict(start=s, end=e, type=t, value=text[s:e], entity_id=eid))
    if check_entities(text, entities):
        return None, "invalid_after_processing", notes
    # The documents validator (training/rewrite/validate_docs.py) rejects these two; drop them here.
    if email_misses(text, entities):
        return None, "email_not_covered", notes
    if placeholder_tokens(text, strict=True):
        return None, "placeholder_like_token", notes
    return entities, None, notes


def iter_rows(args):
    if args.rows:
        for n, line in enumerate(args.rows.read_text(encoding="utf-8").splitlines()):
            yield "local", n, json.loads(line)
        return
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download
    for split, filename in FILES.items():
        path = Path(hf_hub_download(DATASET, filename, repo_type="dataset", revision=args.revision, local_dir=args.raw))
        print(f"  read {path} ({path.stat().st_size / 1e6:.1f} MB)")
        for n, row in enumerate(pq.read_table(path).to_pylist()):
            yield split, n, row


def resolve_revision(args):
    if args.rows:
        return "local-rows"
    from huggingface_hub import HfApi
    revision = args.revision or REVISION
    for info in HfApi().get_paths_info(DATASET, list(FILES.values()), repo_type="dataset", revision=revision):
        print(f"  {info.path}: {(info.size or 0) / 1e6:.1f} MB")
    return revision


def select(cands, n, rng):
    """Round-robin over document types for variety; inside a type, preferred expanded types first."""
    buckets = defaultdict(list)
    for c in sorted(cands, key=lambda c: c["doc_id"]):
        buckets[c["subtype"]].append(c)
    for b in buckets.values():
        rng.shuffle(b)
        b.sort(key=lambda c: not PREFERRED_EXPANDED_RE.search(c["_expanded"]))  # stable: keeps the shuffle
    order = sorted(buckets)
    chosen = []
    while len(chosen) < n and any(buckets.values()):
        for k in order:
            if buckets[k] and len(chosen) < n:
                chosen.append(buckets[k].pop(0))
    return chosen


def assign_splits(docs, rng):
    by_group = defaultdict(list)
    for d in sorted(docs, key=lambda d: d["doc_id"]):
        by_group[d["group"]].append(d)
    for group_docs in by_group.values():
        rng.shuffle(group_docs)
        n, i = len(group_docs), 0
        for k, (split, share) in enumerate(SPLIT_SHARES):
            j = n if k == len(SPLIT_SHARES) - 1 else i + round(n * share)
            for d in group_docs[i:j]:
                d["split"] = split
            i = j


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--revision", help=f"dataset commit hash (default: the pinned {REVISION})")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--raw", type=Path, default=RAW_DEFAULT, help="download directory, outside the repo")
    ap.add_argument("--rows", type=Path, help="local JSONL rows instead of the Hugging Face dataset (tests)")
    ap.add_argument("--out-dir", type=Path, help="write financial.jsonl / insurance.jsonl here instead of data/docs")
    args = ap.parse_args()
    args.raw = args.raw.resolve()
    if args.raw.is_relative_to(REPO):
        sys.exit("raw files must be kept outside the repo")
    label_map = load_label_map()
    revision = resolve_revision(args)
    args.revision = revision if not args.rows else None

    stats, drops, notes, uk_drops, types_seen, out_of_scope = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    cands, cols = [], None
    for split, n, row in iter_rows(args):
        if cols is None:
            cols = dict(text=pick_col(row, TEXT_COLS, "text"), spans=pick_col(row, SPAN_COLS, "PII spans"),
                        lang=pick_col(row, ("language",), "language"), type=pick_col(row, ("document_type",), "document type"),
                        expanded=pick_col(row, ("expanded_type",), "expanded type", required=False),
                        id=pick_col(row, ID_COLS, "row id", required=False),
                        locale=pick_col(row, LOCALE_COLS, "locale", required=False))
            print("columns used:", cols)
        stats["rows"] += 1
        if not str(row[cols["lang"]]).lower().startswith(("english", "en")):
            continue
        stats["english"] += 1
        text = row[cols["text"]]
        not_uk = uk_check(text, row, cols["locale"])
        if not_uk:
            uk_drops[not_uk] += 1
            continue
        stats["english_uk"] += 1
        doc_type = str(row[cols["type"]])
        types_seen[doc_type] += 1
        group = GROUP_OF.get(doc_type)
        if group is None:
            out_of_scope[doc_type] += 1
            drops["document_type_out_of_scope"] += 1
            continue
        stats["uk_in_scope"] += 1
        entities, reason, nt = convert(text, row[cols["spans"]], label_map)
        if reason:
            drops[reason] += 1
            continue
        notes.update(nt)
        row_id = f"{split}-{row[cols['id']] if cols['id'] else n}"
        cands.append(dict(
            doc_id=f"{group}-gretel-{row_id}", source_id=f"gretel-{row_id}", group=group, subtype=slug(doc_type),
            split=None, fill=0, text=text, entities=entities,
            provenance=dict(url=URL, licence="Apache-2.0", kind="synthetic",
                            attribution="Gretel.ai, gretelai/synthetic_pii_finance_multilingual"),
            _expanded=str(row[cols["expanded"]]) if cols["expanded"] else "",
        ))
    stats["valid_candidates"] = len(cands)
    rng = stable_rng(SEED)
    n_ins = round(args.n * INSURANCE_SHARE)
    ins = select([c for c in cands if c["group"] == "insurance"], n_ins, rng)
    fin = select([c for c in cands if c["group"] == "financial"], args.n - len(ins), rng)
    chosen = fin + ins
    assign_splits(chosen, rng)
    expanded = Counter(f"{c['group']}/{c['subtype']}/{c['_expanded']}" for c in chosen)
    for c in chosen:
        del c["_expanded"]

    for group in ("financial", "insurance"):
        recs = [c for c in chosen if c["group"] == group]
        if args.out_dir:
            assert_valid(recs, group, group)
            args.out_dir.mkdir(parents=True, exist_ok=True)
            (args.out_dir / f"{group}.jsonl").write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in sorted(recs, key=lambda r: r["doc_id"])),
                encoding="utf-8")
        else:
            merge_write(group, recs, lambda r: r["source_id"].startswith("gretel-"))

    by_group_subtype = defaultdict(Counter)
    for c in chosen:
        by_group_subtype[c["group"]][c["subtype"]] += 1
    summary = dict(
        dataset=DATASET, url=URL, revision=revision, files=list(FILES.values()), licence="Apache-2.0",
        attribution="Gretel.ai", seed=SEED,
        uk_rule=UK_RULE if cols["locale"] else "no locale column: a UK signal in the text and no non-UK signal",
        document_types=DOC_TYPES,
        label_map="training/sources/financial_insurance/label_map.md",
        counts=dict(
            rows_seen=stats["rows"], english=stats["english"], not_uk=dict(uk_drops.most_common()),
            english_uk=stats["english_uk"], uk_in_scope=stats["uk_in_scope"],
            valid_candidates=stats["valid_candidates"],
            valid_by_group=dict(Counter(c["group"] for c in cands)), selected=len(chosen),
            drop_reasons=dict(drops.most_common()), fixes_in_candidates=dict(notes.most_common()),
            by_group_split={g: dict(sorted(Counter(c["split"] for c in chosen if c["group"] == g).items()))
                            for g in ("financial", "insurance")},
            by_group_subtype={g: dict(sorted(v.items())) for g, v in sorted(by_group_subtype.items())},
            preferred_expanded_selected={k: v for k, v in sorted(expanded.items()) if PREFERRED_EXPANDED_RE.search(k)},
            entities_by_type=dict(Counter(e["type"] for c in chosen for e in c["entities"]).most_common()),
            uk_document_types_out_of_scope=dict(out_of_scope.most_common()),
        ),
    )
    if not args.out_dir:
        update_manifest("gretel", summary)
    print(json.dumps(summary["counts"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
