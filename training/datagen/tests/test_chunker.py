import random

from datagen.build import finish
from datagen.chunker import chunk_doc, find_cuts
from datagen.doctypes import load_all
from datagen.validate import check_chunk

REG = load_all()


def _doc(name, i, neg=False):
    rec = finish(REG[name].fn(random.Random(f"chunk:{name}:{i}"), neg), neg)
    rec.update(doc_id=f"d{i}", split="train")
    return rec


def _check(doc, chunks, max_chars):
    assert sum(len(c["entities"]) for c in chunks) == len(doc["entities"])
    prev_end = 0
    for k, c in enumerate(chunks):
        assert len(c["text"]) <= max_chars
        assert c["chunk_id"] == f"{doc['doc_id']}-c{k:02d}"
        assert not check_chunk(c, doc)
        a, b = c["meta"]["char_start"], c["meta"]["char_end"]
        assert a >= prev_end and doc["text"][prev_end:a].strip() == ""  # nothing but whitespace dropped
        prev_end = b
        for e in doc["entities"]:  # no span crosses a boundary
            assert not (e["start"] < a < e["end"]) and not (e["start"] < b < e["end"])
    assert doc["text"][prev_end:].strip() == ""


def test_long_documents_split_without_cutting_spans():
    for name in ("tenancy_agreement", "bank_statement", "employment_contract", "engagement_letter"):
        for i in range(25):
            doc = _doc(name, i)
            for max_chars in (6000, 1500, 600):
                chunks = chunk_doc(doc, max_chars)
                _check(doc, chunks, max_chars)
                if len(doc["text"]) > max_chars:
                    assert len(chunks) > 1


def test_short_documents_single_chunk():
    for i in range(50):
        doc = _doc("ai_prompt", i, neg=i % 4 == 0)
        chunks = chunk_doc(doc)
        assert len(chunks) == 1
        a = chunks[0]["meta"]["char_start"]
        assert chunks[0]["entities"] == [{"start": e["start"] - a, "end": e["end"] - a, "text": e["text"],
                                          "type": e["type"]} for e in doc["entities"]]
        assert chunks[0]["meta"]["negative"] == (not doc["entities"])


def test_hard_cut_falls_back_to_span_start():
    # no whitespace at all near the limit: the cut must move to the start of the span it would split
    text = "a" * 40 + "BBBBBBBBBBBBBBBBBBBB" + "c" * 40
    cuts = find_cuts(text, [(40, 60)], max_chars=50)
    assert cuts[0] == (0, 40)
    assert all(not (40 < x < 60) for ab in cuts for x in ab)


def test_boundary_moves_when_span_would_be_cut():
    text = "x" * 50 + " " + "A" * 10 + "\nB" * 5 + " tail"
    spans = [(51, 71)]  # a multi-line span around the only separators
    cuts = find_cuts(text, spans, max_chars=60)
    for a, b in cuts:
        assert not (51 < a < 71) and not (51 < b < 71)
    assert "".join(text[a:b] for a, b in cuts).replace(" ", "") == text.replace(" ", "")
