"""Tests for the ``edit`` tool's execution (``edit_tool.py``).

These edit real files under pytest's ``tmp_path`` and assert on bytes
wherever line endings, a BOM or trailing whitespace are at stake: the whole
point of the tool is that everything outside the matched span comes back
unchanged. The preview caps are patched down so the folding cases stay
small.
"""

import os

import pytest

from nanopycodeagent import edit_tool


def test_unique_match_is_replaced(tmp_path):
    path = tmp_path / "app.py"
    path.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    output, is_error = edit_tool.run_edit(str(path), "beta", "BETA")

    assert path.read_text(encoding="utf-8") == "alpha\nBETA\ngamma\n"
    assert output == f"[edited {path}: replaced 1 occurrence at line 2]"
    assert is_error is False


def test_multi_line_replacement_reports_the_first_changed_line(tmp_path):
    path = tmp_path / "app.py"
    path.write_text("a\nb\nc\nd\ne\n", encoding="utf-8")

    output, _ = edit_tool.run_edit(str(path), "c\nd", "C\nD")

    assert path.read_text(encoding="utf-8") == "a\nb\nC\nD\ne\n"
    assert "at line 3" in output


def test_empty_new_text_deletes_exactly_and_nothing_more(tmp_path):
    path = tmp_path / "app.py"
    path.write_text("keep\ndrop\nkeep\n", encoding="utf-8")

    # The newline after the match is not swept along with it: deleting
    # "drop" leaves the blank line its own newline made.
    output, is_error = edit_tool.run_edit(str(path), "drop", "")

    assert path.read_text(encoding="utf-8") == "keep\n\nkeep\n"
    assert is_error is False
    assert output.startswith(f"[edited {path}:")


def test_unicode_text_is_replaced_as_utf8(tmp_path):
    path = tmp_path / "cn.txt"
    path.write_text("你好\n世界\n", encoding="utf-8")

    output, is_error = edit_tool.run_edit(str(path), "世界", "地球")

    assert path.read_bytes() == "你好\n地球\n".encode("utf-8")
    assert is_error is False


def test_identical_old_and_new_text_is_an_error(tmp_path):
    path = tmp_path / "app.py"
    path.write_text("same\n", encoding="utf-8")

    output, is_error = edit_tool.run_edit(str(path), "same", "same")

    assert path.read_text(encoding="utf-8") == "same\n"  # untouched
    assert "identical" in output
    assert is_error is True


def test_empty_old_text_points_at_write(tmp_path):
    path = tmp_path / "app.py"
    path.write_text("content\n", encoding="utf-8")

    output, is_error = edit_tool.run_edit(str(path), "", "new")

    assert path.read_text(encoding="utf-8") == "content\n"
    assert "write" in output  # creation and whole-file rewrites stay there
    assert is_error is True


def test_no_match_fails_and_leaves_the_file_alone(tmp_path):
    path = tmp_path / "app.py"
    path.write_text("alpha\nbeta\n", encoding="utf-8")

    output, is_error = edit_tool.run_edit(str(path), "missing", "x")

    assert path.read_text(encoding="utf-8") == "alpha\nbeta\n"
    assert "no match for old_text" in output
    assert "read the file again" in output  # the error says how to recover
    assert is_error is True


def test_repeated_match_reports_the_count_instead_of_guessing(tmp_path):
    path = tmp_path / "app.py"
    path.write_text("x = 1\ny = 1\nz = 1\n", encoding="utf-8")

    output, is_error = edit_tool.run_edit(str(path), "1", "2")

    assert path.read_text(encoding="utf-8") == "x = 1\ny = 1\nz = 1\n"
    assert "matches 3 times" in output
    assert "replace_all=true" in output
    assert is_error is True


def test_replace_all_changes_every_occurrence_and_counts_them(tmp_path):
    path = tmp_path / "app.py"
    path.write_text("x = 1\ny = 1\nz = 1\n", encoding="utf-8")

    output, is_error = edit_tool.run_edit(str(path), "= 1", "= 2", replace_all=True)

    assert path.read_text(encoding="utf-8") == "x = 2\ny = 2\nz = 2\n"
    assert output == f"[edited {path}: replaced 3 occurrences, first at line 1]"
    assert is_error is False


def test_old_text_is_a_literal_not_a_regex(tmp_path):
    path = tmp_path / "app.py"
    path.write_text("a.b\naxb\n", encoding="utf-8")

    # As a regex, "a.b" would match both lines and the first hit would be
    # ambiguous; as a literal it matches exactly one.
    output, is_error = edit_tool.run_edit(str(path), "a.b", "OK")

    assert path.read_text(encoding="utf-8") == "OK\naxb\n"
    assert is_error is False


