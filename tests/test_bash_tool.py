"""Tests for the ``bash`` tool's execution (``bash_tool.py``).

These run real bash commands; the timeout and output cap are patched down so
every case finishes quickly.
"""

from nanopycodeagent import bash_tool
from nanopycodeagent.deadline import DeadlineExceeded, wall_clock_limit
import pytest
import shlex
import shutil
import sys
import time


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


def test_timeout_kills_children_before_they_can_write(tmp_path):
    target = tmp_path / "must-not-exist"
    output, is_error = bash_tool.run_bash(
        f"(sleep 0.4; touch {shlex.quote(str(target))}) & wait",
        timeout_seconds=0.05,
    )
    assert is_error and "timed out" in output
    time.sleep(0.5)
    assert not target.exists()


def test_normal_exit_preserves_background_service(tmp_path):
    target = tmp_path / "finished"
    output, is_error = bash_tool.run_bash(
        f"(sleep 0.1; touch {shlex.quote(str(target))}) >/dev/null 2>&1 &",
        timeout_seconds=1,
    )
    assert not is_error
    time.sleep(0.3)
    assert target.exists()


@pytest.mark.skipif(sys.platform != "linux" or not shutil.which("timeout"),
                    reason="requires Linux and GNU timeout")
@pytest.mark.parametrize("deadline", [False, True])
def test_timeout_stops_children_in_another_process_group(tmp_path, deadline):
    target = tmp_path / "must-not-exist"
    child = f"sleep 0.8; touch {shlex.quote(str(target))}"
    command = f"timeout 5 bash -c {shlex.quote(child)}; true"
    started = time.monotonic()
    if deadline:
        with pytest.raises(DeadlineExceeded), wall_clock_limit(0.1):
            bash_tool.run_bash(command)
    else:
        output, is_error = bash_tool.run_bash(command, timeout_seconds=0.1)
        assert is_error and "timed out" in output
    assert time.monotonic() - started < 0.6
    time.sleep(0.9)
    assert not target.exists()


@pytest.mark.skipif(sys.platform != "linux" or not shutil.which("setsid"),
                    reason="requires Linux and setsid")
def test_timeout_does_not_drain_pipes_held_by_detached_child():
    started = time.monotonic()
    output, is_error = bash_tool.run_bash(
        "setsid bash -c 'sleep 0.8' & wait", timeout_seconds=0.1,
    )
    assert is_error and "timed out" in output
    assert time.monotonic() - started < 0.6
