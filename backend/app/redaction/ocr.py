"""Photos and scanned PDFs as PDF Documents with a box for every word.

app.ingest reads each page with Apple Vision into text lines, one box per line. Here each line is
split into words, each word gets a box from its characters' place in the line, and the boxes are
mapped onto the page as stored in the PDF. Images first become a PDF (one page per image or TIFF
frame), so photos and scans get black boxes in review and a truly redacted PDF download, the same
as PDFs with a text layer.

Frames. ingest's line boxes are fractions (0 to 1, origin at the top left) of the last image it
read for that page: the page as shown (photos with their EXIF orientation applied; PDF pages as
pdfium renders them, with /Rotate and the CropBox applied), turned counterclockwise by
Page.rotation degrees with the canvas grown to fit (PIL rotate with expand=True). Page.rotation
covers both a deskew of a few degrees and a page read on its side or upside down (90, 180, 270).
Word.bbox is in PDF points in PyMuPDF's unrotated page frame, the frame page.get_text("words") and
add_redact_annot use, as in document.py. Text-layer pages of a mixed PDF (some pages scanned) have
boxes in another frame; see _from_text_layer.
"""

from __future__ import annotations

import io
import logging
import math
import re
from collections.abc import Callable
from dataclasses import replace
from difflib import SequenceMatcher
from itertools import accumulate
from typing import Any

import pymupdf
import pypdfium2 as pdfium
from PIL import ExifTags, Image, ImageOps

from app import ingest
from app.ingest.extract import page_frames
from app.ingest.layout import assemble, group_rows
from app.redaction.document import Document, Word, extract_text

log = logging.getLogger("veil.ocr")

PAD_CHARS = 1.5  # word boxes grow by this many average character widths each side, within the line box
PHOTO_SIDE = 842.0  # points (A4's long side): the page size of a photo, whose dpi says nothing about paper
MAX_SCAN_SIDE = 1200.0  # points; a page longer than this at the image's dpi is a photo, not a scan
MAX_PIXELS = 3000  # long side of the stored image; OCR has already read the full-size one
LOSSY = {"JPEG", "MPO", "HEIF", "HEIC", "AVIF", "WEBP"}  # stored as JPEG; anything else as PNG

# Helvetica advance widths (1/1000 em) for ASCII 32 to 126. A word's place in its line is estimated
# twice, from these widths and from plain character counts, and its box covers both: on test renders
# the widths are within 1.3 characters for proportional fonts (counts alone were up to 3 off), and
# counts are exact for monospaced ones.
HELVETICA = (
    278,
    278,
    355,
    556,
    556,
    889,
    667,
    191,
    333,
    333,
    389,
    584,
    278,
    333,
    278,
    278,  # space to /
    556,
    556,
    556,
    556,
    556,
    556,
    556,
    556,
    556,
    556,
    278,
    278,
    584,
    584,
    584,
    556,  # 0 to ?
    1015,
    667,
    667,
    722,
    722,
    667,
    611,
    778,
    722,
    278,
    500,
    667,
    556,
    833,
    722,
    778,  # @ to O
    667,
    778,
    722,
    667,
    611,
    722,
    667,
    944,
    667,
    667,
    611,
    278,
    278,
    278,
    469,
    556,  # P to _
    333,
    556,
    556,
    500,
    556,
    556,
    278,
    556,
    556,
    222,
    222,
    500,
    222,
    833,
    556,
    556,  # ` to o
    556,
    556,
    333,
    500,
    278,
    556,
    500,
    722,
    500,
    500,
    500,
    334,
    260,
    334,
    584,  # p to ~
)

Point = Callable[[float, float], pymupdf.Point]


