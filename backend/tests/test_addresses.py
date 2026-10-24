import pytest
from evalkit.spans import Span

from app.addresses import expand
from app.extract import extract_text
from app.pipeline import T1Result, run_pipeline


def widened(text: str, *parts: tuple[str, str]) -> list[tuple[str, str]]:
    spans = []
    for value, etype in parts:
        start = text.index(value)
        spans.append(Span(start, start + len(value), etype, value))
    return [(s.text, s.type) for s in expand(text, sorted(spans, key=lambda s: s.start))]


def test_flat_building_and_town_join_the_street_the_model_hid():
    text = "Relating to: Flat 3306, Amory Tower, 203 Marsh Wall, London, E14 9SE"
    assert widened(text, ("203 Marsh Wall", "ADDRESS"), ("E14 9SE", "POSTCODE")) == [
        ("Flat 3306, Amory Tower, 203 Marsh Wall, London", "ADDRESS"), ("E14 9SE", "POSTCODE")]


def test_an_address_over_several_lines_is_taken_in_whole():
    text = "Flat 4\n78 St Mary's Gardens\nHackney\nLONDON\nEC1M 0XJ"
    assert widened(text, ("78 St Mary's Gardens", "ADDRESS"), ("EC1M 0XJ", "POSTCODE")) == [
        ("Flat 4\n78 St Mary's Gardens\nHackney\nLONDON", "ADDRESS"), ("EC1M 0XJ", "POSTCODE")]


@pytest.mark.parametrize("text, parts, expected", [
    # a role after the address, with no postcode after it
    ("Ms Jo Smith, 4 Oak Road, Landlord", [("Jo Smith", "PERSON"), ("4 Oak Road", "ADDRESS")],
     [("Jo Smith", "PERSON"), ("4 Oak Road", "ADDRESS")]),
    # a label before the address stays visible
    ("Property: 4 Oak Road, Leeds LS6 2AB", [("4 Oak Road", "ADDRESS"), ("LS6 2AB", "POSTCODE")],
     [("4 Oak Road, Leeds", "ADDRESS"), ("LS6 2AB", "POSTCODE")]),
    # a place name that is not a building, and no blank line is crossed
    ("the communal Rose Garden, 4 Oak Road", [("4 Oak Road", "ADDRESS")], [("4 Oak Road", "ADDRESS")]),
    ("Flat 2\n\n4 Oak Road", [("4 Oak Road", "ADDRESS")], [("4 Oak Road", "ADDRESS")]),
])
def test_what_is_not_part_of_the_address_stays_visible(text, parts, expected):
    assert widened(text, *parts) == expected


def test_an_address_the_model_missed_is_read_back_from_its_postcode():
    text = "Virginia Power Energy Marketing, Inc., Level 12, 98 Mill Close, Oxford OX7 4FR"
    assert widened(text, ("OX7 4FR", "POSTCODE")) == [
        ("Level 12, 98 Mill Close, Oxford", "ADDRESS"), ("OX7 4FR", "POSTCODE")]


def test_a_postcode_without_a_street_before_it_hides_only_the_postcode():
    assert widened("Registered office: London EC1A 1BB", ("EC1A 1BB", "POSTCODE")) == [("EC1A 1BB", "POSTCODE")]


def test_the_pipeline_widens_the_model_address():
    doc = extract_text("Relating to: Flat 3306, Amory Tower, 203 Marsh Wall, London, E14 9SE")
    res = run_pipeline(doc, t1=lambda chunk: T1Result([{"text": "203 Marsh Wall", "type": "ADDRESS"}], "mreq_1", None))
    assert res.redacted_text == "Relating to: [ADDRESS_1], [POSTCODE_1]"
