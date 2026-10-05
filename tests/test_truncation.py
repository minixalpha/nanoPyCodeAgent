"""Response-budget exhaustion must remain distinct from task completion."""

import json
from types import SimpleNamespace

import anthropic
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
    sdk_http_module,
    text_block,
    tool_use_block,
    write_tool_use_block,
)


def _journal_entries():
    paths = list((settings.SETTINGS_PATH.parent / "journals").glob("*.jsonl"))
    assert len(paths) == 1
    return EventJournal.replay(paths[0])


@pytest.mark.parametrize("max_turns", [1, 5])
@pytest.mark.parametrize("max_tokens", [8192, 32768])
@pytest.mark.parametrize("content", [
    [text_block("Partial answer")],
    [ThinkingBlock(type="thinking", thinking="Still analyzing", signature="")],
    [],
])
def test_truncation_stops_with_usage_cost_and_distinct_terminal(
    monkeypatch, tmp_path, capsys, content, max_turns, max_tokens
):
    attempts = 1 if max_turns == 1 else 2
    messages = FakeMessages([
        FakeStream(
            content,
            stop_reason="max_tokens",
            usage=SimpleNamespace(input_tokens=10, output_tokens=max_tokens),
            response_headers={"x-generation-id": f"gen-truncated-{index}"},
        )
        for index in range(attempts)
    ])
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
        "--max-tokens", str(max_tokens),
        "--trajectory", str(trajectory_path),
    ]) == 0

    assert len(messages.calls) == attempts
    assert all(call["max_tokens"] == max_tokens for call in messages.kwargs)
    captured = capsys.readouterr()
    assert captured.out == ("Partial answer\n" * attempts if content and content[0].type == "text" else "")
    assert "response truncated" in captured.err
    assert "max_tokens" in captured.err
    assert "stopped after" not in captured.err
    assert captured.err.count("recovery 1/1") == attempts - 1
    assert reconciled == [f"gen-truncated-{index}" for index in range(attempts)]

    entries = _journal_entries()
    assert all(entry.schema_version == 4 for entry in entries)
    assert entries[-1].type == "run.completed"
    assert entries[-1].payload["outcome"] == "response_truncated"
    completed = next(entry for entry in entries if entry.type == "model.completed")
    assert completed.payload["stop_reason"] == "max_tokens"
    assert completed.payload["usage"]["output_tokens"] == max_tokens
    assert completed.payload["content"] == agent._native_content_blocks(content)
    assert not any(entry.type.startswith("tool.") for entry in entries)

    trajectory = json.loads(trajectory_path.read_text())
    assert trajectory["schema_version"] == "ATIF-v1.7"
    assert trajectory["extra"]["terminal"]["outcome"] == "response_truncated"
    assert next(step for step in trajectory["steps"] if step["source"] == "agent")["extra"]["stop_reason"] == "max_tokens"
    assert trajectory["final_metrics"]["total_prompt_tokens"] == 10 * attempts
    assert trajectory["agent"]["extra"]["max_tokens"] == max_tokens
    assert trajectory["final_metrics"]["total_completion_tokens"] == max_tokens * attempts
    assert trajectory["final_metrics"]["total_cost_usd"] == 0.01 * attempts


