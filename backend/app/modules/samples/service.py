"""Synthetic sample documents to try the app with: the PDFs in VEIL_SAMPLES_DIR (data/synthetic/pdfs),
each optionally with a .gold.json beside it that names its title and its personal values."""

import json
import re
from collections import Counter
from pathlib import Path

import pymupdf

from app.core.errors import NotFoundError
from app.modules.samples.schemas import SampleCard
from app.redaction.document import Document, extract_pdf

LABEL_WORDS = {"nda": "NDA", "cv": "CV", "hr": "HR", "gov": "government"}
THUMB_GAMMA = 0.35  # darken: at thumbnail size, thin text strokes would otherwise fade to white


def label(name: str) -> str:
    words = re.sub(r"^\d+_", "", Path(name).stem).split("_")
    text = " ".join(LABEL_WORDS.get(w, w) for w in words)
    return text[0].upper() + text[1:]


class SampleService:
    def __init__(self, samples_dir: Path) -> None:
        self.dir = samples_dir

    def cards(self) -> list[SampleCard]:
        if not self.dir.is_dir():
            return []
        return [self._card(p) for p in sorted(self.dir.glob("*.pdf"))]

    def thumbnail(self, name: str, width: int) -> bytes:
        page = pymupdf.open(self._path(name))[0]
        zoom = width / page.rect.width
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        pix.gamma_with(THUMB_GAMMA)
        return pix.tobytes("png")

    def document(self, name: str) -> Document:
        return extract_pdf(self._path(name).read_bytes(), name)

    def _path(self, name: str) -> Path:
        path = self.dir / name
        if "/" in name or ".." in name or not path.is_file() or path.suffix != ".pdf":
            raise NotFoundError("No such sample.")
        return path

    @staticmethod
    def _card(path: Path) -> SampleCard:
        name = label(path.name)
        card = SampleCard(
            name=path.name,
            label=name,
            title=name,
            kind=re.sub(r"^\d+_", "", path.stem),
            pages=len(pymupdf.open(path)),
            values=None,
            types={},
        )
        gold = path.with_suffix(".gold.json")
        if gold.is_file():
            data = json.loads(gold.read_text())
            entities = data.get("entities", [])
            card.title = data.get("text", "").split("\n", 1)[0].strip() or name
            card.kind = data.get("doc_type", card.kind)
            card.values = len(entities)
            card.types = dict(Counter(e["type"] for e in entities))
        return card
