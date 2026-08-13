"""The ``write`` tool: its definition and its execution.

Each call writes a whole UTF-8 text file from a structured
``{path, content}`` input: the content lands on disk as data, never
passing through shell expansion, heredoc delimiters or quoting, which is
what makes a heredoc silently corrupt a file while exiting 0.
"""

import shlex
from pathlib import Path

from anthropic.types import ToolParam

# The terminal echo folds the content to this many lines, and any one line
# to this many characters, so a large write does not flood the terminal the
# way the heredoc it replaces would. The full content reaches the file (and
# the model already holds it); only the echo is folded.
WRITE_PREVIEW_LINES = 10
WRITE_PREVIEW_LINE_CHARS = 200

WRITE_TOOL: ToolParam = {
    "name": "write",
    "description": (
        "Write a UTF-8 text file: create it if missing (parent directories "
        "included), or replace its entire content if it exists. The result "
        "says which of the two happened. Use this for new files and "
        "whole-file rewrites instead of shell redirection or heredocs; use "
        "bash to append or to transform many files at once. The write is a "
        "plain overwrite — last writer wins, with no check that the file "
        "was read first or is unchanged since."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "Path to the file, absolute or relative to the agent's "
                    "working directory. A leading ~ is expanded."
                ),
            },
            "content": {
                "type": "string",
                "description": (
                    "The complete file content, written exactly as given — "
                    "no newline or whitespace normalization."
                ),
            },
        },
        "required": ["path", "content"],
    },
}


def _logical_lines(content: str) -> list[str]:
    """Split ``content`` into the lines read would number.

    The split is on ``\\n`` alone, and the newline ending the last line
    starts no new one — so ``"a\\nb\\n"`` is two lines, not three.
    """
    lines = content.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def content_preview(content: str) -> str:
    """Fold ``content`` for the terminal echo of a write call.

    The first few lines are shown, over-long lines are cut short, and a
    closing note counts the hidden lines, so the echo reads as "where the
    write goes and how it starts" rather than the whole file.
    """
    lines = _logical_lines(content)
    if not lines:
        return "(empty)"
    shown = [
        line
        if len(line) <= WRITE_PREVIEW_LINE_CHARS
        else line[:WRITE_PREVIEW_LINE_CHARS] + "..."
        for line in lines[:WRITE_PREVIEW_LINES]
    ]
    hidden = len(lines) - len(shown)
    if hidden > 0:
        shown.append(f"... (+{hidden} more lines)")
    return "\n".join(shown)


def run_write(path_str: str, content: str) -> tuple[str, bool]:
    """Write ``content`` to the file whole and return ``(output, is_error)``.

    The file is created when missing — parent directories included — and
    replaced entirely when it exists; the result names which of the two
    happened, plus the byte and line counts the model can check its intent
    against. ``is_error`` is true when the target is a directory or any
    other non-regular file, or when the write itself fails. A FIFO is
    refused because opening one for writing blocks until a reader appears,
    with no timeout here to escape that; a device file is refused because
    writing to one changes the machine, not the workspace. A symlink to a
    regular file is followed: the write lands in its target.

    Content is encoded as UTF-8 and written as given — no newline or
    whitespace normalization, no trailing-newline fix-up. The write is a
    plain overwrite: nothing checks that the file was read first or is
    unchanged since, and there is no atomic-replace step. In this agent's
    single-threaded loop those guards would only be pretend safety, so the
    semantics are stated plainly instead: last writer wins.
    """
    path = Path(path_str).expanduser()
    if path.is_dir():
        return (
            f"[{path_str} is a directory, not a file; give a path to a file "
            f"inside it]",
            True,
        )
    existed = path.exists()
    if existed and not path.is_file():
        # Opening a FIFO for writing blocks until a reader shows up, and a
        # device file must not be overwritten as if it were text. Same
        # check as read's, from the writing side.
        return (
            f"[{path_str} is not a regular file; write refuses FIFOs and "
            f"device files — if it really is the target, write it with "
            f"bash, whose timeout escapes a blocked open]",
            True,
        )
    try:
        data = content.encode("utf-8")
    except UnicodeEncodeError as exc:
        # A lone surrogate cannot reach disk as UTF-8; writing a replacement
        # instead would corrupt the file silently — the heredoc failure mode
        # this tool exists to remove.
        return f"[content is not encodable as UTF-8: {exc}; resend it]", True
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    except OSError as exc:
        # ``exc`` names the OS reason — permission denied, a file sitting
        # in the parent path, a full disk. The hint points at the usual
        # first suspect, following read's bash-hint conventions: expanded
        # path, quoted, behind -- so it cannot read as an option.
        return (
            f"[cannot write {path_str}: {exc}; inspect the parent with "
            f"bash, e.g. ls -ld -- {shlex.quote(str(path.parent))}]",
            True,
        )

    verb = "overwrote" if existed else "created"
    return (
        f"[{verb} {path_str}: {len(data)} bytes, "
        f"{len(_logical_lines(content))} lines]",
        False,
    )
