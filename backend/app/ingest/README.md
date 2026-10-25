# Document ingestion

[Documentation index](../../../docs/README.md) · [Data protection](../../../docs/SECURITY.md)

Turns an uploaded PDF or image into plain text for T1 inside the backend process.
Extraction itself makes no LLM or network call. The later T1 detection step sends
original extracted chunks through Mubit; extraction is not an outbound privacy
barrier. Apple Vision OCR requires macOS and is unavailable on Railway's Linux
backend. Text-layer PDF extraction remains available there.

```python
from app.ingest import extract, scanned_pages

doc = extract(pdf_or_image_bytes)  # or a path
doc.text  # T1 format: visual lines joined by "\n", paragraphs and pages separated by a blank line
doc.pages  # per page: source ("text_layer" or "ocr"), text, lines with boxes and confidence, rotation
doc.fixes  # identifier repairs made after OCR (kind, before, after)
doc.warnings  # empty pages, low-confidence lines, page limit

scanned_pages(pdf_bytes)  # 1-based numbers of the PDF pages extract() would read with OCR
```

How a page is read:

- **PDF with a text layer:** pdfium's text, in its reading order; line boxes come from the
  character boxes, so paragraphs are found from vertical gaps. No OCR.
- **Scanned PDF page** (no text, or little text over an image covering 40% or more of the
  page) and **images** (JPG, PNG, HEIC, TIFF with several pages, WebP; an iPhone MPO JPEG is
  one page, its later frames being a depth map or a preview): rendered at 300 dpi and read with
  Apple Vision, language correction off (it drops digits from identifiers).
  EXIF orientation is applied; a page whose text leans more than 0.5 degrees, or lies on its
  side, is straightened and read again; an unreadable page is also tried at 90, 180 and 270.
- **After OCR:** deterministic repairs of look-alike characters inside UK postcodes, sort
  codes, GB IBANs (checked with mod 97), NI numbers and mostly-digit runs, plus Cyrillic or
  Greek look-alikes inside English words (`fixes.py`). Ordinary words are never touched.

Raises `UnsupportedDocument` for other formats and for damaged or password-protected PDFs,
and `OcrError` when Apple Vision is unavailable (not macOS).

Known limits: one column of text is assumed (two columns read row by row across both);
DOCX is not handled here; OCR quality drops on phone photos (about 97% of personal values
kept, against 99 to 100% on scans; see `scripts/ocr/README.md`).
