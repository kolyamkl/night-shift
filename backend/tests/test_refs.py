import pytest

from app.domain import refs
from app.domain.extract import extract_text
from app.domain.pipeline import run_pipeline


def found(text: str) -> list[str]:
    return [sp.text for sp in refs.detect(text)]


@pytest.mark.parametrize("text, value", [
    ("Client code: CL-78892 | Matter: M/2025/856", "CL-78892"),
    ("Our ref: M/2023/218\nYour ref: 5158160/83", "M/2023/218"),
    ("registered under policy number 239-0728815-83.", "239-0728815-83"),
    ("Claim number: CLM·1173·RS", "CLM·1173·RS"),
    ("Ref. POL GN 147856", "POL GN 147856"),
    ("| Employee number | OAT8003 |", "OAT8003"),
    ("Account number: 6997 6487 7759\nBill date", "6997 6487 7759"),
    ("Tenant ID: NPM-404605 Prepared by Northgate", "NPM-404605"),
    ("(hospital reference number RX19-00937)", "RX19-00937"),
    ("CONFIRMATION: 050708509XQPDP", "050708509XQPDP"),
    ("Please quote case TEY-5513-F3.", "TEY-5513-F3"),
    ("Electricity meter serial E17Z045321, reading 018442.", "E17Z045321"),
    ("Heat meter serial HM-2209-7718, reading 3,120 kWh.", "HM-2209-7718"),
    ("MPAN: 1200023305967", "1200023305967"),
    ("Gas MPRN 7140812302", "7140812302"),
    ("Supply number 1012345678901", "1012345678901"),
    ("Serial number: SN-4471-B", "SN-4471-B"),
])
def test_a_reference_after_its_label_is_found(text, value):
    assert value in found(text)


@pytest.mark.parametrize("text", [
    "Company number: 01234567",
    "VAT reg no 123456789",
    "Invoice ref INV-2022-12345",
    "Order number 12345678",
    "Please see case 12 and Ref: 2024.",
    "Deposit amount: £1,857.69",
    "BONDARENKO REF FLAT DEPOSIT 102.06",
    "Our ref: GH/AO",
    "Date ref 12/03/2024",
    "The reference is in the letter.",
    "Meter reading 018442 on 1 September.",
    "The meter is in the hall cupboard and has a serial number on its front.",
])
def test_company_numbers_amounts_dates_and_words_stay_visible(text):
    assert found(text) == []


def test_the_pipeline_hides_a_reference_even_when_the_model_is_off():
    doc = extract_text("Tenant ID: NPM-404605. Account number: 12345678. Company number: 01234567.")
    res = run_pipeline(doc, t1=None)
    assert res.redacted_text == "Tenant ID: [CUSTOM_1]. Account number: [ACCOUNT_1]. Company number: 01234567."
    # On a tie the evalkit baseline's type wins, so a bank account stays a bank account.
    assert [(s.text, s.type) for s in res.spans] == [("NPM-404605", "CUSTOM"), ("12345678", "BANK_ACCOUNT")]
