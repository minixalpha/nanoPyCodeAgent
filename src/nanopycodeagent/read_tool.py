"""The ``read`` tool: its definition and its execution.

Each call reads a window of a UTF-8 text file and returns it with 1-based
line numbers, ``cat -n`` style, plus a continuation hint whenever the
window stops short of the end of the file.
"""

from pathlib import Path

from anthropic.types import ToolParam

# Guardrails for the read tool: one call returns at most this many lines and
# this many characters, whichever is hit first, so a single file cannot flood
# the context. Truncation happens at line boundaries, never mid-line.
MAX_READ_LINES = 2_000
MAX_READ_CHARS = 50_000

# The output caps above only bound what reaches the context; the file itself
# is read whole, so a byte cap is what bounds memory. It is generous next to
# the output caps because a small window may sit deep inside a large source
# file — it only has to keep a multi-gigabyte log from being loaded at all.
MAX_READ_BYTES = 10_000_000

READ_TOOL: ToolParam = {
    "name": "read",
    "description": (
        "Read a UTF-8 text file and return its content with 1-based line "
        "numbers, `cat -n` style. Use `offset` (first line to read) and "
        "`limit` (number of lines) to read a window of a large file. Output "
        "is capped by line count and character count; a truncated result "
        "names the range returned, the file's total line count, and the "
        "offset to continue from. Binary files are rejected. Prefer this "
        "over `cat`/`sed` in bash for viewing files; use bash for searching "
        "(grep) and for slicing single lines too long to return."
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
            "offset": {
                "type": "integer",
                "description": "1-based line number to start from (default 1).",
            },
            "limit": {
                "type": "integer",
                "description": (
                    f"Maximum number of lines to return. Omit to read up to "
                    f"the {MAX_READ_LINES}-line cap; larger values are "
                    f"clamped to it."
                ),
            },
        },
        "required": ["path"],
    },
}


def run_read(
    path_str: str, offset: int = 1, limit: int | None = None
) -> tuple[str, bool]:
    """Read a window of the file and return ``(output, is_error)``.

    ``is_error`` is true when the tool could not produce a reading: a bad
    argument, a missing file, a directory or any other non-regular file, a
    file over the byte cap, a binary file, or a single line over the
    character cap. Only regular files are opened — a FIFO or a device file
    would block or never end, and there is no timeout here to escape that.
    Every error message states what to do next — the file's total line
    count, a bash command to slice an over-long line — rather than just
    what failed.

    Content is decoded as UTF-8 with invalid bytes replaced, matching the
    bash tool's tolerance. The whole file is read into memory: fine for
    source and config files, and the output caps bound what reaches the
    context either way. Files over the byte cap are turned away before the
    read, since the output caps would otherwise apply only after the whole
    file had already been loaded.
    """
    if offset < 1:
        return f"[invalid offset {offset}: line numbers start at 1]", True
    if limit is not None and limit < 1:
        return f"[invalid limit {limit}: must be at least 1]", True

    path = Path(path_str).expanduser()
    if not path.exists():
        return f"[file not found: {path_str}]", True
    if path.is_dir():
        return f"[{path_str} is a directory, not a file]", True
    if not path.is_file():
        # A FIFO blocks until something writes to it and a device file like
        # /dev/zero never ends. Reading either would hang the session, and
        # unlike the bash tool there is no timeout to escape it.
        return f"[{path_str} is not a regular file; read is text-only]", True
    try:
        size = path.stat().st_size
        if size > MAX_READ_BYTES:
            return (
                f"[{path_str} is {size} bytes, over the "
                f"{MAX_READ_BYTES}-byte cap; read loads the whole file into "
                f"memory, so slice it with bash instead, e.g. with "
                f"sed -n '1,200p']",
                True,
            )
        data = path.read_bytes()
    except FileNotFoundError:  # the file went away after the check above
        return f"[file not found: {path_str}]", True
    except OSError as exc:
        return f"[cannot read {path_str}: {exc}]", True

    # Null bytes near the start mark a binary file; a text reading of it
    # would only waste context.
    if b"\x00" in data[:8192]:
        return f"[{path_str} looks like a binary file; read is text-only]", True

    # Split on \n alone, not with splitlines(): that also breaks on \x0c,
    # \x0b, \x85 and U+2028, which would number the lines differently from
    # sed, grep -n and the user's editor. A trailing \r is dropped so CRLF
    # files read like LF ones.
    lines = [
        line.removesuffix("\r")
        for line in data.decode("utf-8", errors="replace").split("\n")
    ]
    if lines and lines[-1] == "":
        lines.pop()  # the newline ending the last line starts no new one
    total = len(lines)
    if total == 0:
        return "(empty file)", False
    if offset > total:
        return (
            f"[offset {offset} is past the end of {path_str} ({total} lines)]",
            True,
        )

    max_lines = MAX_READ_LINES if limit is None else min(limit, MAX_READ_LINES)
    window = lines[offset - 1 : offset - 1 + max_lines]

    # A single line over the character cap cannot be returned whole, and
    # returning a bare fragment would hide where it came from — point at
    # bash instead.
    if len(window[0]) > MAX_READ_CHARS:
        return (
            f"[line {offset} is {len(window[0])} characters long, over the "
            f"{MAX_READ_CHARS}-character cap; slice it with bash instead, "
            f"e.g. sed -n '{offset}p' {path_str} | cut -c 1-2000]",
            True,
        )

    selected: list[str] = []
    chars = 0
    for number, line in enumerate(window, start=offset):
        rendered = f"{number:6}\t{line}"
        added = len(rendered) + (1 if selected else 0)  # + the joining newline
        if selected and chars + added > MAX_READ_CHARS:
            break
        selected.append(rendered)
        chars += added

    last = offset + len(selected) - 1
    body = "\n".join(selected)
    if last < total:
        body += (
            f"\n[showing lines {offset}-{last} of {total}; "
            f"continue with offset={last + 1}]"
        )
    return body, False
