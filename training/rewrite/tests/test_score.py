import json

import pytest
from conftest import FIXTURES, make_doc

import build_chunks
import score


@pytest.fixture(scope="module")
def fixture_chunks(tmp_path_factory):
    out = tmp_path_factory.mktemp("chunks")
    assert build_chunks.main(["--docs-dir", str(FIXTURES / "docs"), "--out-dir", str(out)]) == 0
    return {s: [json.loads(line) for line in (out / f"{s}.jsonl").read_text().splitlines()] for s in ("train", "fresh", "eval")}


def one_chunk(text, marks):
    [chunk] = build_chunks.chunk_document(make_doc(text, marks))
    return chunk


def test_train_fixture_missed_entity_and_malformed_placeholder(fixture_chunks):
    r = score.score_split(fixture_chunks["train"], FIXTURES / "results" / "train.jsonl")
    o = r["overall"]
    assert (o["gold"], o["detected"], o["pred"], o["over_redacted"], o["leaked"]) == (12, 11, 11, 0, 1)
    assert o["recall"] == pytest.approx(11 / 12, abs=1e-4)
    assert o["precision"] == 1.0
    assert o["leak_rate"] == pytest.approx(1 / 12, abs=1e-4)
    assert r["per_type"]["CUSTOM"] == {
        "gold": 1, "recalled": 0, "recall": 0.0, "pred": 0, "correct_pred": 0, "precision": None, "leaked": 1, "leak_rate": 1.0,
    }
    assert r["per_type"]["PERSON"]["recall"] == 1.0  # [Person 1] still counts
    assert r["leaks"] == [{"chunk_id": "contracts-C3-f1-c000", "type": "CUSTOM", "value": "EMP-55821"}]
    assert r["malformed_placeholders"] == {"[Person 1]": 1}
    assert r["documents"]["zero_leaks"] == 0 and r["documents"]["with_leaks"] == ["contracts-C3-f1"]
    # The failed first attempt is superseded by the later successful row.
    assert r["chunks_failed"] == [] and r["chunks_scored"] == 1
    assert r["changed_outside_placeholders"] == []
    # "[ADDRESS_1] [POSTCODE_1]" for a two-line address plus postcode still lands on the right spans.
    assert r["per_type"]["ADDRESS"]["precision"] == 1.0 and r["per_type"]["POSTCODE"]["precision"] == 1.0


def test_fresh_fixture_is_perfect(fixture_chunks):
    r = score.score_split(fixture_chunks["fresh"], FIXTURES / "results" / "fresh.jsonl")
    o = r["overall"]
    assert (o["recall"], o["precision"], o["leak_rate"], o["char_coverage"]) == (1.0, 1.0, 0.0, 1.0)
    assert r["documents"]["zero_leaks"] == 1
    assert r["numbering_consistent_chunks"] == 1


def test_eval_fixture_over_redaction(fixture_chunks):
    r = score.score_split(fixture_chunks["eval"], FIXTURES / "results" / "eval.jsonl")
    o = r["overall"]
    assert (o["gold"], o["pred"], o["over_redacted"], o["leaked"]) == (11, 14, 2, 0)
    assert o["recall"] == 1.0
    assert o["precision"] == pytest.approx(12 / 14, abs=1e-4)
    assert r["per_type"]["PERSON"]["precision"] == 0.8
    assert r["per_type"]["DOB"]["precision"] == 0.5
    assert [(x["type"], x["text"]) for x in r["over_redactions_looking_personal"]] == [("PERSON", "Rose Garden")]
    assert sorted(x["text"] for x in r["over_redactions"]) == ["12 October 2026", "Rose Garden"]
    assert r["documents"]["zero_leaks"] == 1


