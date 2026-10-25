"""nvidia/Nemotron-PII -> canonical (pool A). Train and test parquet; `spans` is a Python-literal string."""
from __future__ import annotations

import ast
from collections import Counter

import pyarrow.parquet as pq

from . import mapping as M
from .mapping import address_flags
from .common import RAW, resolve_overlaps, slug

DATASET = {
    "id": "nvidia/Nemotron-PII",
    "dir": "nvidia__Nemotron-PII",
    "short": "nemo",
    "license": "CC-BY-4.0",
    "pool": "A",
    "revision": "b70ffaf5ff39e079776134c5bf4381f00a9fd1ed",
}

MAP = M.Mapping(
    simple={
        "email": "EMAIL",
        "phone_number": "PHONE",
        "fax_number": "PHONE",
        "postcode": "POSTCODE",
        "date_of_birth": "DOB",
        "credit_debit_card": "CARD",
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
    addr_parts={"street_address", "city", "state", "county"},
    addr_anchor={"street_address"},
    keep={
        "company_name", "date", "time", "date_time", "occupation", "country", "city", "state", "county",
        "employment_status", "education_level", "race_ethnicity", "religious_belief", "blood_type", "gender",
        "age", "political_view", "sexuality", "language", "url", "swift_bic",
    },
    out_of_scope={
        "password", "pin", "cvv", "api_key", "http_cookie", "ipv4", "ipv6", "mac_address", "device_identifier",
        "biometric_identifier", "vehicle_identifier", "license_plate", "coordinate", "user_name",
        "bank_routing_number", "unique_id",
    },
)


def convert(stats: Counter):
    for sp in ("train", "test"):
        t = pq.read_table(RAW / DATASET["dir"] / "data" / f"{sp}-00000-of-00001.parquet")
        stats[f"rows_read_{sp}"] = t.num_rows
        for r in t.to_pylist():
            text = r["text"]
            spans = ast.literal_eval(r["spans"])  # literal parsing only, never eval
            raw = []
            for x in spans:
                if not (0 <= x["start"] < x["end"] <= len(text)):
                    stats["skip_row_bad_offsets"] += 1
                    raw = None
                    break
                if str(x.get("text", "")).lower() != text[x["start"]:x["end"]].lower():
                    stats["skip_row_span_text_mismatch"] += 1
                    raw = None
                    break
                if str(x.get("text")) != text[x["start"]:x["end"]]:
                    stats["span_text_case_differs_offsets_used"] += 1
                raw.append({"start": x["start"], "end": x["end"], "label": x["label"]})
            if raw is None:
                continue
            res = M.apply(text, raw, MAP, stats)
            if res is None:
                stats["skip_row_mapping_failed"] += 1
                continue
            ents, dropped, oos = res
            ents = resolve_overlaps(ents, stats)
            yield {
                "text": text,
                "entities": ents,
                "split": "train" if sp == "train" else "eval",
                "doc_type": slug(r["document_type"]),
                "meta": {
                    "mubit_ok": True,
                    "locale": "en-US" if r["locale"] == "us" else "en-intl",
                    "source_uid": r["uid"],
                    "source_split": sp,
                    "domain": r["domain"],
                    "document_format": r["document_format"],
                    "revision": DATASET["revision"],
                    "orig_labels": [[x["start"], x["end"], x["label"]] for x in raw],
                    "dropped_labels": dict(dropped),
                    "out_of_scope": oos,
                    "quality_flags": address_flags(ents),
                },
            }
