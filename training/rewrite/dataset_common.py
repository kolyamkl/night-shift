"""Shared constants and helpers for the T1 dataset scripts.

The documents schema is described in data/README.md. Every script in this
folder imports from here, so the schema lives in one place.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Iterable, Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = DATA_DIR / "docs"
CHUNKS_DIR = DATA_DIR / "chunks"
RESULTS_DIR = DATA_DIR / "results"

ENTITY_TYPES = (
    "PERSON",
    "ADDRESS",
    "POSTCODE",
    "EMAIL",
    "PHONE",
    "BANK_ACCOUNT",
    "SORT_CODE",
    "IBAN",
    "CARD",
    "NI_NUMBER",
    "DOB",
    "ID_DOC",
    "CUSTOM",
)
GROUPS = ("contracts", "correspondence", "financial", "insurance")
SPLITS = ("train", "fresh", "eval")
PROVENANCE_KINDS = ("template", "filled_real", "synthetic")

# Filled sources from design section 4. Gretel documents use "gretel-<row id>".
FILLED_SOURCES = (
    tuple(f"C{i}" for i in range(1, 13))
    + tuple(f"R{i}" for i in range(1, 12))
    + ("INS1", "INS2")
)
# Eval holdout by source (design section 5): all fills go to eval, never to train or fresh.
# C6 and C7 (IPO NDAs) were added on 24 Oct because C5 and C10 (SEC EDGAR) could not be fetched.
EVAL_SOURCES = frozenset({"C2", "C5", "C6", "C7", "C10", "R5", "R7", "R9"})
GRETEL_PREFIX = "gretel-"

# Default chunk limit in estimated tokens (design section 3, decision 6).
MAX_CHUNK_TOKENS = 1000

# Token estimator: characters / 3.5, rounded up. Claude's tokenizer averages
# about 4 characters per token on English prose, so dividing by 3.5 over-counts
# ordinary text by roughly 15%, which keeps chunks under the real limit. Text
# dense in digits and symbols (IBANs, phone numbers) tokenises worse, which is
# why the margin matters. No API is called.
CHARS_PER_TOKEN = 3.5


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def expected_group(source_id: str) -> tuple[str, ...]:
    """Groups a source may belong to."""
    if source_id.startswith("C"):
        return ("contracts",)
    if source_id.startswith("R"):
        return ("correspondence",)
    if source_id.startswith("INS"):
        return ("insurance",)
    return ("financial", "insurance")


def is_gretel(source_id: str) -> bool:
    return source_id.startswith(GRETEL_PREFIX) and len(source_id) > len(GRETEL_PREFIX)


def expected_split(source_id: str, fill: int) -> str | None:
    """Split required by the design for a filled source, or None for Gretel."""
    if is_gretel(source_id):
        return None
    if source_id in EVAL_SOURCES:
        return "eval"
    return "train" if fill <= 3 else "fresh"


# Placeholders. The canonical form is [TYPE_N]. PLACEHOLDER_RE also accepts the
# small variations a model may produce ([PERSON 1], [Person_1], [BANK ACCOUNT 1],
# [PERSON]); normalise_placeholder decides whether a match counts.
CANONICAL_PLACEHOLDER_RE = re.compile(r"\[(" + "|".join(ENTITY_TYPES) + r")_(\d+)\]")
PLACEHOLDER_RE = re.compile(r"\[\s*([A-Za-z]+(?:[ _-]+[A-Za-z]+)*)(?:[ _-]*#?(\d+))?\s*\]")


def normalise_placeholder(name: str, number: str | None) -> str | None:
    """Return the entity type a bracketed token stands for, or None if it is not a placeholder.

    Known types are accepted in any case and with spaces or hyphens instead of
    underscores. An unknown name counts only when written in capitals with a
    number, like [NAME_1]; it is returned as "OTHER:NAME".
    """
    norm = re.sub(r"[ _-]+", "_", name.strip()).upper()
    if norm in ENTITY_TYPES:
        return norm
    if number is not None and name == name.upper():
        return f"OTHER:{norm}"
    return None


def placeholder(entity_type: str, number: int) -> str:
    return f"[{entity_type}_{number}]"


def read_jsonl(path: Path) -> Iterator[tuple[int, object]]:
    """Yield (line number, parsed object) for each non-empty line. Raises ValueError on bad JSON."""
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                yield lineno, json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {e}") from e


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return n


def load_docs(docs_dir: Path) -> list[dict]:
    """Load every document from <docs_dir>/*.jsonl, in file then line order."""
    docs = []
    for path in sorted(docs_dir.glob("*.jsonl")):
        for _, obj in read_jsonl(path):
            docs.append(obj)
    return docs


def format_table(headers: list[str], rows: list[list[object]]) -> str:
    cells = [headers] + [[str(c) for c in row] for row in rows]
    widths = [max(len(r[i]) for r in cells) for i in range(len(headers))]
    lines = []
    for idx, row in enumerate(cells):
        lines.append("  ".join(c.rjust(w) if i else c.ljust(w) for i, (c, w) in enumerate(zip(row, widths))))
        if idx == 0:
            lines.append("  ".join("-" * w for w in widths))
    return "\n".join(lines)
