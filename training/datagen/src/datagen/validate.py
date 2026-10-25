"""Record validators (used by tests, by generate.py on every document, and by the CLI)."""
from __future__ import annotations

from . import ids
from .core import ENTITY_SET

# identifier types whose *full* values must pass a checksum / format check
_CHECKS = {
    "CARD": ids.is_valid_card,
    "IBAN": ids.is_valid_iban,
    "NI_NUMBER": ids.is_valid_ni,
    "SORT_CODE": ids.is_valid_sort,
    "POSTCODE": ids.is_valid_postcode,
}


def id_doc_kind(text: str) -> str | None:
    t = text.replace(" ", "").upper()
    if ids.is_valid_passport(t):
        return "passport"
    if ids.is_valid_nhs(t):
        return "nhs"
    if ids.is_valid_licence(t):
        return "licence"
    return None


def check_spans(text: str, entities: list[dict], where: str = "") -> list[str]:
    errs = []
    prev_end = -1
    for e in entities:
        s, t = e["start"], e["end"]
        if not (0 <= s < t <= len(text)):
            errs.append(f"{where}: bad offsets {e}")
            continue
        if text[s:t] != e["text"]:
            errs.append(f"{where}: text mismatch {text[s:t]!r} != {e['text']!r}")
        if e["type"] not in ENTITY_SET:
            errs.append(f"{where}: bad type {e['type']}")
        if s < prev_end:
            errs.append(f"{where}: overlap at {s}")
        prev_end = max(prev_end, t)
        if e["text"] != e["text"].strip():
            errs.append(f"{where}: padded span {e['text']!r}")
    return errs


def is_partial(e: dict, hard: list[dict]) -> bool:
    return any(h["kind"] == "partial_number" and h["start"] == e["start"] and h["end"] == e["end"] for h in hard)


def check_identifiers(rec: dict) -> list[str]:
    errs = []
    hard = rec["meta"].get("hard_cases", [])
    for e in rec["entities"]:
        fn = _CHECKS.get(e["type"])
        if e["type"] in ("CARD", "BANK_ACCOUNT") and is_partial(e, hard):
            if not (e["text"].isdigit() and len(e["text"]) == 4):
                errs.append(f"{rec.get('doc_id')}: bad partial {e}")
            continue
        if fn and not fn(e["text"]):
            errs.append(f"{rec.get('doc_id')}: invalid {e['type']} {e['text']!r}")
        if e["type"] == "BANK_ACCOUNT" and not ids.is_valid_account(e["text"]):
            errs.append(f"{rec.get('doc_id')}: invalid BANK_ACCOUNT {e['text']!r}")
        if e["type"] == "PHONE" and not ids.is_valid_phone(e["text"]):
            errs.append(f"{rec.get('doc_id')}: invalid PHONE {e['text']!r}")
        if e["type"] == "ID_DOC" and id_doc_kind(e["text"]) is None:
            errs.append(f"{rec.get('doc_id')}: invalid ID_DOC {e['text']!r}")
        if e["type"] == "EMAIL" and ("@" not in e["text"] or " " in e["text"]):
            errs.append(f"{rec.get('doc_id')}: invalid EMAIL {e['text']!r}")
    return errs


def check_keep_traps(rec: dict) -> list[str]:
    errs = []
    text = rec["text"]
    spans = [(e["start"], e["end"]) for e in rec["entities"]]
    for k in rec["meta"].get("keep_traps", []):
        if text[k["start"]:k["end"]] != k["text"]:
            errs.append(f"{rec.get('doc_id')}: keep trap text mismatch {k}")
        for s, t in spans:
            if k["start"] < t and s < k["end"]:
                errs.append(f"{rec.get('doc_id')}: keep trap overlaps entity {k}")
                break
    for h in rec["meta"].get("hard_cases", []):
        if not (0 <= h["start"] <= h["end"] <= len(text)):
            errs.append(f"{rec.get('doc_id')}: bad hard case offsets {h}")
    return errs


def check_record(rec: dict) -> list[str]:
    errs = check_spans(rec["text"], rec["entities"], rec.get("doc_id", ""))
    errs += check_identifiers(rec)
    errs += check_keep_traps(rec)
    if rec["meta"].get("negative") and rec["entities"]:
        errs.append(f"{rec.get('doc_id')}: negative document has entities")
    if len(rec["meta"].get("entity_refs", [])) != len(rec["entities"]):
        errs.append(f"{rec.get('doc_id')}: entity_refs misaligned")
    return errs


def check_chunk(chunk: dict, doc: dict | None = None) -> list[str]:
    errs = check_spans(chunk["text"], chunk["entities"], chunk["chunk_id"])
    if doc is not None:
        a = chunk["meta"]["char_start"]
        b = chunk["meta"]["char_end"]
        if doc["text"][a:b] != chunk["text"]:
            errs.append(f"{chunk['chunk_id']}: chunk text != doc slice")
        for e in chunk["entities"]:
            if doc["text"][a + e["start"]: a + e["end"]] != e["text"]:
                errs.append(f"{chunk['chunk_id']}: relative offset wrong {e}")
    return errs
