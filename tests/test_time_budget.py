"""A headless wall-clock budget must reach the model and stop the run.

Unlike ``max_turns`` (a count of replies), the time budget is what the harness
actually enforces. The loop has to tell the model how much time is left and
stop on its own before that harness timeout kills the process with nothing
written.
"""

import json

import pytest

from nanopycodeagent import agent, cli, settings
from nanopycodeagent.event_journal import EventJournal

from helpers import (
    FakeClient,
    FakeMessages,
    FakeStream,
    patch_client,
    text_block,
    tool_use_block,
)


class FakeTime:
    def __init__(self, start=1000.0):
        self.now = start

    def monotonic(self):
        return self.now

    def perf_counter_ns(self):
        return int(self.now * 1_000_000_000)

    def advance(self, seconds):
        self.now += seconds


class AdvancingFakeMessages(FakeMessages):
    """Advance a fake clock every time a model reply is requested."""

    def __init__(self, script, clock, seconds_per_call):
        super().__init__(script)
        self.clock = clock
        self.seconds_per_call = seconds_per_call

    def stream(self, **kwargs):
        self.clock.advance(self.seconds_per_call)
        return super().stream(**kwargs)


def _journal_entries():
    paths = list((settings.SETTINGS_PATH.parent / "journals").glob("*.jsonl"))
    assert len(paths) == 1
    return EventJournal.replay(paths[0])


def _texts(messages):
    """All text carried by a snapshot of the message list."""
    out = []
    for message in messages:
        content = message["content"]
        if isinstance(content, str):
            out.append(content)
        else:
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    out.append(block["text"])
    return "\n".join(out)


def _fake_bash(executions):
    def run_bash(command):
        executions.append(command)
        return "ok", False

    return run_bash


def test_time_budget_is_injected_and_stops_the_run(monkeypatch, capsys):
    clock = FakeTime()
    monkeypatch.setattr(agent, "time", clock)
    executions = []
    monkeypatch.setattr(agent, "run_bash", _fake_bash(executions))

    replies = [
        FakeStream([tool_use_block("call-1", "echo one")], stop_reason="tool_use"),
        FakeStream([tool_use_block("call-2", "echo two")], stop_reason="tool_use"),
        FakeStream([tool_use_block("call-3", "echo three")], stop_reason="tool_use"),
        FakeStream([text_block("done")], stop_reason="end_turn"),
    ]
    # 450s consumed per reply against a 1000s budget: the first two replies
    # still have room, the third lands in the reserved finalization window,
    # and by the fourth the deadline has already passed.
    messages = AdvancingFakeMessages(replies, clock, 450.0)
    patch_client(monkeypatch, FakeClient(messages))

    assert (
        cli.main(
            [
                "-p",
                "finish the task",
                "--max-turns",
                "10",
                "--time-budget-seconds",
                "1000",
            ]
        )
        == 0
    )

    # The third reply crossed the deadline, so its tools never run and a
    # fourth reply is never requested.
    assert len(messages.calls) == 3
    assert executions == ["echo one", "echo two"]

    # The reminder must not touch the system prompt: keeping it constant is what
    # lets the provider reuse its prefix cache. It rides at the tail instead.
    systems = [call["system"] for call in messages.kwargs]
    assert len(set(systems)) == 1
    assert "[time budget]" not in systems[0]
    assert "Elapsed 0:00 of 16:40; 16:40 remaining" in _texts(messages.calls[0])
    assert "Elapsed 7:30 of 16:40; 9:10 remaining" in _texts(messages.calls[1])
    final_text = _texts(messages.calls[2])
    assert "Only 1:40 of 16:40 left" in final_text
    assert "Stop investigating now" in final_text

    captured = capsys.readouterr()
    assert "1000s time budget" in captured.err
    assert "stopped after 10 turns" not in captured.err

    entries = _journal_entries()
    assert entries[0].payload["time_budget_seconds"] == 1000
    assert entries[-1].type == "run.completed"
    assert entries[-1].payload["outcome"] == "time_budget_exhausted"


def test_without_a_budget_the_system_prompt_is_unchanged(monkeypatch):
    clock = FakeTime()
    monkeypatch.setattr(agent, "time", clock)
    monkeypatch.setattr(agent, "run_bash", _fake_bash([]))
    messages = FakeMessages([FakeStream([text_block("done")], stop_reason="end_turn")])
    patch_client(monkeypatch, FakeClient(messages))

    assert cli.main(["-p", "just answer", "--max-turns", "5"]) == 0

    assert "[time budget]" not in messages.kwargs[0]["system"]
    assert "[time budget]" not in _texts(messages.calls[0])
    entries = _journal_entries()
    assert entries[0].payload["time_budget_seconds"] is None
    assert entries[-1].payload["outcome"] == "completed"
    assert not any(entry.type == "input.injected" for entry in entries)


