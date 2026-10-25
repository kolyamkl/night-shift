"""Consistent placeholders and restoration (team pack FR-5, FR-7).

The same real value always gets the same placeholder within a conversation: [PERSON_1], [ACCOUNT_1].
The vault stays in our backend; only placeholders go to the provider.
"""

import re
from dataclasses import dataclass, field

from .spans import Span

# Shorter labels read better in an LLM answer than the internal type names.
PLACEHOLDER_LABEL = {
    "BANK_ACCOUNT": "ACCOUNT",
    "NI_NUMBER": "NI",
    "ID_DOC": "ID",
}


def _key(value: str) -> str:
    return " ".join(value.split()).casefold()


@dataclass
class Vault:
    by_key: dict[str, str] = field(default_factory=dict)  # normalised value -> placeholder
    by_placeholder: dict[str, str] = field(default_factory=dict)  # placeholder -> original value
    counters: dict[str, int] = field(default_factory=dict)

    def placeholder_for(self, value: str, etype: str) -> str:
        key = _key(value)
        if key in self.by_key:
            return self.by_key[key]
        label = PLACEHOLDER_LABEL.get(etype, etype)
        self.counters[label] = self.counters.get(label, 0) + 1
        ph = f"[{label}_{self.counters[label]}]"
        self.by_key[key] = ph
        self.by_placeholder[ph] = value
        return ph


def apply(text: str, spans: list[Span], vault: Vault) -> str:
    """Replace spans (non-overlapping, any order) with placeholders from the vault."""
    out: list[str] = []
    pos = 0
    for sp in sorted(spans, key=lambda s: s.start):
        out.append(text[pos:sp.start])
        out.append(vault.placeholder_for(sp.text, sp.type))
        pos = sp.end
    out.append(text[pos:])
    return "".join(out)


_TOLERANT = re.compile(r"\[?\b([A-Z][A-Z_]*?)[ _](\d+)\b\]?", re.I)


def restore(answer: str, vault: Vault) -> tuple[str, list[str]]:
    """Put real values back. Returns (restored text, placeholders we could not resolve).

    Exact placeholders first; then tolerant forms the model may write ("PERSON 1", "person_1").
    Unknown placeholders are reported, never guessed.
    """
    for ph, value in vault.by_placeholder.items():
        answer = answer.replace(ph, value)
    unknown: list[str] = []

    def _sub(m: re.Match) -> str:
        ph = f"[{m.group(1).upper()}_{m.group(2)}]"
        if ph in vault.by_placeholder:
            return vault.by_placeholder[ph]
        if m.group(0).startswith("[") or "_" in m.group(0):
            unknown.append(m.group(0))
        return m.group(0)

    labels = {ph[1:].rsplit("_", 1)[0] for ph in vault.by_placeholder}
    if labels:
        answer = _TOLERANT.sub(lambda m: _sub(m) if m.group(1).upper() in labels else m.group(0), answer)
    # Any bracketed placeholder still left (for example a type that is not in this vault).
    for leftover in re.findall(r"\[[A-Z][A-Z_]*_\d+\]", answer):
        if leftover not in unknown:
            unknown.append(leftover)
    return answer, unknown
