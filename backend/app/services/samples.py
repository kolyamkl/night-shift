"""The invented sample documents shipped with the app, with what each sample card shows."""

import json
import re
from collections import Counter
from pathlib import Path

import pymupdf

from ..core.errors import NotFound
from ..domain.extract import Document, extract_pdf

LABEL_WORDS = {"nda": "NDA", "cv": "CV", "hr": "HR", "gov": "government"}


def label(name: str) -> str:
    words = re.sub(r"^\d+_", "", Path(name).stem).split("_")
    text = " ".join(LABEL_WORDS.get(w, w) for w in words)
    return text[0].upper() + text[1:]


class SampleLibrary:
    def __init__(self, directory: Path):
        self._dir = directory

    def cards(self) -> list[dict]:
        if not self._dir.is_dir():
            return []
        return [self._card(p) for p in sorted(self._dir.glob("*.pdf"))]

    def path(self, name: str) -> Path:
        path = self._dir / name
        if "/" in name or ".." in name or not path.is_file() or path.suffix != ".pdf":
            raise NotFound("No such sample.")
        return path

    def document(self, name: str) -> Document:
        return extract_pdf(self.path(name).read_bytes(), name)

    def thumbnail(self, name: str, width: int) -> bytes:
        page = pymupdf.open(self.path(name))[0]
        zoom = width / page.rect.width
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        pix.gamma_with(0.35)  # darken: at thumbnail size, thin text strokes would otherwise fade to white
        return pix.tobytes("png")

    @staticmethod
    def _card(path: Path) -> dict:
        """The document's own title, its pages and how many personal values it holds."""
        name = label(path.name)
        card = {"name": path.name, "label": name, "title": name, "kind": re.sub(r"^\d+_", "", path.stem),
                "pages": len(pymupdf.open(path)), "values": None, "types": {}}
        gold = path.with_suffix(".gold.json")
        if gold.is_file():
            data = json.loads(gold.read_text())
            card["title"] = data.get("text", "").split("\n", 1)[0].strip() or name
            card["kind"] = data.get("doc_type", card["kind"])
            card["values"] = len(data.get("entities", []))
            card["types"] = dict(Counter(e["type"] for e in data.get("entities", [])))
        return card