def test_headless_recovery_keeps_committed_work_and_discards_truncated_tools(
    monkeypatch, tmp_path
):
    unsafe = tmp_path / "must-not-exist.txt"
    answer = tmp_path / "answer.txt"
    executed = []
    monkeypatch.setattr(agent, "run_bash", lambda command, **kwargs: (executed.append(command) or "saved", False))

    def reply(content, reason="tool_use", tokens=10):
        return FakeStream(content, stop_reason=reason,
                          usage=SimpleNamespace(input_tokens=10, output_tokens=tokens, cost=0.01))

    messages = FakeMessages([
        reply([tool_use_block("committed", "append once")]),
        reply([
            ThinkingBlock(type="thinking", thinking="Unfinished thinking", signature=""),
            text_block("Partial reply"),
            write_tool_use_block("discard-complete", path=str(unsafe), content="unsafe"),
            write_tool_use_block("discard-partial", path=str(unsafe)),
        ], "max_tokens", 8192),
        reply([write_tool_use_block("fresh", path=str(answer), content="done")]),
        reply([text_block("Finished")], "end_turn"),
    ])
    patch_client(monkeypatch, FakeClient(messages))
    trajectory_path = tmp_path / "trajectory.json"
    assert agent.run_headless("task", max_turns=4, max_tokens=8192, trajectory_path=trajectory_path) == 0
    assert executed == ["append once"]
    assert not unsafe.exists()
    assert answer.read_text() == "done"
    followup = messages.calls[2]
    assert [m["role"] for m in followup] == ["user", "assistant", "user", "assistant", "user"]
    assert followup[-2]["content"].startswith("Partial reply\n\n")
    assert "not executed" in followup[-2]["content"]
    assert agent._TRUNCATION_RECOVERY_NOTE in followup[-1]["content"]
    assert "Turn 3 of 4" in followup[-1]["content"]
    assert "Unfinished thinking" not in str(followup)
    assert "discard-complete" not in str(followup)
    assert "discard-partial" not in str(followup)
    assert all(call["max_tokens"] == 8192 for call in messages.kwargs)
    assert len({call["system"] for call in messages.kwargs}) == 1

    entries = _journal_entries()
    injected = [e for e in entries if e.type == "input.injected" and e.payload["reason"] == "truncation_recovery"]
    assert len(injected) == 1
    starts = [e for e in entries if e.type == "model.started"]
    assert injected[0].payload["model_call_id"] == starts[2].payload["model_call_id"]
    assert [e.payload["tool_call_id"] for e in entries if e.type == "tool.started"] == ["committed", "fresh"]
    trajectory = json.loads(trajectory_path.read_text())
    assert trajectory["extra"]["terminal"]["outcome"] == "completed"
    recoveries = [s for s in trajectory["steps"] if s.get("extra", {}).get("reason") == "truncation_recovery"]
    assert len(recoveries) == 1 and recoveries[0]["message"] == agent._TRUNCATION_RECOVERY_NOTE
    assert trajectory["final_metrics"]["total_prompt_tokens"] == 40
    assert trajectory["final_metrics"]["total_completion_tokens"] == 8222
    assert trajectory["final_metrics"]["total_cost_usd"] == 0.04


def test_recovery_allowance_is_not_reset_by_tool_work_or_stream_retry(monkeypatch):
    import httpx
    from test_stream_recovery import BrokenStream

    monkeypatch.setattr(agent.time, "sleep", lambda _: None)
    executed = []
    monkeypatch.setattr(agent, "run_bash", lambda command, **kwargs: (executed.append(command) or "ok", False))
    messages = FakeMessages([
        FakeStream([], stop_reason="max_tokens"),
        BrokenStream(httpx.ReadError("interrupted recovery")),
        FakeStream([tool_use_block("fresh", "work")], stop_reason="tool_use"),
        FakeStream([], stop_reason="max_tokens"),
    ])
    patch_client(monkeypatch, FakeClient(messages))
    assert agent.run_headless("task", max_turns=10) == 0
    assert len(messages.calls) == 4
    assert messages.calls[1] == messages.calls[2]
    assert executed == ["work"]
    entries = _journal_entries()
    assert entries[-1].payload["outcome"] == "response_truncated"
    assert sum(e.type == "input.injected" and e.payload["reason"] == "truncation_recovery" for e in entries) == 1


def test_recovery_cannot_bypass_last_turn_tool_guard(monkeypatch, tmp_path):
    target = tmp_path / "must-not-exist.txt"
    messages = FakeMessages([
        FakeStream([], stop_reason="max_tokens"),
        FakeStream([write_tool_use_block("last", path=str(target), content="late")], stop_reason="tool_use"),
    ])
    patch_client(monkeypatch, FakeClient(messages))
    assert agent.run_headless("task", max_turns=2) == 0
    assert len(messages.calls) == 2
    assert not target.exists()
    assert _journal_entries()[-1].payload["outcome"] == "max_turns_exhausted"


