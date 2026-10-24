from app.extract import extract_pdf, extract_text
from app.pipeline import T1Result, chunk_ranges, rebuild, run_pipeline


def model_finds(*values):
    """A stand-in for the T1 model: reports the given (text, type) pairs when they are in the chunk."""
    calls = []

    def t1(chunk: str) -> T1Result:
        calls.append(chunk)
        ents = [{"text": v, "type": t} for v, t in values if v in chunk]
        return T1Result(entities=ents, mreq_id=f"mreq_{len(calls)}", error=None)

    t1.calls = calls
    return t1


def test_regex_hits_are_kept_even_when_the_model_misses_them():
    doc = extract_text("Pay sort code 20-45-77 now.")
    res = run_pipeline(doc, t1=model_finds())
    assert [(s.text, s.type) for s in res.spans] == [("20-45-77", "SORT_CODE")]
    assert res.redacted_text == "Pay sort code [SORT_CODE_1] now."


def test_a_value_found_in_one_chunk_is_hidden_everywhere():
    text = "Tenant: Raj Patel.\n\n" + ("Clause text. " * 400) + "\n\nSigned: Raj Patel"
    doc = extract_text(text)
    t1 = model_finds(("Raj Patel", "PERSON"))
    t1_only_first = lambda chunk: t1(chunk) if "Tenant" in chunk else T1Result([], "mreq_x", None)  # noqa: E731
    res = run_pipeline(doc, t1=t1_only_first, max_chars=2000)
    assert len(res.chunks) > 1
    assert res.redacted_text.count("[PERSON_1]") == 2
    assert "Raj Patel" not in res.redacted_text


def test_each_chunk_keeps_its_mubit_request_id():
    text = "\n\n".join(["Jo Smith lives here." + " filler" * 300] * 3)
    res = run_pipeline(extract_text(text), t1=model_finds(("Jo Smith", "PERSON")), max_chars=2500)
    assert [c.mreq_id for c in res.chunks] == [f"mreq_{i}" for i in range(1, len(res.chunks) + 1)]
    assert all(c.error is None for c in res.chunks)


def test_without_a_model_the_regex_layer_still_runs():
    res = run_pipeline(extract_text("Email jo@example.com please"), t1=None)
    assert res.redacted_text == "Email [EMAIL_1] please"
    assert (res.chunks[0].status, res.chunks[0].error, res.chunks[0].latency_ms) == ("off", "model off", None)


def test_progress_is_reported_through_emit():
    text = "Tenant: Raj Patel.\n\n" + "Clause. " * 300 + "\n\nPay sort code 20-45-77."
    events = []
    res = run_pipeline(extract_text(text), t1=model_finds(("Raj Patel", "PERSON")), max_chars=1000,
                       emit=lambda name, data: events.append((name, data)))
    assert [n for n, _ in events] == ["start", "regex"] + ["chunk"] * len(res.chunks)
    assert [c["index"] for c in events[0][1]["chunks"]] == list(range(len(res.chunks)))
    assert [e["text"] for e in events[1][1]["entities"]] == ["20-45-77"]
    by_index = {d["index"]: d for n, d in events if n == "chunk"}
    assert by_index[0]["entities"] == [{"start": 8, "end": 17, "text": "Raj Patel", "type": "PERSON", "source": "model"}]
    assert by_index[0]["found"] == 1 and all(by_index[i]["found"] == 0 for i in range(1, len(res.chunks)))


def test_a_model_error_is_an_error_chunk_without_values():
    res = run_pipeline(extract_text("Jo Smith"), t1=lambda chunk: T1Result([{"text": "Jo Smith", "type": "PERSON"}],
                                                                          "mreq_e", "unreadable answer"))
    chunk = res.chunks[0]
    assert (chunk.status, chunk.error, chunk.mreq_id, chunk.found) == ("error", "unreadable answer", "mreq_e", 0)
    assert res.redacted_text == "Jo Smith"


def test_chunks_cut_on_paragraphs_and_cover_the_text():
    text = "a" * 50 + "\n\n" + "b" * 50 + "\n\n" + "c" * 50
    ranges = chunk_ranges(text, max_chars=60)
    assert [text[s:e].strip() for s, e in ranges] == ["a" * 50, "b" * 50, "c" * 50]


