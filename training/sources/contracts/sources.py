"""Approved contract sources C1 to C12 (design doc section 4).

Shared by fetch.py and build.py. `fetch` lists what fetch.py downloads; when it
is missing, fetch.py downloads `url` itself.
"""

OGL = "Open Government Licence v3.0"
SEC = "Public filing, SEC EDGAR"

SOURCES = [
    {
        "source_id": "C1",
        "title": "Model agreement for an assured shorthold tenancy (England)",
        "url": "https://webarchive.nationalarchives.gov.uk/ukgwa/20260105195424mp_/https://www.gov.uk/government/publications/model-agreement-for-a-shorthold-assured-tenancy",
        "subtype": "tenancy",
        "kind": "template",
        "licence": OGL,
        # The PDF keeps the clause and heading numbers; the ODT generates them from list styles.
        "attachment_ext": [".pdf", ".odt"],
    },
    {
        "source_id": "C2",
        "title": "Model written statement, periodic standard contract (Wales)",
        "url": "https://www.gov.wales/model-written-statement-periodic-standard-contracts",
        "subtype": "tenancy",
        "kind": "template",
        "licence": OGL,
        # The PDF keeps the list letters and the footnotes, which the DOCX holds outside the text.
        "attachment_ext": [".pdf", ".docx"],
    },
    {
        "source_id": "C3",
        "title": "Acas written statement of employment particulars, employee",
        "url": "https://www.acas.org.uk/templates-for-written-statements/written-statement-employee-template",
        "subtype": "employment",
        "kind": "template",
        "licence": OGL,
    },
    {
        "source_id": "C4",
        "title": "JELD-WEN UK service agreement",
        "url": "https://www.sec.gov/Archives/edgar/data/1674335/000167433519000023/exhibit1039_pxmaxwellxeea.htm",
        "subtype": "employment",
        "kind": "filled_real",
        "licence": SEC,
    },
    {
        "source_id": "C5",
        "title": "National Grid UK service agreement",
        "url": "https://www.sec.gov/Archives/edgar/data/1004315/000100431519000071/ex4c5-serviceagreement_and.htm",
        "subtype": "employment",
        "kind": "filled_real",
        "licence": SEC,
    },
    {
        "source_id": "C6",
        "title": "IPO example non-disclosure agreement, one-way",
        "url": "https://www.gov.uk/government/publications/non-disclosure-agreements",
        "subtype": "nda",
        "kind": "template",
        "licence": OGL,
        "attachment_hint": "one-way",
    },
    {
        "source_id": "C7",
        "title": "IPO example non-disclosure agreement, mutual",
        "url": "https://www.gov.uk/government/publications/non-disclosure-agreements",
        "subtype": "nda",
        "kind": "template",
        "licence": OGL,
        "attachment_hint": "mutual",
    },
    {
        "source_id": "C8",
        "title": "Common Paper Mutual NDA, version 1.0 (cover page and standard terms)",
        "url": "https://commonpaper.com/standards/mutual-nda/",
        "provenance_url": "https://commonpaper.com/standards/mutual-nda/1.0",
        "subtype": "nda",
        "kind": "template",
        "licence": "CC BY 4.0",
        # The publisher's own repository of version 1.0, pinned to a commit.
        # commonpaper.com is blocked from the build sandbox; github.com is not.
        "note": "Version 1.0 text from the publisher's own GitHub repository, because commonpaper.com "
                "is blocked from the build sandbox. The approved page may now show a later version; "
                "the template follows version 1.0, which Common Paper keeps unchanged at the provenance URL.",
        "fetch": [
            "https://raw.githubusercontent.com/CommonPaper/Mutual-NDA/2a3068b6c0ab6015c440f541d5b215bc3ac2f4cb/Mutual-NDA-coverpage.md",
            "https://raw.githubusercontent.com/CommonPaper/Mutual-NDA/2a3068b6c0ab6015c440f541d5b215bc3ac2f4cb/Mutual-NDA.md",
        ],
    },
    {
        "source_id": "C9",
        "title": "Proxicom / Dimension Data confidentiality agreement",
        "url": "https://www.sec.gov/Archives/edgar/data/0001070052/000095013001501801/dex99d2.txt",
        "subtype": "nda",
        "kind": "filled_real",
        "licence": SEC,
    },
    {
        "source_id": "C10",
        "title": "SafeNet / Vector confidentiality agreement",
        "url": "https://www.sec.gov/Archives/edgar/data/0000850313/000095014907000090/f28028toexv99wxdyx2y.htm",
        "subtype": "nda",
        "kind": "filled_real",
        "licence": SEC,
    },
    {
        "source_id": "C11",
        "title": "CoStar / Nokia London agreement for lease",
        "url": "https://www.sec.gov/Archives/edgar/data/0001057352/000105735208000004/london_lease-areement.htm",
        "subtype": "lease",
        "kind": "filled_real",
        "licence": SEC,
    },
    {
        "source_id": "C12",
        "title": "Silver Hill Mines engagement letter",
        "url": "https://sec.gov/Archives/edgar/data/1434994/000105291810000281/ex10.htm",
        "subtype": "engagement_letter",
        "kind": "filled_real",
        "licence": SEC,
    },
]

# Design section 5: one source per contract subtype goes only to eval.
# C6 and C7 (IPO NDAs) were added on 24 Oct because C5 and C10 (SEC EDGAR) could not be fetched.
EVAL_SOURCES = {"C2", "C5", "C6", "C7", "C10"}

BY_ID = {s["source_id"]: s for s in SOURCES}
