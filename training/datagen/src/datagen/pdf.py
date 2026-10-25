"""Render demo PDFs (A4) with gold labels next to them, then extract the text back and re-align
the gold spans to the extracted text to measure how well labels survive PDF round-tripping.

    uv run python -m datagen.pdf --out ../../data/synthetic/pdfs --n 30 --seed 42
"""
from __future__ import annotations

import argparse
import difflib
import json
import random
import re
from collections import Counter
from pathlib import Path

from fpdf import FPDF

from .build import finish
from .doctypes import load_all
from .validate import check_record

FONT_DIR = Path("/System/Library/Fonts/Supplemental")
PDF_TYPES = ["tenancy_agreement", "tenancy_agreement", "employment_contract", "employment_contract", "nda",
             "nda", "service_agreement", "service_agreement", "engagement_letter", "engagement_letter", "invoice",
             "invoice", "utility_bill", "utility_bill", "phone_bill", "phone_bill", "bank_statement",
             "bank_statement", "payslip", "payslip", "insurance_claim_letter", "insurance_claim_letter",
             "gov_letter", "gov_letter", "medical_letter", "medical_letter", "cv", "cv", "hr_form", "email_thread"]
SERIF_TYPES = {"tenancy_agreement", "employment_contract", "nda", "service_agreement", "engagement_letter",
               "insurance_claim_letter", "gov_letter", "medical_letter"}


class _PDF(FPDF):
    def __init__(self, label: str, serif: bool):
        super().__init__(format="A4")
        self.label = label
        self.serif = serif
        self.set_margins(18, 16, 18)
        self.set_auto_page_break(True, margin=18)
        fonts = {"Body": "Georgia" if serif else "Arial", "Sans": "Arial"}
        for fam, base in fonts.items():
            self.add_font(fam, "", str(FONT_DIR / f"{base}.ttf"))
            self.add_font(fam, "B", str(FONT_DIR / f"{base} Bold.ttf"))
        self.add_font("Mono", "", str(FONT_DIR / "Courier New.ttf"))
        self.add_font("Uni", "", str(FONT_DIR / "Arial Unicode.ttf"))
        self.set_fallback_fonts(["Uni"])

    def footer(self):
        self.set_y(-12)
        self.set_font("Sans", "", 7.5)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, f"{self.label}    Page {self.page_no()} of {{nb}}", align="C")
        self.set_text_color(0, 0, 0)


def _table(pdf: _PDF, rows: list[list[str]]):
    pdf.set_font("Sans", "", 8.5)
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    from fpdf.fonts import FontFace
    with pdf.table(first_row_as_headings=True, line_height=4.6, text_align="LEFT",
                   headings_style=FontFace(emphasis="BOLD", fill_color=(235, 238, 242)),
                   borders_layout="SINGLE_TOP_LINE") as t:
        for r in rows:
            row = t.row()
            for cell in r:
                row.cell(cell)
    pdf.ln(2)


def render_pdf(text: str, path: Path, doc_type: str):
    serif = doc_type in SERIF_TYPES
    pdf = _PDF(doc_type.replace("_", " ").title(), serif)
    pdf.alias_nb_pages()
    pdf.add_page()
    lines = text.expandtabs(4).split("\n")
    i = 0
    first = True
    body_size = 10 if serif else 9.5
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            if rows:
                _table(pdf, rows)
            continue
        i += 1
        if not ln.strip():
            pdf.ln(2.2)
            continue
        clean = ln.replace("**", "")
        if first:
            pdf.set_font("Sans", "B", 14)
            pdf.multi_cell(0, 7, clean.lstrip("# "), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.5)
            first = False
            continue
        if clean.startswith("#"):
            pdf.set_font("Body", "B", body_size + 1.5)
            pdf.multi_cell(0, 6, clean.lstrip("# "), new_x="LMARGIN", new_y="NEXT")
            continue
        is_heading = len(clean) < 70 and clean.isupper() and any(c.isalpha() for c in clean)
        if re.search(r"\S {2,}\S", clean.strip()) or set(clean.strip()) <= set("-=_ "):
            pdf.set_font("Mono", "", 8 if len(clean) < 100 else 6.5)   # column-aligned text
            pdf.multi_cell(0, 4.2, clean, new_x="LMARGIN", new_y="NEXT")
            continue
        pdf.set_font("Body", "B" if is_heading else "", body_size)
        pdf.multi_cell(0, 4.8, clean, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(path))