def test_pdf_spans_become_boxes_on_the_right_page(tenancy_pdf):
    doc = extract_pdf(tenancy_pdf, "lease.pdf")
    res = run_pipeline(doc, t1=model_finds(("Raj Patel", "PERSON"), ("12 Oak Road, Leeds", "ADDRESS")))
    person_boxes = [b for b in res.boxes if b.type == "PERSON"]
    assert sorted(b.page for b in person_boxes) == [0, 1]
    assert all(b.placeholder == "[PERSON_1]" for b in person_boxes)
    # one rectangle per line: "Raj Patel" is a single line, so a single box each time
    assert len(person_boxes) == 2
    sort_code = [b for b in res.boxes if b.type == "SORT_CODE"]
    assert len(sort_code) == 1 and sort_code[0].page == 1


def test_reviewer_can_hide_a_missed_value_everywhere_without_calling_the_model_again():
    doc = extract_text("Quote CL-20931 when you write. CL-20931 again.")
    t1 = model_finds()
    first = run_pipeline(doc, t1=t1)
    assert "CL-20931" in first.redacted_text
    fixed = rebuild(doc, first, hide={"CL-20931": "CUSTOM"})
    assert fixed.redacted_text == "Quote [CUSTOM_1] when you write. [CUSTOM_1] again."
    assert len(t1.calls) == 1  # the fix reuses the model's earlier answers


def test_reviewer_can_unhide_a_false_positive():
    doc = extract_text("Jo Smith bought a Rose Garden ticket.")
    res = run_pipeline(doc, t1=model_finds(("Jo Smith", "PERSON"), ("Rose Garden", "ADDRESS")))
    fixed = rebuild(doc, res, unhide={"Rose Garden"})
    assert fixed.redacted_text == "[PERSON_1] bought a Rose Garden ticket."


def test_a_stopped_run_makes_no_more_calls():
    t1 = model_finds(("Jo Smith", "PERSON"))
    res = run_pipeline(extract_text("Jo Smith.\n\n" * 50), t1=t1, max_chars=100, stop=lambda: True)
    assert t1.calls == [] and {c.status for c in res.chunks} == {"error"}
    assert res.chunks[0].error.startswith("stopped")


def test_failed_chunk_retry_keeps_review_decisions_and_retries_the_model():
    doc = extract_text("Public name: Jo Smith. Private phrase: silver meadow.")
    failed = run_pipeline(doc, t1=lambda _: T1Result([], "failed", "try again"))
    reviewed = rebuild(doc, failed, hide={"silver meadow": "CUSTOM"}, unhide={"Jo Smith"})
    t1 = model_finds(("Jo Smith", "PERSON"))
    retried = run_pipeline(doc, t1=t1, reuse=reviewed)
    assert len(t1.calls) == 1
    assert retried.chunks[0].status == "ok"
    assert retried.redacted_text == reviewed.redacted_text
    assert retried.hidden == reviewed.hidden and retried.hidden is not reviewed.hidden
    assert retried.unhidden == reviewed.unhidden and retried.unhidden is not reviewed.unhidden


def test_full_rescan_keeps_corrections_without_reusing_model_answers():
    doc = extract_text("Jo Smith. silver meadow. Raj Patel.")
    reviewed = rebuild(doc, run_pipeline(doc, t1=model_finds(("Jo Smith", "PERSON"))),
                       hide={"silver meadow": "CUSTOM"}, unhide={"Jo Smith"})
    t1 = model_finds(("Jo Smith", "PERSON"), ("Raj Patel", "PERSON"))
    rescanned = run_pipeline(doc, t1=t1, corrections=reviewed, plan="new-plan")
    assert len(t1.calls) == 1
    assert "Jo Smith" in rescanned.redacted_text
    assert "silver meadow" not in rescanned.redacted_text
    assert "Raj Patel" not in rescanned.redacted_text


def test_a_reused_run_keeps_ok_chunks_only_under_the_same_plan_and_ranges():
    doc = extract_text("Jo Smith.\n\n" * 50)
    t1 = model_finds(("Jo Smith", "PERSON"))
    first = run_pipeline(doc, t1=t1, max_chars=100, plan="evalkit")
    assert len(first.chunk_values) == len(first.chunks) and first.chunk_values[0] == [{"text": "Jo Smith", "type": "PERSON"}]
    t1.calls.clear()
    again = run_pipeline(doc, t1=t1, max_chars=100, plan="evalkit", reuse=first)
    assert t1.calls == [] and again.chunks == first.chunks and again.redacted_text == first.redacted_text
    run_pipeline(doc, t1=t1, max_chars=200, plan="evalkit", reuse=first)  # other ranges: every chunk again
    assert len(t1.calls) == len(chunk_ranges(doc.text, 200))
