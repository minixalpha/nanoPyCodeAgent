"""A headless wall-clock budget must reach the model and stop the run.

Unlike ``max_turns`` (a count of replies), the time budget is what the harness
actually enforces. The loop has to tell the model how much time is left and
stop on its own before that harness timeout kills the process with nothing
written.
"""

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

    assert "Elapsed 0:00 of 16:40; 16:40 remaining" in messages.kwargs[0]["system"]
    assert "Elapsed 7:30 of 16:40; 9:10 remaining" in messages.kwargs[1]["system"]
    final_system = messages.kwargs[2]["system"]
    assert "Only 1:40 of 16:40 left" in final_system
    assert "Stop investigating now" in final_system

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
    entries = _journal_entries()
    assert entries[0].payload["time_budget_seconds"] is None
    assert entries[-1].payload["outcome"] == "completed"


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
