"""Tests for the ``bash`` tool's execution (``bash_tool.py``).

These run real bash commands; the timeouts and output caps are patched down so
every case finishes quickly.
"""

import time

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
    # reserved for tool failures (timeout, bash missing). A non-zero exit is
    # often a valid negative answer, e.g. grep finding no match.
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


def test_run_bash_returns_when_background_child_keeps_output_open(monkeypatch):
    # A backgrounded child inherits bash's stdout/stderr; run_bash must wait
    # for bash itself, not for the output streams to close, or a plain
    # "start a server" command stalls until the timeout and is reported as a
    # spurious failure.
    monkeypatch.setattr(bash_tool, "BASH_TIMEOUT_SECONDS", 5)

    output, is_error = bash_tool.run_bash("echo started; sleep 10 &")

    assert output == "started"
    assert is_error is False


def test_run_bash_timeout_kills_the_whole_process_tree(monkeypatch, tmp_path):
    # On timeout the work the command forked must die with it: a surviving
    # grandchild would keep burning CPU or holding ports after the tool
    # reported "timed out". The subshell below would write the marker after
    # the timeout fires — it only stays absent if the group was killed.
    monkeypatch.setattr(bash_tool, "BASH_TIMEOUT_SECONDS", 0.3)
    marker = tmp_path / "survived"

    output, is_error = bash_tool.run_bash(f"(sleep 0.8; touch {marker}) & wait")

    assert "timed out" in output
    assert is_error is True
    time.sleep(1.0)  # past the grandchild's write moment
    assert not marker.exists()


def test_run_bash_timeout_forwards_partial_output(monkeypatch):
    # A command killed at the timeout already produced useful output; the
    # model must see how far it got, not just a bare timeout notice.
    monkeypatch.setattr(bash_tool, "BASH_TIMEOUT_SECONDS", 0.3)

    output, is_error = bash_tool.run_bash("echo progress; echo warn >&2; sleep 5")

    assert "progress" in output
    assert "[stderr]\nwarn" in output
    assert "timed out" in output
    assert is_error is True


def test_run_bash_truncates_long_output(monkeypatch):
    monkeypatch.setattr(bash_tool, "MAX_TOOL_OUTPUT_BYTES", 10)

    output, is_error = bash_tool.run_bash("printf 'a%.0s' {1..100}")

    assert output.startswith("a" * 10)
    assert output.endswith("[... output truncated ...]")
    assert is_error is False


def test_run_bash_with_embedded_nul_returns_error_result():
    # An embedded NUL byte is legal in the tool-call JSON but rejected by the
    # OS; it must come back as an error result, not crash the agent.
    output, is_error = bash_tool.run_bash("echo \x00hi")

    assert output.startswith("Could not run bash:")
    assert is_error is True


def test_run_bash_output_exactly_at_the_limit_is_not_marked_truncated(monkeypatch):
    # Boundary check for the bounded read: only output beyond the cap gets
    # the truncation marker.
    monkeypatch.setattr(bash_tool, "MAX_TOOL_OUTPUT_BYTES", 6)

    output, is_error = bash_tool.run_bash("printf 'abcde\\n'")

    assert output == "abcde"
    assert is_error is False


def test_run_bash_truncation_keeps_stderr_and_exit_code_visible(monkeypatch):
    # A failing command with chatty stdout must not have its diagnosis cut
    # off: each stream is truncated on its own, so the [stderr] section and
    # the exit-code marker survive no matter how much stdout was printed.
    monkeypatch.setattr(bash_tool, "MAX_TOOL_OUTPUT_BYTES", 50)

    output, is_error = bash_tool.run_bash(
        "printf 'a%.0s' {1..500}; echo boom >&2; exit 3"
    )

    assert "[... output truncated ...]" in output
    assert "[stderr]\nboom" in output
    assert output.endswith("[exit code: 3]")
    assert is_error is False  # completed command; the exit code is in the text
