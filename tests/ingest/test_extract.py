import io

import pytest
from ingest_helpers import image_pdf, macos_only, no_ocr, png_bytes, render_page, text_pdf
from PIL import Image

from app.ingest import Line, UnsupportedDocument, extract

LETTER = [
    "Hollis & Mercer Ltd\nLevel 12, 95 Queen's Court\nLeeds LS14 1TP",
    "Dear Mrs Kovalenko,",
    "Your salary of £32,000 will be paid into account 41960183,\nsort code 20-45-77. Your NI number is QQ 12 34 56 C.",
    "Kind regards,\nRhodri Evans",
]
KEY_VALUES = ["Hollis & Mercer Ltd", "LS14 1TP", "Kovalenko", "41960183", "20-45-77", "QQ 12 34 56 C", "Rhodri Evans"]


def assert_values(text):
    missing = [v for v in KEY_VALUES if v not in text]
    assert not missing, f"missing {missing} in:\n{text}"


def test_text_layer_pdf_is_read_without_ocr():
    pdf = text_pdf([["Tenant: Oleksandra Kovalenko", "", "Rent: £1,250 a month"], ["Signed: Ann Lee"]])
    doc = extract(pdf, recognize=no_ocr)
    assert doc.kind == "pdf" and [p.source for p in doc.pages] == ["text_layer", "text_layer"]
    assert doc.text == "Tenant: Oleksandra Kovalenko\n\nRent: £1,250 a month\n\nSigned: Ann Lee"
    assert doc.fixes == [] and doc.warnings == []


@pytest.mark.parametrize(
    ("data", "kind"),
    [
        pytest.param(lambda: image_pdf(render_page(LETTER)), "pdf", id="scanned-pdf"),
        pytest.param(lambda: png_bytes(render_page(LETTER)), "image", id="png"),
        pytest.param(lambda: _jpeg(render_page(LETTER), 45), "image", id="jpeg-q45"),
        pytest.param(lambda: _heic(render_page(LETTER)), "image", id="heic"),
    ],
)
@macos_only
def test_scans_and_images_are_read_with_ocr(data, kind):
    doc = extract(data())
    assert doc.kind == kind and [p.source for p in doc.pages] == ["ocr"]
    assert_values(doc.text)
    assert "Dear Mrs Kovalenko,\n\nYour salary" in doc.text  # paragraph break kept


@macos_only
def test_mixed_pdf_reads_each_page_the_right_way():
    pdf = text_pdf([["Page one has a real text layer for Ann Lee."]], scan_after=render_page(LETTER))
    doc = extract(pdf)
    assert [p.source for p in doc.pages] == ["text_layer", "ocr"]
    assert doc.text.startswith("Page one has a real text layer for Ann Lee.\n\n")
    assert_values(doc.text)


@macos_only
def test_multi_page_tiff_gives_one_page_per_frame():
    pages = [render_page(LETTER[:2]), render_page(LETTER[2:])]
    buf = io.BytesIO()
    pages[0].save(buf, "TIFF", save_all=True, append_images=pages[1:])
    doc = extract(buf.getvalue())
    assert [p.number for p in doc.pages] == [1, 2]
    assert_values(doc.text)


@macos_only
def test_exif_orientation_is_applied():
    upright = render_page(LETTER)
    stored = upright.rotate(90, expand=True)  # a phone stores the pixels turned and records Orientation=6
    exif = Image.Exif()
    exif[0x0112] = 6
    buf = io.BytesIO()
    stored.save(buf, "JPEG", quality=90, exif=exif)
    doc = extract(buf.getvalue())
    assert doc.pages[0].rotation == 0
    assert_values(doc.text)


@pytest.mark.parametrize("turn", [90, 180, 270])
@macos_only
def test_a_page_scanned_sideways_or_upside_down_is_turned_back(turn):
    doc = extract(png_bytes(render_page(LETTER).rotate(turn, expand=True)))
    assert_values(doc.text)


@macos_only
def test_transparent_png_and_small_images():
    page = render_page(LETTER).convert("RGBA")
    page.putalpha(page.convert("L").point(lambda v: 255 - v))  # black text on a transparent background
    assert_values(extract(png_bytes(page)).text)
    small = render_page(LETTER).resize((827, 1170))  # about 100 dpi
    assert_values(extract(png_bytes(small)).text)


@macos_only
def test_times_new_roman_postcode_is_repaired():
    page = render_page(["Write to us at 12 Mill Road, Leeds LS14 1TP or Dundee DD9 1SE."], font="Times New Roman.ttf")
    doc = extract(png_bytes(page))
    assert "LS14 1TP" in doc.text and "DD9 1SE" in doc.text


@macos_only
def test_blank_page_gives_no_text_and_a_warning():
    doc = extract(png_bytes(Image.new("RGB", (1654, 2339), "white")))
    assert doc.text == ""
    assert doc.warnings == ["page 1: no text found"]


def test_an_iphone_mpo_is_read_as_one_page():
    # iPhone JPEGs are often MPO files: the second frame is a depth map or a preview, not a page
    seen = []

    def recognize(image):
        seen.append(image.size)
        return [Line(text="Dear Ann Lee, thank you for your letter.", bbox=(0.1, 0.1, 0.9, 0.14), confidence=1.0)]

    buf = io.BytesIO()
    Image.new("RGB", (1600, 1200), "white").save(buf, "MPO", save_all=True, append_images=[Image.new("RGB", (400, 300))])
    assert Image.open(io.BytesIO(buf.getvalue())).n_frames == 2
    doc = extract(buf.getvalue(), recognize=recognize)
    assert [p.number for p in doc.pages] == [1] and seen == [(1600, 1200)]
    assert doc.text == "Dear Ann Lee, thank you for your letter."


def test_unreadable_inputs_are_refused():
    with pytest.raises(UnsupportedDocument):
        extract(b"just some bytes, not a document")
    with pytest.raises(UnsupportedDocument):
        extract(text_pdf([["Ann Lee"]])[:200])  # cut short
    with pytest.raises(UnsupportedDocument):
        extract(text_pdf([["Ann Lee"]], encrypt="secret"))


def _jpeg(img, quality):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def _heic(img):
    pillow_heif = pytest.importorskip("pillow_heif")
    buf = io.BytesIO()
    pillow_heif.from_pillow(img).save(buf, quality=80)
    return buf.getvalue()
