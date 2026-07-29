"""Tests for the ``read`` tool's execution (``read_tool.py``).

These read real files under pytest's ``tmp_path``; the line and character
caps are patched down so every case stays small.
"""

import os
import shlex

import pytest

from nanopycodeagent import read_tool


def _write(tmp_path, name, content):
    path = tmp_path / name
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def test_run_read_numbers_lines(tmp_path):
    path = _write(tmp_path, "notes.txt", "alpha\nbeta\n")

    output, is_error = read_tool.run_read(str(path))

    assert output == "     1\talpha\n     2\tbeta"
    assert is_error is False


def test_offset_and_limit_select_a_window(tmp_path):
    path = _write(tmp_path, "notes.txt", "one\ntwo\nthree\nfour\nfive\n")

    output, is_error = read_tool.run_read(str(path), offset=2, limit=2)

    # The window carries its real line numbers, and the note names the
    # range, the total, and the offset to continue from.
    assert output == (
        "     2\ttwo\n     3\tthree\n"
        "[showing lines 2-3 of 5; continue with offset=4]"
    )
    assert is_error is False


def test_reading_to_the_end_has_no_truncation_note(tmp_path):
    path = _write(tmp_path, "notes.txt", "one\ntwo\n")

    output, is_error = read_tool.run_read(str(path), offset=2)

    assert output == "     2\ttwo"
    assert is_error is False


def test_line_cap_truncates_with_continuation(tmp_path, monkeypatch):
    monkeypatch.setattr(read_tool, "MAX_READ_LINES", 3)
    path = _write(tmp_path, "notes.txt", "".join(f"l{n}\n" for n in range(1, 11)))

    output, is_error = read_tool.run_read(str(path))

    assert output.endswith("[showing lines 1-3 of 10; continue with offset=4]")
    assert output.count("\t") == 3  # only three numbered lines made it out
    assert is_error is False


def test_char_cap_truncates_at_a_line_boundary(tmp_path, monkeypatch):
    monkeypatch.setattr(read_tool, "MAX_READ_CHARS", 30)
    # Each rendered line is 6 (number) + 1 (tab) + 5 (text) = 12 chars, so
    # only two fit under a 30-char cap (12 + 1 + 12 = 25; a third needs 38).
    path = _write(tmp_path, "notes.txt", "aaaaa\nbbbbb\nccccc\nddddd\n")

    output, is_error = read_tool.run_read(str(path))

    assert output == (
        "     1\taaaaa\n     2\tbbbbb\n"
        "[showing lines 1-2 of 4; continue with offset=3]"
    )
    assert is_error is False


def test_explicit_limit_still_notes_the_remainder(tmp_path):
    path = _write(tmp_path, "notes.txt", "one\ntwo\nthree\n")

    output, is_error = read_tool.run_read(str(path), limit=1)

    assert output.endswith("[showing lines 1-1 of 3; continue with offset=2]")
    assert is_error is False


def test_single_line_over_the_char_cap_suggests_bash(tmp_path, monkeypatch):
    monkeypatch.setattr(read_tool, "MAX_READ_CHARS", 20)
    path = _write(tmp_path, "big.json", "x" * 100 + "\n")

    output, is_error = read_tool.run_read(str(path))

    # The line is not silently truncated; the error hands the model a bash
    # command that can slice it.
    assert "line 1 is 100 characters long" in output
    assert "sed -n '1p'" in output
    assert is_error is True


def test_the_bash_hint_survives_a_hostile_filename(tmp_path, monkeypatch):
    monkeypatch.setattr(read_tool, "MAX_READ_CHARS", 20)
    path = _write(tmp_path, "-a $(echo pwned).json", "x" * 100 + "\n")

    output, is_error = read_tool.run_read(str(path))

    # The hint is a command the model may run, so parse it back the way the
    # shell would: the path has to arrive as one argument, unexpanded, and
    # its leading dash must not read as an option.
    hint = output.split("e.g. ")[1].rstrip("]").split(" | ")[0]
    assert shlex.split(hint) == ["sed", "-n", "1p", "--", str(path)]
    assert is_error is True


