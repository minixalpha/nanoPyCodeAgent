"""End-to-end event and text-projection tests for the agent loop."""

from types import SimpleNamespace

import httpx

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


def test_headless_model_reply_is_journaled_without_changing_stdout(monkeypatch, capsys):
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


def test_failed_tool_events_project_the_existing_tool_transcript(
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
    started = entries[4].payload
    completed = entries[5].payload
    assert started["model_call_id"] == first_model_call_id
    assert started["tool_call_id"] == "tool-1"
    assert started["tool_name"] == "read"
    assert started["input"] == {"path": str(missing)}
    assert started["source_timestamp"].endswith("Z")
    assert started["timestamp_source"] == "core"
    assert completed["model_call_id"] == first_model_call_id
    assert completed["tool_call_id"] == "tool-1"
    assert completed["tool_name"] == "read"
    assert completed["result"] == f"[file not found: {missing}]"
    assert completed["is_error"] is True
    assert completed["duration_ms"] >= 0


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
