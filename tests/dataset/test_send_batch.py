import json

import httpx2
import pytest
from conftest import make_doc

import build_chunks
import send_batch
from app.llm import prompts


@pytest.fixture
def chunks_dir(tmp_path):
    d = tmp_path / "chunks"
    train = make_doc("Tenant: Ann Lee.", [("Ann Lee", "PERSON", "p1")])
    train2 = make_doc("Tenant: Bo Tan.", [("Bo Tan", "PERSON", "p1")], doc_id="contracts-C1-f2", fill=2)
    ev = make_doc("Tenant: Cy Dee.", [("Cy Dee", "PERSON", "p1")], doc_id="contracts-C2-f1", source_id="C2", split="eval")
    by_split, _ = build_chunks.build([train, train2, ev])
    for split, rows in by_split.items():
        build_chunks.write_jsonl(d / f"{split}.jsonl", rows)
    return d


def message_body(text="Tenant: [PERSON_1].", stop_reason="end_turn"):
    return {
        "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-haiku-4-5",
        "content": [{"type": "text", "text": text}], "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 900, "output_tokens": 12},
    }


class FakeMubit:
    def __init__(self, responses=None):
        self.requests = []
        self.responses = list(responses or [])

    def __call__(self, request):
        self.requests.append(request)
        if self.responses:
            return self.responses.pop(0)
        n = len(self.requests)
        return httpx2.Response(200, json=message_body(), headers={"x-middleware-request-id": f"mreq_{n:032x}"})


