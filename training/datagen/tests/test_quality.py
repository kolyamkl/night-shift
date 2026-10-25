"""Label quality: no personal data outside gold spans (regex + name-pool audit) and PDF round trip."""
import json
import random

from datagen.audit import audit_record, name_vocab
from datagen.generate import make_doc


def test_no_unlabelled_identifiers():
    vocab = name_vocab()
    hits = []
    names = 0
    for i in range(3000):
        rec, _ = make_doc(i, 99)
        for kind, val in audit_record(rec, vocab):
            if kind == "NAME?":
                names += 1
                if val != "Shevchenko":  # 'Taras Shevchenko National University' is an institution (keep)
                    hits.append((rec["doc_id"], kind, val))
            else:
                hits.append((rec["doc_id"], kind, val))
    assert not hits, hits[:10]


def test_pdf_round_trip(tmp_path):
    from datagen.pdf import build_pdfs
    rep = build_pdfs(tmp_path, n=4, seed=5)
    assert rep["n_pdfs"] == 4
    assert rep["mismatch_rate"] <= 0.05
    gold = json.loads(next(tmp_path.glob("*.gold.json")).read_text())
    for e in gold["entities"]:
        assert gold["text"][e["start"]:e["end"]] == e["text"]
    for e in gold["extracted_entities"]:
        assert gold["extracted_text"][e["start"]:e["end"]] == e["text"]