def test_main_writes_json_and_markdown(fixture_chunks, tmp_path):
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    for split, rows in fixture_chunks.items():
        (chunks_dir / f"{split}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    out = tmp_path / "scores"
    assert score.main(["--chunks-dir", str(chunks_dir), "--results-dir", str(FIXTURES / "results"), "--out-dir", str(out)]) == 0
    for split in ("train", "fresh", "eval"):
        assert json.loads((out / f"score-{split}.json").read_text())["chunks_scored"] == 1
        assert (out / f"score-{split}.md").read_text().startswith(f"# T1 score: {split}")


@pytest.mark.parametrize("variant", ["[PERSON_1]", "[PERSON 1]", "[Person_1]", "[person-1]", "[PERSON]", "[ PERSON_7 ]"])
def test_placeholder_variations_are_tolerated(variant):
    chunk = one_chunk("Contact Raj Patel today.", [("Raj Patel", "PERSON", "p1")])
    s = score.score_chunk(chunk, f"Contact {variant} today.")
    assert s["gold"][0]["type_match"] and not s["gold"][0]["leaked"]
    assert s["changed_chars"] == 0


def test_unknown_placeholder_type_hides_but_does_not_match():
    chunk = one_chunk("Contact Raj Patel today.", [("Raj Patel", "PERSON", "p1")])
    s = score.score_chunk(chunk, "Contact [NAME_1] today.")
    assert s["gold"][0]["detected"] and not s["gold"][0]["type_match"]
    assert s["preds"][0]["type"] == "OTHER:NAME"


def test_ambiguous_cut_prefers_key_boundaries():
    chunk = one_chunk("Send to 12 Oak Road, Leeds LS1 4AB now.", [("12 Oak Road, Leeds", "ADDRESS", "a1"), ("LS1 4AB", "POSTCODE", "pc1")])
    s = score.score_chunk(chunk, "Send to [ADDRESS_1] [POSTCODE_1] now.")
    assert [(p["type"], p["text"]) for p in s["preds"]] == [("ADDRESS", "12 Oak Road, Leeds"), ("POSTCODE", "LS1 4AB")]


def test_text_changed_outside_placeholders_is_reported():
    chunk = one_chunk("Dear Ann Lee,\n\nThe rent of £900 is due on 1 May 2026. Call 07700 900321.",
                      [("Ann Lee", "PERSON", "p1"), ("07700 900321", "PHONE", "ph1")])
    out = "Here is the redacted chunk:\n\nDear [PERSON_1],\n\nThe rent of £900 is due on 1st May 2026. Call [PHONE_1]."
    s = score.score_chunk(chunk, out)
    assert s["changed_chars"] > 0
    assert all(g["type_match"] for g in s["gold"])
    assert not [p for p in s["preds"] if not p["overlaps_gold"]]


def test_straightened_quotes_are_not_a_change():
    chunk = one_chunk("The Tenant’s deposit (“the Deposit”) is held for Siobhán O’Brien.",
                      [("Siobhán O’Brien", "PERSON", "p1")])
    s = score.score_chunk(chunk, "The Tenant's deposit (\"the Deposit\") is held for [PERSON_1].")
    assert s["changed_chars"] == 0
    assert s["gold"][0]["type_match"] and s["gold"][0]["covered_chars"] == s["gold"][0]["chars"]
    # A leak is still caught when the output straightens the quote inside the value.
    leaked = score.score_chunk(chunk, "The Tenant's deposit (\"the Deposit\") is held for Siobhán O'Brien.")
    assert leaked["gold"][0]["leaked"]


def test_leak_check_uses_word_boundaries():
    chunk = one_chunk("Signed: Jo. Job title: manager.", [("Jo", "PERSON", "p1")])
    assert not score.score_chunk(chunk, "Signed: [PERSON_1]. Job title: manager.")["gold"][0]["leaked"]
    assert score.score_chunk(chunk, "Signed: Jo. Job title: manager.")["gold"][0]["leaked"]


def test_only_failed_rows(tmp_path):
    chunk = one_chunk("Contact Raj Patel today.", [("Raj Patel", "PERSON", "p1")])
    results = tmp_path / "train.jsonl"
    results.write_text(json.dumps({"chunk_id": chunk["chunk_id"], "output": None, "error": "HTTP 500"}) + "\n")
    r = score.score_split([chunk], results)
    assert r["chunks_failed"] == [chunk["chunk_id"]] and r["chunks_scored"] == 0 and r["chunks_missing"] == 0


def test_looks_personal():
    assert score.looks_personal("Rose Garden")
    assert score.looks_personal("CL-20931")
    assert score.looks_personal("SW1A 1AA")
    assert not score.looks_personal("£2,450.00")
    assert not score.looks_personal("12 October 2026")
    assert not score.looks_personal("the tenant")
