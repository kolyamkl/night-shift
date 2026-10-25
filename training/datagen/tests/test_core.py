import pytest

from datagen.build import finish, skeleton
from datagen.core import HC, Doc, E, K, fmt, render


def test_render_offsets_and_regions():
    atoms = fmt("Dear {t} {name},\nYour rent of {amt} is due. Address: {addr}", t="Mr",
                name=E("Patel", "PERSON", "p1"), amt=K("£950.00", "amount"),
                addr=HC("multiline_address", E("12 Oak Road\nLeeds", "ADDRESS"), "\n", E("LS6 2AB", "POSTCODE")))
    text, ents, hard, keep, refs = render(atoms)
    for e in ents:
        assert text[e["start"]:e["end"]] == e["text"]
    assert [e["type"] for e in ents] == ["PERSON", "ADDRESS", "POSTCODE"]
    assert "Mr" not in ents[0]["text"]
    assert keep[0]["text"] == "£950.00" and text[keep[0]["start"]:keep[0]["end"]] == "£950.00"
    reg = [h for h in hard if h["kind"] == "multiline_address"][0]
    assert text[reg["start"]:reg["end"]] == "12 Oak Road\nLeeds\nLS6 2AB"
    assert refs == ["p1", None, None]


def test_padded_entity_rejected():
    with pytest.raises(ValueError):
        render([E(" Patel", "PERSON")])
    with pytest.raises(ValueError):
        E("x", "NAME")


def test_same_person_three_ways_and_negative_guard():
    d = Doc("t", "t/v1")
    d.add(E("Oleksandra Kovalenko", "PERSON", "p1"), " ... Ms ", E("Kovalenko", "PERSON", "p1"), " ... ",
          E("Oleksandra", "PERSON", "p1"), " ... ", E("Jo", "PERSON", "p2"))
    rec = finish(d, negative=False)
    kinds = [h for h in rec["meta"]["hard_cases"] if h["kind"] == "same_person_3_ways"]
    assert len(kinds) == 3
    d2 = Doc("t", "t/v1")
    d2.add("no pii here but ", E("Jo", "PERSON"))
    with pytest.raises(ValueError):
        finish(d2, negative=True)


def test_skeleton_masks_entities():
    text = "Call Jo on 07700 900123 about £12.50"
    ents = [{"start": 5, "end": 7, "text": "Jo", "type": "PERSON"},
            {"start": 11, "end": 23, "text": "07700 900123", "type": "PHONE"}]
    assert skeleton(text, ents) == "call <person> on <phone> about £00.00"
