"""Recover redacted spans from a "rewrite" answer (the teammates' T1 design, backend/app/prompts.py),
so both designs are scored with the same metric.

The answer is the chunk with personal values replaced by [TYPE_N]. We diff the original against the
answer: a stretch of the original that turns into one or more placeholders is a hidden span. Text the
model changed or dropped without a placeholder is counted separately (it is not a hidden value).
"""

import difflib
import re

from .spans import Span

PLACEHOLDER = re.compile(r"\[([A-Z][A-Z_]*?)_(\d+)\]")
_SENT = 0xF0000  # private-use code points stand in for placeholders during the diff


def spans_from_rewrite(original: str, answer: str) -> tuple[list[Span], int]:
    """Return (hidden spans in original coordinates, characters changed outside placeholders)."""
    types: list[str] = []

    def to_sentinel(m: re.Match) -> str:
        types.append(m.group(1))
        return chr(_SENT + len(types) - 1)

    coded = PLACEHOLDER.sub(to_sentinel, answer)
    sm = difflib.SequenceMatcher(None, original, coded, autojunk=False)
    spans: list[Span] = []
    changed = 0
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        new = coded[j1:j2]
        sentinels = [c for c in new if ord(c) >= _SENT]
        if sentinels and i2 > i1:
            seg = original[i1:i2]
            # Trim whitespace the model kept outside the placeholder.
            lead = len(seg) - len(seg.lstrip())
            trail = len(seg) - len(seg.rstrip())
            s, e = i1 + lead, i2 - trail
            if e > s:
                spans.append(Span(s, e, types[ord(sentinels[0]) - _SENT], original[s:e]))
            changed += sum(1 for c in new if ord(c) < _SENT and not c.isspace())
        else:
            changed += max(i2 - i1, j2 - j1)
    return spans, changed