@pytest.mark.parametrize("budget, expected_calls", [(4, 1), (6, 2)])
def test_recovery_shares_the_original_deadline(monkeypatch, budget, expected_calls):
    from test_time_budget import AdvancingFakeMessages, FakeTime

    clock = FakeTime()
    monkeypatch.setattr(agent, "time", clock)
    messages = AdvancingFakeMessages([
        FakeStream([], stop_reason="max_tokens"),
        FakeStream([text_block("late")]),
    ], clock, 4)
    patch_client(monkeypatch, FakeClient(messages))
    assert agent.run_headless("task", time_budget_seconds=budget) == 0
    assert len(messages.calls) == expected_calls
    assert messages.kwargs[0]["timeout"] == budget
    if expected_calls == 2:
        assert messages.kwargs[1]["timeout"] == 2
        assert "Turn 2 of 50" in messages.calls[1][-1]["content"]
    assert _journal_entries()[-1].payload["outcome"] == "time_budget_exhausted"


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


@pytest.mark.parametrize("recover", [False, True])
def test_sdk_stream_with_partial_tool_json_preserves_truncation(
    monkeypatch, tmp_path, capsys, recover
):
    """Use the real SDK accumulator with an input JSON delta cut mid-string."""
    httpx = sdk_http_module()
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
        if recover and len(requests) == 2:
            completed = [
                {"type": "message_start", "message": {
                    "id": "msg-recovered", "type": "message", "role": "assistant",
                    "model": "test-model", "content": [], "stop_reason": None,
                    "stop_sequence": None, "usage": {"input_tokens": 20, "output_tokens": 0},
                }},
                {"type": "content_block_start", "index": 0,
                 "content_block": {"type": "text", "text": "Done"}},
                {"type": "content_block_stop", "index": 0},
                {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                 "usage": {"output_tokens": 1}},
                {"type": "message_stop"},
            ]
            body = "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in completed)
        else:
            body = wire
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=body
        )

    with anthropic.Anthropic(
        api_key="test-key", base_url="https://example.test",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    ) as client:
        patch_client(monkeypatch, client)
        assert agent.run_headless(
            "write a file", max_tokens=65536, trajectory_path=tmp_path / "trajectory.json"
        ) == 0

    assert len(requests) == 2
    assert json.loads(requests[0].content)["max_tokens"] == 65536
    followup = json.loads(requests[1].content)["messages"]
    assert isinstance(followup[-2]["content"], str)
    assert "partial-tool" not in json.dumps(followup)
    assert "response truncated" in capsys.readouterr().err
    entries = _journal_entries()
    assert entries[-1].payload["outcome"] == ("completed" if recover else "response_truncated")
    completed = next(entry for entry in entries if entry.type == "model.completed")
    assert completed.payload["tool_calls"][0]["input"] == {}
    assert not any(entry.type.startswith("tool.") for entry in entries)
    trajectory = json.loads((tmp_path / "trajectory.json").read_text())
    assert next(step for step in trajectory["steps"] if step["source"] == "agent")["tool_calls"][0]["arguments"] == {}
    assert "observation" not in next(step for step in trajectory["steps"] if step["source"] == "agent")


@pytest.mark.parametrize("schema_version", [1, 2, 3, 4])
@pytest.mark.parametrize("outcome", [
    "completed", "max_turns_exhausted", "response_truncated", "time_budget_exhausted",
])
def test_journal_outcome_versions(schema_version, outcome):
    record = {
        "schema_version": schema_version, "run_id": "run-1", "seq": 1,
        "recorded_at": "2026-09-07T00:00:00.000Z", "type": "run.completed",
        "payload": {"outcome": outcome, "duration_ms": 1, "source_timestamp": None},
    }
    minimum_version = {"response_truncated": 2, "time_budget_exhausted": 4}.get(outcome, 1)
    if schema_version < minimum_version:
        with pytest.raises(ValueError, match=f"requires Journal Entry schema {minimum_version}"):
            JournalEntry.from_dict(record)
    else:
        assert JournalEntry.from_dict(record).to_dict() == record
