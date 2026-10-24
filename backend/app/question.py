"""The user's question goes to the AI provider pseudonymised, like the document.

Before T2 sees a question:
- every value the document's vault holds becomes its placeholder, matched with any case and spacing
  ("When can daryna  shevchenko leave?" -> "When can [PERSON_1] leave?");
- a part of a known person's name does too ("Daryna" -> [PERSON_1]) when it is written with a capital
  letter or is six letters or longer, so a lower-case "grant" is not taken for Mr Grant (a capital "Will"
  at the start of a sentence is hidden when someone in the document is called Will, to be safe); a part
  shared by two people
  ("Wierzbicki" for two family members) gets a placeholder of its own, so it is hidden without
  pointing at either of them;
- values the regex layer finds in the question (an email, a phone number, a client reference) get new
  placeholders.
This works on a copy of the vault, so the stored result never changes; the answer is restored with that
copy, so the new placeholders come back as the values the user typed.

Answers are shown as plain text, so Markdown emphasis and headings are taken out of them.
"""

import copy
import re

from evalkit.redact import Vault
from evalkit.spans import Span

from .pipeline import _merge, _regex

TITLES = {"mr", "mrs", "ms", "miss", "mx", "dr", "prof", "sir", "dame", "rev", "lord", "lady"}
NAME_PART = re.compile(r"[^\W\d_][\w'’-]*")
_BOLD = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", re.S)
_EMPHASIS = re.compile(r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])")
_HEADING = re.compile(r"^[ \t]*#{1,6}[ \t]+", re.M)
_BULLET = re.compile(r"^([ \t]*)[*+][ \t]+", re.M)


def _pattern(value: str) -> re.Pattern | None:
    """Any case, any run of spaces or commas between the words, not inside a longer word or number."""
    parts = [re.escape(p) for p in re.split(r"[\s,]+", value) if p]
    if not parts:
        return None
    return re.compile(r"(?<!\w)" + r"[\s,]+".join(parts) + r"(?!\w)", re.IGNORECASE)


def _known(question: str, vault: Vault) -> list[tuple[int, int, str]]:
    """(start, end, placeholder) for every known value and every unambiguous part of a known name."""
    hits: list[tuple[int, int, str]] = []
    parts: dict[str, set[str]] = {}
    for placeholder, value in vault.by_placeholder.items():
        pattern = _pattern(value)
        if pattern:
            hits += [(m.start(), m.end(), placeholder) for m in pattern.finditer(question)]
        if placeholder.startswith("[PERSON_"):
            for token in NAME_PART.findall(value):
                for part in {token, *token.replace("’", "-").split("-")}:
                    if len(part) >= 3 and part.casefold() not in TITLES:
                        parts.setdefault(part.casefold(), set()).add(placeholder)
    for part, owners in parts.items():
        pattern = _pattern(part)
        for m in pattern.finditer(question):
            if not (m.group()[0].isupper() or len(part) >= 6):
                continue
            owner = next(iter(owners)) if len(owners) == 1 else None
            hits.append((m.start(), m.end(), owner or vault.placeholder_for(m.group(), "PERSON")))
    return hits


def pseudonymise(question: str, vault: Vault) -> tuple[str, Vault]:
    """The question as the AI provider may see it, and the vault copy to restore its answer with."""
    local = copy.deepcopy(vault)
    hits = _known(question, local)
    # Longer hits win: "Daryna Shevchenko" over "Daryna"; then the regex layer fills the gaps.
    spans = [Span(s, e, ph, question[s:e]) for s, e, ph in hits]
    for sp in _regex(question):
        if not any(sp.start < e and s < sp.end for s, e, _ in hits):
            spans.append(Span(sp.start, sp.end, "NEW:" + sp.type, sp.text))
    out, pos = [], 0
    for sp in _merge(spans, question):
        out.append(question[pos:sp.start])
        if sp.type.startswith("NEW:"):
            out.append(local.placeholder_for(sp.text, sp.type[4:]))
        elif sp.type.startswith("["):
            out.append(sp.type)
        else:  # a merge of a known hit and a regex hit: hide the whole stretch as one new value
            out.append(local.placeholder_for(sp.text, "CUSTOM"))
        pos = sp.end
    out.append(question[pos:])
    return "".join(out), local


def plain(answer: str) -> str:
    """The answer without Markdown emphasis, headings or star bullets ("**£373.47**" -> "£373.47")."""
    answer = _BOLD.sub(r"\2", answer)
    answer = _EMPHASIS.sub(r"\1", answer)
    answer = _HEADING.sub("", answer)
    return _BULLET.sub(r"\1- ", answer)