def run(args, fake=None):
    client = httpx2.Client(transport=httpx2.MockTransport(fake)) if fake else None
    return send_batch.run(send_batch.parse_args(args), http_client=client)


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_dry_run_is_the_default(chunks_dir, tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("MUBIT_API_KEY", raising=False)
    assert run(["--chunks-dir", str(chunks_dir), "--results-dir", str(tmp_path / "results")]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "estimated cost $" in out and "session doc-contracts-C1-f1" in out
    assert not (tmp_path / "results").exists()


def test_send_builds_the_agreed_request(chunks_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("MUBIT_API_KEY", "mbt_test")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "must-not-be-sent")
    fake = FakeMubit()
    results = tmp_path / "results"
    assert run(["--send", "--chunks-dir", str(chunks_dir), "--results-dir", str(results)], fake) == 0

    assert len(fake.requests) == 2
    # Requests run concurrently, so pick the C1 fill 1 request by its session, not by position.
    req = next(r for r in fake.requests if json.loads(r.content)["metadata"]["user_id"] == "doc-contracts-C1-f1")
    assert str(req.url) == "https://api.mubit.ai/anthropic/v1/messages"
    # SDK 2.x sends the key as a Bearer token, which Mubit accepts; only the Mubit key is sent.
    assert req.headers["authorization"] == "Bearer mbt_test"
    assert "x-api-key" not in req.headers
    assert "must-not-be-sent" not in str(req.headers)
    assert "x-middleware-record" not in req.headers
    body = json.loads(req.content)
    assert set(body) == {"model", "max_tokens", "system", "messages", "metadata"}
    assert body["model"] == prompts.MODEL_ID == "claude-haiku-4-5"
    assert body["max_tokens"] == 2048
    assert body["system"] == prompts.T1_SYSTEM_PROMPT
    assert body["messages"] == [{"role": "user", "content": "Tenant: Ann Lee."}]
    assert body["metadata"] == {"user_id": "doc-contracts-C1-f1"}

    got = rows(results / "train.jsonl")
    assert {r["chunk_id"] for r in got} == {"contracts-C1-f1-c000", "contracts-C1-f2-c000"}
    for r in got:
        assert r["request_id"].startswith("mreq_") and r["error"] is None
        assert r["output"] == "Tenant: [PERSON_1]." and r["prompt_version"] == 1
        assert r["usage"]["input_tokens"] == 900 and r["model"] == "claude-haiku-4-5"

    # Resumable: a second run sends nothing.
    fake2 = FakeMubit()
    assert run(["--send", "--chunks-dir", str(chunks_dir), "--results-dir", str(results)], fake2) == 0
    assert fake2.requests == []


def test_eval_split_turns_recording_off_behind_a_flag(chunks_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("MUBIT_API_KEY", "mbt_test")
    fake = FakeMubit()
    assert run(["--send", "--split", "eval", "--chunks-dir", str(chunks_dir), "--results-dir", str(tmp_path / "a")], fake) == 0
    assert fake.requests[0].headers["x-middleware-record"] == "off"
    assert rows(tmp_path / "a" / "eval.jsonl")[0]["record_off"] is True

    fake = FakeMubit()
    args = ["--send", "--split", "eval", "--no-eval-record-off", "--chunks-dir", str(chunks_dir), "--results-dir", str(tmp_path / "b")]
    assert run(args, fake) == 0
    assert "x-middleware-record" not in fake.requests[0].headers


def test_retry_after_on_429_and_limit(chunks_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("MUBIT_API_KEY", "mbt_test")
    busy = httpx2.Response(
        429, json={"type": "error", "error": {"type": "rate_limit_error", "message": "slow down"}},
        headers={"retry-after": "0", "x-middleware-request-id": "mreq_" + "a" * 32},
    )
    fake = FakeMubit([busy])
    results = tmp_path / "results"
    assert run(["--send", "--limit", "1", "--chunks-dir", str(chunks_dir), "--results-dir", str(results)], fake) == 0
    assert len(fake.requests) == 2
    [row] = rows(results / "train.jsonl")
    assert row["error"] is None and row["request_id"] == f"mreq_{2:032x}"


def test_errors_are_recorded_and_retried_only_on_request(chunks_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("MUBIT_API_KEY", "mbt_test")
    bad = httpx2.Response(400, json={"type": "error", "error": {"type": "invalid_request_error", "message": "starter_credit_model"}})
    results = tmp_path / "results"
    args = ["--send", "--limit", "1", "--chunks-dir", str(chunks_dir), "--results-dir", str(results)]
    fake = FakeMubit([bad])
    assert run(args, fake) == 1
    assert len(fake.requests) == 1
    assert "HTTP 400" in rows(results / "train.jsonl")[0]["error"]

    fake = FakeMubit()
    assert run(args, fake) == 0
    assert json.loads(fake.requests[0].content)["metadata"]["user_id"] == "doc-contracts-C1-f2"  # the failed chunk is skipped

    fake = FakeMubit()
    assert run(args + ["--retry-errors"], fake) == 0
    assert json.loads(fake.requests[0].content)["metadata"]["user_id"] == "doc-contracts-C1-f1"


def test_truncated_output_is_an_error(chunks_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("MUBIT_API_KEY", "mbt_test")
    cut = httpx2.Response(200, json=message_body("Tenant: [PER", "max_tokens"), headers={"x-middleware-request-id": "mreq_" + "b" * 32})
    results = tmp_path / "results"
    assert run(["--send", "--limit", "1", "--chunks-dir", str(chunks_dir), "--results-dir", str(results)], FakeMubit([cut])) == 1
    assert "max_tokens" in rows(results / "train.jsonl")[0]["error"]


def test_key_comes_from_env_file_when_unset(chunks_dir, tmp_path, monkeypatch):
    # setenv first so monkeypatch removes the variable that load_env_file sets once the test ends.
    monkeypatch.setenv("MUBIT_API_KEY", "placeholder")
    monkeypatch.delenv("MUBIT_API_KEY")
    env_file = tmp_path / ".env"
    env_file.write_text("# Mubit\nMUBIT_API_KEY='mbt_fromfile'\n")
    fake = FakeMubit()
    args = ["--send", "--limit", "1", "--chunks-dir", str(chunks_dir), "--results-dir", str(tmp_path / "r")]
    assert run(args + ["--env-file", str(env_file)], fake) == 0
    assert fake.requests[0].headers["authorization"] == "Bearer mbt_fromfile"

    # A variable already set in the environment wins over the file.
    monkeypatch.setenv("MUBIT_API_KEY", "mbt_fromenv")
    fake2 = FakeMubit()
    assert run(args + ["--env-file", str(env_file), "--results-dir", str(tmp_path / "r2")], fake2) == 0
    assert fake2.requests[0].headers["authorization"] == "Bearer mbt_fromenv"


def test_refuses_a_key_that_is_not_a_mubit_key(chunks_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("MUBIT_API_KEY", "sk-ant-provider-key")
    fake = FakeMubit()
    assert run(["--send", "--chunks-dir", str(chunks_dir), "--results-dir", str(tmp_path / "r")], fake) == 2
    assert fake.requests == []
