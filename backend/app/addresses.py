"""Widen an ADDRESS span to the whole postal address around it.

T1 often hides only the street: "Flat 2714, Halcyon Tower, [ADDRESS_1], London, [POSTCODE_1]", though its
prompt counts the flat, the building, the town and the county as part of the address. So after the
spans are merged, each ADDRESS span takes in its neighbours, segment by segment (a segment ends at a
comma or a line break, never at a blank line):
- before it, a flat or unit ("Flat 2714", "Level 12", "2nd Floor") or a building name that ends in a
  building word ("Halcyon Tower", "Halden House");
- after it, a town or county ("London", "Newcastle upon Tyne", "LONDON"), but only when a POSTCODE or
  another ADDRESS span follows, so "Ms Smith, 4 Oak Road, Landlord" keeps "Landlord" visible.
The postcode keeps its own span.

When T1 hid nothing of an address but the regex layer found its postcode, the segments before the
postcode become an ADDRESS span if they read as one: towns, then a street with a house number
("98 Mill Close"), then flats and buildings. Without a street nothing is hidden, so "Registered
office: London EC1A 1BB" keeps "London". A company name ("Energy Marketing, Inc.") stops every walk.
"""

import re

from evalkit.spans import Span

MAX_SEGMENTS = 3
UNIT = re.compile(
    r"(?i:flat|apartment|apt\.?|unit|suite|room|studio|maisonette|penthouse|block|level)\s+[A-Za-z0-9][\w/-]*"
    r"|(?i:ground|lower\s+ground|basement|\d+(?:st|nd|rd|th))\s+(?i:floor)"
)
BUILDING = re.compile(
    r"(?:[A-Z][\w'’&.-]*\s+){0,4}"
    r"(?:Tower|House|Court|Building|Buildings|Lodge|Mansions|Hall|Point|Heights|Wharf|Quay|Mill|Gardens|Square"
    r"|Terrace|Cottage|Cottages|Villas|Apartments|Residence|Residences|Centre|Chambers|Manor|Barn|Farm|Works"
    r"|Yard|Place|Close|Mews)"
)
STREET = re.compile(r"\d+[A-Za-z]?(?:-\d+[A-Za-z]?)?\s+[A-Z][\w'’.-]*(?:\s+[A-Z][\w'’.-]*){0,4}")
# The same after a label or a lower-case word: "Relating to: Flat 2714", "address Rose Court".
_AFTER_LABEL = r"(?:[:;]|\b[a-z]+)\s+"
LABELLED_PART = re.compile(_AFTER_LABEL + "(" + UNIT.pattern + "|" + BUILDING.pattern + r")$")
LABELLED_STREET = re.compile(_AFTER_LABEL + "(" + STREET.pattern + r")$")
COMPANY = re.compile(r"(?i)\b(?:inc|ltd|limited|llp|llc|plc|corp|corporation|company|co)\b\.?")
TOWN_WORD = r"(?:[A-Z][A-Za-z'’.&-]*)"
TOWN = re.compile(TOWN_WORD + r"(?:\s+(?:" + TOWN_WORD + r"|upon|on|in|le|under|by|the))*")
SEPARATOR = re.compile(r"\s*,\s*|[ \t]*\n[ \t]*")


def _block(text: str, lo: int, start: int) -> int:
    """Where the text before start begins, from lo but never across a blank line."""
    cut = text.rfind("\n\n", lo, start)
    return cut + 2 if cut >= 0 else lo


def _segments(text: str, lo: int, hi: int) -> list[tuple[int, int]]:
    """(start, end) in text of each segment of text[lo:hi], split at commas and single line breaks,
    without the spaces around it."""
    out, pos = [], lo
    for m in SEPARATOR.finditer(text, lo, hi):
        out.append((pos, m.start()))
        pos = m.end()
    out.append((pos, hi))
    trimmed = []
    for s, e in out:
        seg = text[s:e]
        if seg.strip():
            trimmed.append((s + len(seg) - len(seg.lstrip()), e - len(seg) + len(seg.rstrip())))
    return trimmed


def _is_town(segment: str) -> bool:
    return (len(segment) <= 40 and len(segment.split()) <= 4 and bool(TOWN.fullmatch(segment))
            and not COMPANY.search(segment))


def _left(text: str, lo: int, start: int) -> int:
    """The new start of an ADDRESS span: take in flat, unit and building segments just before it."""
    base = _block(text, lo, start)
    before = text[base:start].rstrip(" \t")
    if before and before[-1] not in ",\n":
        return start  # the span does not start a segment, as in "Property: 4 Oak Road"
    new = start
    for s, e in reversed(_segments(text, base, start)[-MAX_SEGMENTS:]):
        seg = text[s:e]
        if UNIT.fullmatch(seg) or BUILDING.fullmatch(seg):
            new = s
            continue
        labelled = LABELLED_PART.search(seg)  # "Relating to: Flat 2714": the label stays visible
        if labelled:
            new = s + labelled.start(1)
        break
    return new


def _right(text: str, end: int, hi: int) -> int:
    """The new end of an ADDRESS span: take in town segments between it and the next span at hi."""
    if "\n\n" in text[end:hi]:
        return end
    segs = _segments(text, end, hi)
    if not segs or len(segs) > MAX_SEGMENTS or not all(_is_town(text[s:e]) for s, e in segs):
        return end
    return segs[-1][1]


def _before_postcode(text: str, lo: int, start: int) -> tuple[int, int] | None:
    """An address T1 missed, read back from its postcode at start: (start, end) of towns, a street, then
    flats and buildings; None unless a street is among them."""
    base = _block(text, lo, start)
    picked: list[tuple[int, int]] = []
    street = False
    for s, e in reversed(_segments(text, base, start)[-5:]):
        seg = text[s:e]
        if COMPANY.search(seg):
            break
        if not street and _is_town(seg):
            picked.append((s, e))
            continue
        if not street and STREET.fullmatch(seg):
            street = True
            picked.append((s, e))
            continue
        if street and (UNIT.fullmatch(seg) or BUILDING.fullmatch(seg)):
            picked.append((s, e))
            continue
        labelled = (LABELLED_PART if street else LABELLED_STREET).search(seg)
        if labelled:
            street = True
            picked.append((s + labelled.start(1), e))
        break
    return (picked[-1][0], picked[0][1]) if street else None


def expand(text: str, spans: list[Span]) -> list[Span]:
    """Spans sorted and not overlapping, as pipeline._merge returns them; ADDRESS spans are widened and
    an address found only by its postcode gets an ADDRESS span."""
    out: list[Span] = []
    for i, sp in enumerate(spans):
        lo = out[-1].end if out else 0
        if sp.type == "POSTCODE":
            follows_address = out and out[-1].type == "ADDRESS" and not text[lo:sp.start].strip(" ,\n\t")
            found = None if follows_address else _before_postcode(text, lo, sp.start)
            if found:
                out.append(Span(found[0], found[1], "ADDRESS", text[found[0]:found[1]]))
            out.append(sp)
            continue
        if sp.type != "ADDRESS":
            out.append(sp)
            continue
        start = _left(text, lo, sp.start)
        end = sp.end
        if i + 1 < len(spans) and spans[i + 1].type in ("POSTCODE", "ADDRESS"):
            end = _right(text, sp.end, spans[i + 1].start)
        out.append(Span(start, end, "ADDRESS", text[start:end]) if (start, end) != (sp.start, sp.end) else sp)
    return out
