"""Unit tests for the conversion helpers (no data files needed)."""
from collections import Counter

from dataconv.bitext import _list_head, classify, FIELD_BEFORE
from dataconv.common import (chunk_bounds, chunk_doc, is_dob_context, is_uk_postcode, merge_runs, person_bounds,
                             resolve_overlaps, validate_doc)
from dataconv.mapping import NAME_GAP
from dataconv.quantum import align


def test_resolve_overlaps_keeps_longer():
    log = Counter()
    spans = [{"start": 0, "end": 4, "type": "PERSON"}, {"start": 0, "end": 10, "type": "PERSON"},
             {"start": 12, "end": 15, "type": "EMAIL"}]
    out = resolve_overlaps(spans, log)
    assert [(s["start"], s["end"]) for s in out] == [(0, 10), (12, 15)]
    assert log["overlap_dropped_PERSON"] == 1


def test_merge_given_and_surname():
    text = "Dear John Smith, hi"
    spans = [{"start": 5, "end": 9, "label": "GIVENNAME"}, {"start": 10, "end": 15, "label": "SURNAME"}]
    out = merge_runs(text, spans, "label", {"GIVENNAME", "SURNAME"}, NAME_GAP)
    assert len(out) == 1 and text[out[0]["start"]:out[0]["end"]] == "John Smith"


def test_person_bounds_strip_title_and_possessive():
    t = "Mr. John Smith's car"
    s, e = person_bounds(t, 0, 16)
    assert t[s:e] == "John Smith"


def test_dob_context():
    t = "Date of Birth: 08/03/1944, appointment 12/05/2024"
    assert is_dob_context(t, 15, 25)
    assert not is_dob_context(t, 39, 49)


def test_uk_postcode():
    assert is_uk_postcode("SW1A 1AA") and is_uk_postcode("ls62ab")
    assert not is_uk_postcode("YO19") and not is_uk_postcode("90210")


def test_chunking_never_cuts_span_and_respects_max():
    para = ("word " * 300).strip()
    text = "\n\n".join([para] * 10)  # ~15k chars
    s = text.index("word", 5990)
    ents = [{"start": s, "end": s + 40, "text": text[s:s + 40], "type": "PERSON"}]
    bounds = chunk_bounds(text, ents, 6000)
    assert all(b - a <= 6000 for a, b in bounds)
    assert bounds[0][0] == 0 and bounds[-1][1] == len(text)
    for a, b in bounds:
        for e in ents:
            assert not (a < e["start"] < b < e["end"])  # never cut
    doc = {"doc_id": "x", "text": text, "entities": ents, "split": "eval", "doc_type": "t", "source": "s",
           "license": "MIT", "meta": {"mubit_ok": False}}
    chunks = chunk_doc(doc, 6000)
    assert sum(len(c["entities"]) for c in chunks) == 1
    for c in chunks:
        assert text[c["meta"]["char_start"]:c["meta"]["char_end"]] == c["text"]
        assert not validate_doc({"text": c["text"], "entities": c["entities"]})


def test_quantum_alignment_unique_and_typed():
    text = "Next of kin: Oscar Iqbal, 0161 496 0606, 113 York Avenue, Preston. PS the website is down again."
    masked = "Next of kin: [NAME], [PHONE], [ADDRESS]. PS the website is down again."
    sols = align(text, masked)
    assert len(sols) == 1
    got = [(text[a:b], t) for a, b, t in sols[0]]
    assert got == [("Oscar Iqbal", "NAME"), ("0161 496 0606", "PHONE"), ("113 York Avenue, Preston", "ADDRESS")]


def test_quantum_alignment_address_postcode_split():
    text = "Send it to 12 Hope Street, Leeds, LS6 2AB please"
    masked = "Send it to [ADDRESS], [POSTCODE] please"
    sols = align(text, masked)
    assert len(sols) == 1 and text[sols[0][1][0]:sols[0][1][1]] == "LS6 2AB"


def test_bitext_field_reference_rules():
    assert classify("Customer Support Phone Number") == ("PHONE", "PHONE")
    assert classify("Password")[0] == "LITERAL" and classify("Username")[0] == "LITERAL"
    assert classify("Order Number") == ("REF", None)  # transaction reference: keep class
    head = _list_head("please provide your {{Loan Account Number}}, {{Customer ID}} and ")
    assert FIELD_BEFORE.search(head)
