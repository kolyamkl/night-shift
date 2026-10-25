"""Noise applied to atoms *before* rendering, so offsets stay exact.

* typos / casing for chat-like text
* PDF-like artefacts: page headers/footers, hyphenation across lines, double spaces,
  column breaks (a sidebar block dropped into the middle of a paragraph).
"""
from __future__ import annotations

import random
import re

from .core import E, HCEnd, HCStart, K, flatten, merge_str

_KEYB = {"a": "qs", "s": "ad", "e": "wr", "i": "uo", "o": "ip", "n": "bm", "t": "ry", "r": "et", "l": "k",
         "h": "gj", "d": "sf", "m": "n", "u": "yi", "c": "xv", "g": "fh", "y": "tu", "p": "o", "b": "vn"}
_WORD = re.compile(r"[A-Za-z]{4,}")


def _typo_word(rng: random.Random, w: str) -> str:
    i = rng.randrange(1, len(w) - 1)
    op = rng.randrange(4)
    if op == 0:
        return w[:i] + w[i + 1] + w[i] + w[i + 2:]
    if op == 1:
        return w[:i] + w[i + 1:]
    if op == 2:
        return w[:i] + w[i] + w[i:]
    c = w[i].lower()
    return w[:i] + rng.choice(_KEYB.get(c, c)) + w[i + 1:]


def typos(atoms: list, rng: random.Random, rate: float = 0.04) -> list:
    out = []
    for a in atoms:
        if isinstance(a, str) and len(a) > 3:
            a = _WORD.sub(lambda m: _typo_word(rng, m.group()) if rng.random() < rate else m.group(), a)
        out.append(a)
    return out


def lower_all(atoms: list, include_entities: bool = True) -> list:
    """Lower-case everything (chat style). Entity texts are lower-cased too; spans stay exact."""
    out = []
    for a in atoms:
        if isinstance(a, str):
            out.append(a.lower())
        elif isinstance(a, K):
            out.append(K(a.text.lower(), a.kind))
        elif isinstance(a, E) and include_entities and a.type in ("PERSON", "ADDRESS", "POSTCODE", "EMAIL"):
            out.append(E(a.text.lower(), a.type, a.ref, a.hard + ("lowercase_entity",)))
        else:
            out.append(a)
    return out


def double_spaces(atoms: list, rng: random.Random, rate: float = 0.03) -> list:
    out = []
    for a in merge_str(atoms):
        if isinstance(a, str) and " " in a:
            b = re.sub(r"(?<=\S) (?=\S)", lambda m: "  " if rng.random() < rate else " ", a)
            if b != a:
                out.extend([HCStart("pdf_double_space"), b, HCEnd()])
                continue
        out.append(a)
    return out


def hyphenate(atoms: list, rng: random.Random, rate: float = 0.25) -> list:
    """Break one long word per plain segment across a line with a hyphen (PDF line wrap)."""
    out = []
    for a in merge_str(atoms):
        if isinstance(a, str) and len(a) > 60 and rng.random() < rate:
            words = [m for m in re.finditer(r"[a-z]{9,}", a)]
            if words:
                m = rng.choice(words)
                w = m.group()
                cut = rng.randint(3, len(w) - 4)
                out.append(a[: m.start()])
                out.extend([HCStart("pdf_hyphenation"), w[:cut] + "-\n" + w[cut:], HCEnd()])
                out.append(a[m.end():])
                continue
        out.append(a)
    return out


def page_breaks(atoms: list, rng: random.Random, header_fn, footer_fn, every: int = 2600) -> list:
    """Insert page footer/header blocks at paragraph boundaries roughly every ``every`` chars.

    ``header_fn(page, total)`` and ``footer_fn(page, total)`` return segment lists (may contain E,
    e.g. the tenant's name in a running header: a hard case)."""
    atoms = merge_str(atoms)
    # pass 1: find split points (atom index, char offset within atom)
    pos = 0
    nxt = every
    splits = []
    for i, a in enumerate(atoms):
        if isinstance(a, str):
            j = 0
            while pos + len(a) > nxt:
                k = a.find("\n\n", max(j, nxt - pos))
                if k == -1:
                    break
                splits.append((i, k))
                j = k + 2
                nxt = pos + k + every
            pos += len(a)
        elif isinstance(a, (E, K)):
            pos += len(a.text)
    if not splits:
        return atoms
    total = len(splits) + 1
    out = []
    by_atom: dict[int, list[int]] = {}
    for i, k in splits:
        by_atom.setdefault(i, []).append(k)
    page = 1
    for i, a in enumerate(atoms):
        if i not in by_atom:
            out.append(a)
            continue
        last = 0
        for k in by_atom[i]:
            out.append(a[last:k])
            out.append("\n\n")
            out.append(HCStart("pdf_header_footer"))
            flatten(footer_fn(page, total), out)
            page += 1
            out.append("\n\n")
            flatten(header_fn(page, total), out)
            out.append(HCEnd())
            last = k
        out.append(a[last:])
    return [x for x in out if not (isinstance(x, str) and x == "")]


def column_break(atoms: list, rng: random.Random, sidebar) -> list:
    """Drop a sidebar block into the middle of one long paragraph (two-column PDF extraction)."""
    atoms = merge_str(atoms)
    cands = [i for i, a in enumerate(atoms) if isinstance(a, str) and len(a) > 160 and ". " in a]
    if not cands:
        return atoms
    i = rng.choice(cands)
    a = atoms[i]
    spaces = [m.start() for m in re.finditer(r"(?<=[a-z,]) (?=[a-z])", a)]
    if not spaces:
        return atoms
    k = rng.choice(spaces)
    block = [a[:k], "\n\n", HCStart("pdf_column_break"), *flatten(sidebar), HCEnd(), "\n\n", a[k + 1:]]
    return atoms[:i] + block + atoms[i + 1:]