def test_the_bash_hint_carries_the_expanded_path(tmp_path, monkeypatch):
    monkeypatch.setattr(read_tool, "MAX_READ_CHARS", 20)
    monkeypatch.setenv("HOME", str(tmp_path))
    _write(tmp_path, "big.json", "x" * 100 + "\n")

    output, is_error = read_tool.run_read("~/big.json")

    # Quoting the path stops the shell from expanding ~ itself, so the hint
    # has to hand over the path already expanded.
    assert f"-- {tmp_path}/big.json" in output
    assert is_error is True


def test_empty_file_is_not_an_error(tmp_path):
    path = _write(tmp_path, "empty.txt", "")

    output, is_error = read_tool.run_read(str(path))

    assert output == "(empty file)"
    assert is_error is False


def test_missing_file_is_an_error(tmp_path):
    output, is_error = read_tool.run_read(str(tmp_path / "nope.txt"))

    assert "file not found" in output
    assert is_error is True


def test_directory_is_an_error(tmp_path):
    output, is_error = read_tool.run_read(str(tmp_path))

    assert "is a directory" in output
    assert is_error is True


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX-only file type")
def test_fifo_is_rejected_instead_of_blocking(tmp_path):
    path = tmp_path / "pipe"
    os.mkfifo(path)

    # Opening it would block until a writer shows up, with no timeout to
    # escape; the type check has to come before the read.
    output, is_error = read_tool.run_read(str(path))

    assert "not a regular file" in output
    assert is_error is True


def test_file_over_the_byte_cap_is_turned_away_before_reading(tmp_path, monkeypatch):
    monkeypatch.setattr(read_tool, "MAX_READ_BYTES", 10)
    path = _write(tmp_path, "big.log", "x" * 100 + "\n")
    # Never loading the file is the whole point of the cap, so fail loudly
    # if the read happens anyway.
    monkeypatch.setattr(
        read_tool.Path, "read_bytes", lambda self: pytest.fail("the file was read")
    )

    output, is_error = read_tool.run_read(str(path))

    assert "101 bytes, over the 10-byte cap" in output
    assert "sed" in output  # and bash is named as the way to read it anyway
    assert is_error is True


def test_offset_past_the_end_reports_total_lines(tmp_path):
    path = _write(tmp_path, "notes.txt", "one\ntwo\n")

    output, is_error = read_tool.run_read(str(path), offset=5)

    assert "past the end" in output
    assert "(2 lines)" in output
    assert is_error is True


def test_non_positive_offset_and_limit_are_errors(tmp_path):
    path = _write(tmp_path, "notes.txt", "one\n")

    assert read_tool.run_read(str(path), offset=0)[1] is True
    assert read_tool.run_read(str(path), limit=0)[1] is True


def test_binary_file_is_rejected(tmp_path):
    path = _write(tmp_path, "blob.bin", b"\x00\x01\x02data")

    output, is_error = read_tool.run_read(str(path))

    assert "binary" in output
    assert is_error is True


def test_invalid_utf8_bytes_are_replaced(tmp_path):
    path = _write(tmp_path, "latin1.txt", b"caf\xe9\n")

    output, is_error = read_tool.run_read(str(path))

    assert output == "     1\tcaf�"
    assert is_error is False


def test_only_newlines_break_lines(tmp_path):
    # A form feed is an ordinary character inside a line for sed, grep -n and
    # editors; splitlines() would break on it and shift every number after it.
    path = _write(tmp_path, "page.txt", b"one\ntwo\x0cthree\nfour\n")

    output, is_error = read_tool.run_read(str(path))

    assert output == "     1\tone\n     2\ttwo\x0cthree\n     3\tfour"
    assert is_error is False


def test_crlf_line_endings_read_like_lf(tmp_path):
    path = _write(tmp_path, "dos.txt", b"one\r\n\r\ntwo\r\n")

    output, is_error = read_tool.run_read(str(path))

    assert output == "     1\tone\n     2\t\n     3\ttwo"
    assert is_error is False


def test_last_line_without_a_trailing_newline_is_kept(tmp_path):
    path = _write(tmp_path, "notes.txt", "one\ntwo")

    output, is_error = read_tool.run_read(str(path))

    assert output == "     1\tone\n     2\ttwo"
    assert is_error is False


def test_tilde_is_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _write(tmp_path, "home.txt", "hello\n")

    output, is_error = read_tool.run_read("~/home.txt")

    assert output == "     1\thello"
    assert is_error is False
