import io
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

FONTS = Path("/System/Library/Fonts/Supplemental")
PAGE_W, PAGE_H = 1654, 2339  # A4 at 200 dpi

macos_only = pytest.mark.skipif(sys.platform != "darwin", reason="Apple Vision OCR needs macOS")


def render_page(paragraphs: list[str], font: str = "Arial.ttf", size: int = 30) -> Image.Image:
    """A white A4 page at 200 dpi with each paragraph on its own lines and a blank line between paragraphs."""
    img = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    draw = ImageDraw.Draw(img)
    face = ImageFont.truetype(str(FONTS / font), size)
    y = 150
    for para in paragraphs:
        for line in para.split("\n"):
            draw.text((150, y), line, font=face, fill="black")
            y += int(size * 1.3)
        y += int(size * 1.3)
    return img


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def image_pdf(*pages: Image.Image) -> bytes:
    buf = io.BytesIO()
    pages[0].save(buf, "PDF", resolution=200, save_all=True, append_images=list(pages[1:]))
    return buf.getvalue()


def text_pdf(pages: list[list[str]], scan_after: Image.Image | None = None, **canvas_kwargs) -> bytes:
    """A PDF with a real text layer, one list of lines per page, optionally followed by an image-only page."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, **canvas_kwargs)
    for lines in pages:
        y = 780
        for line in lines:
            if line:
                c.setFont("Helvetica", 11)
                c.drawString(72, y, line)
            y -= 16
        c.showPage()
    if scan_after is not None:
        c.drawImage(ImageReader(scan_after), 0, 0, width=A4[0], height=A4[1])
        c.showPage()
    c.save()
    return buf.getvalue()


def no_ocr(_image):
    raise AssertionError("OCR must not run for pages with a text layer")
