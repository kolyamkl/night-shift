import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "training" / "rewrite"))
sys.path.insert(0, str(ROOT / "backend"))

FIXTURES = ROOT / "data" / "fixtures"


def read_docs() -> list[dict]:
    docs = []
    for path in sorted((FIXTURES / "docs").glob("*.jsonl")):
        docs.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return docs


def write_docs(dir_: Path, docs: list[dict], name: str = "docs") -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / f"{name}.jsonl").write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in docs), encoding="utf-8")
    return dir_


def make_doc(text: str, marks: list[tuple[str, str, str]], **fields) -> dict:
    """A schema document; marks are (value, type, entity_id), located left to right in text."""
    entities, pos = [], 0
    for value, etype, eid in marks:
        start = text.index(value, pos)
        entities.append({"start": start, "end": start + len(value), "type": etype, "value": value, "entity_id": eid})
        pos = start + len(value)
    doc = {
        "doc_id": "contracts-C1-f1",
        "source_id": "C1",
        "group": "contracts",
        "subtype": "tenancy",
        "split": "train",
        "fill": 1,
        "text": text,
        "entities": entities,
        "provenance": {"url": "https://example.org/source", "licence": "OGL-UK-3.0", "kind": "template"},
    }
    doc.update(fields)
    return doc


@pytest.fixture
def fixture_docs() -> list[dict]:
    return copy.deepcopy(read_docs())
