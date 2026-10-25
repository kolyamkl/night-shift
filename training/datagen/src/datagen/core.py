"""Segment-based document builder.

Documents are assembled from a flat list of *atoms*:

* ``str``      plain text (never labelled)
* ``E``        an entity value; its offsets are recorded when the document is rendered
* ``K``        a keep trap: plain text that must NOT be labelled (amount, ordinary date, ...)
* ``HCStart`` / ``HCEnd``  mark a region as a hard case (address inside a table, ...)

Offsets are computed once, by walking the atoms in order, so labels can never drift.
Nothing is ever searched for or replaced after the text exists.
"""
from __future__ import annotations

import string
from typing import Iterable

ENTITY_TYPES = (
    "PERSON", "ADDRESS", "POSTCODE", "EMAIL", "PHONE", "BANK_ACCOUNT", "SORT_CODE",
    "IBAN", "CARD", "NI_NUMBER", "DOB", "ID_DOC", "CUSTOM",
)
ENTITY_SET = frozenset(ENTITY_TYPES)


class E:
    """An entity value. ``ref`` groups mentions of the same real-world thing (same person)."""

    __slots__ = ("text", "type", "ref", "hard")

    def __init__(self, text: str, type: str, ref: str | None = None, hard: Iterable[str] = ()):
        if type not in ENTITY_SET:
            raise ValueError(f"bad entity type {type!r}")
        self.text = text
        self.type = type
        self.ref = ref
        self.hard = tuple(hard)

    def with_hard(self, *kinds: str) -> "E":
        return E(self.text, self.type, self.ref, self.hard + tuple(kinds))

    def __repr__(self) -> str:  # pragma: no cover
        return f"E({self.text!r}, {self.type})"


class K:
    """Keep trap: text that looks sensitive or entity-like but must stay unlabelled."""

    __slots__ = ("text", "kind")

    def __init__(self, text: str, kind: str):
        self.text = text
        self.kind = kind

    def __repr__(self) -> str:  # pragma: no cover
        return f"K({self.text!r}, {self.kind})"


class HCStart:
    __slots__ = ("kind",)

    def __init__(self, kind: str):
        self.kind = kind


class HCEnd:
    __slots__ = ()


def HC(kind: str, *inner) -> list:
    """Wrap segments in a hard-case region."""
    return [HCStart(kind), *inner, HCEnd()]


Atom = str | E | K | HCStart | HCEnd


def flatten(x, out: list | None = None) -> list:
    if out is None:
        out = []
    if x is None or x == "":
        return out
    if isinstance(x, (str, E, K, HCStart, HCEnd)):
        out.append(x)
    elif isinstance(x, (int, float)):
        out.append(str(x))
    else:  # list / tuple / generator
        for y in x:
            flatten(y, out)
    return out


_FMT_CACHE: dict[str, list[tuple[str, str | None]]] = {}
_formatter = string.Formatter()


def merge_str(atoms: list) -> list:
    """Join adjacent plain-text atoms (so noise passes can see paragraph breaks)."""
    out: list = []
    for a in atoms:
        if isinstance(a, str) and out and isinstance(out[-1], str):
            out[-1] = out[-1] + a
        elif not (isinstance(a, str) and a == ""):
            out.append(a)
    return out


def fmt(template: str, **kw) -> list:
    """Format ``template`` where each ``{field}`` is a str, E, K, HC list or nested list."""
    parsed = _FMT_CACHE.get(template)
    if parsed is None:
        parsed = [(lit, field) for lit, field, _spec, _conv in _formatter.parse(template)]
        _FMT_CACHE[template] = parsed
    out: list = []
    for lit, field in parsed:
        if lit:
            out.append(lit)
        if field is not None:
            flatten(kw[field], out)
    return out


def text_of(x) -> str:
    """Plain text of a segment tree (for length checks inside generators)."""
    parts = []
    for a in flatten(x):
        if isinstance(a, str):
            parts.append(a)
        elif isinstance(a, (E, K)):
            parts.append(a.text)
    return "".join(parts)


def render(atoms: list) -> tuple[str, list[dict], list[dict], list[dict], list]:
    """Join atoms into text and record spans.

    Returns (text, entities, hard_cases, keep_traps, entity_refs).
    """
    parts: list[str] = []
    pos = 0
    ents: list[dict] = []
    refs: list = []
    hard: list[dict] = []
    keep: list[dict] = []
    stack: list[tuple[str, int]] = []
    for a in atoms:
        if isinstance(a, str):
            parts.append(a)
            pos += len(a)
        elif isinstance(a, E):
            t = a.text
            if not t or t != t.strip():
                raise ValueError(f"entity text empty or padded: {t!r} ({a.type})")
            ents.append({"start": pos, "end": pos + len(t), "text": t, "type": a.type})
            refs.append(a.ref)
            for k in a.hard:
                hard.append({"kind": k, "start": pos, "end": pos + len(t)})
            parts.append(t)
            pos += len(t)
        elif isinstance(a, K):
            t = a.text
            if t:
                keep.append({"kind": a.kind, "start": pos, "end": pos + len(t), "text": t})
                parts.append(t)
                pos += len(t)
        elif isinstance(a, HCStart):
            stack.append((a.kind, pos))
        elif isinstance(a, HCEnd):
            kind, s = stack.pop()
            if pos > s:
                hard.append({"kind": kind, "start": s, "end": pos})
        else:  # pragma: no cover
            raise TypeError(type(a))
    if stack:
        raise ValueError("unclosed hard-case region")
    return "".join(parts), ents, hard, keep, refs


class Doc:
    """Mutable builder for one document."""

    def __init__(self, doc_type: str, template_id: str):
        self.doc_type = doc_type
        self.template_id = template_id
        self.atoms: list = []
        self.variant: list[str] = []
        self.meta: dict = {}

    # building -----------------------------------------------------------
    def add(self, *segs) -> "Doc":
        for s in segs:
            flatten(s, self.atoms)
        return self

    def f(self, template: str, **kw) -> "Doc":
        self.atoms.extend(fmt(template, **kw))
        return self

    def ln(self, *segs) -> "Doc":
        self.add(*segs)
        self.atoms.append("\n")
        return self

    def blank(self) -> "Doc":
        self.atoms.append("\n")
        return self

    def v(self, name: str) -> "Doc":
        """Record a variant choice (feeds the template/variant id)."""
        self.variant.append(name)
        return self

    def length(self) -> int:
        return len(text_of(self.atoms))

    @property
    def variant_id(self) -> str:
        return self.template_id + ("|" + ",".join(self.variant) if self.variant else "")
