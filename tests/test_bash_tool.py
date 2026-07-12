"""Tests for the ``bash`` tool's execution (``bash_tool.py``).

These run real bash commands; the timeout and output cap are patched down so
every case finishes quickly.
"""

from nanopycodeagent import bash_tool


def test_run_bash_captures_stdout():
    output, is_error = bash_tool.run_bash("echo hello")

    assert output == "hello"
    assert is_error is False


def test_run_bash_reports_stderr_and_exit_code():
    output, is_error = bash_tool.run_bash("echo oops >&2; exit 3")

    assert "[stderr]\noops" in output
    assert "[exit code: 3]" in output
    # A command that ran to completion is a successful tool call whatever its
    # exit code — the code is reported in the text, and is_error stays
    # reserved for tool failures (timeout). A non-zero exit is often a valid
    # negative answer, e.g. grep finding no match.
    assert is_error is False


def test_run_bash_placeholder_for_empty_output():
    output, is_error = bash_tool.run_bash("true")

    assert output == "(no output)"
    assert is_error is False


def test_run_bash_times_out(monkeypatch):
    monkeypatch.setattr(bash_tool, "BASH_TIMEOUT_SECONDS", 0.2)

    output, is_error = bash_tool.run_bash("sleep 5")

    assert "timed out" in output
    assert is_error is True


def test_run_bash_does_not_read_the_terminal_stdin(monkeypatch):
    # A command that reads stdin must see EOF immediately (stdin is
    # /dev/null), not block on — and consume — the user's terminal input.
    monkeypatch.setattr(bash_tool, "BASH_TIMEOUT_SECONDS", 5)

    output, is_error = bash_tool.run_bash("cat; echo done")

    assert output == "done"
    assert is_error is False


def test_run_bash_truncates_long_output(monkeypatch):
    monkeypatch.setattr(bash_tool, "MAX_TOOL_OUTPUT_CHARS", 10)

    output, is_error = bash_tool.run_bash("printf 'a%.0s' {1..100}")

    assert output == "a" * 10 + "\n[... output truncated ...]"
    assert is_error is False
