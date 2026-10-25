"""gretelai/synthetic_pii_finance_multilingual -> canonical (pool A). English train + test parquet only."""
from __future__ import annotations

import json
from collections import Counter

import pyarrow.parquet as pq

from . import mapping as M
from .mapping import address_flags
from .common import RAW, resolve_overlaps, slug

DATASET = {
    "id": "gretelai/synthetic_pii_finance_multilingual",
    "dir": "gretelai__synthetic_pii_finance_multilingual",
    "short": "gfin",
    "license": "Apache-2.0",
    "pool": "A",
    "revision": "7b844d16738527a04264f50214cb426a4cea0897",
}

MAP = M.Mapping(
    simple={
        "name": "PERSON",
        "street_address": "ADDRESS",
        "email": "EMAIL",
        "phone_number": "PHONE",
        "iban": "IBAN",
        "bban": "BANK_ACCOUNT",
        "credit_card_number": "CARD",
        "date_of_birth": "DOB",
        "passport_number": "ID_DOC",
        "driver_license_number": "ID_DOC",
        "customer_id": "CUSTOM",
        "employee_id": "CUSTOM",
    },
    fn={"ssn": M.ssn_type},
    person_parts={"first_name", "last_name"},
    keep={"company", "date", "time", "date_time", "swift_bic_code"},
    out_of_scope={
        "credit_card_security_code", "account_pin", "api_key", "password", "user_name", "ipv4", "ipv6",
        "local_latlng", "bank_routing_number",
    },
)


def convert(stats: Counter):
    for sp in ("train", "test"):
        t = pq.read_table(RAW / DATASET["dir"] / "data" / f"English_{sp}-00000-of-00001.parquet")
        stats[f"rows_read_{sp}"] = t.num_rows
        for r in t.to_pylist():
            if r["language"] != "English":
                stats["skip_not_english"] += 1
                continue
            text = r["generated_text"]
            raw = []
            for x in json.loads(r["pii_spans"]):
                if not (0 <= x["start"] < x["end"] <= len(text)):
                    raw = None
                    break
                raw.append({"start": x["start"], "end": x["end"], "label": x["label"]})
            if raw is None:
                stats["skip_row_bad_offsets"] += 1
                continue
            res = M.apply(text, raw, MAP, stats)
            if res is None:
                stats["skip_row_mapping_failed"] += 1
                continue
            ents, dropped, oos = res
            ents = resolve_overlaps(ents, stats)
            uk = "United Kingdom" in (r["language_description"] or "")
            yield {
                "text": text,
                "entities": ents,
                "split": "train" if sp == "train" else "eval",
                "doc_type": slug(r["document_type"]),
                "meta": {
                    "mubit_ok": True,
                    "locale": "en-GB" if uk else "en-US/GB/CA",
                    "source_index": r.get("__index_level_0__"),
                    "source_split": sp,
                    "expanded_type": r["expanded_type"],
                    "revision": DATASET["revision"],
                    "orig_labels": [[x["start"], x["end"], x["label"]] for x in raw],
                    "dropped_labels": dict(dropped),
                    "out_of_scope": oos,
                    "quality_flags": address_flags(ents),
                },
            }
