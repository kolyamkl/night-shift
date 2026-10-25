"""Generic label mapping for datasets that already have typed character spans."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

from .common import (PHONE_EXT, has_bank_context, has_driver_context, is_dob_context, merge_runs, mk, person_bounds,
                     span_ok, ssn_like_type, trim)

NAME_GAP = re.compile(r"[ \t]{1,2}")
ADDR_GAP = re.compile(r"[ \t]*,?[ \t]*(?:\n[ \t]*)?")


def account_type(text: str, s: int, e: int) -> str:
    """Bank account if banking words are near, else an organisation account reference (CUSTOM)."""
    return "BANK_ACCOUNT" if has_bank_context(text, s, e) else "CUSTOM"


def licence_type(text: str, s: int, e: int) -> str:
    """Driving licence -> ID_DOC; any other certificate / professional licence number -> CUSTOM."""
    return "ID_DOC" if has_driver_context(text, s) else "CUSTOM"


def dob_or_drop(text: str, s: int, e: int) -> str | None:
    return "DOB" if is_dob_context(text, s, e) else None


def ssn_type(text: str, s: int, e: int) -> str:
    return ssn_like_type(text[s:e])


@dataclass
class Mapping:
    simple: dict[str, str]                                   # label -> our type
    keep: set[str]                                           # keep classes: left unlabelled
    out_of_scope: set[str]                                   # sensitive but not one of our 13: unlabelled + recorded
    person_parts: set[str] = field(default_factory=set)     # merged into one PERSON when adjacent
    addr_parts: set[str] = field(default_factory=set)       # merged when adjacent
    addr_anchor: set[str] = field(default_factory=set)      # a run becomes ADDRESS only if it has one of these
    fn: dict[str, Callable[[str, int, int], str | None]] = field(default_factory=dict)  # context decisions


def apply(text: str, raw: list[dict], m: Mapping, stats: Counter):
    """raw: [{start, end, label}] (already validated against text).

    Returns (entities, dropped Counter, out_of_scope list) or None when the row has an unknown label.
    """
    spans = []
    for x in raw:
        s, e = trim(text, x["start"], x["end"])
        if s >= e:
            stats["span_empty_after_trim"] += 1
            continue
        spans.append({"start": s, "end": e, "label": x["label"]})
    runs = merge_runs(text, spans, "label", m.person_parts, NAME_GAP) if m.person_parts else spans
    for x in runs:
        if x.get("_run"):
            x["label"] = "_PERSON"
            del x["_run"]
    runs = merge_runs(text, runs, "label", m.addr_parts, ADDR_GAP) if m.addr_parts else runs
    ents, oos, dropped = [], [], Counter()
    ents = _Checked(text, stats)
    for x in runs:
        s, e = x["start"], x["end"]
        if x.get("_run"):
            parts = set(x["parts"])
            if parts & m.addr_anchor:
                ents.append(mk(text, s, e, "ADDRESS"))
            else:
                for p in parts:
                    dropped[p] += 1
            continue
        lab = x["label"]
        if lab == "_PERSON":
            ents.append(mk(text, s, e, "PERSON"))
            continue
        if lab in m.fn:
            typ = m.fn[lab](text, s, e)
            if typ is None:
                dropped[lab] += 1
            else:
                ents.append(mk(text, s, e, typ))
            continue
        if lab in m.simple:
            typ = m.simple[lab]
            if typ == "PHONE":
                mm = PHONE_EXT.search(text, s, e)
                if mm and mm.start() > s and mm.end() == e:
                    s, e = trim(text, s, mm.start())
                    stats["phone_extension_trimmed"] += 1
            ents.append(mk(text, s, e, typ))
        elif lab in m.keep:
            dropped[lab] += 1
        elif lab in m.out_of_scope:
            oos.append([s, e, lab])
        else:
            stats["unknown_label_" + lab] += 1
            return None
    if ents.bad:
        return None
    return list(ents), dropped, oos


class _Checked(list):
    """List of entities that normalises PERSON bounds and records broken spans."""

    def __init__(self, text: str, stats: Counter):
        super().__init__()
        self.text, self.stats, self.bad = text, stats, False

    def append(self, ent: dict) -> None:
        if ent["type"] == "PERSON":
            s, e = person_bounds(self.text, ent["start"], ent["end"])
            if (s, e) != (ent["start"], ent["end"]):
                self.stats["person_title_or_possessive_trimmed"] += 1
                ent = mk(self.text, s, e, "PERSON")
        if not span_ok(ent["type"], ent["text"]):
            self.stats["broken_span_" + ent["type"]] += 1
            self.bad = True
        super().append(ent)


def address_flags(ents: list[dict]) -> list[str]:
    """Flag documents whose ADDRESS spans have no house number (may be a street used as a place: keep trap)."""
    return ["address_without_number"] if any(e["type"] == "ADDRESS" and not re.search(r"\d", e["text"]) for e in ents) else []
