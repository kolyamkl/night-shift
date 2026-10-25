import json

import pytest
from conftest import FIXTURES, make_doc, write_docs

import build_chunks
from dataset_common import estimate_tokens


def check_chunks(doc, chunks, limit):
    placed = []
    for ch in chunks:
        assert doc["text"][ch["doc_start"]:ch["doc_start"] + len(ch["text"])] == ch["text"]
        assert ch["text"] == ch["text"].strip()
        assert ch["est_tokens"] == estimate_tokens(ch["text"]) <= limit
        for ent in ch["entities"]:
            assert ch["text"][ent["start"]:ent["end"]] == ent["value"]
            placed.append((ent["start"] + ch["doc_start"], ent["end"] + ch["doc_start"], ent["entity_id"]))
    assert placed == [(e["start"], e["end"], e["entity_id"]) for e in doc["entities"]]


@pytest.mark.parametrize("limit", [20, 30, 45, 60, 100, 1000])
def test_never_splits_an_entity_and_respects_the_limit(fixture_docs, limit):
    for doc in fixture_docs:
        chunks = build_chunks.chunk_document(doc, limit)
        check_chunks(doc, chunks, limit)
        if limit == 1000:
            assert len(chunks) == 1


def test_entity_across_a_paragraph_break_keeps_its_paragraphs_together():
    text = "Opening words here.\n\nSend it to Flat 3\n\nRiver House now.\n\nClosing words here."
    doc = make_doc(text, [("Flat 3\n\nRiver House", "ADDRESS", "a1")])
    chunks = build_chunks.chunk_document(doc, 5)
    assert any("Flat 3\n\nRiver House" in c["text"] for c in chunks)
    assert sum(len(c["entities"]) for c in chunks) == 1


def test_long_paragraph_splits_on_sentences():
    sentences = [f"Sentence number {i} says something about the tenancy terms." for i in range(10)]
    doc = make_doc(" ".join(sentences), [])
    chunks = build_chunks.chunk_document(doc, 40)
    assert len(chunks) > 1
    for ch in chunks:
        assert ch["text"].endswith(".")
        assert ch["est_tokens"] <= 40
    assert " ".join(c["text"] for c in chunks) == doc["text"]


def test_placeholder_numbering_by_entity_id():
    text = "Raj Patel met Ann Lee at 4 Oak Road. Mr Patel paid. R. Patel and Ann left. Email raj@example.com."
    doc = make_doc(text, [
        ("Raj Patel", "PERSON", "p1"), ("Ann Lee", "PERSON", "p2"), ("4 Oak Road", "ADDRESS", "a1"),
        ("Mr Patel", "PERSON", "p1"), ("R. Patel", "PERSON", "p1"), ("Ann", "PERSON", "p2"),
        ("raj@example.com", "EMAIL", "e1"),
    ])
    [chunk] = build_chunks.chunk_document(doc)
    assert chunk["expected_redacted"] == (
        "[PERSON_1] met [PERSON_2] at [ADDRESS_1]. [PERSON_1] paid. [PERSON_1] and [PERSON_2] left. Email [EMAIL_1]."
    )


def test_numbering_restarts_in_every_chunk_and_keeps_line_breaks():
    text = "Tenant: Ann Lee, Flat 2\n  Leeds.\n\n" + "Plain clause text. " * 12 + "\n\nSigned by Bo Tan and Ann Lee's agent."
    doc = make_doc(text, [
        ("Ann Lee", "PERSON", "p1"), ("Flat 2\n  Leeds", "ADDRESS", "a1"),
        ("Bo Tan", "PERSON", "p2"), ("Ann Lee", "PERSON", "p1"),
    ])
    chunks = build_chunks.chunk_document(doc, 30)
    assert chunks[0]["expected_redacted"] == "Tenant: [PERSON_1], [ADDRESS_1]\n  [ADDRESS_1]."
    assert chunks[-1]["expected_redacted"] == "Signed by [PERSON_1] and [PERSON_2]'s agent."


