# OCR evaluation

[Documentation index](../../docs/README.md) · [Ingestion](../../backend/app/ingest/README.md). Run commands from the repository root; real Apple Vision OCR requires macOS.

`eval_ocr.py` measures how much personal data survives `backend/app/ingest` on dataset
documents. Each sampled document is printed in one of four fonts (Arial, Times New Roman,
Georgia, Courier New) and turned into a text-layer PDF and five image-only PDFs: a clean
300 dpi scan, an office scan (slight rotation, blur, noise, 200 dpi JPEG), a low-resolution
scan (150 dpi), a phone photo (perspective, uneven light, rotation, blur, 150 dpi JPEG) and
a page turned sideways. Every key entity on the drawn pages is then looked up in the output.

```
python scripts/ocr/eval_ocr.py [--per-group 6] [--max-pages 3] [--out data/results/ocr]
```

Results on 24 documents (6 per group, up to 3 pages each), 24 Oct 2026. "Content kept"
ignores spaces, accents and case, so "0131207 7641" for "0131 207 7641" or "Eabha" for
"Éabha" still count; a harmful fix is one that changed text that was already correct.

| Level | Word accuracy | Kept verbatim | Content kept | Harmful fixes | Sec per page |
|---|---:|---:|---:|---:|---:|
| text_pdf | 0.999 | 100.0% | 100.0% | 0 of 0 | 0.01 |
| clean_scan | 0.981 | 99.4% | 100.0% | 0 of 1 | 0.53 |
| office_scan | 0.982 | 98.8% | 99.4% | 0 of 0 | 1.50 |
| low_res_scan | 0.981 | 98.5% | 99.7% | 0 of 2 | 0.77 |
| phone_photo | 0.915 | 96.1% | 96.7% | 0 of 1 | 2.17 |
| sideways | 0.985 | 100.0% | 100.0% | 0 of 1 | 1.31 |

What is still lost on scans is a real misreading of letters ("LS11 8FZ" read as "LS11 8EZ",
"@" read as "d" in Courier, "Schiffer" as "Schifffer"); phone photos also lose a few
addresses and e-mail addresses to perspective. The redaction model still sees such values
as an address or a name, but an answer key built from the source text will not match them
verbatim.
