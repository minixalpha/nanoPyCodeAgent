"""The ``edit`` tool: its definition and its execution.

Each call replaces one exact stretch of an existing UTF-8 text file, so a
small change costs a small message: the model sends the old text and the
new text instead of regenerating the whole file the way ``write`` needs it
to. The old text doubles as a precondition — it has to be present, and by
default exactly once — so an edit fails loudly when the file has moved on,
where a whole-file overwrite would silently bury the change.

Matching is exact. The only conversions applied to the model's input are
the UTF-8 BOM and, for a CRLF file, a single LF→CRLF retry; both are
forced by what ``read`` shows the model, both are stated in the tool
description, and neither widens the match beyond the literal it was given.
There is no regex, whitespace, indentation or similarity fallback: with no
approval step between the match and the write, a fuzzy hit would let the
tool change more than the model asked for and report success.
"""

import shlex
from pathlib import Path

from anthropic.types import ToolParam

from .read_tool import MAX_READ_BYTES

# The terminal echo folds each side of the edit to this many lines, and any
# one line to this many characters. The full strings are already in the
# model's tool input, so the echo only has to show what is being swapped.
EDIT_PREVIEW_LINES = 6
EDIT_PREVIEW_LINE_CHARS = 200

EDIT_TOOL: ToolParam = {
    "name": "edit",
    "description": (
        "Replace an exact stretch of text in an existing UTF-8 text file. "
        "Prefer this over write for changing part of a file: only the old "
        "and new text travel, and the rest of the file is left untouched. "
        "Use write to create a file or rewrite it whole, and bash to "
        "transform many files at once. The match is literal, not a regex, "
        "and must be unique unless replace_all is set; nothing is trimmed, "
        "re-indented or fuzzily matched, so a call that does not match "
        "fails instead of guessing a place to edit. The two exceptions are "
        "the UTF-8 BOM and line endings: in a CRLF file, a multi-line "
        "old_text written with plain newlines still matches and is written "
        "back with CRLF. On failure, read the file again rather than "
        "resending the same call."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "Path to the file, absolute or relative to the agent's "
                    "working directory. A leading ~ is expanded. The file "
                    "must already exist."
                ),
            },
            "old_text": {
                "type": "string",
                "description": (
                    "The text to replace, copied from the file character "
                    "for character — without read's line-number prefix. Two "
                    "to four lines are usually enough to be unique; add "
                    "surrounding lines when they are not."
                ),
            },
            "new_text": {
                "type": "string",
                "description": (
                    "The replacement text. An empty string deletes old_text "
                    "exactly, taking nothing else with it."
                ),
            },
            "replace_all": {
                "type": "boolean",
                "description": (
                    "Replace every occurrence instead of requiring a unique "
                    "one (default false). Use it only when every identical "
                    "occurrence should change, e.g. renaming a local "
                    "variable."
                ),
            },
        },
        "required": ["path", "old_text", "new_text"],
    },
}


def _to_crlf(text: str) -> str:
    """Return ``text`` with every line ending written as CRLF."""
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


def _fold(text: str, marker: str) -> str:
    """Fold one side of an edit into a few marked, length-capped lines."""
    if not text:
        return ""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()  # the newline ending the last line starts no new one
    shown = [
        line
        if len(line) <= EDIT_PREVIEW_LINE_CHARS
        else line[:EDIT_PREVIEW_LINE_CHARS] + "..."
        for line in lines[:EDIT_PREVIEW_LINES]
    ]
    hidden = len(lines) - len(shown)
    if hidden > 0:
        shown.append(f"... (+{hidden} more lines)")
    return "\n".join(f"{marker} {line}" for line in shown)


def edit_preview(old_text: str, new_text: str) -> str:
    """Fold both sides of an edit into a small ``-``/``+`` diff for the echo.

    A deletion shows only the removed side, so an empty ``new_text`` reads
    as a removal rather than as a swap for nothing.
    """
    sides = (_fold(old_text, "-"), _fold(new_text, "+"))
    return "\n".join(side for side in sides if side)


def _match(text: str, old_text: str, new_text: str) -> tuple[str, str, int, bool]:
    """Locate ``old_text`` in ``text``; return what to use and how often.

    The first pass is a raw exact search. Only when it finds nothing does a
    single CRLF pass follow, and only for the case that makes it necessary:
    ``read`` drops the ``\\r`` of a CRLF file when it shows it, so a
    multi-line ``old_text`` copied out of that view can hold LF alone —
    the model cannot produce the file's real bytes. An ``old_text`` that
    does carry ``\\r`` is taken at its word and gets the raw pass only.

    The two passes are never merged: whichever one matches decides both
    uniqueness and the replacement count, so there is no way for hits in
    different encodings to overlap or to be counted twice. In a file with
    mixed line endings that means one call reaches one style and the other
    fails closed, which the caller's error message says out loud.

    Returns ``(old, new, count, crlf_pass_ran)``.
    """
    count = text.count(old_text)
    if count:
        return old_text, new_text, count, False
    if "\r\n" in text and "\n" in old_text and "\r" not in old_text:
        old_crlf = _to_crlf(old_text)
        return old_crlf, _to_crlf(new_text), text.count(old_crlf), True
    return old_text, new_text, 0, False


