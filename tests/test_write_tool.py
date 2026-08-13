"""Tests for the ``write`` tool's execution (``write_tool.py``).

These write real files under pytest's ``tmp_path``; the preview caps are
patched down so the folding cases stay small.
"""

import os

import pytest

from nanopycodeagent import write_tool


def test_creating_a_new_file_writes_the_content_exactly(tmp_path):
    path = tmp_path / "hello.py"

    output, is_error = write_tool.run_write(str(path), 'print("hi")\n')

    assert path.read_text(encoding="utf-8") == 'print("hi")\n'
    assert output == f"[created {path}: 12 bytes, 1 lines]"
    assert is_error is False


def test_overwriting_replaces_the_whole_file(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("old content, longer than the new\n", encoding="utf-8")

    output, is_error = write_tool.run_write(str(path), "new\n")

    assert path.read_text(encoding="utf-8") == "new\n"
    assert output.startswith(f"[overwrote {path}:")
    assert is_error is False


def test_missing_parent_directories_are_created(tmp_path):
    path = tmp_path / "a" / "b" / "deep.txt"

    output, is_error = write_tool.run_write(str(path), "x\n")

    assert path.read_text(encoding="utf-8") == "x\n"
    assert is_error is False


def test_content_is_written_as_given_without_normalization(tmp_path):
    path = tmp_path / "raw.txt"
    # CRLF endings, trailing spaces and a missing final newline all survive.
    content = "one \r\ntwo"

    write_tool.run_write(str(path), content)

    assert path.read_bytes() == b"one \r\ntwo"


def test_unicode_content_lands_as_utf8(tmp_path):
    path = tmp_path / "cn.txt"

    output, is_error = write_tool.run_write(str(path), "你好\n")

    assert path.read_bytes() == "你好\n".encode("utf-8")
    assert "7 bytes, 1 lines" in output  # bytes, not characters
    assert is_error is False


def test_empty_content_creates_an_empty_file(tmp_path):
    path = tmp_path / "empty.txt"

    output, is_error = write_tool.run_write(str(path), "")

    assert path.read_bytes() == b""
    assert output == f"[created {path}: 0 bytes, 0 lines]"
    assert is_error is False


def test_tilde_is_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    output, is_error = write_tool.run_write("~/home.txt", "hello\n")

    assert (tmp_path / "home.txt").read_text(encoding="utf-8") == "hello\n"
    assert is_error is False


def test_directory_target_is_an_error(tmp_path):
    output, is_error = write_tool.run_write(str(tmp_path), "content\n")

    assert "is a directory" in output
    assert is_error is True


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX-only file type")
def test_fifo_is_rejected_instead_of_blocking(tmp_path):
    path = tmp_path / "pipe"
    os.mkfifo(path)

    # Opening it for writing would block until a reader shows up, with no
    # timeout to escape; the type check has to come before the open.
    output, is_error = write_tool.run_write(str(path), "content\n")

    assert "not a regular file" in output
    assert is_error is True


def test_parent_path_through_a_file_is_an_error(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a directory\n", encoding="utf-8")

    output, is_error = write_tool.run_write(str(blocker / "child.txt"), "x\n")

    assert output.startswith("[cannot write")
    assert is_error is True


def test_symlink_to_a_regular_file_writes_its_target(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("old\n", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(target)

    output, is_error = write_tool.run_write(str(link), "new\n")

    assert target.read_text(encoding="utf-8") == "new\n"
    assert link.is_symlink()  # the link itself was not replaced
    assert output.startswith(f"[overwrote {link}:")
    assert is_error is False


def test_lone_surrogate_content_is_an_error_not_a_corrupt_file(tmp_path):
    path = tmp_path / "bad.txt"

    output, is_error = write_tool.run_write(str(path), "ok \ud800 broken")

    assert not path.exists()  # nothing was written
    assert "not encodable as UTF-8" in output
    assert is_error is True


def test_line_count_matches_how_read_numbers_lines(tmp_path):
    path = tmp_path / "notes.txt"

    # The newline ending the last line starts no new one, and a file without
    # a final newline still counts its last line.
    output, _ = write_tool.run_write(str(path), "one\ntwo\n")
    assert "2 lines" in output
    output, _ = write_tool.run_write(str(path), "one\ntwo")
    assert "2 lines" in output


def test_preview_shows_short_content_whole():
    assert write_tool.content_preview("one\ntwo\n") == "one\ntwo"


def test_preview_folds_long_content(monkeypatch):
    monkeypatch.setattr(write_tool, "WRITE_PREVIEW_LINES", 2)
    content = "".join(f"l{n}\n" for n in range(1, 6))

    assert write_tool.content_preview(content) == "l1\nl2\n... (+3 more lines)"


def test_preview_cuts_an_over_long_line(monkeypatch):
    monkeypatch.setattr(write_tool, "WRITE_PREVIEW_LINE_CHARS", 5)

    assert write_tool.content_preview("abcdefgh\n") == "abcde..."


def test_preview_of_empty_content():
    assert write_tool.content_preview("") == "(empty)"