@pytest.mark.parametrize("tool_seconds", [1, 2])
def test_deadline_is_checked_before_each_tool(monkeypatch, tmp_path, tool_seconds):
    clock = FakeTime()
    monkeypatch.setattr(agent, "time", clock)
    executions = []

    def run_bash(command):
        executions.append(command)
        clock.advance(tool_seconds)
        return "first result", False

    monkeypatch.setattr(agent, "run_bash", run_bash)
    messages = FakeMessages([
        FakeStream([
            tool_use_block("call-1", "first"),
            text_block("then another command"),
            tool_use_block("call-2", "second"),
        ], stop_reason="tool_use"),
    ])
    patch_client(monkeypatch, FakeClient(messages))
    trajectory_path = tmp_path / "trajectory.json"

    assert agent.run_headless(
        "task", time_budget_seconds=1, trajectory_path=trajectory_path
    ) == 0

    assert executions == ["first"]
    assert len(messages.calls) == 1
    entries = _journal_entries()
    assert entries[-1].payload["outcome"] == "time_budget_exhausted"
    tool_events = [entry for entry in entries if entry.type.startswith("tool.")]
    assert [(entry.type, entry.payload["tool_call_id"]) for entry in tool_events] == [
        ("tool.started", "call-1"), ("tool.completed", "call-1"),
    ]
    trajectory = json.loads(trajectory_path.read_text())
    assert trajectory["extra"]["terminal"]["outcome"] == "time_budget_exhausted"
    model_step = next(step for step in trajectory["steps"] if step["source"] == "agent")
    assert [call["tool_call_id"] for call in model_step["tool_calls"]] == ["call-1", "call-2"]
    assert [result["source_call_id"] for result in model_step["observation"]["results"]] == ["call-1"]


@pytest.mark.parametrize("structured_task", [False, True])
def test_budget_reminders_survive_journal_and_atif(monkeypatch, tmp_path, structured_task):
    clock = FakeTime()
    monkeypatch.setattr(agent, "time", clock)
    monkeypatch.setattr(agent, "run_bash", _fake_bash([]))
    messages = AdvancingFakeMessages([
        FakeStream([tool_use_block("call-1", "first")], stop_reason="tool_use"),
        FakeStream([tool_use_block("call-2", "second")], stop_reason="tool_use"),
        FakeStream([text_block("done")]),
    ], clock, 450)
    task = [{"type": "text", "text": "task"}] if structured_task else "task"
    trajectory_path = tmp_path / "trajectory.json"

    assert agent._run_exchange(
        FakeClient(messages), "test-model", [{"role": "user", "content": task}],
        agent.HEADLESS_SYSTEM_PROMPT, max_turns=10, time_budget_seconds=1000,
        trajectory_path=trajectory_path,
    ) == "completed"

    notes = []
    for call in messages.calls:
        content = call[-1]["content"]
        notes.append(content.split("\n\n")[-1] if isinstance(content, str) else content[-1]["text"])
    assert len(notes) == 3
    assert "Elapsed 0:00" in notes[0]
    assert "Elapsed 7:30" in notes[1]
    assert "Stop investigating now" in notes[2]
    assert "write your best answer to it" in notes[2]

    entries = _journal_entries()
    user_entry = next(entry for entry in entries if entry.type == "user.message")
    assert user_entry.payload["content"] == (
        [{"type": "text", "text": "task"}] if structured_task else "task"
    )
    reminders = [entry for entry in entries if entry.type == "input.injected"]
    assert [entry.payload["content"] for entry in reminders] == notes
    for entry in reminders:
        following = entries[entries.index(entry) + 1]
        assert following.type == "model.started"
        assert entry.payload["model_call_id"] == following.payload["model_call_id"]
        assert entry.payload["reason"] == "time_budget"

    trajectory = json.loads(trajectory_path.read_text())
    steps = trajectory["steps"]
    assert [step["source"] for step in steps] == [
        "user", "user", "agent", "user", "agent", "user", "agent",
    ]
    injected = [step for step in steps if step.get("extra", {}).get("injected")]
    assert [step["message"] for step in injected] == notes
    for step, entry in zip(injected, reminders, strict=True):
        assert step["extra"]["model_call_id"] == entry.payload["model_call_id"]
        assert step["extra"]["reason"] == "time_budget"
    for index, tool_id in ((2, "call-1"), (4, "call-2")):
        result = steps[index]["observation"]["results"][0]
        assert result["source_call_id"] == tool_id
        assert result["content"] == "ok"


@pytest.mark.parametrize("value", ["0", "-3"])
def test_non_positive_budget_is_a_usage_error(value, monkeypatch, capsys):
    messages = FakeMessages([])
    patch_client(monkeypatch, FakeClient(messages))
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["-p", "task", "--time-budget-seconds", value])
    assert excinfo.value.code == cli.EXIT_USAGE
    assert "at least 1" in capsys.readouterr().err


def test_finalization_note_escalates_below_the_reserve():
    early = agent._time_budget_note(
        turn=1, elapsed=10, budget=1000, remaining=990
    )
    late = agent._time_budget_note(
        turn=9, elapsed=990, budget=1000, remaining=10
    )
    assert "remaining" in early and "Stop investigating now" not in early
    assert "Stop investigating now" in late
