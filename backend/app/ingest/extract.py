"""Turn an uploaded PDF or image into plain text for T1, entirely on this machine.

PDF pages that have a text layer are read directly. Pages without one (scans), and
images (JPG, PNG, HEIC, TIFF, WebP and anything else Pillow opens), are rendered and
read with Apple Vision. No LLM and no network call is involved. OCR text then gets
deterministic identifier repairs (see fixes.py). The output text uses the T1 training
format: visual lines joined by "\n", paragraphs and pages separated by a blank line.
"""

from __future__ import annotations

import io
import re
from collections.abc import Callable
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw
from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError

from . import vision
from .fixes import fix_identifiers
from .layout import assemble
from .types import ExtractedDocument, Fix, Line, Page, UnsupportedDocument

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # HEIC photos then fail to open, everything else still works
    pass

OCR_DPI = 300
MAX_PAGES = 100
MAX_SIDE = 4200  # pixels; larger page images are scaled down before OCR
MIN_WIDTH = 1200  # pixels; narrower images are scaled up, which helps Vision with small type
FULL_TEXT_CHARS = 200  # a text layer this long is used even over a page image (scanners often add one)
SCAN_COVER = 0.4  # an image covering this share of a page with little or no text marks the page as a scan
WEAK_OCR_CHARS = 20  # an OCR result this short makes us try the other three rotations
DESKEW_MIN = 0.5  # degrees; a page whose text leans more than this is turned straight and read again

Recognizer = Callable[[Image.Image], list[Line]]


def _alnum(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]", text))


def _prepare(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.getchannel("A"))
        img = bg
    img = img.convert("RGB")
    w, h = img.size
    if max(w, h) > MAX_SIDE:
        scale = MAX_SIDE / max(w, h)
        img = img.resize((round(w * scale), round(h * scale)), Image.Resampling.LANCZOS)
    elif w < MIN_WIDTH:
        scale = MIN_WIDTH / w
        img = img.resize((round(w * scale), round(h * scale)), Image.Resampling.LANCZOS)
    return img


def _score(lines: list[Line]) -> float:
    return sum(len(ln.text) * ln.confidence for ln in lines)


def _lean(lines: list[Line]) -> float:
    """The page's text direction: the median line angle, weighted by text length."""
    weighted = sorted((ln.angle, len(ln.text)) for ln in lines if ln.text.strip())
    if not weighted:
        return 0.0
    half, acc = sum(w for _, w in weighted) / 2, 0
    for angle, w in weighted:
        acc += w
        if acc >= half:
            return angle
    return weighted[-1][0]


def _turn(img: Image.Image, degrees: float) -> Image.Image:
    return img.rotate(degrees, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=(255, 255, 255))


def _ocr_page(img: Image.Image, number: int, recognize: Recognizer, fix: bool) -> tuple[Page, list]:
    img = _prepare(img)
    best_rotation, best = 0.0, recognize(img)
    lean = _lean(best)
    if abs(lean) > DESKEW_MIN:  # a skewed scan or photo, or a page lying on its side: straighten and read again
        straightened = recognize(_turn(img, -lean))
        if _score(straightened) >= _score(best):
            best_rotation, best = -lean, straightened
    if _alnum(" ".join(ln.text for ln in best)) < WEAK_OCR_CHARS:  # upside down, or nothing readable yet
        for rotation in (90.0, 180.0, 270.0):
            lines = recognize(_turn(img, rotation))
            if _score(lines) > _score(best):
                best_rotation, best = rotation, lines
    text = assemble(best)
    fixes: list[Fix] = []
    if fix:
        text, fixes = fix_identifiers(text, number)
    page = Page(number=number, source="ocr", text=text, lines=best, rotation=round(best_rotation % 360, 1))
    if not text:
        page.warnings.append(f"page {number}: no text found")
    elif page.low_confidence_lines:
        page.warnings.append(f"page {number}: {len(page.low_confidence_lines)} low-confidence lines, check them")
    return page, fixes


def _text_layer_lines(pdf_page: pdfium.PdfPage) -> list[Line]:
    """One Line per line of pdfium's own reading order, boxed by the union of its characters' boxes.

    pdfium's text order is clean but has no paragraph breaks; the boxes let assemble() find them
    from vertical gaps, the same way it does for OCR. (Reading text rectangle by rectangle instead
    duplicated and split words: "STAN DARD", "t o the".)
    """
    width, height = pdf_page.get_size()
    textpage = pdf_page.get_textpage()
    text = textpage.get_text_range()
    lines = []
    for m in re.finditer(r"[^\r\n]+", text):
        boxes = [textpage.get_charbox(i) for i in range(m.start(), m.end())]
        tall = [b for b in boxes if b[3] - b[1] > 0.5]  # spaces and generated characters have no height
        content = m.group().strip()
        if not content or not tall:
            continue
        left, right = min(b[0] for b in tall), max(b[2] for b in tall)
        bottom, top = min(b[1] for b in tall), max(b[3] for b in tall)
        lines.append(
            Line(
                text=content, bbox=(left / width, 1 - top / height, right / width, 1 - bottom / height), confidence=1.0
            )
        )
    return lines


