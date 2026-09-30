"""Invalid model calls must yield recoverable results without side effects."""

import json
from types import SimpleNamespace

import anthropic
import pytest

from nanopycodeagent import agent, settings
from nanopycodeagent.event_journal import EventJournal

from helpers import (
    FakeClient,
    FakeMessages,
    FakeStream,
    edit_tool_use_block,
    patch_client,
    patch_client_and_input,
    sdk_http_module,
    text_block,
    write_tool_use_block,
)


def journal_entries():
    path, = (settings.SETTINGS_PATH.parent / "journals").glob("*.jsonl")
    return EventJournal.replay(path)


@pytest.mark.parametrize(("name", "arguments", "diagnostic"), [
    ("read", {}, "path"),
    ("write", {"path": "file"}, "content"),
    ("write", {"content": "text"}, "path"),
    ("edit", {"old_text": "old", "new_text": "new"}, "path"),
    ("edit", {"path": "file", "new_text": "new"}, "old_text"),
    ("edit", {"path": "file", "old_text": "old"}, "new_text"),
    ("bash", {}, "command"),
    ("read", {"path": None}, "path must be string"),
    ("read", {"path": [], "offset": 1}, "path must be string"),
    ("read", {"path": "file", "offset": True}, "offset must be integer"),
    ("read", {"path": "file", "limit": 1.5}, "limit must be integer"),
    ("read", {"path": "file", "limit": None}, "limit must be integer"),
    ("write", {"path": "file", "content": 3}, "content must be string"),
    ("edit", {"path": "file", "old_text": None, "new_text": ""}, "old_text must be string"),
    ("edit", {"path": "file", "old_text": "old", "new_text": []}, "new_text must be string"),
    ("edit", {"path": "file", "old_text": "old", "new_text": "new", "replace_all": "false"}, "replace_all must be boolean"),
    ("bash", {"command": ["echo", "hello"]}, "command must be string"),
    ("read", {"path": "a\x00b"}, "NUL"),
    ("bash", {"command": "echo\x00hello"}, "NUL"),
    ("unoffered", {"command": "echo must-not-run"}, "Unknown tool"),
    ("write", [], "expected a JSON object"),
    ("bash", "echo must-not-run", "expected a JSON object"),
    ("read", None, "expected a JSON object"),
])
def test_invalid_calls_are_reported_without_executing(
    monkeypatch, tmp_path, capsys, name, arguments, diagnostic
):
    def must_not_run(*args, **kwargs):
        pytest.fail("Invalid input reached a tool implementation")

    for tool in ("read", "write", "edit", "bash"):
        monkeypatch.setattr(agent, "run_" + tool, must_not_run)
    block = SimpleNamespace(type="tool_use", id="bad", name=name, input=arguments)
    messages = FakeMessages([
        FakeStream([block], stop_reason="tool_use"), [text_block("done")],
    ])
    patch_client(monkeypatch, FakeClient(messages))
    trajectory_path = tmp_path / "trajectory.json"

    assert agent.run_headless("work", trajectory_path=trajectory_path) == 0

    result, = [block for block in messages.calls[1][-1]["content"] if block["type"] == "tool_result"]
    assert result["tool_use_id"] == "bad" and result["is_error"] is True
    assert diagnostic in result["content"]
    assert "not executed" in capsys.readouterr().out
    entries = journal_entries()
    completed = next(e for e in entries if e.type == "tool.completed")
    assert completed.payload["result"] == result["content"]
    assert completed.payload["error"]["type"] == "ToolInputError"
    assert entries[-1].payload["outcome"] == "completed"
    trajectory = json.loads(trajectory_path.read_text())
    step = next(step for step in trajectory["steps"] if step["source"] == "agent")
    observation, = step["observation"]["results"]
    assert observation["source_call_id"] == "bad"
    assert observation["extra"]["is_error"] is True
    if not isinstance(arguments, dict):
        assert step["tool_calls"][0]["extra"]["raw_input"] == arguments
        assert messages.calls[1][-2]["content"][0].input == {}


@pytest.mark.parametrize("interactive", [False, True])
def test_model_corrects_bad_call_and_keeps_successful_sibling(
    monkeypatch, tmp_path, interactive
):
    target = tmp_path / "result.txt"
    good = write_tool_use_block("good", path=str(target), content="original")
    bad = edit_tool_use_block("bad", old_text="original", new_text="corrected")
    correction = edit_tool_use_block(
        "fixed", path=str(target), old_text="original", new_text="corrected"
    )
    messages = FakeMessages([
        FakeStream([good, bad], stop_reason="tool_use"),
        FakeStream([correction], stop_reason="tool_use"),
        [text_block("done")],
    ])
    client = FakeClient(messages)
    if interactive:
        prompts = patch_client_and_input(monkeypatch, client=client, inputs=["work", "/exit"])
        assert agent.run() == 0
        assert len(prompts) == 2
    else:
        patch_client(monkeypatch, client)
        assert agent.run_headless("work", max_turns=3) == 0

    assert target.read_text() == "corrected"
    results = [block for block in messages.calls[1][-1]["content"] if block["type"] == "tool_result"]
    assert [r["tool_use_id"] for r in results] == ["good", "bad"]
    assert [r["is_error"] for r in results] == [False, True]
    assert messages.calls[2][-1]["content"][0]["is_error"] is False
    starts = [e.payload["tool_call_id"] for e in journal_entries() if e.type == "tool.started"]
    assert starts == ["good", "bad", "fixed"]