def document_from_ocr(data: bytes, filename: str) -> Document:
    """Read a photo or a scanned PDF with app.ingest and return it as a PDF Document with word boxes.

    The text is exactly ingest's text, so character offsets agree with what T1 and the regex layer
    see. Raises what ingest raises (UnsupportedDocument, OcrError).
    """
    ocr = ingest.extract(data)
    try:
        source = _image_pdf(data, len(ocr.pages)) if ocr.kind == "image" else _first_pages(data, len(ocr.pages))
        pdf = pymupdf.open(stream=source, filetype="pdf")
        words, missed, total = _words(ocr, pdf, source)
    except Exception as exc:  # noqa: BLE001 - fall back to text only, as before boxes existed
        log.warning("OCR boxes failed (%s); this document is kept as text only", type(exc).__name__)
        return extract_text(ocr.text, filename)
    if missed:
        log.warning(
            "OCR boxes: %d of %d lines could not be placed in the text; their words have no boxes", missed, total
        )
    pages = [(page.rect.width, page.rect.height) for page in pdf]
    return replace(extract_text(ocr.text, filename), kind="pdf", words=words, pages=pages, source=source)


def _words(ocr: ingest.ExtractedDocument, pdf: pymupdf.Document, source: bytes) -> tuple[list[Word], int, int]:
    """Words of every page with offsets into ocr.text and boxes on the PDF page, plus how many OCR
    lines were missed and how many there were."""
    words: list[Word] = []
    missed = total = 0
    start = 0  # where this page's text begins in ocr.text: pages with text are joined by a blank line
    pdfium_doc = pdfium.PdfDocument(source) if any(p.source == "text_layer" for p in ocr.pages) else None
    for page in ocr.pages:
        if not page.text:
            continue
        pno = page.number - 1
        pdf_page = pdf[pno]
        if page.source == "text_layer" and pdfium_doc is not None:  # opened whenever such a page exists
            point = _from_text_layer(pdfium_doc[pno])
        else:
            point = _to_pdf(pdf_page, page.rotation)
        bounds = pdf_page.rect * pdf_page.derotation_matrix
        placed, page_missed = _place_lines(page)
        missed += page_missed
        total += len(placed) + page_missed
        for (row, piece), line, lstart, lend in placed:
            text = page.text[lstart:lend]
            line_box = _rect(point, line.bbox, bounds)
            for s, e, t0, t1 in _word_spans(text):
                x0, y0, x1, y1 = _rect(point, _along(line.bbox, line.angle, t0, t1), bounds)
                box = (max(x0, line_box[0]), max(y0, line_box[1]), min(x1, line_box[2]), min(y1, line_box[3]))
                words.append(Word(text[s:e], pno, box, start + lstart + s, start + lstart + e, (pno, row, piece)))
        start += len(page.text) + 2
    return words, missed, total


def _place_lines(page: ingest.Page) -> tuple[list[tuple[tuple[int, int], ingest.Line, int, int]], int]:
    """Each OCR line's (row, piece) key and its start and end in page.text, in reading order, plus
    how many lines could not be placed.

    ingest builds page.text by joining the lines in group_rows order (a space within a row, a line
    break or a blank line between rows), then repairs identifiers, which can change a few characters
    and add or drop a space. So each line is found, in order, in the text before the repairs, and its
    range is carried over to the repaired text by aligning the two.
    """
    lines = [ln for ln in page.lines if ln.text.strip()]
    raw = assemble(lines)
    to_text = _offset_map(raw, page.text)
    placed = []
    missed = cursor = skipped = 0
    for row, pieces in enumerate(group_rows(lines)):
        for piece, line in enumerate(pieces):
            want = line.text.strip()
            pos = raw.find(want, cursor)
            # only separators may lie between two lines, plus the text of lines just missed
            if pos < 0 or len(raw[cursor:pos].strip()) > skipped:
                missed += 1
                skipped += len(want) + 2
                continue
            cursor, skipped = pos + len(want), 0
            start, end = to_text[pos], to_text[cursor]
            text = page.text[start:end]
            start, end = start + len(text) - len(text.lstrip()), end - len(text) + len(text.rstrip())
            if start >= end:
                missed += 1
                continue
            placed.append(((row, piece), line, start, end))
    return placed, missed


