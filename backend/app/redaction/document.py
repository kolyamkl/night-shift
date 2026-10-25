"""Turn an upload into one text string plus, for PDFs, where every word sits on the page.

The text is what T1 sees. Each Word keeps its character range in that text and its box on the
page, so a redacted character range maps straight back to rectangles on the PDF.
"""

import uuid
from dataclasses import dataclass, field

import pymupdf


@dataclass
class Word:
    text: str
    page: int
    bbox: tuple[float, float, float, float]  # PDF points: x0, y0, x1, y1
    start: int  # character range in Document.text
    end: int
    line: tuple[int, int, int]  # (page, block, line): words on one line share it


@dataclass
class Document:
    doc_id: str
    kind: str  # "text" | "pdf"
    filename: str
    text: str
    words: list[Word] = field(default_factory=list)
    pages: list[tuple[float, float]] = field(default_factory=list)  # page width, height in points
    source: bytes | None = None


def _new_id() -> str:
    return uuid.uuid4().hex


def extract_text(text: str, filename: str = "pasted.txt") -> Document:
    return Document(doc_id=_new_id(), kind="text", filename=filename, text=text)


def extract_pdf(data: bytes, filename: str) -> Document:
    """Words in reading order: a space within a line, a newline between lines, a blank line
    between blocks and pages."""
    pdf = pymupdf.open(stream=data, filetype="pdf")
    parts: list[str] = []
    words: list[Word] = []
    pages: list[tuple[float, float]] = []
    pos = 0
    prev_line: tuple[int, int, int] | None = None

    for pno, page in enumerate(pdf):
        pages.append((page.rect.width, page.rect.height))
        for x0, y0, x1, y1, text, block, line, _ in sorted(page.get_text("words"), key=lambda w: (w[5], w[6], w[7])):
            key = (pno, block, line)
            if prev_line is not None:
                if key[:2] != prev_line[:2]:
                    sep = "\n\n"  # new block or new page
                elif key != prev_line:
                    sep = "\n"
                else:
                    sep = " "
                parts.append(sep)
                pos += len(sep)
            words.append(Word(text, pno, (x0, y0, x1, y1), pos, pos + len(text), key))
            parts.append(text)
            pos += len(text)
            prev_line = key
    return Document(
        doc_id=_new_id(), kind="pdf", filename=filename, text="".join(parts), words=words, pages=pages, source=data
    )
