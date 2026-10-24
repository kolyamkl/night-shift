import pytest

from app import identifiers
from app.extract import extract_text
from app.pipeline import run_pipeline


def found(text: str) -> list[tuple[str, str]]:
    return [(sp.text, sp.type) for sp in identifiers.detect(text)]


@pytest.mark.parametrize("text, expected", [
    ("Logged IP Address: 64.137.54.89", [("64.137.54.89", "IP_ADDRESS")]),
    ("IP: 10.0.0.1 at login", [("10.0.0.1", "IP_ADDRESS")]),
    ("from 192.168.1.20.", [("192.168.1.20", "IP_ADDRESS")]),
    ("IPv6 2001:db8:85a3::8a2e:370:7334 seen", [("2001:db8:85a3::8a2e:370:7334", "IP_ADDRESS")]),
    ("Signature Reference: 1BA790A7-C543-4DED-8A6B-1782F7D6FDE0",
     [("1BA790A7-C543-4DED-8A6B-1782F7D6FDE0", "CUSTOM")]),
])
def test_ip_addresses_and_uuids_are_found(text, expected):
    assert found(text) == expected


@pytest.mark.parametrize("text", [
    "Clause 4.2.1.3 applies.",
    "Use version 1.2.3.4 of the form.",
    "Date Agreed: 20-08-2026 17:06:16",
    "Rent: £1,610.00 pcm",
    "Call 0113 496 0738.",
])
def test_clause_numbers_versions_times_and_amounts_stay_visible(text):
    assert found(text) == []


def test_the_pipeline_hides_them_even_when_the_model_is_off():
    doc = extract_text("Logged IP Address: 64.137.54.89\nSignature Reference: 01495D0F-8963-453D-9DE6-5087ABEA531D")
    res = run_pipeline(doc, t1=None)
    assert res.redacted_text == "Logged IP Address: [IP_ADDRESS_1]\nSignature Reference: [CUSTOM_1]"
