"""Recover response-body failures without replaying tools or partial replies."""

import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from nanopycodeagent import agent, settings
from nanopycodeagent.event_journal import EventJournal, JournalEntry

from helpers import FakeClient, FakeMessages, FakeStream, patch_client, sdk_http_module, text_block


def entries():
    path, = (settings.SETTINGS_PATH.parent / "journals").glob("*.jsonl")
    return EventJournal.replay(path)


class BrokenStream(FakeStream):
    def __init__(self, error):
        super().__init__([])
        self.error = error
        self.closed = False

    def __iter__(self):
        yield SimpleNamespace(type="text", text="partial")
        raise self.error

    def __exit__(self, *args):
        self.closed = True


@pytest.mark.parametrize("family", ["httpx", "httpx2"])
@pytest.mark.parametrize("error_name", ["ReadError", "ReadTimeout", "RemoteProtocolError"])
def test_transport_families_recover_and_preserve_failed_attempt(
    monkeypatch, tmp_path, family, error_name
):
    http = pytest.importorskip(family)
    sleeps = []
    monkeypatch.setattr(agent.time, "sleep", sleeps.append)
    broken = BrokenStream(getattr(http, error_name)("disconnected"))
    messages = FakeMessages([broken, [text_block("done")]])
    patch_client(monkeypatch, FakeClient(messages))
    trajectory_path = tmp_path / "trajectory.json"
    assert agent.run_headless("task", max_turns=1, trajectory_path=trajectory_path) == 0
    assert messages.calls[0] == messages.calls[1]
    assert broken.closed
    assert sleeps == [1.0]
    failed = [e for e in entries() if e.type == "model.failed"]
    assert len(failed) == 1 and failed[0].payload["will_retry"] is True
    trajectory = json.loads(trajectory_path.read_text())
    assert [s["message"] for s in trajectory["steps"]] == ["task", "partial", "done"]
    assert trajectory["steps"][1]["extra"]["incomplete"] is True
    assert trajectory["extra"]["terminal"]["outcome"] == "completed"
    assert trajectory["final_metrics"]["extra"]["usage_complete"] is False
    assert trajectory["final_metrics"]["extra"]["cost_is_partial"] is True


@pytest.mark.parametrize("family", ["httpx", "httpx2"])
def test_exhausted_retries_exit_cleanly_and_keep_all_attempts(monkeypatch, capsys, family):
    http = pytest.importorskip(family)
    sleeps = []
    monkeypatch.setattr(agent.time, "sleep", sleeps.append)
    streams = [BrokenStream(http.RemoteProtocolError("disconnected")) for _ in range(3)]
    messages = FakeMessages(streams)
    patch_client(monkeypatch, FakeClient(messages))
    assert agent.run_headless("task") == 1
    assert len(messages.calls) == 3
    assert all(stream.closed for stream in streams)
    assert sleeps == [1.0, 2.0]
    assert "API error: disconnected" in capsys.readouterr().err
    failures = [e for e in entries() if e.type == "model.failed"]
    assert [e.payload["will_retry"] for e in failures] == [True, True, False]
    assert len({e.payload["model_call_id"] for e in failures}) == 3
    assert entries()[-1].type == "run.failed"


def test_retry_window_stops_new_attempts_after_slow_retry(monkeypatch):
    clock = iter([0.0, 301.0])
    sleeps = []
    monkeypatch.setattr(agent, "time", SimpleNamespace(
        perf_counter_ns=agent.time.perf_counter_ns,
        monotonic=lambda: next(clock), sleep=sleeps.append,
    ))
    messages = FakeMessages([BrokenStream(httpx.ReadError("broken")) for _ in range(2)])
    patch_client(monkeypatch, FakeClient(messages))
    assert agent.run_headless("task") == 1
    assert len(messages.calls) == 2
    assert sleeps == [1.0]


@pytest.mark.parametrize("error", [ValueError("bug"), KeyboardInterrupt()])
def test_programming_errors_and_interrupts_are_not_retried(monkeypatch, error):
    messages = FakeMessages([BrokenStream(error)])
    patch_client(monkeypatch, FakeClient(messages))
    with pytest.raises(type(error)):
        agent.run_headless("task")
    assert len(messages.calls) == 1


def test_permanent_http_errors_are_not_retried(monkeypatch):
    messages = FakeMessages([BrokenStream(httpx.LocalProtocolError("bad request"))])
    patch_client(monkeypatch, FakeClient(messages))
    assert agent.run_headless("task") == 1
    assert len(messages.calls) == 1


