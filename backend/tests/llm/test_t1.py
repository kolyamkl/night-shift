import importlib.util
import json
from pathlib import Path

import httpx2
import pytest

from app.llm import prompts, t1
from app.llm.rewrite import align_rewrite, rewrite_values
from app.llm.t1 import REWRITE, make_t1_factory
from app.redaction.document import extract_text
from app.redaction.pipeline import run_pipeline

REPO = Path(__file__).resolve().parents[3]


def message(text: str, stop_reason: str = "end_turn") -> dict:
    return {"id": "msg_test", "type": "message", "role": "assistant", "model": prompts.MODEL_ID,
            "content": [{"type": "text", "text": text}], "stop_reason": stop_reason, "stop_sequence": None,
            "usage": {"input_tokens": 900, "output_tokens": 12}}


class FakeMubit:
    """An httpx2 transport standing in for api.mubit.ai: records requests, plays back responses."""

    def __init__(self, *responses: httpx2.Response):
        self.requests: list[httpx2.Request] = []
        self.responses = list(responses)

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return self.responses.pop(0)

    def client(self) -> httpx2.Client:
        return httpx2.Client(transport=httpx2.MockTransport(self))


def ok(text: str, stop_reason: str = "end_turn", mreq: str = "mreq_1") -> httpx2.Response:
    return httpx2.Response(200, json=message(text, stop_reason), headers={"x-middleware-request-id": mreq})


def rewrite_t1(fake: FakeMubit, doc_id: str = "d1"):
    return make_t1_factory("mbt_test", prompt=REWRITE, http_client=fake.client())(doc_id)