def _image_cover(pdf_page: pdfium.PdfPage) -> float:
    width, height = pdf_page.get_size()
    area = 0.0
    for obj in pdf_page.get_objects(filter=[pdfium_raw.FPDF_PAGEOBJ_IMAGE]):
        left, bottom, right, top = obj.get_bounds()
        area += max(0.0, min(right, width) - max(left, 0.0)) * max(0.0, min(top, height) - max(bottom, 0.0))
    return min(area / (width * height), 1.0)


def _is_scan(pdf_page: pdfium.PdfPage, lines: list[Line]) -> bool:
    """A page with no text, or with little text over a large image, is read with OCR."""
    chars = _alnum(" ".join(ln.text for ln in lines))
    if chars >= FULL_TEXT_CHARS:
        return False
    return chars == 0 or _image_cover(pdf_page) >= SCAN_COVER


def _open_pdf(data: bytes) -> pdfium.PdfDocument:
    try:
        return pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        raise UnsupportedDocument(f"cannot open the PDF (damaged or password protected): {exc}") from exc


def _from_pdf(data: bytes, recognize: Recognizer, fix: bool) -> ExtractedDocument:
    pdf = _open_pdf(data)
    doc = ExtractedDocument(kind="pdf", pages=[])
    try:
        count = len(pdf)
        if count > MAX_PAGES:
            doc.warnings.append(f"only the first {MAX_PAGES} of {count} pages were read")
        for index in range(min(count, MAX_PAGES)):
            pdf_page = pdf[index]
            lines = _text_layer_lines(pdf_page)
            if not _is_scan(pdf_page, lines):
                doc.pages.append(Page(number=index + 1, source="text_layer", text=assemble(lines), lines=lines))
                continue
            image = pdf_page.render(scale=OCR_DPI / 72).to_pil()
            page, fixes = _ocr_page(image, index + 1, recognize, fix)
            doc.pages.append(page)
            doc.fixes.extend(fixes)
    finally:
        pdf.close()
    return doc


def _from_image(data: bytes, recognize: Recognizer, fix: bool) -> ExtractedDocument:
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise UnsupportedDocument("not a PDF or an image format we can read") from exc
    doc = ExtractedDocument(kind="image", pages=[])
    for index, frame in enumerate(page_frames(img)):
        if index >= MAX_PAGES:
            doc.warnings.append(f"only the first {MAX_PAGES} frames were read")
            break
        page, fixes = _ocr_page(frame.copy(), index + 1, recognize, fix)
        doc.pages.append(page)
        doc.fixes.extend(fixes)
    return doc


def page_frames(img: Image.Image) -> list[Image.Image] | ImageSequence.Iterator:
    """The pages of an image: a multi-page TIFF has several frames. An iPhone JPEG (MPO) has one page;
    its later frames are a depth map or a preview."""
    return [img] if img.format == "MPO" else ImageSequence.Iterator(img)


def scanned_pages(source: bytes | str | Path) -> list[int]:
    """Numbers (1-based) of the PDF pages extract() reads with OCR: no text layer, or little text over
    an image covering much of the page (a scan with a page-number stamp). Empty for an image."""
    data = Path(source).read_bytes() if isinstance(source, (str, Path)) else source
    if data[:5] != b"%PDF-":
        return []
    pdf = _open_pdf(data)
    try:
        return [i + 1 for i in range(min(len(pdf), MAX_PAGES)) if _is_scan(pdf[i], _text_layer_lines(pdf[i]))]
    finally:
        pdf.close()


def extract(source: bytes | str | Path, *, fix: bool = True, recognize: Recognizer | None = None) -> ExtractedDocument:
    """Read a PDF or an image (bytes or a path) into text. `recognize` replaces Apple Vision, for tests."""
    data = Path(source).read_bytes() if isinstance(source, (str, Path)) else source
    recognize = recognize or vision.recognize
    if data[:5] == b"%PDF-":
        doc = _from_pdf(data, recognize, fix)
    else:
        doc = _from_image(data, recognize, fix)
    for page in doc.pages:
        doc.warnings.extend(page.warnings)
    return doc
