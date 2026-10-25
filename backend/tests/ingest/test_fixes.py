import pytest

from app.ingest import fix_identifiers


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("Leeds LS14 ITP", "Leeds LS14 1TP"),
        ("Dundee DD9ISE", "Dundee DD9 1SE"),
        ("London EC1A IBB.", "London EC1A 1BB."),
        ("London SW1P 4DF and W1A OAA", "London SW1P 4DF and W1A 0AA"),
        ("Bristol BSI4 8PT", "Bristol BS14 8PT"),
        ("London, EC4R gAN, United Kingdom", "London, EC4R 9AN, United Kingdom"),  # Georgia's old-style 9
        ("Exeter, EX1 ЗAY.", "Exeter, EX1 3AY."),  # Cyrillic Ze for the digit 3
        ("Ref: CL-4850Ѕ", "Ref: CL-4850S"),
        ("sort code 2O-45-77", "sort code 20-45-77"),
        ("IBAN GB82 WEST I234 5698 7654 32", "IBAN GB82 WEST 1234 5698 7654 32"),
        ("IBAN G882 WEST 1234 5698 7654 32", "IBAN GB82 WEST 1234 5698 7654 32"),
        ("IBAN GB7O WEST 1234 5656 9876 51", "IBAN GB70 WEST 1234 5656 9876 51"),
        ("card 4111 I111 1111 1111", "card 4111 1111 1111 1111"),
        ("NI QQ I2 34 56 C", "NI QQ 12 34 56 C"),
        ("account 4196O183", "account 41960183"),
        ("tel 07700 9OO123", "tel 07700 900123"),
        ("signed in 2O24", "signed in 2024"),
        ("email john.doe/@example.com", "email john.doe@example.com"),
        ("email jo.lee@ example.co.uk", "email jo.lee@example.co.uk"),
    ],
)
def test_lookalikes_are_repaired(before, after):
    text, fixes = fix_identifiers(before, page=3)
    assert text == after
    assert fixes and all(f.page == 3 for f in fixes)


@pytest.mark.parametrize(
    "text",
    [
        "LS14 1TP, 20-45-77, GB82 WEST 1234 5698 7654 32, QQ 12 34 56 C, 41960183",  # already right
        "SOLID GOLD OIL TANK, LION KING, ITEM 4, PO BOX 12, HELLO WORLD, BOIL ICE",
        "Illinois, OOO, 1st floor, Il Duomo, I/O port, the 1990s",
        "attachment ENA(03-02-00).doc and IO-OO-IO",  # sort-code shape with too few real digits
        "IBAN GB9I WEST 1234 5698 7654 32",  # the repaired check digits fail mod 97, so they are left alone
        "follow us @twitter and @ home",
        "Олена Коваленко and Σοφία write in their own scripts",  # no ASCII in the token: left alone
        "a gAS leak, the egg box",
    ],
)
def test_ordinary_text_and_unverifiable_runs_are_left_alone(text):
    fixed, fixes = fix_identifiers(text)
    assert fixed == text
    assert fixes == []


def test_fixes_record_kind_before_and_after():
    _, fixes = fix_identifiers("Leeds LS14 ITP, account 4196O183")
    assert [(f.kind, f.before, f.after) for f in fixes] == [
        ("postcode", "LS14 ITP", "LS14 1TP"),
        ("digits", "4196O183", "41960183"),
    ]