def extract_text(path: Path) -> str:
    import pdfplumber
    with pdfplumber.open(str(path)) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)


def align(spans: list[dict], extracted: str) -> tuple[list[dict], list[dict]]:
    """Find each gold span in the extracted text (whitespace-flexible, in order)."""
    found, missing = [], []
    cursor = 0
    for e in spans:
        toks = e["text"].split()
        pat = re.compile(r"\s*".join(re.escape(t) for t in toks)) if toks else None
        m = pat.search(extracted, cursor) if pat else None
        if m is None and pat is not None:
            m = pat.search(extracted)
        if m is None:
            missing.append(e)
            continue
        found.append({"start": m.start(), "end": m.end(), "text": extracted[m.start():m.end()], "type": e["type"],
                      "gold_text": e["text"], "exact": extracted[m.start():m.end()] == e["text"]})
        cursor = m.end()
    return found, missing


def build_pdfs(out: Path, n: int = 30, seed: int = 42) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    reg = load_all()
    totals = Counter()
    miss_by_type = Counter()
    span_by_type = Counter()
    sims = []
    items = []
    for k in range(n):
        dt = PDF_TYPES[k % len(PDF_TYPES)]
        for attempt in range(10):
            rng = random.Random(f"{seed}:pdf:{k}:{attempt}")
            rec = finish(reg[dt].fn(rng, False), False)
            rec.update({"doc_id": f"pdf-{k + 1:03d}", "source": "synthetic", "split": "demo"})
            if not check_record(rec) and rec["entities"]:
                break
        name = f"{k + 1:02d}_{dt}"
        pdf_path = out / f"{name}.pdf"
        render_pdf(rec["text"], pdf_path, dt)
        ext = extract_text(pdf_path)
        found, missing = align(rec["entities"], ext)
        a = re.sub(r"\s+", " ", rec["text"]).strip()
        b = re.sub(r"\s+", " ", ext).strip()
        sim = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() if len(a) < 30000 else float("nan")
        sims.append(sim)
        totals["spans"] += len(rec["entities"])
        totals["missing"] += len(missing)
        totals["inexact"] += sum(1 for f in found if not f["exact"])
        for e in rec["entities"]:
            span_by_type[e["type"]] += 1
        for e in missing:
            miss_by_type[e["type"]] += 1
        gold = {
            "doc_id": rec["doc_id"], "doc_type": dt, "pdf": pdf_path.name, "text": rec["text"],
            "entities": rec["entities"], "meta": {k2: rec["meta"][k2] for k2 in ("template_id", "variant_id",
                                                                              "hard_cases", "keep_traps")},
            "extracted_text": ext, "extracted_entities": found, "missing_in_extracted": missing,
            "text_similarity": round(sim, 4),
        }
        (out / f"{name}.gold.json").write_text(json.dumps(gold, ensure_ascii=False, indent=1))
        items.append({"pdf": pdf_path.name, "spans": len(rec["entities"]), "missing": len(missing),
                      "similarity": round(sim, 4), "missing_examples": [m["text"] for m in missing[:5]]})
    rep = {
        "n_pdfs": n, "spans": totals["spans"], "missing": totals["missing"],
        "mismatch_rate": totals["missing"] / max(1, totals["spans"]),
        "whitespace_changed_rate": totals["inexact"] / max(1, totals["spans"]),
        "mean_text_similarity": round(sum(sims) / len(sims), 4) if sims else None,
        "missing_by_type": {t: f"{miss_by_type[t]}/{span_by_type[t]}" for t in sorted(span_by_type)},
        "documents": items,
    }
    (out / "pdf_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    return rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("../../data/synthetic/pdfs"))
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args(argv)
    rep = build_pdfs(a.out.resolve(), a.n, a.seed)
    print(json.dumps({k: v for k, v in rep.items() if k != "documents"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
