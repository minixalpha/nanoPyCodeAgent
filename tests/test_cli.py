"""Tests for the command line: how a task gets in, and what comes back out.

Every Anthropic API access is mocked, so these tests never hit the network and
never spend tokens. The exit codes are the point of most of them: a harness
reads a non-zero code as "this agent broke" and may pay to retry the trial, so
a task that merely went badly has to come back as 0.
"""

import io

import anthropic
import httpx
import pytest

from nanopycodeagent import agent, cli

from helpers import (
    FakeClient,
    FakeMessages,
    FakeStream,
    patch_client,
    patch_client_and_input,
    text_block,
    tool_use_block,
    write_tool_use_block,
)


class TtyStdin(io.StringIO):
    """A stdin that claims to be a terminal, i.e. nothing was piped in."""

    def isatty(self):
        return True


def test_package_entry_point_is_the_cli():
    # pyproject points the console script at nanopycodeagent:main, and the
    # wrapper it generates exits with whatever that returns.
    from nanopycodeagent import main

    assert main is cli.main


def test_prompt_argument_runs_the_task_and_exits_zero(monkeypatch, capsys):
    messages = FakeMessages([[text_block("done")]])
    patch_client(monkeypatch, FakeClient(messages))

    assert cli.main(["-p", "say hi"]) == 0

    assert messages.calls[0] == [{"role": "user", "content": "say hi"}]
    # The headless prompt goes out, not the conversational one.
    assert messages.kwargs[0]["system"] == agent.HEADLESS_SYSTEM_PROMPT
    out = capsys.readouterr().out
    assert "done" in out
    # stdout is the run itself: no chat prompts wrapped around the reply.
    assert "Agent>" not in out
    assert "You>" not in out


def test_stdin_pipe_is_taken_as_the_task(monkeypatch, capsys):
    # printf "%s" "$TASK" | nanoPyCodeAgent — how a harness avoids shell
    # quoting and command-length limits.
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO("fix the bug\n"))
    messages = FakeMessages([[text_block("fixed")]])
    patch_client(monkeypatch, FakeClient(messages))

    assert cli.main([]) == 0

    assert messages.calls[0] == [{"role": "user", "content": "fix the bug"}]


def test_prompt_file_is_read_as_the_task(monkeypatch, tmp_path, capsys):
    task_file = tmp_path / "instruction.md"
    task_file.write_text("port the parser\n", encoding="utf-8")
    messages = FakeMessages([[text_block("ported")]])
    patch_client(monkeypatch, FakeClient(messages))

    assert cli.main(["--prompt-file", str(task_file)]) == 0

    assert messages.calls[0] == [{"role": "user", "content": "port the parser"}]


def test_banner_stays_off_stdout_in_a_headless_run(monkeypatch, capsys):
    messages = FakeMessages([[text_block("done")]])
    patch_client(monkeypatch, FakeClient(messages))

    cli.main(["-p", "say hi"])

    captured = capsys.readouterr()
    assert "nanoPyCodeAgent v" not in captured.out  # stdout carries the run
    assert "nanoPyCodeAgent v" in captured.err  # the banner still lands in logs


def test_no_task_on_a_terminal_starts_an_interactive_session(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys, "stdin", TtyStdin())
    messages = FakeMessages([[text_block("hello there")]])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["hi", "/exit"])

    assert cli.main([]) == 0

    out = capsys.readouterr().out
    assert "Bye!" in out
    # The conversational prompt is the one an interactive session sends.
    assert messages.kwargs[0]["system"] == agent.SYSTEM_PROMPT


def test_missing_credentials_exit_non_zero(monkeypatch, capsys):
    messages = FakeMessages([])
    patch_client(monkeypatch, FakeClient(messages, api_key=None, auth_token=None))

    # A run that never happened is the harness's problem, not the task's.
    assert cli.main(["-p", "say hi"]) == 1

    assert "No API credentials found." in capsys.readouterr().err
    assert messages.calls == []


def test_exhausted_turn_budget_still_exits_zero(monkeypatch, capsys, tmp_path):
    # Two replies are all the budget allows; the second one's tool call is
    # never run, because no reply is left to read its result.
    marker = tmp_path / "second_turn.txt"
    first = FakeStream([tool_use_block("tu_1", "echo one")], stop_reason="tool_use")
    second = FakeStream(
        [write_tool_use_block("tu_2", path=str(marker), content="x")],
        stop_reason="tool_use",
    )
    messages = FakeMessages([first, second])
    patch_client(monkeypatch, FakeClient(messages))

    assert cli.main(["-p", "loop forever", "--max-turns", "2"]) == 0

    assert len(messages.calls) == 2
    assert not marker.exists()
    captured = capsys.readouterr()
    assert "[bash]$ echo one" in captured.out  # tool activity lands in the log
    assert "stopped after 2 turns" in captured.err


def test_api_error_is_reported_verbatim_and_exits_non_zero(monkeypatch, capsys):
    # A harness classifies a failed run by pattern-matching this text, so it
    # goes out unedited.
    class ExplodingMessages:
        calls: list = []

        def stream(self, **kwargs):
            raise anthropic.APIConnectionError(
                message="Overloaded (529)",
                request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
            )

    patch_client(monkeypatch, FakeClient(ExplodingMessages()))

    assert cli.main(["-p", "say hi"]) == 1

    assert "Overloaded (529)" in capsys.readouterr().err


def test_empty_task_is_a_usage_error(monkeypatch):
    patch_client(monkeypatch, FakeClient(FakeMessages([])))

    with pytest.raises(SystemExit) as excinfo:
        cli.main(["-p", "   "])

    assert excinfo.value.code == cli.EXIT_USAGE


def test_empty_stdin_is_a_usage_error(monkeypatch):
    # The container case: stdin is redirected but carries nothing. Starting a
    # session here is what used to make the agent print "Bye!" and do nothing.
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO(""))
    patch_client(monkeypatch, FakeClient(FakeMessages([])))

    with pytest.raises(SystemExit) as excinfo:
        cli.main([])

    assert excinfo.value.code == cli.EXIT_USAGE


def test_unreadable_prompt_file_is_a_usage_error(monkeypatch, tmp_path, capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--prompt-file", str(tmp_path / "missing.md")])

    assert excinfo.value.code == cli.EXIT_USAGE
    assert "cannot read --prompt-file" in capsys.readouterr().err


def test_prompt_and_prompt_file_are_mutually_exclusive(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["-p", "a task", "--prompt-file", str(tmp_path / "task.md")])

    assert excinfo.value.code == cli.EXIT_USAGE


def test_max_turns_must_be_positive():
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["-p", "say hi", "--max-turns", "0"])

    assert excinfo.value.code == cli.EXIT_USAGE


def test_version_flag_prints_the_version(capsys):
    # Harbor probes an installed agent's version with its own --version call.
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--version"])

    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert f"nanoPyCodeAgent {agent._package_version()}" in out
    assert "unknown" not in out  # metadata is present in the test environment
