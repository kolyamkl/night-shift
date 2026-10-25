import pytest
from conftest import FIXTURES, make_doc, write_docs

import validate_docs


def errors_for(tmp_path, docs):
    rep, _ = validate_docs.validate(write_docs(tmp_path / "docs", docs))
    return rep.errors, rep.warnings


def test_fixtures_are_valid():
    rep, docs = validate_docs.validate(FIXTURES / "docs")
    assert rep.errors == []
    assert rep.warnings == []
    assert len(docs) == 3
    assert validate_docs.main(["--docs-dir", str(FIXTURES / "docs")]) == 0


def test_bad_offsets_are_caught(tmp_path, fixture_docs):
    doc = fixture_docs[0]
    doc["entities"][0]["start"] += 1
    errors, _ = errors_for(tmp_path, [doc])
    assert any("but value is" in e for e in errors), errors


def test_offsets_outside_text(tmp_path, fixture_docs):
    doc = fixture_docs[0]
    doc["entities"][-1]["end"] = len(doc["text"]) + 5
    errors, _ = errors_for(tmp_path, [doc])
    assert any("outside text" in e for e in errors), errors


def test_overlap_is_caught(tmp_path):
    doc = make_doc("Tenant: Ann Lee of Leeds.", [("Ann Lee", "PERSON", "p1")])
    doc["entities"].append({"start": 12, "end": 18, "type": "PERSON", "value": "Lee of", "entity_id": "p2"})
    errors, _ = errors_for(tmp_path, [doc])
    assert any("overlaps the previous entity" in e for e in errors), errors


def test_unsorted_entities_are_caught(tmp_path):
    doc = make_doc("Ann Lee and Bo Tan.", [("Ann Lee", "PERSON", "p1"), ("Bo Tan", "PERSON", "p2")])
    doc["entities"].reverse()
    errors, _ = errors_for(tmp_path, [doc])
    assert any("not sorted" in e for e in errors), errors


@pytest.mark.parametrize(
    "change, message",
    [
        ({"split": "train"}, "must be 'eval'"),  # eval source R7 in train
        ({"split": "fresh"}, "must be 'eval'"),
        ({"fill": 0}, "fill 1..5"),
        ({"group": "contracts"}, "cannot be in group"),
        ({"source_id": "R99"}, "unknown source_id"),
        ({"subtype": "Letter Of Complaint"}, "lower-case slug"),
    ],
)
def test_split_and_source_rules(tmp_path, fixture_docs, change, message):
    doc = next(d for d in fixture_docs if d["source_id"] == "R7")
    doc.update(change)
    errors, _ = errors_for(tmp_path, [doc])
    assert any(message in e for e in errors), errors


def test_fill_decides_train_or_fresh(tmp_path, fixture_docs):
    doc = next(d for d in fixture_docs if d["fill"] == 4)
    doc["split"] = "train"
    errors, _ = errors_for(tmp_path, [doc])
    assert any("must be 'fresh'" in e for e in errors), errors


def test_gretel_rules(tmp_path):
    doc = make_doc("Account holder: Ann Lee.", [("Ann Lee", "PERSON", "p1")], doc_id="financial-gretel-00042",
                   source_id="gretel-00042", group="financial", subtype="bank_statement", split="eval", fill=0,
                   provenance={"url": "https://huggingface.co/datasets/gretelai/synthetic_pii_finance_multilingual",
                               "licence": "Apache-2.0", "kind": "synthetic"})
    errors, _ = errors_for(tmp_path, [doc])
    assert errors == []
    doc["fill"] = 1
    errors, _ = errors_for(tmp_path, [doc])
    assert any("fill 0" in e for e in errors), errors


def test_duplicate_doc_id_and_fill(tmp_path, fixture_docs):
    doc = fixture_docs[0]
    errors, _ = errors_for(tmp_path, [doc, doc])
    assert any("duplicate doc_id" in e for e in errors), errors
    assert any("fill 1 already used" in e for e in errors), errors


def test_leftover_slot_marker(tmp_path):
    doc = make_doc("Landlord: {{landlord_name}}. Tenant: Ann Lee.", [("Ann Lee", "PERSON", "p1")])
    errors, _ = errors_for(tmp_path, [doc])
    assert any("leftover slot marker" in e for e in errors), errors


def test_placeholder_like_text_in_input(tmp_path):
    doc = make_doc("Tenant: [Person_1] and Ann Lee.", [("Ann Lee", "PERSON", "p1")])
    errors, _ = errors_for(tmp_path, [doc])
    assert any("placeholder-like token" in e for e in errors), errors


def test_labelling_rules(tmp_path):
    doc = make_doc("Write to ann@example.com about Patel's flat.", [("Patel's", "PERSON", "p1")])
    errors, _ = errors_for(tmp_path, [doc])
    assert any("email address 'ann@example.com'" in e for e in errors), errors
    assert any("possessive" in e for e in errors), errors

    doc = make_doc("Ann Lee, ann@example.com", [("Ann Lee", "PERSON", "x"), ("ann@example.com", "EMAIL", "x")])
    errors, _ = errors_for(tmp_path, [doc])
    assert any("used with several types" in e for e in errors), errors

    doc = make_doc("Type test: Ann Lee.", [("Ann Lee", "NAME", "p1")])
    errors, _ = errors_for(tmp_path, [doc])
    assert any("unknown type 'NAME'" in e for e in errors), errors


def test_unlabelled_structured_values_warn(tmp_path):
    doc = make_doc("Ann Lee can be reached on 07700 900456, NI number QQ 11 22 33 B.", [("Ann Lee", "PERSON", "p1")])
    errors, warnings = errors_for(tmp_path, [doc])
    assert errors == []
    assert any("PHONE" in w for w in warnings), warnings
    assert any("NI_NUMBER" in w for w in warnings), warnings


def test_main_exit_code(tmp_path, fixture_docs):
    fixture_docs[0]["entities"][0]["end"] += 2
    docs_dir = write_docs(tmp_path / "docs", fixture_docs)
    assert validate_docs.main(["--docs-dir", str(docs_dir)]) == 1
    assert validate_docs.main(["--docs-dir", str(tmp_path / "empty")]) == 1