def _offset_map(raw: str, text: str) -> list[int]:
    """For every position in raw (and its end), the matching position in text."""
    if raw == text:
        return list(range(len(raw) + 1))
    out = [0] * (len(raw) + 1)
    for _tag, i1, i2, j1, j2 in SequenceMatcher(None, raw, text, autojunk=False).get_opcodes():
        for i in range(i1, i2):  # equal: one to one; replace: spread evenly; delete: all to j1
            out[i] = j1 + (i - i1) * (j2 - j1) // (i2 - i1)
    out[len(raw)] = len(text)
    return out


def _advance(ch: str) -> int:
    o = ord(ch)
    return HELVETICA[o - 32] if 32 <= o <= 126 else 556


def _word_spans(text: str) -> list[tuple[int, int, float, float]]:
    """Each word's start and end in the line text, and the part of the line it covers (0 to 1)."""
    n = len(text)
    cum = [0, *accumulate(_advance(ch) for ch in text)]
    total = cum[-1] or 1
    pad = PAD_CHARS / n
    out = []
    for m in re.finditer(r"\S+", text):
        s, e = m.span()
        t0 = min(s / n, cum[s] / total) - pad
        t1 = max(e / n, cum[e] / total) + pad
        out.append((s, e, max(t0, 0.0), min(t1, 1.0)))
    return out


def _along(
    bbox: tuple[float, float, float, float], angle: float, t0: float, t1: float
) -> tuple[float, float, float, float]:
    """The part of a line box from t0 to t1 in reading order. Vision's baseline angle is counterclockwise:
    0 reads left to right, 90 bottom to top (a page on its side), 180 right to left (upside down)."""
    x0, y0, x1, y1 = bbox
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    if abs(c) >= abs(s):
        if c > 0:
            return x0 + t0 * (x1 - x0), y0, x0 + t1 * (x1 - x0), y1
        return x1 - t1 * (x1 - x0), y0, x1 - t0 * (x1 - x0), y1
    if s > 0:
        return x0, y1 - t1 * (y1 - y0), x1, y1 - t0 * (y1 - y0)
    return x0, y0 + t0 * (y1 - y0), x1, y0 + t1 * (y1 - y0)


def _to_pdf(pdf_page: pymupdf.Page, rotation: float) -> Point:
    """Map a point in ingest's frame (fractions of the turned page image) to PDF points on the stored page.

    Undo ingest's turn about the page centre, scale the shown page to points, then take away the
    PDF's own /Rotate. Rounding of pixel sizes inside ingest is ignored: under one OCR pixel.
    """
    w, h = pdf_page.rect.width, pdf_page.rect.height  # the page as shown, as ingest rendered it
    c, s = math.cos(math.radians(rotation)), math.sin(math.radians(rotation))
    fw, fh = w * abs(c) + h * abs(s), w * abs(s) + h * abs(c)  # the turned canvas, grown to fit
    derotate = pdf_page.derotation_matrix

    def point(fx: float, fy: float) -> pymupdf.Point:
        dx, dy = fx * fw - fw / 2, fy * fh - fh / 2
        return pymupdf.Point(w / 2 + dx * c - dy * s, h / 2 + dx * s + dy * c) * derotate

    return point


def _from_text_layer(pdf_page: pdfium.PdfPage) -> Point:
    """Map a point of a text-layer line box to PDF points on the stored page.

    Those boxes are not in the frame above: ingest divides pdfium's character boxes (PDF user space,
    before /Rotate) by the page size as shown and flips y (ingest.extract._text_layer_lines). Undo
    exactly that, then put the origin at the CropBox's top left, as PyMuPDF does.
    """
    w, h = pdf_page.get_size()
    left, _bottom, _right, top = pdf_page.get_cropbox()

    def point(fx: float, fy: float) -> pymupdf.Point:
        return pymupdf.Point(fx * w - left, top - (1 - fy) * h)

    return point


