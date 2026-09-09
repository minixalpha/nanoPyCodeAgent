"""Generation limits must reach every request and remain observable."""

import io
import json
from types import SimpleNamespace

import pytest

from nanopycodeagent import agent, cli, settings
from nanopycodeagent.event_journal import EventJournal, NativeEvent

from helpers import (
    FakeClient,
    FakeMessages,
    FakeStream,
    patch_client,
    patch_client_and_input,
    read_tool_use_block,
    text_block,
    write_settings,
)


class TtyStdin(io.StringIO):
    def isatty(self):
        return True


@pytest.mark.parametrize("interactive", [False, True])
@pytest.mark.parametrize("file_value,env_value,cli_value,expected", [
    (None, None, None, 32768),
    ("16384", None, None, 16384),
    ("8192", "65536", None, 65536),
    ("invalid", "16384", None, 16384),
    ("invalid", "invalid", "1024", 1024),
    (None, None, "1", 1),
])
def test_budget_precedence_reaches_every_request_and_execution_record(
    monkeypatch, tmp_path, capsys, interactive, file_value, env_value, cli_value, expected
):
    if file_value is not None:
        write_settings(settings.SETTINGS_PATH, {"ANTHROPIC_MAX_TOKENS": file_value})
    if env_value is not None:
        monkeypatch.setenv("ANTHROPIC_MAX_TOKENS", env_value)
    target = tmp_path / "input.txt"
    target.write_text("hello")
    usage = SimpleNamespace(input_tokens=10, output_tokens=1)
    messages = FakeMessages([
        FakeStream([read_tool_use_block("read-1", path=str(target))],
                   stop_reason="tool_use", usage=usage),
        FakeStream([text_block("done")], usage=usage),
    ])
    patch_client_and_input(monkeypatch, client=FakeClient(messages), inputs=["read it", "/exit"])
    trajectory_path = tmp_path / "trajectory.json"
    if interactive:
        monkeypatch.setattr(cli.sys, "stdin", TtyStdin())
        args = []
    else:
        args = ["-p", "read it", "--trajectory", str(trajectory_path)]
    if cli_value is not None:
        args += ["--max-tokens", cli_value]

    assert cli.main(args) == 0

    assert [request["max_tokens"] for request in messages.kwargs] == [expected, expected]
    captured = capsys.readouterr()
    assert f"max tokens {expected}" in (captured.out if interactive else captured.err)
    journal_path, = (tmp_path / "journals").glob("*.jsonl")
    entries = EventJournal.replay(journal_path)
    assert entries[0].payload["max_tokens"] == expected
    assert entries[-1].payload["outcome"] == "completed"
    if not interactive:
        trajectory = json.loads(trajectory_path.read_text())
        assert trajectory["agent"]["extra"]["max_tokens"] == expected
        assert trajectory["final_metrics"]["total_completion_tokens"] == 2


@pytest.mark.parametrize("source", ["cli", "env", "file"])
@pytest.mark.parametrize("value", ["0", "-1", "3.5", "invalid"])
def test_invalid_budget_fails_before_starting_a_run(monkeypatch, tmp_path, capsys, source, value):
    args = ["-p", "do not run"]
    if source == "cli":
        args += ["--max-tokens", value]
    elif source == "env":
        monkeypatch.setenv("ANTHROPIC_MAX_TOKENS", value)
    else:
        write_settings(settings.SETTINGS_PATH, {"ANTHROPIC_MAX_TOKENS": value})
    messages = FakeMessages([])
    patch_client(monkeypatch, FakeClient(messages))

    with pytest.raises(SystemExit) as excinfo:
        cli.main(args)

    assert excinfo.value.code == cli.EXIT_USAGE
    diagnostic = "--max-tokens" if source == "cli" else "ANTHROPIC_MAX_TOKENS"
    assert diagnostic in capsys.readouterr().err
    assert messages.calls == []
    assert not (tmp_path / "journals").exists()


def test_direct_headless_entry_point_honors_environment(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MAX_TOKENS", "16384")
    messages = FakeMessages([[text_block("done")]])
    patch_client(monkeypatch, FakeClient(messages))
    assert agent.run_headless("say hi") == 0
    assert messages.kwargs[0]["max_tokens"] == 16384


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "32768", None])
def test_journal_rejects_invalid_recorded_budgets(value):
    with pytest.raises(ValueError, match="run.started.max_tokens"):
        NativeEvent("run.started", {
            "mode": "headless", "model": "test", "max_turns": 50,
            "max_tokens": value,
            "producer": {"name": "nanoPyCodeAgent", "version": "test"},
            "source_timestamp": None,
        })