def test_sdk_stream_retry_discards_partial_tool_and_does_not_replay_work(monkeypatch, tmp_path):
    http = sdk_http_module()
    requests = []
    closed = []
    monkeypatch.setattr(agent.time, "sleep", lambda _: None)
    monkeypatch.setattr(agent, "resolve_generation_cost", lambda *args, **kwargs: None)
    target = tmp_path / "answer.txt"

    def wire(events):
        return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()

    def start(number):
        return {"type": "message_start", "message": {
            "id": f"msg-{number}", "type": "message", "role": "assistant",
            "model": "test-model", "content": [], "stop_reason": None,
            "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 0},
        }}

    def finish(reason):
        return [
            {"type": "content_block_stop", "index": 0},
            {"type": "message_delta", "delta": {"stop_reason": reason, "stop_sequence": None},
             "usage": {"output_tokens": 5}},
            {"type": "message_stop"},
        ]

    class Body(http.SyncByteStream):
        def __init__(self, data, interrupt):
            self.data, self.interrupt = data, interrupt

        def __iter__(self):
            yield self.data
            if self.interrupt:
                raise http.RemoteProtocolError("incomplete chunked read")

        def close(self):
            closed.append(self.interrupt)

    def respond(request):
        requests.append(json.loads(request.content))
        number = len(requests)
        # First execute one append, then interrupt the next reply after its
        # complete-looking tool JSON. Reissuing that reply must not append twice.
        if number == 1:
            block = {"type": "tool_use", "id": "append", "name": "bash", "input": {}}
            args = {"command": f"printf x >> '{target}'"}
        elif number in (2, 3):
            block = {"type": "tool_use", "id": "discard" if number == 2 else "read", "name": "read", "input": {}}
            args = {"path": str(target)}
        else:
            block = {"type": "text", "text": "done"}
        events = [start(number), {"type": "content_block_start", "index": 0, "content_block": block}]
        if number < 4:
            events.append({"type": "content_block_delta", "index": 0,
                           "delta": {"type": "input_json_delta", "partial_json": json.dumps(args)}})
        if number != 2:
            events += finish("tool_use" if number < 4 else "end_turn")
        return http.Response(200, headers={"content-type": "text/event-stream", "x-generation-id": f"gen-{number}"},
                             stream=Body(wire(events), number == 2))

    with anthropic.Anthropic(api_key="test", base_url="https://example.test",
                            http_client=http.Client(transport=http.MockTransport(respond))) as client:
        patch_client(monkeypatch, client)
        trajectory_path = tmp_path / "trajectory.json"
        assert agent.run_headless("task", max_turns=3, trajectory_path=trajectory_path) == 0
    assert len(requests) == 4
    assert requests[1] == requests[2]
    assert target.read_text() == "x"
    assert closed.count(True) == 1
    tools = [e.payload["tool_call_id"] for e in entries() if e.type == "tool.started"]
    assert tools == ["append", "read"]
    failed = next(e for e in entries() if e.type == "model.failed")
    assert failed.payload["generation_id"] == "gen-2"
    trajectory = json.loads(trajectory_path.read_text())
    assert [s["extra"].get("incomplete", False) for s in trajectory["steps"]] == [False, False, True, False, False]


def test_interrupted_generation_cost_is_reconciled_without_inventing_usage(monkeypatch, tmp_path):
    monkeypatch.setattr(agent.time, "sleep", lambda _: None)
    broken = BrokenStream(httpx.ReadError("disconnected"))
    broken.response.headers = {"x-generation-id": "gen-broken"}
    reply = FakeStream([text_block("done")], usage=SimpleNamespace(input_tokens=5, output_tokens=2),
                       response_headers={"x-generation-id": "gen-done"})
    messages = FakeMessages([broken, reply])
    patch_client(monkeypatch, FakeClient(messages, base_url="https://openrouter.ai/api"))
    looked_up = []

    def resolve(base_url, generation_id, credential, **kwargs):
        looked_up.append(generation_id)
        return {"generation_id": generation_id, "amount": "0.01", "currency": "USD", "source": "test"}

    monkeypatch.setattr(agent, "resolve_generation_cost", resolve)
    path = tmp_path / "trajectory.json"
    assert agent.run_headless("task", trajectory_path=path) == 0
    assert looked_up == ["gen-broken", "gen-done"]
    final = json.loads(path.read_text())["final_metrics"]
    assert final["total_cost_usd"] == 0.02
    assert final["extra"]["usage_complete"] is False
    assert "total_prompt_tokens" not in final


@pytest.mark.parametrize("schema", [1, 2, 3])
def test_failed_attempt_requires_v3_schema(schema):
    record = {
        "schema_version": schema, "run_id": "run-1", "seq": 1,
        "recorded_at": "2026-09-15T00:00:00.000Z", "type": "model.failed",
        "payload": {
            "model_call_id": "model-1", "error_type": "ReadError", "message": "broken",
            "generation_id": None, "duration_ms": 12, "will_retry": True,
            "retry_delay_seconds": 1, "source_timestamp": None,
        },
    }
    if schema < 3:
        with pytest.raises(ValueError, match="requires Journal Entry schema 3"):
            JournalEntry.from_dict(record)
    else:
        assert JournalEntry.from_dict(record).to_dict() == record