def _rect(
    point: Point, box: tuple[float, float, float, float], bounds: pymupdf.Rect
) -> tuple[float, float, float, float]:
    """The PDF rectangle around a box in ingest's frame, clipped to the page. After a deskew the
    box lands a little tilted, so the rectangle is the one around its four corners."""
    x0, y0, x1, y1 = box
    corners = [point(x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    xs, ys = [p.x for p in corners], [p.y for p in corners]

    def clip(v: float, lo: float, hi: float) -> float:
        return min(max(v, lo), hi)

    return (
        clip(min(xs), bounds.x0, bounds.x1),
        clip(min(ys), bounds.y0, bounds.y1),
        clip(max(xs), bounds.x0, bounds.x1),
        clip(max(ys), bounds.y0, bounds.y1),
    )


def _first_pages(data: bytes, count: int) -> bytes:
    """A scanned PDF is kept as uploaded, unless ingest read only its first pages (it stops at
    ingest.extract.MAX_PAGES): the pages it did not read are dropped, since nothing on them is found."""
    pdf = pymupdf.open(stream=data, filetype="pdf")
    if len(pdf) <= count:
        return data
    pdf.select(range(count))
    return pdf.tobytes(garbage=3, deflate=True)


def _image_pdf(data: bytes, count: int) -> bytes:
    """One PDF page per image or TIFF frame that ingest read, holding the pixels it read.

    Every image is encoded again, so nothing of the upload's metadata (EXIF with GPS, device and
    owner, XMP, PNG text) reaches the PDF: a page with no box is never rewritten by the redaction.
    """
    img = Image.open(io.BytesIO(data))
    pdf = pymupdf.open()
    for index, frame in enumerate(page_frames(img)):  # the frames ingest reads: one for an iPhone MPO
        if index >= count:
            break
        frame = frame.copy()
        orientation = frame.getexif().get(ExifTags.Base.Orientation, 1)
        upright = ImageOps.exif_transpose(frame)  # what ingest does first, so pixels and boxes agree
        width, height = _page_size(upright, _dpi(frame), turned=orientation in (5, 6, 7, 8))
        page = pdf.new_page(width=width, height=height)
        page.insert_image(page.rect, stream=_encode(upright, lossy=img.format in LOSSY), keep_proportion=False)
    return pdf.tobytes(garbage=3, deflate=True)


def _dpi(img: Image.Image) -> tuple[float, float] | None:
    """The image's resolution, or None when it has none (or a nonsense one)."""
    dpi: Any = img.info.get("dpi")
    try:
        x, y = float(dpi[0]), float(dpi[1])
    except (TypeError, ValueError, IndexError):
        return None
    return (x, y) if 10 <= x <= 10000 and 10 <= y <= 10000 else None


def _page_size(img: Image.Image, dpi: tuple[float, float] | None, turned: bool) -> tuple[float, float]:
    """A scan keeps its paper size (pixels at its dpi). A photo (no dpi, or a page longer than
    MAX_SCAN_SIDE at it: phones say 72 dpi) gets a page whose long side is PHOTO_SIDE."""
    xdpi, ydpi = dpi or (72.0, 72.0)
    if turned:  # EXIF turned the image a quarter: the axes swap
        xdpi, ydpi = ydpi, xdpi
    width, height = img.width * 72 / xdpi, img.height * 72 / ydpi
    if dpi is None or max(width, height) > MAX_SCAN_SIDE:
        scale = PHOTO_SIDE / max(width, height)
        width, height = width * scale, height * scale
    return width, height


def _encode(img: Image.Image, lossy: bool) -> bytes:
    """PNG or JPEG bytes of the image with no metadata, transparency put on white as ingest does
    before OCR, at most MAX_PIXELS on the long side."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        img = Image.new("RGB", rgba.size, (255, 255, 255))
        img.paste(rgba, mask=rgba.getchannel("A"))
    else:
        img = img.convert("L" if img.mode in ("1", "L") else "RGB")
    img.info = {}  # EXIF, XMP, ICC, text chunks: none of it is written
    img.thumbnail((MAX_PIXELS, MAX_PIXELS), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    if lossy:
        img.save(buf, "JPEG", quality=92)
    else:
        img.save(buf, "PNG")
    return buf.getvalue()
