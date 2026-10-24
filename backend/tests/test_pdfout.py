import io

import pymupdf
import pytest
from PIL import Image, ImageCms

from app.domain.extract import extract_pdf
from app.domain.pdfout import _jpeg_without_metadata, redact_pdf
from app.domain.pipeline import Box, T1Result, run_pipeline


def test_redacted_pdf_has_the_values_removed_not_just_covered(tenancy_pdf):
    doc = extract_pdf(tenancy_pdf, "lease.pdf")

    def t1(chunk):
        return T1Result([{"text": "Raj Patel", "type": "PERSON"}], "mreq_1", None)

    res = run_pipeline(doc, t1=t1)
    out = redact_pdf(doc.source, res.boxes)
    text = "".join(page.get_text() for page in pymupdf.open(stream=out, filetype="pdf"))
    assert "Patel" not in text
    assert "20-45-77" not in text and "31926819" not in text
    assert "Rent: 950 pounds per month" in text  # everything else stays


SECRET = "Jane Secretname"


def _jpeg_with_exif(colour=(40, 40, 40)) -> bytes:
    exif = Image.Exif()
    exif[0x013B] = SECRET  # Artist
    buf = io.BytesIO()
    img = Image.new("RGB", (400, 300), "white")
    img.paste(colour, (40, 40, 360, 80))
    img.save(buf, "JPEG", quality=90, exif=exif, icc_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
    return buf.getvalue()


def _pdf_naming_someone_outside_its_pages(scan: bool) -> bytes:
    """A text PDF, or a scan with an EXIF-tagged JPEG, that names SECRET only outside its page content."""
    pdf = pymupdf.open()
    page = pdf.new_page()
    if scan:
        page.insert_image(pymupdf.Rect(72, 72, 472, 372), stream=_jpeg_with_exif())
    else:
        page.insert_text((72, 100), "Tenant: Raj Patel", fontsize=11)
        page.insert_text((72, 120), "Rent: 950 pounds per month", fontsize=11)
    pdf.set_metadata({"author": SECRET, "title": f"Lease for {SECRET}", "subject": SECRET, "keywords": SECRET})
    pdf.set_xml_metadata(f'<x:xmpmeta xmlns:x="adobe:ns:meta/"><dc:creator>{SECRET}</dc:creator></x:xmpmeta>')
    pdf.embfile_add("notes.txt", f"Call {SECRET}".encode())
    pdf.set_toc([[1, f"{SECRET} contract", 1]])
    page.add_file_annot(pymupdf.Point(500, 40), f"From {SECRET}".encode(), "attached.txt")
    for key, body in (("Thumb", "<</Type/XObject/Subtype/Image/Width 1/Height 1/ColorSpace/DeviceGray/BitsPerComponent 8>>"),
                      ("Metadata", "<</Type/Metadata/Subtype/XML>>")):
        xref = pdf.get_new_xref()
        pdf.update_object(xref, body)
        pdf.update_stream(xref, f"picture of the page naming {SECRET}".encode())
        pdf.xref_set_key(page.xref, key, f"{xref} 0 R")
    pdf.xref_set_key(page.xref, "PieceInfo", f"<</App<</Private({SECRET})>>>>")
    return pdf.tobytes()


def _traces(pdf_bytes: bytes) -> list[str]:
    found = ["file"] if SECRET.encode() in pdf_bytes else []
    pdf = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    for xref in range(1, pdf.xref_length()):
        if SECRET in pdf.xref_object(xref):
            found.append(f"object {xref}")
        if pdf.xref_is_stream(xref) and any(SECRET.encode() in (d or b"") for d in (pdf.xref_stream_raw(xref), pdf.xref_stream(xref))):
            found.append(f"stream {xref}")
    return found


@pytest.mark.parametrize("scan", [False, True], ids=["text", "scan"])
@pytest.mark.parametrize("boxed", [False, True], ids=["no-box", "boxed"])
def test_redacted_pdf_keeps_no_name_outside_its_pages(scan, boxed):
    source = _pdf_naming_someone_outside_its_pages(scan)
    assert len(_traces(source)) >= 8
    hit = pymupdf.open(stream=source, filetype="pdf")[0].search_for("Raj Patel") or [pymupdf.Rect(100, 100, 300, 300)]
    boxes = [Box(0, *hit[0], type="PERSON", placeholder="[PERSON_1]", span_index=0)] if boxed else []
    out = redact_pdf(source, boxes)
    pdf = pymupdf.open(stream=out, filetype="pdf")
    page = pdf[0]
    assert all(not v for k, v in pdf.metadata.items() if k not in ("format", "encryption")), pdf.metadata  # info
    assert pdf.get_xml_metadata() == ""  # XMP
    assert pdf.embfile_count() == 0  # embedded files
    assert list(page.annots()) == []  # file attachments
    assert pdf.get_toc() == []  # outline
    for key in ("Thumb", "Metadata", "PieceInfo"):  # thumbnail, page XMP, app data
        assert pdf.xref_get_key(page.xref, key)[0] == "null", key
    assert _traces(out) == []  # and no trace anywhere, EXIF inside the JPEG included
    if not scan:
        text = page.get_text()
        assert ("Patel" in text) != boxed and "Rent: 950 pounds per month" in text


def test_jpeg_metadata_is_dropped_without_touching_the_image():
    jpeg = _jpeg_with_exif()
    clean = _jpeg_without_metadata(jpeg)
    assert SECRET.encode() not in clean and len(clean) < len(jpeg)
    before, after = Image.open(io.BytesIO(jpeg)), Image.open(io.BytesIO(clean))
    assert after.getexif() == {} and after.info.get("icc_profile") == before.info.get("icc_profile")  # colour kept
    assert after.tobytes() == before.tobytes()  # same pixels: only header segments went
    assert clean.endswith(jpeg[jpeg.index(b"\xff\xda"):])  # the scan data byte for byte


def test_a_broken_xref_entry_in_the_upload_does_not_block_the_download(tenancy_pdf, monkeypatch):
    # Some real PDFs list an object their xref cannot load ("cannot find object in xref (24 0 R)").
    # MuPDF repairs most broken files we can build here, so the unloadable object is simulated.
    real = pymupdf.Document.xref_get_key
    pdf = pymupdf.open(stream=tenancy_pdf, filetype="pdf")
    broken = pdf.xref_length() - 1

    def xref_get_key(self, xref, key):
        if xref == broken:
            raise pymupdf.mupdf.FzErrorFormat(f"cannot find object in xref ({xref} 0 R)")
        return real(self, xref, key)

    monkeypatch.setattr(pymupdf.Document, "xref_get_key", xref_get_key)
    words = pdf[0].get_text("words")
    out = redact_pdf(tenancy_pdf, [Box(0, *words[0][:4], "NAME", "[NAME_1]", 0)])
    assert pymupdf.open(stream=out, filetype="pdf").page_count == pdf.page_count
