"""Turn a T1 "rewrite" answer (the chunk with placeholders) back into the values it hid."""

import re

from evalkit.rewrite import PLACEHOLDER, spans_from_rewrite
from evalkit.spans import Span

# What a hidden value of a type may look like inside one line. A rewrite answer is matched line by
# line as a template; these settle where two neighbouring placeholders split, as in "[ADDRESS_1] [POSTCODE_1]".
_VALUE_PATTERNS = {
    "PERSON": r"[^\d@\n]+?",
    "POSTCODE": r"[A-Za-z0-9]{2,5}(?:[ -][A-Za-z0-9]{2,4})?",
    "EMAIL": r"[^\s@]+@[^\s@]+",
    "PHONE": r"\+?[\d(][\d\s().-]*\d",
    "SORT_CODE": r"\d{2}[- ]?\d{2}[- ]?\d{2}",
}
_ANY_VALUE = r"[^\n]+?"
_TITLES = r"(?:Mr|Mrs|Ms|Miss|Mx|Dr|Prof|Sir|Dame|Rev)\.?"
_TITLE = re.compile(rf"^{_TITLES}\s+(?=\S)", re.IGNORECASE)
_TITLE_ONLY = re.compile(_TITLES, re.IGNORECASE)


def _literal(text: str) -> str:
    return r"\s+".join(re.escape(part) for part in re.split(r"\s+", text))


def _lines(text: str) -> list[tuple[int, str]]:
    """(offset, line) for each line, leaving out blank lines at either end."""
    out, pos = [], 0
    for line in text.split("\n"):
        out.append((pos, line))
        pos += len(line) + 1
    while out and not out[-1][1].strip():
        out.pop()
    while out and not out[0][1].strip():
        out.pop(0)
    return out


def _match_line(line: str, answer: str) -> list[tuple[int, int, str]] | None:
    """Hidden (start, end, type) in one line if the answer line is that line with placeholders, else None."""
    literals, types, pos = [], [], 0
    for m in PLACEHOLDER.finditer(answer):
        literals.append(answer[pos:m.start()])
        types.append(m.group(1))
        pos = m.end()
    literals.append(answer[pos:])
    literals[0], literals[-1] = literals[0].lstrip(), literals[-1].rstrip()
    # Placeholders split only by spaces or punctuation are where the template search branches; many
    # of them on one line could make it very slow, so such a line goes to the diff instead.
    if sum(1 for lit in literals[1:-1] if not any(c.isalnum() for c in lit)) > 2:
        return None
    pattern = r"\s*" + _literal(literals[0])
    for etype, lit in zip(types, literals[1:]):
        pattern += f"({_VALUE_PATTERNS.get(etype, _ANY_VALUE)})" + _literal(lit)
    m = re.fullmatch(pattern + r"\s*", line)
    if not m:
        return None
    found = []
    for i, etype in enumerate(types, 1):
        value = m.group(i)
        start = m.start(i) + len(value) - len(value.lstrip())
        found.append((start, start + len(value.strip()), etype))
    return found


def align_rewrite(chunk: str, answer: str) -> tuple[list[Span], int]:
    """Hidden spans in the chunk and the characters changed outside placeholders.

    The chunk is sent stripped, as in the training data, so the answer is aligned against chunk.strip();
    the spans keep offsets into the chunk. The rewrite prompt keeps line breaks and never lets a value
    cross one, so lines are matched as templates one by one; a line that does not fit, or an answer with
    a different number of lines, falls back to evalkit's diff."""
    sent = chunk.strip()
    lead = len(chunk) - len(chunk.lstrip())
    lines, answers = _lines(sent), _lines(answer)
    if len(lines) != len(answers):
        spans, changed = spans_from_rewrite(sent, answer)
        return [Span(sp.start + lead, sp.end + lead, sp.type, sp.text) for sp in spans], changed
    spans = []
    changed = 0
    for (offset, line), (_, ans) in zip(lines, answers):
        found = _match_line(line, ans)
        if found is None:
            line_spans, line_changed = spans_from_rewrite(line, ans)
            found = [(sp.start, sp.end, sp.type) for sp in line_spans]
            changed += line_changed
        spans += [Span(lead + offset + s, lead + offset + e, t, line[s:e]) for s, e, t in found]
    return spans, changed


def rewrite_values(chunk: str, answer: str) -> list[dict] | None:
    """Distinct values from a rewrite answer, or None when the answer does not line up with the chunk
    (more than a little text changed outside the placeholders, such as a summary or a refusal).

    Every value is later hidden everywhere in the document, so tiny ones are dropped: fewer than two
    letters or digits, or a PERSON that is only a title (a misaligned diff can turn "Mr" into a value).
    A title before a name stays visible, as in the evalkit prompt, so "Mr Raj Patel" and a later
    "Raj Patel" share one placeholder."""
    spans, changed = align_rewrite(chunk, answer)
    if changed > max(30, len(chunk.strip()) // 20):
        return None
    values: dict[str, str] = {}
    for sp in spans:
        value = _TITLE.sub("", sp.text) if sp.type == "PERSON" else sp.text
        if sum(c.isalnum() for c in value) < 2 or (sp.type == "PERSON" and _TITLE_ONLY.fullmatch(value)):
            continue
        values.setdefault(value, sp.type)
    return [{"text": v, "type": t} for v, t in values.items()]