def test_dedented_old_text_does_not_match(tmp_path):
    path = tmp_path / "app.py"
    path.write_text("def f(x):\n    if x:\n        return 1\n", encoding="utf-8")

    # No indentation flexibility: the model has to send what is in the file.
    output, is_error = edit_tool.run_edit(
        str(path), "if x:\n    return 1", "if x:\n    return 2"
    )

    assert "no match for old_text" in output
    assert is_error is True


def test_trailing_whitespace_difference_does_not_match(tmp_path):
    path = tmp_path / "app.py"
    path.write_text("value  =  1\n", encoding="utf-8")

    # No whitespace normalization either: "value = 1" is simply not there.
    output, is_error = edit_tool.run_edit(str(path), "value = 1", "value = 2")

    assert "no match for old_text" in output
    assert is_error is True


def test_untouched_bytes_survive_an_edit(tmp_path):
    path = tmp_path / "raw.txt"
    # Trailing spaces, a CRLF line, and no final newline: all of it has to
    # come back byte for byte outside the matched span.
    path.write_bytes(b"one  \r\ntwo\nthree")

    output, is_error = edit_tool.run_edit(str(path), "three", "3")

    assert path.read_bytes() == b"one  \r\ntwo\n3"
    assert is_error is False


def test_lf_old_text_matches_a_crlf_file_and_is_written_back_as_crlf(tmp_path):
    path = tmp_path / "crlf.txt"
    path.write_bytes(b"one\r\ntwo\r\nthree\r\n")

    # read shows CRLF files without the \r, so a multi-line old_text copied
    # out of that view can only hold LF; the retry is what makes it land.
    output, is_error = edit_tool.run_edit(str(path), "one\ntwo", "1\n2")

    assert path.read_bytes() == b"1\r\n2\r\nthree\r\n"
    assert is_error is False


def test_the_crlf_pass_counts_its_own_occurrences(tmp_path):
    path = tmp_path / "crlf.txt"
    path.write_bytes(b"a\r\nb\r\na\r\nb\r\n")

    output, is_error = edit_tool.run_edit(
        str(path), "a\nb", "X\nY", replace_all=True
    )

    assert path.read_bytes() == b"X\r\nY\r\nX\r\nY\r\n"
    assert "replaced 2 occurrences" in output
    assert is_error is False


def test_mixed_endings_reach_one_style_per_call(tmp_path):
    path = tmp_path / "mixed.txt"
    path.write_bytes(b"a\r\nb\r\na\nb\n")

    # The raw pass finds the LF pair, so the CRLF pass never runs and the
    # CRLF pair is left alone — one call, one line-ending style.
    output, is_error = edit_tool.run_edit(str(path), "a\nb", "X\nY")

    assert path.read_bytes() == b"a\r\nb\r\nX\nY\n"
    assert "replaced 1 occurrence" in output
    assert is_error is False


def test_single_line_old_text_spans_both_ending_styles(tmp_path):
    path = tmp_path / "mixed.txt"
    path.write_bytes(b"x\r\nx\n")

    # An old_text without a newline is line-ending agnostic: the raw pass
    # finds every occurrence and no retry is needed.
    output, is_error = edit_tool.run_edit(str(path), "x", "y", replace_all=True)

    assert path.read_bytes() == b"y\r\ny\n"
    assert "replaced 2 occurrences" in output
    assert is_error is False


def test_old_text_carrying_cr_gets_the_raw_pass_only(tmp_path):
    path = tmp_path / "crlf.txt"
    path.write_bytes(b"one\r\ntwo\r\n")

    # An explicit \r is taken at face value: it either matches the real
    # bytes or it fails, with no second guess.
    output, is_error = edit_tool.run_edit(str(path), "one\r\ntwo", "1\r\n2")
    assert path.read_bytes() == b"1\r\n2\r\n"
    assert is_error is False

    output, is_error = edit_tool.run_edit(str(path), "nope\r\nhere", "x")
    assert "no match for old_text" in output
    assert "CRLF" not in output  # no retry ran, so none is claimed
    assert is_error is True


def test_a_failed_crlf_retry_says_it_was_tried(tmp_path):
    path = tmp_path / "crlf.txt"
    path.write_bytes(b"one\r\ntwo\r\n")

    output, is_error = edit_tool.run_edit(str(path), "nope\nhere", "x")

    assert "CRLF form was already tried" in output
    assert is_error is True


