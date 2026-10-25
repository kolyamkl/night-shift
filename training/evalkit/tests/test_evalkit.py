from evalkit import providers, redact, regex_baseline
from evalkit.rewrite import spans_from_rewrite
from evalkit.score import pred_spans
from evalkit.team_docs import to_chunks
from evalkit.prompts import T1_SYSTEM_PROMPT
from evalkit.score import score_records
from evalkit.send_batch import build_request, is_mubit_safe, parse_entities
from evalkit.spans import locate


def test_locate_finds_every_occurrence_and_prefers_longer_values():
    text = "Oleksandra Kovalenko signed. Later Kovalenko paid. Kovalenko again."
    spans = locate(text, [{"text": "Kovalenko", "type": "PERSON"}, {"text": "Oleksandra Kovalenko", "type": "PERSON"}])
    assert [s.text for s in spans] == ["Oleksandra Kovalenko", "Kovalenko", "Kovalenko"]


def test_locate_is_whitespace_and_comma_flexible_and_word_bounded():
    text = "Flat 3\n12 Oak Road\nLeeds\nWill is willing."
    spans = locate(text, [{"text": "Flat 3, 12 Oak Road, Leeds", "type": "ADDRESS"}, {"text": "Will", "type": "PERSON"}])
    assert spans[0].text == "Flat 3\n12 Oak Road\nLeeds"
    assert [s.text for s in spans if s.type == "PERSON"] == ["Will"]  # not inside "willing"


def test_redact_is_consistent_and_restores_exact_and_tolerant_forms():
    text = "Pay Jo Smith from account 12345678. Jo Smith agreed."
    vault = redact.Vault()
    spans = locate(text, [{"text": "Jo Smith", "type": "PERSON"}, {"text": "12345678", "type": "BANK_ACCOUNT"}])
    red = redact.apply(text, spans, vault)
    assert red == "Pay [PERSON_1] from account [ACCOUNT_1]. [PERSON_1] agreed."
    restored, unknown = redact.restore("Yes, PERSON 1 owns [ACCOUNT_1]. [PERSON_7] is unknown.", vault)
    assert restored.startswith("Yes, Jo Smith owns 12345678.")
    assert "[PERSON_7]" in unknown


def test_regex_baseline_finds_uk_identifiers():
    text = ("IBAN GB82 WEST 1234 5698 7654 32, sort code 20-45-77, account no 31926819, "
            "NI number AB 12 34 56 C, postcode LS6 2AB, call 07700 900123, mail jo@example.com")
    types = {e["type"] for e in regex_baseline.predict(text)}
    assert {"IBAN", "SORT_CODE", "BANK_ACCOUNT", "NI_NUMBER", "POSTCODE", "PHONE", "EMAIL"} <= types


def test_score_counts_leaks_partial_hides_and_keep_traps():
    gold = [{
        "doc_id": "syn-1", "chunk_id": "syn-1-c00",
        "text": "Jo Smith owes £20 at Flat 3, 12 Oak Road.",
        "entities": [
            {"start": 0, "end": 8, "text": "Jo Smith", "type": "PERSON"},
            {"start": 21, "end": 40, "text": "Flat 3, 12 Oak Road", "type": "ADDRESS"},
        ],
        "meta": {"keep_traps": [{"start": 14, "end": 17, "text": "£20", "kind": "amount"}]},
    }]
    preds = {"syn-1-c00": [{"text": "Jo Smith", "type": "PERSON"}, {"text": "12 Oak Road", "type": "ADDRESS"},
                            {"text": "£20", "type": "CUSTOM"}]}
    r = score_records(gold, preds)
    assert r["leaked_values"] == 1  # the address is only partly hidden
    assert r["per_type"]["PERSON"]["recall_strict"] == 1.0
    assert r["per_type"]["ADDRESS"]["recall_partial"] == 1.0
    assert r["keep_trap_hit_rate"] == 1.0
    assert r["zero_leak_docs"] == 0.0


def test_send_batch_safety_and_request_shape():
    assert is_mubit_safe({"doc_id": "syn-000001"})
    assert is_mubit_safe({"doc_id": "x", "meta": {"mubit_ok": True}})
    assert not is_mubit_safe({"doc_id": "tab-1", "meta": {"mubit_ok": False}})
    assert not is_mubit_safe({"doc_id": "x"})
    req = build_request({"doc_id": "syn-1", "text": "hello"}, "gpt-6-luna", None, None)
    assert req["messages"][0]["content"] == T1_SYSTEM_PROMPT
    assert req["metadata"] == {"session_id": "doc-syn-1"}
    assert "temperature" not in req
    assert parse_entities('{"entities": [{"text": "Jo", "type": "PERSON"}]}') == ([{"text": "Jo", "type": "PERSON"}], False)
    assert parse_entities("not json")[1] is True


def test_rewrite_answers_become_exact_spans():
    original = "Dear Mr Patel,\nyour account 31926819 is open. Patel's card ends 4821."
    answer = "Dear [PERSON_1],\nyour account [BANK_ACCOUNT_1] is open. [PERSON_1]'s card ends [CARD_1]."
    spans, changed = spans_from_rewrite(original, answer)
    texts = [(s.text, s.type) for s in spans]
    assert ("31926819", "BANK_ACCOUNT") in texts and ("4821", "CARD") in texts
    assert any(t.endswith("Patel") for t, _ in texts)
    assert changed == 0
    # Exact spans are scored as given, not expanded to every occurrence.
    scored = pred_spans(original, {"spans": [{"start": s.start, "end": s.end, "type": s.type} for s in spans]})
    assert len(scored) == len(spans)


def test_rewrite_counts_text_changed_outside_placeholders():
    spans, changed = spans_from_rewrite("Pay Jo Smith now.", "Please pay [PERSON_1] now.")
    assert [s.text for s in spans] == ["Jo Smith"]
    assert changed > 0


def test_provider_routing():
    assert providers.provider_for("claude-haiku-4-5") == "anthropic"
    assert providers.provider_for("gemini-3.8-flash") == "gemini"
    assert providers.provider_for("gpt-6-luna") == "openai"


def test_team_docs_chunking_keeps_spans_whole():
    text = ("Tenant: Raj Patel\n\n" + "Clause text. " * 400 + "\n\nSigned Raj Patel, 12 Oak Road")
    s1 = text.index("Raj Patel")
    s2 = text.rindex("Raj Patel")
    s3 = text.index("12 Oak Road")
    doc = {"doc_id": "contracts-C1-f1", "source_id": "C1", "group": "contracts", "split": "eval", "text": text,
           "entities": [{"start": s1, "end": s1 + 9, "type": "PERSON", "value": "Raj Patel", "entity_id": "p"},
                        {"start": s2, "end": s2 + 9, "type": "PERSON", "value": "Raj Patel", "entity_id": "p"},
                        {"start": s3, "end": s3 + 11, "type": "ADDRESS", "value": "12 Oak Road", "entity_id": "a"}]}
    chunks = to_chunks(doc)
    assert len(chunks) >= 2
    assert sum(len(c["entities"]) for c in chunks) == 3
    assert all(c["meta"]["mubit_ok"] and c["doc_id"] == "team-contracts-C1-f1" for c in chunks)
