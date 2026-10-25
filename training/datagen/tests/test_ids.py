import random

import pytest

from datagen import ids


def rngs(n=2000):
    return (random.Random(f"ids:{i}") for i in range(n))


def test_luhn_known_values():
    assert ids.luhn_ok("4539578763621486")
    assert not ids.luhn_ok("4539578763621487")
    assert ids.is_valid_card("3782 822463 10005")  # Amex test number


@pytest.mark.parametrize("scheme,length,prefixes", [("visa", 16, ("4",)), ("mastercard", 16, ("5", "2")),
                                                    ("amex", 15, ("34", "37"))])
def test_generated_cards(scheme, length, prefixes):
    for r in rngs(500):
        c = ids.card_number(r, scheme)
        assert len(c) == length and c.startswith(prefixes) and ids.luhn_ok(c)
        for st in (0, 1, 2):
            assert ids.is_valid_card(ids.format_card(c, st))


def test_iban_mod97():
    assert ids.is_valid_iban("GB82WEST12345698765432")       # published example
    assert ids.is_valid_iban("GB82 WEST 1234 5698 7654 32")
    assert not ids.is_valid_iban("GB83WEST12345698765432")
    for r in rngs(1000):
        name, code, pre = r.choice(ids.BANKS)
        sc = ids.sort_code(r, r.choice(pre))
        acct = ids.account_number(r)
        iban = ids.gb_iban(code, sc, acct)
        assert len(iban) == 22 and iban[8:14] == sc and iban[14:] == acct
        assert ids.is_valid_iban(iban) and ids.is_valid_iban(ids.format_iban(iban, True))


def test_ni_rules():
    for bad in ("DA123456A", "AD123456A", "QQ123456C", "BG123456A", "GB123456A", "NK123456A", "TN123456A",
                "ZZ123456A", "AO123456A", "AB123456E", "AB12345A"):
        assert not ids.is_valid_ni(bad), bad
    assert ids.is_valid_ni("AB 12 34 56 C")
    for r in rngs():
        ni = ids.ni_number(r)
        assert ni[0] not in "DFIQUV" and ni[1] not in "DFIQUVO" and ni[:2] not in ids.NI_BAD_PREFIX
        for st in (0, 1, 2):
            assert ids.is_valid_ni(ids.format_ni(ni, st))


def test_postcodes():
    for good in ("LS6 2AB", "M1 1AE", "SW1A 1AA", "EC1V 9HX", "W1T 3BB", "CR0 2AB", "ls62ab"):
        assert ids.is_valid_postcode(good), good
    for bad in ("LS6 2CI", "QS6 2AB", "123 4AB", "LS6"):
        assert not ids.is_valid_postcode(bad), bad
    from datagen import world
    for r in rngs(1000):
        a = world.make_address(r)
        assert ids.is_valid_postcode(a.postcode_text), a.postcode_text


def test_sort_and_account_formats():
    assert ids.is_valid_sort("20-45-77") and ids.is_valid_sort("20 45 77") and ids.is_valid_sort("204577")
    assert not ids.is_valid_sort("20-45 77")
    for r in rngs(300):
        sc = ids.sort_code(r, "20")
        for st in (0, 1, 2):
            assert ids.is_valid_sort(ids.format_sort(sc, st))
        assert ids.is_valid_account(ids.account_number(r))


def test_nhs_mod11():
    assert ids.is_valid_nhs("943 476 5919")
    assert not ids.is_valid_nhs("943 476 5918")
    for r in rngs():
        assert ids.is_valid_nhs(ids.nhs_number(r))


def test_driving_licence_structure():
    from datetime import date
    lic = ids.driving_licence(random.Random(1), "Morgan", "Sarah", "Jane", date(1965, 7, 11), True)
    assert lic.startswith("MORGA6") and lic[6:8] == "57" and lic[8:10] == "11" and lic[10] == "5"
    assert lic[11:13] == "SJ" and ids.is_valid_licence(lic) and len(lic) == 16
    lic2 = ids.driving_licence(random.Random(2), "Ó Súilleabháin", "Seán", "", date(1990, 1, 2), False)
    assert ids.is_valid_licence(lic2) and lic2[11:13] == "S9"


def test_passport_and_phones():
    for r in rngs(500):
        assert ids.is_valid_passport(ids.passport_number(r))
        nsn = ids.mobile_number(r)
        for st in range(7):
            assert ids.is_valid_phone(ids.format_mobile(nsn, st)), ids.format_mobile(nsn, st)
        for st in range(4):
            p = ids.landline_number(r, st)
            assert ids.is_valid_phone(p), p


def test_dates_formats_roundtrip():
    from datetime import date
    d = date(1987, 3, 14)
    outs = {ids.format_date(d, s) for s in range(ids.DATE_STYLES)}
    assert "14/03/1987" in outs and "14 March 1987" in outs and "1987-03-14" in outs and "14th March 1987" in outs
    assert len(outs) == ids.DATE_STYLES


def test_utr_check_digit():
    assert ids.is_valid_utr("3282497350") and ids.is_valid_utr("2234567890") and ids.is_valid_utr("9987654321K")
    assert not ids.is_valid_utr("3282497351") and not ids.is_valid_utr("328249735")
    for r in rngs(500):
        assert ids.is_valid_utr(ids.utr(r, r.random() < 0.5))


def test_vat_check_digits():
    assert ids.is_valid_vat("GB999 9999 73") and ids.is_valid_vat("GB123456782") and ids.is_valid_vat("GB100012318")
    assert not ids.is_valid_vat("GB999 9999 74")
    for r in rngs(500):
        v = ids.vat_number(r)
        for st in range(3):
            assert ids.is_valid_vat(ids.format_vat(v, st))


def test_nhs_known_test_numbers():
    for good in ("999 054 8609", "9990000018", "9990000026"):
        assert ids.is_valid_nhs(good)
    for bad in ("999 123 4567", "999 123 4566", "999 054 8608"):
        assert not ids.is_valid_nhs(bad)