def run_edit(
    path_str: str, old_text: str, new_text: str, replace_all: bool = False
) -> tuple[str, bool]:
    """Replace ``old_text`` with ``new_text`` and return ``(output, is_error)``.

    The file has to exist and be a regular UTF-8 text file: creating one and
    rewriting one whole are ``write``'s job, and an empty ``old_text`` is
    refused rather than quietly becoming either. ``is_error`` is true for a
    bad argument, a missing or unreadable target, a file this tool cannot
    round-trip byte for byte, no match, or an ambiguous match. Every error
    says what to do next — read again, add context, set ``replace_all``,
    fall back to bash — instead of only what failed.

    Invalid UTF-8 and NUL bytes are refused: ``read`` shows those files with
    replacement characters so they can be inspected, and writing that view
    back would corrupt the original bytes for good. A UTF-8 BOM is stripped
    before matching and restored on write, since ``read`` leaves it in place
    and an invisible character would otherwise break every ``old_text``
    aimed at the first line.

    The write is a plain read-compute-write, like ``write``'s: no mtime
    check, no compare-and-swap, no atomic replace. The unique ``old_text``
    is the precondition; in this agent's single-threaded loop the rest
    would be pretend safety.
    """
    if not old_text:
        return (
            "[old_text is empty; use write to create a file or replace it whole]",
            True,
        )
    if old_text == new_text:
        return "[old_text and new_text are identical: nothing to change]", True

    path = Path(path_str).expanduser()
    if not path.exists():
        return f"[file not found: {path_str}; use write to create it]", True
    if path.is_dir():
        return f"[{path_str} is a directory, not a file]", True
    if not path.is_file():
        # Same reasoning as read's and write's: a FIFO blocks until the other
        # end shows up, and a device file is not workspace text.
        return f"[{path_str} is not a regular file; edit is text-only]", True
    try:
        size = path.stat().st_size
        if size > MAX_READ_BYTES:
            return (
                f"[{path_str} is {size} bytes, over the {MAX_READ_BYTES}-byte "
                f"cap; edit rewrites the whole file in memory, so change it "
                f"with bash instead, e.g. with sed -i]",
                True,
            )
        data = path.read_bytes()
    except FileNotFoundError:  # the file went away after the check above
        return f"[file not found: {path_str}]", True
    except OSError as exc:
        return f"[cannot read {path_str}: {exc}]", True

    # Unlike read, which samples the head to spot a binary file, edit has to
    # scan all of it: a NUL anywhere would come back through the round-trip.
    if b"\x00" in data:
        return f"[{path_str} contains NUL bytes; edit is text-only]", True
    try:
        text = data.decode("utf-8")  # strict: no replacement characters
    except UnicodeDecodeError as exc:
        return (
            f"[{path_str} is not valid UTF-8: {exc}; edit only changes text "
            f"it can write back byte for byte — use bash instead]",
            True,
        )

    bom = text.startswith("\ufeff")
    if bom:
        text = text[1:]

    old, new, count, crlf_pass_ran = _match(text, old_text, new_text)
    if count == 0:
        retried = " — the CRLF form was already tried" if crlf_pass_ran else ""
        return (
            f"[no match for old_text in {path_str}; read the file again and "
            f"copy the text exactly{retried}]",
            True,
        )
    if count > 1 and not replace_all:
        return (
            f"[old_text matches {count} times in {path_str}; add surrounding "
            f"context to make it unique, or set replace_all=true]",
            True,
        )

    # str.replace walks left to right over non-overlapping matches, the same
    # ones str.count reported, so the count above is what actually changes.
    line = text.count("\n", 0, text.index(old)) + 1
    edited = text.replace(old, new) if replace_all else text.replace(old, new, 1)
    try:
        path.write_bytes(("\ufeff" + edited if bom else edited).encode("utf-8"))
    except OSError as exc:
        return (
            f"[cannot write {path_str}: {exc}; inspect it with bash, e.g. "
            f"ls -l -- {shlex.quote(str(path))}]",
            True,
        )

    replaced = count if replace_all else 1
    if replaced == 1:
        return f"[edited {path_str}: replaced 1 occurrence at line {line}]", False
    return (
        f"[edited {path_str}: replaced {replaced} occurrences, "
        f"first at line {line}]",
        False,
    )
