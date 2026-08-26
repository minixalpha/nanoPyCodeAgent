"""End-to-end event and text-projection tests for the agent loop."""

from importlib.metadata import version
from types import SimpleNamespace

import httpx
import pytest

from nanopycodeagent import agent, settings
from nanopycodeagent.event_journal import EventJournal

from helpers import (
    FakeClient,
    FakeMessages,
    FakeStream,
    patch_client,
    read_tool_use_block,
    text_block,
)


def _only_journal_path():
    paths = list((settings.SETTINGS_PATH.parent / "journals").glob("*.jsonl"))
    assert len(paths) == 1
    return paths[0]


def test_headless_model_reply_is_journaled_without_changing_stdout(
    monkeypatch, capsys
):
    usage = SimpleNamespace(
        input_tokens=12,
        output_tokens=3,
        cache_read_input_tokens=5,
        cache_creation_input_tokens=2,
    )
    reply = FakeStream(
        [text_block("done")],
        message_id="msg-provider-1",
        model="actual-model",
        usage=usage,
        response_headers={"x-generation-id": "gen-1"},
    )
    patch_client(monkeypatch, FakeClient(FakeMessages([reply])))

    assert agent.run_headless("fix it") == 0

    captured = capsys.readouterr()
    assert captured.out == "done\n"

    entries = EventJournal.replay(_only_journal_path())
    assert [entry.type for entry in entries] == [
        "run.started",
        "user.message",
        "model.started",
        "model.output_delta",
        "model.completed",
        "run.completed",
    ]
    assert [entry.seq for entry in entries] == [1, 2, 3, 4, 5, 6]
    assert all("timestamp_source" not in entry.payload for entry in entries)

    started_run = entries[0].payload
    assert started_run["producer"] == {
        "name": "nanoPyCodeAgent",
        "version": version("nanoPyCodeAgent"),
    }

    user = entries[1].payload
    assert user["content"] == "fix it"
    assert user["message_id"]

    started = entries[2].payload
    completed = entries[4].payload
    assert completed["model_call_id"] == started["model_call_id"]
    assert completed["message_id"] == "msg-provider-1"
    assert completed["provider_response_id"] == "msg-provider-1"
    assert completed["generation_id"] == "gen-1"
    assert completed["model"] == "actual-model"
    assert completed["stop_reason"] == "end_turn"
    assert completed["content"] == [{"type": "text", "text": "done"}]
    assert completed["tool_calls"] == []
    assert completed["usage"] == {
        "input_tokens": 12,
        "output_tokens": 3,
        "cache_read_input_tokens": 5,
        "cache_creation_input_tokens": 2,
    }
    assert completed["duration_ms"] >= 0
    assert completed["source_timestamp"].endswith("Z")
    assert entries[-1].payload["outcome"] == "completed"


def test_model_duration_ends_before_local_response_normalization(monkeypatch):
    reply = FakeStream([text_block("done")], message_id="msg-provider-1")
    patch_client(monkeypatch, FakeClient(FakeMessages([reply])))
    clock_calls = []

    def monotonic_ns():
        clock_calls.append(None)
        return len(clock_calls) * 1_000_000

    original_normalize = agent._native_content_blocks

    def normalize_after_model_timing(value):
        assert len(clock_calls) == 3
        return original_normalize(value)

    monkeypatch.setattr(agent.time, "perf_counter_ns", monotonic_ns)
    monkeypatch.setattr(agent, "_native_content_blocks", normalize_after_model_timing)

    assert agent.run_headless("fix it") == 0

    entries = EventJournal.replay(_only_journal_path())
    completed = next(entry for entry in entries if entry.type == "model.completed")
    assert completed.payload["duration_ms"] == 1