def test_rewrite_request_has_exactly_the_send_batch_fields(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-must-not-be-sent")
    fake = FakeMubit(ok("Tenant: [PERSON_1]."))
    rewrite_t1(fake, "abc123")("Tenant: Raj Patel.")
    req = fake.requests[0]
    assert req.method == "POST" and str(req.url) == "https://api.mubit.ai/anthropic/v1/messages"
    assert json.loads(req.content) == {
        "model": "claude-haiku-4-5",
        "max_tokens": 2048,
        "system": prompts.T1_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": "Tenant: Raj Patel."}],
        "metadata": {"user_id": "doc-abc123"},
    }
    assert req.headers["authorization"] == "Bearer mbt_test"
    assert "x-middleware-record" not in req.headers  # recording on: the calls train the task
    assert "x-api-key" not in req.headers and "sk-ant" not in str(req.headers)
    assert req.headers["x-stainless-retry-count"] == "0"


def test_rewrite_request_is_the_same_as_send_batch_py(monkeypatch):
    """Same body and the same Mubit-relevant headers as scripts/dataset/send_batch.py, so the calls
    land in Nick's Mubit task "Redact personal data"."""
    monkeypatch.syspath_prepend(str(REPO / "scripts" / "dataset"))
    spec = importlib.util.spec_from_file_location("dataset_send_batch", REPO / "scripts" / "dataset" / "send_batch.py")
    send_batch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(send_batch)

    theirs = FakeMubit(ok("Tenant: [PERSON_1]."))
    client = send_batch.make_client("mbt_test", send_batch.MUBIT_BASE_URL, theirs.client())
    chunk = {"chunk_id": "c1", "doc_id": "abc123", "split": "train", "text": "Tenant: Raj Patel."}
    send_batch.send_one(client, chunk, send_batch.request_headers("train", True), 1, send_batch.MAX_TOKENS)
    ours = FakeMubit(ok("Tenant: [PERSON_1]."))
    rewrite_t1(ours, "abc123")("Tenant: Raj Patel.")

    a, b = theirs.requests[0], ours.requests[0]
    assert a.url == b.url and json.loads(a.content) == json.loads(b.content)
    for h in ("authorization", "anthropic-version", "content-type", "user-agent", "x-middleware-record"):
        assert a.headers.get(h) == b.headers.get(h), h


def test_a_rewritten_answer_becomes_the_right_spans():
    text = "Tenant: Mr Raj Patel\n12 Oak Road, Leeds LS6 2AB\nRent 950 pounds. Signed: Raj Patel.\n\n"
    fake = FakeMubit(ok("Tenant: [PERSON_1]\n[ADDRESS_1] [POSTCODE_1]\nRent 950 pounds. Signed: [PERSON_1].",
                        mreq="mreq_rw"))
    res = run_pipeline(extract_text(text), t1=rewrite_t1(fake), max_chars=1400)
    assert [(s.text, s.type) for s in res.spans] == [
        ("Raj Patel", "PERSON"), ("12 Oak Road, Leeds", "ADDRESS"), ("LS6 2AB", "POSTCODE"), ("Raj Patel", "PERSON")]
    assert res.redacted_text == "Tenant: Mr [PERSON_1]\n[ADDRESS_1] [POSTCODE_1]\nRent 950 pounds. Signed: [PERSON_1].\n\n"
    chunk = res.chunks[0]
    assert (chunk.status, chunk.mreq_id, chunk.found, chunk.error) == ("ok", "mreq_rw", 3, None)


def test_neighbouring_placeholders_split_where_the_value_types_fit():
    chunk = "Write to Jo Smith at 4 Elm Street Bath BA1 1AA or call 07700 900123 today."
    answer = "Write to [PERSON_1] at [ADDRESS_1] [POSTCODE_1] or call [PHONE_1] today."
    assert rewrite_values(chunk, answer) == [
        {"text": "Jo Smith", "type": "PERSON"}, {"text": "4 Elm Street Bath", "type": "ADDRESS"},
        {"text": "BA1 1AA", "type": "POSTCODE"}, {"text": "07700 900123", "type": "PHONE"}]


def test_a_line_the_model_changed_falls_back_to_the_diff_and_counts_the_change():
    chunk = "Dear Ann Lee,\nThe colour of the van is red.\n"
    spans, changed = align_rewrite(chunk, "Dear [PERSON_1],\nThe color of the van is red.")
    assert [(s.text, s.type) for s in spans] == [("Ann Lee", "PERSON")] and changed == 1


def test_a_cut_off_answer_is_an_error_not_a_partial_success():
    result = rewrite_t1(FakeMubit(ok("Tenant: [PERSON_1]", stop_reason="max_tokens")))("Tenant: Raj Patel. More text.")
    assert result.entities == [] and result.error == "answer cut off" and result.mreq_id == "mreq_1"


def test_an_answer_that_does_not_line_up_is_unreadable():
    chunk = "Tenant: Raj Patel. The rent is 950 pounds per month, paid on the first day of each month."
    result = rewrite_t1(FakeMubit(ok("I am sorry, I cannot help with redacting this kind of document.")))(chunk)
    assert result.entities == [] and result.error == "unreadable answer"


def test_busy_answers_are_retried_after_retry_after(monkeypatch):
    waits = []
    monkeypatch.setattr(t1.time, "sleep", waits.append)
    busy = httpx2.Response(429, json={"type": "error", "error": {"type": "rate_limit_error", "message": "busy"}},
                           headers={"retry-after": "3"})
    fake = FakeMubit(busy, ok("Tenant: [PERSON_1]."))
    result = rewrite_t1(fake)("Tenant: Raj Patel.")
    assert waits == [3.0] and len(fake.requests) == 2
    assert result.entities == [{"text": "Raj Patel", "type": "PERSON"}] and result.error is None


def test_other_http_errors_are_not_retried():
    bad = httpx2.Response(400, json={"type": "error", "error": {"type": "invalid_request_error", "message": "nope"}},
                          headers={"x-middleware-request-id": "mreq_bad"})
    fake = FakeMubit(bad)
    result = rewrite_t1(fake)("Tenant: Raj Patel.")
    assert len(fake.requests) == 1
    assert result.error.startswith("http 400") and result.mreq_id == "mreq_bad"


def test_rewrite_chunks_are_sent_stripped_like_the_training_data():
    text = "  Tenant: Raj Patel.\n\nRent is due.\n"
    fake = FakeMubit(ok("Tenant: [PERSON_1]."), ok("Rent is due."))
    res = run_pipeline(extract_text(text), t1=rewrite_t1(fake), max_chars=25, workers=1)
    assert [c.status for c in res.chunks] == ["ok", "ok"] and text[res.chunks[0].start:res.chunks[0].end].endswith("\n\n")
    assert [json.loads(r.content)["messages"] for r in fake.requests] == [
        [{"role": "user", "content": "Tenant: Raj Patel."}], [{"role": "user", "content": "Rent is due."}]]
    assert res.redacted_text == "  Tenant: [PERSON_1].\n\nRent is due.\n"


def test_stripped_alignment_keeps_offsets_into_the_chunk():
    chunk = "\n  Tenant: Raj Patel.\n\n"
    [span], changed = align_rewrite(chunk, "Tenant: [PERSON_1].")
    assert chunk[span.start:span.end] == span.text == "Raj Patel" and changed == 0


def test_tiny_values_and_bare_titles_are_dropped():
    chunk = "From: J. Smith (Mr), ref A\nDear Dr,"
    answer = "From: [PERSON_1]. [PERSON_2] ([PERSON_3]), ref [CUSTOM_1]\nDear [PERSON_4],"
    assert rewrite_values(chunk, answer) == [{"text": "Smith", "type": "PERSON"}]


def test_a_letterhead_misread_by_the_diff_does_not_hide_mr_everywhere():
    """The extra blank line sends this answer to evalkit's diff, which reads "Mr" as a PERSON value."""
    chunk = "Tenant: Mr Raj Patel\n12 Oak Road, Leeds LS6 2AB\nRent 950 pounds. Signed: Raj Patel.\n\n"
    answer = "Tenant: [PERSON_1]\n\n[ADDRESS_1] [POSTCODE_1]\nRent 950 pounds. Signed: [PERSON_1]."
    assert "Mr" in [sp.text for sp in align_rewrite(chunk, answer)[0]]
    values = rewrite_values(chunk, answer)
    assert "Mr" not in [v["text"] for v in values] and {"text": "Raj Patel", "type": "PERSON"} in values