def test_repeated_invalid_calls_do_not_reset_turn_budget(monkeypatch):
    messages = FakeMessages([
        FakeStream([write_tool_use_block(str(i))], stop_reason="tool_use")
        for i in range(3)
    ])
    patch_client(monkeypatch, FakeClient(messages))
    assert agent.run_headless("work", max_turns=3) == 0
    assert len(messages.calls) == 3
    entries = journal_entries()
    assert len([e for e in entries if e.type == "tool.completed"]) == 2
    assert entries[-1].payload["outcome"] == "max_turns_exhausted"


def test_valid_empty_strings_and_extra_fields_remain_allowed(monkeypatch, tmp_path):
    target = tmp_path / "empty.txt"
    messages = FakeMessages([
        FakeStream([write_tool_use_block("empty", path=str(target), content="", extra=1)], stop_reason="tool_use"),
        [text_block("done")],
    ])
    patch_client(monkeypatch, FakeClient(messages))
    assert agent.run_headless("work") == 0
    assert target.read_bytes() == b""
    assert messages.calls[1][-1]["content"][0]["is_error"] is False


def test_programming_keyerror_is_not_converted_to_argument_feedback(monkeypatch):
    def broken(*args):
        raise KeyError("internal bug")

    monkeypatch.setattr(agent, "run_write", broken)
    messages = FakeMessages([
        FakeStream([write_tool_use_block("valid", path="file", content="text")], stop_reason="tool_use"),
    ])
    patch_client(monkeypatch, FakeClient(messages))
    with pytest.raises(KeyError, match="internal bug"):
        agent.run_headless("work")
    assert journal_entries()[-1].type == "run.failed"


@pytest.mark.parametrize("bad_json", [
    "{}", "{", '{"command":"unfinished',
    # The SDK can already expose the complete value despite the missing brace.
    '{"command":"echo must-not-run"', "[]", "null",
])
def test_real_sdk_bad_input_is_rejected_and_corrected(
    monkeypatch, tmp_path, bad_json
):
    httpx = sdk_http_module()
    requests = []
    executions = []

    def run_bash(command):
        executions.append(command)
        return "ok", False

    monkeypatch.setattr(agent, "run_bash", run_bash)

    def respond(request):
        requests.append(json.loads(request.content))
        turn = len(requests)
        events = [{"type": "message_start", "message": {
            "id": f"msg-{turn}", "type": "message", "role": "assistant",
            "model": "test-model", "content": [], "stop_reason": None,
            "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 0},
        }}]
        if turn < 3:
            events += [
                {"type": "content_block_start", "index": 0, "content_block": {
                    "type": "tool_use", "id": f"call-{turn}", "name": "bash", "input": {},
                }},
                {"type": "content_block_delta", "index": 0, "delta": {
                    "type": "input_json_delta", "partial_json": bad_json if turn == 1 else '{"command":"echo corrected"}',
                }},
                {"type": "content_block_stop", "index": 0},
            ]
        events += [
            {"type": "message_delta", "delta": {
                "stop_reason": "tool_use" if turn < 3 else "end_turn", "stop_sequence": None,
            }, "usage": {"output_tokens": 20}},
            {"type": "message_stop"},
        ]
        wire = "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=wire)

    trajectory_path = tmp_path / "trajectory.json"
    with anthropic.Anthropic(
        api_key="test-key", base_url="https://example.test",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    ) as client:
        patch_client(monkeypatch, client)
        assert agent.run_headless("work", max_turns=3, trajectory_path=trajectory_path) == 0

    assert executions == ["echo corrected"]
    assert len(requests) == 3
    rejected = requests[1]["messages"][-1]["content"][0]
    assert rejected["is_error"] is True and rejected["tool_use_id"] == "call-1"
    assert requests[1]["messages"][-2]["content"][0]["input"] == {}
    assert requests[2]["messages"][-1]["content"][0]["is_error"] is False
    trajectory = json.loads(trajectory_path.read_text())
    call = next(step for step in trajectory["steps"] if step["source"] == "agent")["tool_calls"][0]
    if bad_json.startswith("{") and bad_json != "{}":
        assert call["extra"]["input_json"] == bad_json
        assert "JSON" in rejected["content"]
    assert trajectory["final_metrics"]["total_completion_tokens"] == 60
    assert trajectory["extra"]["terminal"]["outcome"] == "completed"