def test_failed_tool_events_project_the_existing_tool_output(
    monkeypatch, capsys, tmp_path
):
    missing = tmp_path / "missing.txt"
    tool_reply = FakeStream(
        [read_tool_use_block("tool-1", path=str(missing))],
        stop_reason="tool_use",
        message_id="msg-tools",
    )
    final_reply = FakeStream([text_block("recovered")], message_id="msg-final")
    patch_client(
        monkeypatch,
        FakeClient(FakeMessages([tool_reply, final_reply])),
    )

    assert agent.run_headless("read the file") == 0

    captured = capsys.readouterr()
    assert captured.out == (
        f"[read] {missing}\n[file not found: {missing}]\nrecovered\n"
    )

    entries = EventJournal.replay(_only_journal_path())
    assert [entry.type for entry in entries] == [
        "run.started",
        "user.message",
        "model.started",
        "model.completed",
        "tool.started",
        "tool.completed",
        "model.started",
        "model.output_delta",
        "model.completed",
        "run.completed",
    ]
    first_model_call_id = entries[2].payload["model_call_id"]
    first_model_completed = entries[3].payload
    started = entries[4].payload
    completed = entries[5].payload
    expected_tool_call = {
        "type": "tool_call",
        "tool_call_id": "tool-1",
        "tool_name": "read",
        "input": {"path": str(missing)},
    }
    assert first_model_completed["content"] == [expected_tool_call]
    assert first_model_completed["tool_calls"] == [expected_tool_call]
    assert started["model_call_id"] == first_model_call_id
    assert started["tool_call_id"] == "tool-1"
    assert started["tool_name"] == "read"
    assert started["input"] == {"path": str(missing)}
    assert started["source_timestamp"].endswith("Z")
    assert "timestamp_source" not in started
    assert completed["model_call_id"] == first_model_call_id
    assert completed["tool_call_id"] == "tool-1"
    assert completed["tool_name"] == "read"
    assert completed["result"] == f"[file not found: {missing}]"
    assert completed["is_error"] is True
    assert completed["duration_ms"] >= 0
    assert "timestamp_source" not in completed


def test_interrupted_model_stream_preserves_partial_stdout_and_records_failure(
    monkeypatch, capsys
):
    class DisconnectingStream(FakeStream):
        @property
        def text_stream(self):
            def _chunks():
                yield "partial"
                raise httpx.ReadError(
                    "peer disconnected",
                    request=httpx.Request("POST", "https://example.test/messages"),
                )

            return _chunks()

    patch_client(
        monkeypatch,
        FakeClient(FakeMessages([DisconnectingStream([])])),
    )

    assert agent.run_headless("keep going") == 1

    captured = capsys.readouterr()
    assert captured.out == "partial"
    assert "API error: peer disconnected" in captured.err

    entries = EventJournal.replay(_only_journal_path())
    assert [entry.type for entry in entries] == [
        "run.started",
        "user.message",
        "model.started",
        "model.output_delta",
        "run.failed",
    ]
    failure = entries[-1].payload
    assert failure["error_type"] == "ReadError"
    assert failure["message"] == "peer disconnected"
    assert failure["duration_ms"] >= 0
    assert "timestamp_source" not in failure


def test_unexpected_tool_exception_is_completed_before_the_run_fails(
    monkeypatch, capsys, tmp_path
):
    target = tmp_path / "notes.txt"
    tool_reply = FakeStream(
        [read_tool_use_block("tool-raises", path=str(target))],
        stop_reason="tool_use",
    )
    patch_client(monkeypatch, FakeClient(FakeMessages([tool_reply])))

    def raise_from_read(*args, **kwargs):
        raise RuntimeError("disk disappeared")

    monkeypatch.setattr(agent, "run_read", raise_from_read)

    with pytest.raises(RuntimeError, match="disk disappeared"):
        agent.run_headless("read notes")

    captured = capsys.readouterr()
    assert captured.out == f"[read] {target}\n"

    entries = EventJournal.replay(_only_journal_path())
    assert [entry.type for entry in entries] == [
        "run.started",
        "user.message",
        "model.started",
        "model.completed",
        "tool.started",
        "tool.completed",
        "run.failed",
    ]
    tool_failure = entries[-2].payload
    assert tool_failure["tool_call_id"] == "tool-raises"
    assert tool_failure["result"] is None
    assert tool_failure["is_error"] is True
    assert tool_failure["error"] == {
        "type": "RuntimeError",
        "message": "disk disappeared",
    }
    assert tool_failure["duration_ms"] >= 0