def test_dedup_of_empty_chunks(fixture_docs):
    by_split, stats = build_chunks.build(fixture_docs, 60)
    clean = [c for s in by_split.values() for c in s if not c["entities"]]
    assert clean, "the fixtures should produce chunks without personal data at this limit"
    assert all(c["fill"] == 1 for c in clean)
    assert len({(c["source_id"], c["text"]) for c in clean}) == len(clean)
    assert not [c for c in by_split["fresh"] if not c["entities"]]
    assert sum(stats["dropped"].values()) == 4
    # The clause run is long enough to be chunked on its own, so fill 1 and fill 4 cut it identically.
    f1 = [c["text"] for c in build_chunks.chunk_document(fixture_docs[0], 60) if not c["entities"]]
    f4 = [c["text"] for c in build_chunks.chunk_document(fixture_docs[1], 60) if not c["entities"]]
    assert set(f1) >= set(f4) and f4


def test_dedup_keeps_new_text_and_other_sources():
    base = "Ann Lee rents the flat.\n\nThe rent is due monthly."
    f1 = make_doc(base, [("Ann Lee", "PERSON", "p1")], doc_id="contracts-C1-f1", fill=1)
    f2 = make_doc(base.replace("Ann Lee", "Bo Tan") + "\n\nPets are allowed.", [("Bo Tan", "PERSON", "p1")],
                  doc_id="contracts-C1-f2", fill=2)
    other = make_doc(base, [("Ann Lee", "PERSON", "p1")], doc_id="contracts-C3-f1", source_id="C3", subtype="employment")
    by_split, stats = build_chunks.build([f2, other, f1], 8, keep_empty_variants=True)
    texts = [(c["doc_id"], c["text"]) for c in by_split["train"] if not c["entities"]]
    assert texts == [
        ("contracts-C1-f1", "The rent is due monthly."),
        ("contracts-C1-f2", "Pets are allowed."),
        ("contracts-C3-f1", "The rent is due monthly."),
    ]
    assert sum(stats["dropped"].values()) == 1


def test_dedup_default_keeps_empty_chunks_from_first_fill_only():
    base = "Ann Lee rents the flat.\n\nThe rent is due monthly."
    f1 = make_doc(base, [("Ann Lee", "PERSON", "p1")], doc_id="contracts-C1-f1", fill=1)
    f2 = make_doc(base.replace("Ann Lee", "Bo Tan").replace("due monthly", "due each month"),
                  [("Bo Tan", "PERSON", "p1")], doc_id="contracts-C1-f2", fill=2)
    other = make_doc(base, [("Ann Lee", "PERSON", "p1")], doc_id="contracts-C3-f1", source_id="C3", subtype="employment")
    by_split, stats = build_chunks.build([f2, other, f1], 8)
    texts = [(c["doc_id"], c["text"]) for c in by_split["train"] if not c["entities"]]
    assert texts == [
        ("contracts-C1-f1", "The rent is due monthly."),
        ("contracts-C3-f1", "The rent is due monthly."),
    ]
    assert sum(stats["dropped"].values()) == 1
    assert [c["doc_id"] for c in by_split["train"] if c["entities"]] == [
        "contracts-C1-f1", "contracts-C1-f2", "contracts-C3-f1"]


def test_main_writes_three_files(tmp_path, capsys):
    out = tmp_path / "chunks"
    assert build_chunks.main(["--docs-dir", str(FIXTURES / "docs"), "--out-dir", str(out)]) == 0
    rows = {s: [json.loads(line) for line in (out / f"{s}.jsonl").read_text().splitlines()] for s in ("train", "fresh", "eval")}
    assert [len(rows[s]) for s in ("train", "fresh", "eval")] == [1, 1, 1]
    assert set(rows["train"][0]) == {
        "chunk_id", "doc_id", "source_id", "group", "subtype", "split", "fill", "chunk_index",
        "doc_start", "text", "entities", "expected_redacted", "est_tokens",
    }
    assert "entity type" in capsys.readouterr().out


def test_main_refuses_invalid_docs(tmp_path, fixture_docs):
    fixture_docs[0]["entities"][0]["start"] += 1
    docs_dir = write_docs(tmp_path / "docs", fixture_docs)
    assert build_chunks.main(["--docs-dir", str(docs_dir), "--out-dir", str(tmp_path / "out")]) == 1
    assert not (tmp_path / "out").exists()
