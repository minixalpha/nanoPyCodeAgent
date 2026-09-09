"""Response-budget exhaustion must remain distinct from task completion."""

import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from anthropic.types import ThinkingBlock

from nanopycodeagent import agent, cli, settings
from nanopycodeagent.event_journal import EventJournal, JournalEntry

from helpers import (
    FakeClient,
    FakeMessages,
    FakeStream,
    patch_client,
    patch_client_and_input,
    text_block,
    write_tool_use_block,
)


def _journal_entries():
    paths = list((settings.SETTINGS_PATH.parent / "journals").glob("*.jsonl"))
    assert len(paths) == 1
    return EventJournal.replay(paths[0])


@pytest.mark.parametrize("max_turns", [1, 5])
@pytest.mark.parametrize("content", [
    [text_block("Partial answer")],
    [ThinkingBlock(type="thinking", thinking="Still analyzing", signature="")],
    [],
])
def test_truncation_stops_with_usage_cost_and_distinct_terminal(
    monkeypatch, tmp_path, capsys, content, max_turns
):
    reply = FakeStream(
        content,
        stop_reason="max_tokens",
        usage=SimpleNamespace(input_tokens=10, output_tokens=8192),
        response_headers={"x-generation-id": "gen-truncated"},
    )
    messages = FakeMessages([reply])
    patch_client(monkeypatch, FakeClient(messages))
    reconciled = []

    def resolve(base_url, generation_id, credential, **kwargs):
        reconciled.append(generation_id)
        return {
            "generation_id": generation_id,
            "amount": "0.01",
            "currency": "USD",
            "source": "provider_generation.total_cost",
        }

    monkeypatch.setattr(agent, "resolve_generation_cost", resolve)
    trajectory_path = tmp_path / "trajectory.json"
    assert cli.main([
        "-p", "fix it", "--max-turns", str(max_turns),
        "--trajectory", str(trajectory_path),
    ]) == 0

    assert len(messages.calls) == 1
    assert messages.kwargs[0]["max_tokens"] == 8192
    captured = capsys.readouterr()
    assert captured.out == ("Partial answer\n" if content and content[0].type == "text" else "")
    assert "response truncated" in captured.err
    assert "max_tokens" in captured.err
    assert "stopped after" not in captured.err
    assert reconciled == ["gen-truncated"]

    entries = _journal_entries()
    assert all(entry.schema_version == 2 for entry in entries)
    assert entries[-1].type == "run.completed"
    assert entries[-1].payload["outcome"] == "response_truncated"
    completed = next(entry for entry in entries if entry.type == "model.completed")
    assert completed.payload["stop_reason"] == "max_tokens"
    assert completed.payload["usage"]["output_tokens"] == 8192
    assert completed.payload["content"] == agent._native_content_blocks(content)
    assert not any(entry.type.startswith("tool.") for entry in entries)

    trajectory = json.loads(trajectory_path.read_text())
    assert trajectory["schema_version"] == "ATIF-v1.7"
    assert trajectory["extra"]["terminal"]["outcome"] == "response_truncated"
    assert trajectory["steps"][1]["extra"]["stop_reason"] == "max_tokens"
    assert trajectory["final_metrics"]["total_prompt_tokens"] == 10
    assert trajectory["final_metrics"]["total_completion_tokens"] == 8192
    assert trajectory["final_metrics"]["total_cost_usd"] == 0.01


def test_truncated_tools_are_not_executed_or_replayed_on_the_next_user_turn(
    monkeypatch, tmp_path, capsys
):
    target = tmp_path / "must-not-exist.txt"
    truncated = FakeStream([
        ThinkingBlock(type="thinking", thinking="Unfinished thinking", signature=""),
        text_block("I was about to write"),
        write_tool_use_block("complete-input", path=str(target), content="unsafe"),
        write_tool_use_block("partial-input", path=str(target)),
    ], stop_reason="max_tokens")
    messages = FakeMessages([truncated, [text_block("New answer")]])
    patch_client_and_input(
        monkeypatch, client=FakeClient(messages), inputs=["write it", "continue", "/exit"]
    )

    assert agent.run() == 0

    assert len(messages.calls) == 2
    assert not target.exists()
    followup = messages.calls[1]
    assert followup[0] == {"role": "user", "content": "write it"}
    assert followup[-1] == {"role": "user", "content": "continue"}
    assert followup[1]["role"] == "assistant"
    assert isinstance(followup[1]["content"], str)
    assert followup[1]["content"].startswith("I was about to write\n\n")
    assert "response truncated" in followup[1]["content"]
    assert "not executed" in followup[1]["content"]
    assert "Unfinished thinking" not in followup[1]["content"]
    captured = capsys.readouterr()
    assert "New answer" in captured.out
    assert "[write]" not in captured.out
    assert captured.err.count("response truncated") == 1


def test_sdk_stream_with_partial_tool_json_preserves_truncation(
    monkeypatch, tmp_path, capsys
):
    """Use the real SDK accumulator with an input JSON delta cut mid-string."""
    events = [
        {"type": "message_start", "message": {
            "id": "msg-truncated", "type": "message", "role": "assistant",
            "model": "test-model", "content": [], "stop_reason": None,
            "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 0},
        }},
        {"type": "content_block_start", "index": 0, "content_block": {
            "type": "tool_use", "id": "partial-tool", "name": "write", "input": {},
        }},
        {"type": "content_block_delta", "index": 0, "delta": {
            "type": "input_json_delta", "partial_json": '{"path": "unfinished',
        }},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {
            "stop_reason": "max_tokens", "stop_sequence": None,
        }, "usage": {"output_tokens": 8192}},
        {"type": "message_stop"},
    ]
    wire = "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events)
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=wire
        )

    with anthropic.Anthropic(
        api_key="test-key", base_url="https://example.test",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    ) as client:
        patch_client(monkeypatch, client)
        assert agent.run_headless(
            "write a file", trajectory_path=tmp_path / "trajectory.json"
        ) == 0

    assert len(requests) == 1
    assert "response truncated" in capsys.readouterr().err
    entries = _journal_entries()
    assert entries[-1].payload["outcome"] == "response_truncated"
    completed = next(entry for entry in entries if entry.type == "model.completed")
    assert completed.payload["tool_calls"][0]["input"] == {}
    assert not any(entry.type.startswith("tool.") for entry in entries)
    trajectory = json.loads((tmp_path / "trajectory.json").read_text())
    assert trajectory["steps"][1]["tool_calls"][0]["arguments"] == {}
    assert "observation" not in trajectory["steps"][1]


@pytest.mark.parametrize("schema_version", [1, 2])
@pytest.mark.parametrize("outcome", ["completed", "max_turns_exhausted", "response_truncated"])
def test_journal_outcome_versions(schema_version, outcome):
    record = {
        "schema_version": schema_version, "run_id": "run-1", "seq": 1,
        "recorded_at": "2026-09-07T00:00:00.000Z", "type": "run.completed",
        "payload": {"outcome": outcome, "duration_ms": 1, "source_timestamp": None},
    }
    if schema_version == 1 and outcome == "response_truncated":
        with pytest.raises(ValueError, match="requires Journal Entry schema 2"):
            JournalEntry.from_dict(record)
    else:
        assert JournalEntry.from_dict(record).to_dict() == record
