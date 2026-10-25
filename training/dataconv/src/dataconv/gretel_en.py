"""gretelai/gretel-pii-masking-en-v1 -> canonical (pool A).

The source has no offsets: `entities` is a Python-literal list of {entity, types}. We locate every
whole-token occurrence of each entity string in the text and label all of them. A document is skipped
when an in-scope entity cannot be found, or when one string is listed with conflicting types.
"""
from __future__ import annotations

import ast
import re
from collections import Counter

import pyarrow.parquet as pq

from . import mapping as M
from .mapping import address_flags
from .common import RAW, mk, resolve_overlaps, slug, trim

DATASET = {
    "id": "gretelai/gretel-pii-masking-en-v1",
    "dir": "gretelai__gretel-pii-masking-en-v1",
    "short": "gen1",
    "license": "Apache-2.0",
    "pool": "A",
    "revision": "e06eb1499ca8d54470f085021cd8e54f9efac7fd",
}

MAP = M.Mapping(
    simple={
        "name": "PERSON",
        "street_address": "ADDRESS",
        "address": "ADDRESS",
        "email": "EMAIL",
        "phone_number": "PHONE",
        "credit_card_number": "CARD",
        "postcode": "POSTCODE",
        "date_of_birth": "DOB",
        "customer_id": "CUSTOM",
        "employee_id": "CUSTOM",
        "medical_record_number": "CUSTOM",
        "health_plan_beneficiary_number": "CUSTOM",
        "tax_id": "CUSTOM",
    },
    fn={
        "ssn": M.ssn_type,
        "national_id": M.ssn_type,
        "account_number": M.account_type,
        "certificate_license_number": M.licence_type,
    },
    person_parts={"first_name", "last_name"},
    addr_parts={"street_address", "city", "state"},
    addr_anchor={"street_address"},
    keep={"date", "time", "date_time", "company_name", "city", "state", "country", "url", "swift_bic"},
    out_of_scope={
        "ipv4", "ipv6", "license_plate", "user_name", "device_identifier", "biometric_identifier",
        "bank_routing_number", "vehicle_identifier", "coordinate", "api_key", "password", "cvv", "pin",
        "unique_identifier",
    },
)
IN_SCOPE = set(MAP.simple) | set(MAP.fn) | MAP.person_parts


def pick_label(types: list[str]) -> str | None:
    for t in types:  # an in-scope type wins over keep / out-of-scope types listed for the same string
        if t in IN_SCOPE:
            return t
    return types[0] if types else None


def find_all(text: str, val: str) -> list[tuple[int, int]]:
    pat = re.compile(r"(?<!\w)" + re.escape(val) + r"(?!\w)")
    return [(m.start(), m.end()) for m in pat.finditer(text)]


def _cat(label: str) -> str:
    if label in IN_SCOPE:
        return "in:" + (MAP.simple.get(label) or ("PERSON" if label in MAP.person_parts else label))
    return "keep" if label in MAP.keep else "oos"


def convert(stats: Counter):
    for sp in ("train", "validation", "test"):
        t = pq.read_table(RAW / DATASET["dir"] / "data" / f"{sp}-00000-of-00001.parquet")
        stats[f"rows_read_{sp}"] = t.num_rows
        for r in t.to_pylist():
            out = convert_row(r, sp, stats)
            if out is not None:
                yield out


def convert_row(r: dict, sp: str, stats: Counter):
    text = r["text"]
    items = ast.literal_eval(r["entities"])  # literal parsing only
    raw, by_span, postcodes = [], {}, []
    for it in items:
        val = str(it["entity"]).strip()
        lab = pick_label(list(it["types"]))
        if not val or lab is None:
            continue
        occ = find_all(text, val)
        if not occ:
            if lab in IN_SCOPE:
                stats["skip_row_entity_not_found"] += 1
                return None
            continue
        for s, e in occ:
            prev = by_span.get((s, e))
            if prev is not None and _cat(prev) != _cat(lab):
                stats["skip_row_conflicting_types_same_string"] += 1
                return None
            by_span[(s, e)] = lab
        if lab == "postcode":
            postcodes.append(val)
    for (s, e), lab in by_span.items():
        raw.append({"start": s, "end": e, "label": lab, "type": lab})
    raw = resolve_overlaps(raw, stats)  # raw level: keep the longer mention
    for x in raw:
        del x["type"]
    res = M.apply(text, raw, MAP, stats)
    if res is None:
        stats["skip_row_mapping_failed"] += 1
        return None
    ents, dropped, oos = res
    # our convention: the postcode is its own span, not part of ADDRESS
    fixed = []
    for x in ents:
        if x["type"] == "ADDRESS":
            for pc in postcodes:
                if x["text"].endswith(pc) and len(x["text"]) > len(pc) + 3:
                    ps = x["end"] - len(pc)
                    a, b = trim(text, x["start"], ps)
                    while b > a and text[b - 1] in ",;":
                        b -= 1
                    a, b = trim(text, a, b)
                    fixed.append(mk(text, a, b, "ADDRESS"))
                    fixed.append(mk(text, ps, x["end"], "POSTCODE"))
                    stats["postcode_split_from_address"] += 1
                    break
            else:
                fixed.append(x)
        else:
            fixed.append(x)
    ents = resolve_overlaps(fixed, stats)
    return {
        "text": text,
        "entities": ents,
        "split": "eval" if sp == "test" else "train",
        "doc_type": slug(r["document_type"]),
        "meta": {
            "mubit_ok": True,
            "locale": "en",
            "source_uid": r["uid"],
            "source_split": sp,
            "domain": r["domain"],
            "revision": DATASET["revision"],
            "orig_labels": [[it["entity"], list(it["types"])] for it in items],
            "dropped_labels": dict(dropped),
            "out_of_scope": oos,
            "quality_flags": ["offsets_recovered_by_string_search"] + address_flags(ents),
        },
    }
