import random
from collections import Counter

import pytest

from datagen.build import finish
from datagen.core import ENTITY_SET
from datagen.doctypes import load_all
from datagen.validate import check_record

REG = load_all()


def test_registry_has_all_doc_types():
    expected = {"tenancy_agreement", "employment_contract", "nda", "service_agreement", "engagement_letter", "invoice",
                "utility_bill", "phone_bill", "bank_statement", "payslip", "insurance_claim_letter", "gov_letter",
                "medical_letter", "cv", "hr_form", "email_thread", "chat_messages", "support_ticket", "meeting_notes",
                "ai_prompt"}
    assert expected <= set(REG)
    assert len(REG) >= 16


@pytest.mark.parametrize("name", sorted(REG))
def test_doc_type_valid(name):
    dt = REG[name]
    types = Counter()
    for i in range(120):
        rng = random.Random(f"test:{name}:{i}")
        neg = dt.neg_weight > 0 and i % 5 == 0
        rec = finish(dt.fn(rng, neg), neg)
        rec["doc_id"] = f"{name}-{i}"
        errs = check_record(rec)
        assert not errs, errs[:3]
        if neg:
            assert rec["entities"] == []
        for e in rec["entities"]:
            assert e["type"] in ENTITY_SET
            types[e["type"]] += 1
        # spans sorted, non-overlapping
        ends = [-1] + [e["end"] for e in rec["entities"]]
        assert all(e["start"] >= p for e, p in zip(rec["entities"], ends))
    assert sum(types.values()) > 0
    assert "PERSON" in types or name in ("phone_bill",)


@pytest.mark.parametrize("name", sorted(REG))
def test_doc_type_deterministic(name):
    a = finish(REG[name].fn(random.Random("same"), False), False)
    b = finish(REG[name].fn(random.Random("same"), False), False)
    c = finish(REG[name].fn(random.Random("other"), False), False)
    assert a == b
    assert a["text"] != c["text"]


def test_hard_cases_and_keep_traps_are_planted():
    hard, keep = Counter(), Counter()
    for name, dt in REG.items():
        for i in range(60):
            rec = finish(dt.fn(random.Random(f"hk:{name}:{i}"), False), False)
            hard.update(h["kind"] for h in rec["meta"]["hard_cases"])
            keep.update(k["kind"] for k in rec["meta"]["keep_traps"])
    for k in ("common_word_name", "non_english_name", "same_person_3_ways", "multiline_address", "flat_number",
              "partial_number", "custom_org_id", "initials", "signature_name", "greeting_name", "sole_trader_name",
              "pdf_header_footer", "account_next_to_amount", "possessive", "address_in_table", "care_of_address"):
        assert hard[k] > 0, k
    for k in ("amount", "date", "public_company", "statute", "clause_number", "place_name", "common_word",
              "company_with_person_name", "doc_reference", "product"):
        assert keep[k] > 0, k
