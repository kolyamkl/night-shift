"""Write the redacted PDF: true redaction (the text under each box is removed from the file),
not a black rectangle drawn on top of text that is still there. Then everything outside the page
content that can name people is taken out (see _strip)."""

import pymupdf

from app.redaction.pipeline import Box

PAD = 1.0  # points around each word box, so glyph edges do not peek out
HIDDEN_KEYS = ("Metadata", "PieceInfo", "Thumb")  # XMP on pages and images, app data, page thumbnails
KEEP_APP = (0xE0, 0xE2, 0xEE)  # JPEG JFIF, ICC profile and Adobe colour segments: needed to decode


def redact_pdf(source: bytes, boxes: list[Box]) -> bytes:
    pdf = pymupdf.open(stream=source, filetype="pdf")
    by_page: dict[int, list[Box]] = {}
    for b in boxes:
        by_page.setdefault(b.page, []).append(b)
    for pno, page_boxes in by_page.items():
        page = pdf[pno]
        for b in page_boxes:
            page.add_redact_annot(pymupdf.Rect(b.x0 - PAD, b.y0 - PAD, b.x1 + PAD, b.y1 + PAD), fill=(0, 0, 0))
        # Image pixels under each box are blanked too (photos and scans). This is PyMuPDF's default; it
        # is spelled out so a change of default cannot leave a scanned value readable in the image.
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS)
    _strip(pdf)
    return pdf.tobytes(garbage=3, deflate=True)


def _strip(pdf: pymupdf.Document) -> None:
    """Take out what lies outside the page content and can name people, on every page, boxed or not:
    the document info (author, title) and XMP, embedded files and file attachments, the outline
    (bookmarks), page thumbnails (a picture of the unredacted page), XMP and app data on pages and
    images, and EXIF, XMP, IPTC and comments inside JPEG images (GPS, device, owner)."""
    pdf.set_metadata({})
    pdf.del_xml_metadata()
    for name in pdf.embfile_names():
        pdf.embfile_del(name)
    pdf.set_toc([])
    for page in pdf:
        for xref in [a.xref for a in page.annots(types=[pymupdf.PDF_ANNOT_FILE_ATTACHMENT])]:
            page.delete_annot(page.load_annot(xref))
    for xref in range(1, pdf.xref_length()):
        try:
            pdf.xref_get_key(xref, "Type")
        except pymupdf.mupdf.FzErrorBase:
            continue  # a broken xref entry in the uploaded file: no object there, so nothing to strip
        for key in HIDDEN_KEYS:
            if pdf.xref_get_key(xref, key)[0] != "null":
                pdf.xref_set_key(xref, key, "null")
        if pdf.xref_get_key(xref, "Filter") == ("name", "/DCTDecode"):
            raw = pdf.xref_stream_raw(xref)
            clean = _jpeg_without_metadata(raw)
            if clean != raw:
                parms = pdf.xref_get_key(xref, "DecodeParms")
                pdf.update_stream(xref, clean, compress=False)  # this also drops /Filter and /DecodeParms
                pdf.xref_set_key(xref, "Filter", "/DCTDecode")
                if parms[0] != "null":
                    pdf.xref_set_key(xref, "DecodeParms", parms[1])


def _jpeg_without_metadata(data: bytes) -> bytes:
    """The JPEG without its APP1 to APP15 segments (EXIF, XMP, IPTC...) and comments, except the ones
    needed to decode it (KEEP_APP). The image data itself is untouched, byte for byte."""
    if data[:2] != b"\xff\xd8":
        return data
    out, i = [data[:2]], 2
    while i + 4 <= len(data) and data[i] == 0xFF:
        marker = data[i + 1]
        if marker == 0xFF:  # fill byte
            i += 1
            continue
        if marker == 0xDA or not 0xC0 <= marker <= 0xFE or 0xD0 <= marker <= 0xD9:
            break  # start of scan, or a marker without a length: the rest is image data
        end = i + 2 + int.from_bytes(data[i + 2:i + 4], "big")
        if not ((0xE0 <= marker <= 0xEF and marker not in KEEP_APP) or marker == 0xFE):
            out.append(data[i:end])
        i = end
    out.append(data[i:])
    return b"".join(out)