def test_bom_is_stripped_for_matching_and_restored_on_write(tmp_path):
    path = tmp_path / "bom.py"
    path.write_bytes("\ufeffimport os\nimport sys\n".encode("utf-8"))

    # read leaves the BOM in place, so an old_text aimed at the first line
    # would never match unless the tool takes it off first.
    output, is_error = edit_tool.run_edit(str(path), "import os", "import io")

    assert path.read_bytes() == "\ufeffimport io\nimport sys\n".encode("utf-8")
    assert is_error is False


def test_invalid_utf8_is_refused_instead_of_round_tripped(tmp_path):
    path = tmp_path / "broken.txt"
    path.write_bytes(b"ok \xff\xfe still here\n")

    output, is_error = edit_tool.run_edit(str(path), "ok", "fine")

    assert path.read_bytes() == b"ok \xff\xfe still here\n"  # bytes preserved
    assert "not valid UTF-8" in output
    assert is_error is True


def test_nul_bytes_are_refused(tmp_path):
    path = tmp_path / "binary.bin"
    path.write_bytes(b"text\x00more text\n")

    output, is_error = edit_tool.run_edit(str(path), "text", "TEXT")

    assert path.read_bytes() == b"text\x00more text\n"
    assert "NUL" in output
    assert is_error is True


def test_missing_file_points_at_write(tmp_path):
    output, is_error = edit_tool.run_edit(str(tmp_path / "gone.py"), "a", "b")

    assert "file not found" in output
    assert "write" in output  # edit never creates
    assert is_error is True


def test_directory_target_is_an_error(tmp_path):
    output, is_error = edit_tool.run_edit(str(tmp_path), "a", "b")

    assert "is a directory" in output
    assert is_error is True


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX-only file type")
def test_fifo_is_rejected_instead_of_blocking(tmp_path):
    path = tmp_path / "pipe"
    os.mkfifo(path)

    output, is_error = edit_tool.run_edit(str(path), "a", "b")

    assert "not a regular file" in output
    assert is_error is True


def test_file_over_the_byte_cap_is_turned_away(tmp_path, monkeypatch):
    path = tmp_path / "big.txt"
    path.write_text("alpha\nbeta\n", encoding="utf-8")
    monkeypatch.setattr(edit_tool, "MAX_READ_BYTES", 4)

    output, is_error = edit_tool.run_edit(str(path), "alpha", "ALPHA")

    assert path.read_text(encoding="utf-8") == "alpha\nbeta\n"
    assert "over the 4-byte cap" in output
    assert "bash" in output  # the error names the way to edit it anyway
    assert is_error is True


def test_tilde_is_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "home.txt").write_text("hello\n", encoding="utf-8")

    output, is_error = edit_tool.run_edit("~/home.txt", "hello", "hi")

    assert (tmp_path / "home.txt").read_text(encoding="utf-8") == "hi\n"
    assert is_error is False


def test_relative_path_resolves_against_the_working_directory(tmp_path, monkeypatch):
    (tmp_path / "notes.txt").write_text("old\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    output, is_error = edit_tool.run_edit("notes.txt", "old", "new")

    assert (tmp_path / "notes.txt").read_text(encoding="utf-8") == "new\n"
    assert is_error is False


def test_symlink_to_a_regular_file_edits_its_target(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("old\n", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(target)

    output, is_error = edit_tool.run_edit(str(link), "old", "new")

    assert target.read_text(encoding="utf-8") == "new\n"
    assert link.is_symlink()  # the link itself was not replaced
    assert is_error is False


def test_edits_apply_one_after_another(tmp_path):
    path = tmp_path / "app.py"
    path.write_text("one\ntwo\n", encoding="utf-8")

    edit_tool.run_edit(str(path), "one", "1")
    # The second call reads what the first one wrote, so the model can chain
    # edits within a single reply.
    output, is_error = edit_tool.run_edit(str(path), "two", "2")

    assert path.read_text(encoding="utf-8") == "1\n2\n"
    assert is_error is False


def test_preview_shows_both_sides_of_a_short_edit():
    assert edit_tool.edit_preview("old\n", "new\n") == "- old\n+ new"


def test_preview_of_a_deletion_shows_only_the_removed_side():
    assert edit_tool.edit_preview("gone\n", "") == "- gone"


def test_preview_folds_long_sides(monkeypatch):
    monkeypatch.setattr(edit_tool, "EDIT_PREVIEW_LINES", 2)
    old = "".join(f"l{n}\n" for n in range(1, 6))

    assert edit_tool.edit_preview(old, "x\n") == (
        "- l1\n- l2\n- ... (+3 more lines)\n+ x"
    )


def test_preview_cuts_an_over_long_line(monkeypatch):
    monkeypatch.setattr(edit_tool, "EDIT_PREVIEW_LINE_CHARS", 5)

    assert edit_tool.edit_preview("abcdefgh\n", "z\n") == "- abcde...\n+ z"
